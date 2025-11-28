import figma_client
import os
import json

def test_figma_connection():
    print("Testing Figma API Connection...")
    
    token = os.getenv("FIGMA_ACCESS_TOKEN")
    if not token:
        print("FAIL: FIGMA_ACCESS_TOKEN not found in env.")
        return

    client = figma_client.FigmaClient()
    
    # Use a dummy file key or ask user? 
    # We can't really test without a valid file key.
    # Let's check if the user provided one in env, otherwise skip.
    file_key = os.getenv("FIGMA_FILE_KEY")
    if not file_key:
        print("SKIP: FIGMA_FILE_KEY not found. Cannot test actual fetch.")
        return

    print(f"Using File Key: {file_key}")
    
    # Try to fetch the file (root) or a known node?
    # Fetching the file metadata might be huge.
    # Let's try to fetch the document root "0:0"
    
    try:
        data = client.get_file_nodes(file_key, ["0:0"])
        if data:
            print("SUCCESS: Fetched node 0:0")
            print(f"Document Name: {data.get('name')}")
        else:
            print("FAIL: No data returned for 0:0")
            
    except Exception as e:
        print(f"FAIL: Exception during fetch: {e}")

if __name__ == "__main__":
    test_figma_connection()
