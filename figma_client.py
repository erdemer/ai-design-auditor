import requests
import config
import json
import os

class FigmaClient:
    def __init__(self):
        self.access_token = config.FIGMA_ACCESS_TOKEN
        self.base_url = "https://api.figma.com/v1"
        self.headers = {
            "X-Figma-Token": self.access_token
        }

    def get_file_nodes(self, file_key, node_ids):
        """
        Fetches specific nodes from a Figma file.
        node_ids: list of strings (e.g., ["1:2", "10:5"])
        """
        if not self.access_token:
            raise Exception("Figma Access Token is missing. Please check your configuration.")

        ids_str = ",".join(node_ids)
        url = f"{self.base_url}/files/{file_key}/nodes?ids={ids_str}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise Exception("Figma API Rate Limit Exceeded. Please try again later.")
            elif e.response.status_code == 403:
                raise Exception("Figma API Access Denied. Check your Token and File permissions.")
            elif e.response.status_code == 404:
                raise Exception("Figma File or Node not found.")
            else:
                raise Exception(f"Figma API Error: {str(e)}")
        except Exception as e:
            raise Exception(f"Figma Connection Error: {str(e)}")

    def get_image(self, file_key, node_id, scale=1.0):
        """
        Generates an image for a specific node and returns the image URL.
        """
        if not self.access_token:
            raise Exception("Figma Access Token is missing.")

        url = f"{self.base_url}/images/{file_key}?ids={node_id}&scale={scale}&format=png"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            images = data.get("images", {})
            return images.get(node_id)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise Exception("Figma API Rate Limit Exceeded (Images).")
            raise Exception(f"Figma Image Error: {str(e)}")
        except Exception as e:
            raise Exception(f"Figma Image Connection Error: {str(e)}")

    def download_image(self, url, output_path):
        """Downloads the image from the URL to the specified path."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return output_path
        except Exception as e:
            print(f"[FigmaClient] Error downloading image: {e}")
            return None

    def parse_figma_response(self, json_data):
        """
        Parses the raw Figma API response into a flat list of components
        compatible with the comparator's expected format.
        Recursively traverses the node tree.
        """
        if not json_data or "nodes" not in json_data:
            return []

        components = []

        for node_id, node_info in json_data["nodes"].items():
            document = node_info.get("document")
            if document:
                # The root node of the request (the Frame)
                # We need its absolute position to use as offset for children
                root_bounds = document.get("absoluteBoundingBox")
                offset_x = 0
                offset_y = 0
                if root_bounds:
                    offset_x = root_bounds["x"]
                    offset_y = root_bounds["y"]
                
                # Traverse children, passing the offset to subtract
                # Note: The root node itself should probably NOT be added as a component?
                # Or if it is, it will be at 0,0.
                # Usually we want the *contents* of the frame.
                if "children" in document:
                    for child in document["children"]:
                        self._traverse_node(child, components, offset_x, offset_y)

        return components

    def _traverse_node(self, node, components, offset_x, offset_y):
        """
        Recursive function to traverse the node tree.
        """
        # Calculate absolute position relative to the Root Frame
        bounds = node.get("absoluteBoundingBox")
        
        if not bounds:
             pass

        # Determine type
        node_type = node.get("type")
        
        # Filter out invisible nodes
        if node.get("visible") is False:
            return

        # --- REFINEMENT: Filter System Bars ---
        node_name_lower = node.get("name", "").lower()
        if "status bar" in node_name_lower or "navigation bar" in node_name_lower or "home indicator" in node_name_lower:
            # Skip system bars entirely from the "Figma" side data
            # This avoids matching them against the App screenshot which might have different bars
            return

        # Map Figma types to our internal types
        internal_type = "Container"
        text_content = ""
        
        if node_type == "TEXT":
            internal_type = "Text"
            text_content = node.get("characters", "")
        elif node_type == "VECTOR" or node_type == "BOOLEAN_OPERATION":
            internal_type = "Icon" # Assumption
        elif node_type == "INSTANCE" or node_type == "COMPONENT":
            # Check if it looks like a button
            if "button" in node_name_lower:
                internal_type = "Button"
        
        # Extract styles (basic)
        fills = node.get("fills", [])
        strokes = node.get("strokes", [])
        color_hex = None
        has_visuals = False
        
        if fills and len(fills) > 0:
            for fill in fills:
                if fill.get("type") == "SOLID" and fill.get("visible") is not False:
                    has_visuals = True
                    color = fill.get("color")
                    if color:
                        # Convert 0-1 RGB to Hex
                        r = int(color["r"] * 255)
                        g = int(color["g"] * 255)
                        b = int(color["b"] * 255)
                        color_hex = f"#{r:02X}{g:02X}{b:02X}"
                    break # Take first visible solid fill
        
        if strokes and len(strokes) > 0:
             for stroke in strokes:
                 if stroke.get("visible") is not False:
                     has_visuals = True
                     break

        # Create component dict
        if bounds:
            # NORMALIZE COORDINATES: Subtract the Root Frame's position
            rel_x = bounds["x"] - offset_x
            rel_y = bounds["y"] - offset_y
            
            comp = {
                "name": node.get("name"),
                "type": internal_type,
                "bounds": {
                    "x": rel_x,
                    "y": rel_y,
                    "w": bounds["width"],
                    "h": bounds["height"]
                },
                "text_content": text_content,
                "estimated_color": color_hex,
            }
            
            should_add = False
            if internal_type == "Text":
                should_add = True
            elif internal_type == "Button":
                should_add = True
            elif internal_type == "Icon":
                should_add = True
            elif node_type == "RECTANGLE" and has_visuals:
                 should_add = True
            elif internal_type == "Container" and has_visuals:
                # Only add containers if they have a background or stroke
                should_add = True
            
            if should_add:
                components.append(comp)


        # Recursion
        if "children" in node:
            for child in node["children"]:
                self._traverse_node(child, components, offset_x, offset_y)

