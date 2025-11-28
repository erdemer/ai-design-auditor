# comparator.py (FULL VERSION - GHOST FILTER + FUZZY MATCH)
import config
import math
import xml.etree.ElementTree as ET

# --- 1. HATA/UYARI TOLERANS AYARLARI ---
# --- 1. HATA/UYARI TOLERANS AYARLARI ---
DIM_TOLERANCE_PCT = 0.30  # %30 Boyut sapmasına kadar OK (Increased from 20%)
POS_TOLERANCE_PCT = 0.20  # %20 Konum sapmasına kadar OK (Increased from 15%)
MIN_PIXEL_BUFFER = 32  # Küçük objeler için minimum 32px tolerans (Increased from 24px)
COLOR_TOLERANCE = 60   # RGB Distance Tolerance (Increased from 50)


# --- 2. EŞLEŞME (MATCHING) KURALLARI ---
MAX_MATCH_DISTANCE = 400  # Bu mesafeden uzaktaysa eşleştirme
ASPECT_RATIO_TOLERANCE = 2.0  # Şekil benzerliği toleransı


# --- YARDIMCI FONKSİYONLAR ---

def _is_within_tolerance(expected, actual, tolerance_pct):
    if expected is None or actual is None: return True
    diff = abs(expected - actual)
    allowed = max(expected * tolerance_pct, MIN_PIXEL_BUFFER)
    return diff <= allowed


def _get_similarity_score(expected, actual):
    if expected == 0: return 100 if actual == 0 else 0
    diff = abs(expected - actual)
    ratio = diff / float(expected)
    return round(max(0, 1.0 - ratio) * 100)


def _get_center(bounds):
    return (bounds['x'] + bounds['w'] / 2.0, bounds['y'] + bounds['h'] / 2.0)


def _get_distance(c1, c2):
    return math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2)


def _get_aspect_ratio(w, h):
    if h == 0: return 0
    return w / float(h)


def _hex_to_rgb(hex_color):
    """Converts hex string to (r, g, b) tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    if len(hex_color) != 6:
        return (0, 0, 0)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _colors_are_similar(c1_hex, c2_hex, tolerance=COLOR_TOLERANCE):
    """Calculates Euclidean distance between two hex colors."""
    if not c1_hex or not c2_hex: return False
    r1, g1, b1 = _hex_to_rgb(c1_hex)
    r2, g2, b2 = _hex_to_rgb(c2_hex)
    distance = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
    return distance <= tolerance



# --- TEST FONKSİYONLARI ---

def _check_dimensions(figma_props, app_props, scale_x, scale_y, tolerance_unused, component_type="Container"):
    status = 'pass'
    diffs = []

    # Text ise Width kontrolünü atla
    props = ['w', 'h']
    if component_type == "Text": props = ['h']

    scores = []
    for prop in props:
        if prop not in figma_props['bounds'] or prop not in app_props['bounds']: continue

        f_val = figma_props['bounds'][prop]
        
        # Use appropriate scale
        scale_factor = scale_x if prop == 'w' else scale_y
        
        expected = f_val * scale_factor 
        actual = app_props['bounds'][prop]

        is_ok = _is_within_tolerance(expected, actual, DIM_TOLERANCE_PCT)

        sim = _get_similarity_score(expected, actual)
        scores.append(sim)

        if not is_ok:
            status = 'fail'
            diffs.append(f"{prop.upper()}: Beklenen≈{expected:.1f}px, Gelen={actual}px (Uyum: %{sim})")

    avg_score = int(sum(scores) / len(scores)) if scores else 0
    msg = f"OK (Uyum: %{avg_score})" if status == 'pass' else f"UYUMSUZ: {', '.join(diffs)}"

    return {"status": status, "message": msg}


def _check_horizontal_paddings(figma_props, app_props, figma_w, app_w, scale_x, tol, ctype="Container"):
    diffs, status = [], 'pass'
    if 'x' not in figma_props['bounds'] or 'x' not in app_props['bounds']:
        return {"status": "fail", "message": "X verisi yok"}

    # Sol
    f_x = figma_props['bounds']['x']
    exp_x = round(f_x * scale_x)
    act_x = app_props['bounds']['x']

    if not _is_within_tolerance(exp_x, act_x, POS_TOLERANCE_PCT):
        status = 'fail'
        diffs.append(f"Sol: {exp_x}px vs {act_x}px")

    # Sağ (Text hariç) - Sadece Width OK ise kontrol et
    # Eğer Width hatalıysa, Sağ padding doğal olarak hatalı çıkar. Çifte hata vermeyelim.
    width_ok = True
    if 'w' in figma_props['bounds'] and 'w' in app_props['bounds']:
        f_w_val = figma_props['bounds']['w']
        a_w_val = app_props['bounds']['w']
        exp_w = f_w_val * scale_x
        if not _is_within_tolerance(exp_w, a_w_val, DIM_TOLERANCE_PCT):
            width_ok = False

    if ctype != "Text" and width_ok and 'w' in figma_props['bounds'] and 'w' in app_props['bounds']:
        f_r = figma_w - (f_x + figma_props['bounds']['w'])
        exp_r = round(f_r * scale_x)
        act_r = app_w - (act_x + app_props['bounds']['w'])

        if not _is_within_tolerance(exp_r, act_r, POS_TOLERANCE_PCT):
            status = 'fail'
            diffs.append(f"Sağ: {exp_r}px vs {act_r}px")

    if status == 'pass': return {"status": "pass", "message": "OK"}
    return {"status": "fail", "message": "Hizalama: " + ", ".join(diffs)}


def _check_vertical_spacing(prev, curr, scale_y, tol):
    f_prev = prev['figma_analysis']['bounds']
    f_curr = curr['figma_analysis']['bounds']
    a_prev = prev['app_analysis']['bounds']
    a_curr = curr['app_analysis']['bounds']

    f_bottom = f_prev['y'] + f_prev['h']
    f_space = f_curr['y'] - f_bottom

    a_bottom = a_prev['y'] + a_prev['h']
    a_space = a_curr['y'] - a_bottom

    exp_space = round(f_space * scale_y)
    exp_space = max(0, exp_space)
    a_space = max(0, a_space)

    if _is_within_tolerance(exp_space, a_space, POS_TOLERANCE_PCT):
        return {"status": "pass", "message": f"OK ({a_space}px)"}
    return {"status": "fail", "message": f"Dikey Boşluk: Beklenen≈{exp_space}px, Gelen={a_space}px"}


def _check_styles(f_style, a_style):
    if not f_style and not a_style: return {"status": "n/a"}
    msgs = []
    status = 'pass'

    # Metin (Normalize & Fuzzy)
    f_txt = str(f_style.get('content') or "").strip()
    a_txt = str(a_style.get('content') or "").strip()
    
    # Remove non-alphanumeric and lowercase for comparison
    f_clean = "".join(c for c in f_txt if c.isalnum()).lower()
    a_clean = "".join(c for c in a_txt if c.isalnum()).lower()

    if f_clean and a_clean and f_clean != a_clean:
        # Allow partial match if one contains the other
        if f_clean not in a_clean and a_clean not in f_clean:
            msgs.append(f"Metin: '{f_txt}' vs '{a_txt}'")
            status = 'audit'

    # Renk (Fuzzy Match)
    f_col = f_style.get('color')
    a_col = a_style.get('color')
    if f_col and a_col:
        # Check if colors are similar enough
        if not _colors_are_similar(f_col, a_col):
             msgs.append(f"Renk: {f_col} vs {a_col}")
             status = 'fail'

    return {"status": status, "messages": msgs, "figma": f_style, "app": a_style}


def _parse_adb_xml(xml_path):
    nodes = []
    try:
        tree = ET.parse(xml_path)
        for node in tree.getroot().iter('node'):
            if node.get('visible-to-user') == 'true' and node.get('bounds'):
                b = node.get('bounds').replace("][", ",").strip("[]").split(",")
                x1, y1, x2, y2 = map(int, b)
                w, h = x2 - x1, y2 - y1
                if w > 0 and h > 0:
                    nodes.append({
                        "bounds": {'x': x1, 'y': y1, 'w': w, 'h': h},
                        "text": node.get('text') or "",
                        "resource_id": node.get('resource-id') or "",
                        "class_name": node.get('class') or ""
                    })
    except Exception as e:
        print(f"[XML Error] {e}")
    return nodes


# --- ZEKİ EŞLEŞTİRME ALGORİTMASI (Filtreli) ---

def _calculate_auto_scale(figma_list, app_list):
    """
    Calculates the scale factors (X, Y) based on the width/height ratio of high-confidence text matches.
    Returns: (scale_x, scale_y)
    """
    ratios_x = []
    ratios_y = []
    
    app_text_map = {}
    for a_node in app_list:
        txt = (a_node.get('text') or a_node.get('text_content') or "").strip().lower()
        clean_txt = "".join(c for c in txt if c.isalnum())
        if len(clean_txt) > 5: # Only long texts
            if clean_txt not in app_text_map: app_text_map[clean_txt] = []
            app_text_map[clean_txt].append(a_node)

    for f_node in figma_list:
        f_txt = (f_node.get('text_content') or "").strip().lower()
        f_clean = "".join(c for c in f_txt if c.isalnum())
        
        if len(f_clean) > 5 and f_clean in app_text_map:
            f_w = f_node['bounds']['w']
            f_h = f_node['bounds']['h']
            
            if f_w < 10 or f_h < 10: continue
            
            for a_node in app_text_map[f_clean]:
                a_w = a_node['bounds']['w']
                a_h = a_node['bounds']['h']
                
                if a_w > 10: ratios_x.append(a_w / float(f_w))
                if a_h > 10: ratios_y.append(a_h / float(f_h))

    if not ratios_x or not ratios_y: return None
    
    # Return median ratios
    ratios_x.sort()
    ratios_y.sort()
    
    mid_x = len(ratios_x) // 2
    mid_y = len(ratios_y) // 2
    
    return (ratios_x[mid_x], ratios_y[mid_y])


def _calculate_global_offset(figma_list, app_list, scale, axis='y'):
    """
    Finds the median offset (X or Y) between high-confidence text matches.
    """
    offsets = []
    
    # Create a quick lookup for app text
    app_text_map = {}
    for a_node in app_list:
        txt = (a_node.get('text') or a_node.get('text_content') or "").strip().lower()
        clean_txt = "".join(c for c in txt if c.isalnum())
        if len(clean_txt) > 3:
            if clean_txt not in app_text_map: app_text_map[clean_txt] = []
            app_text_map[clean_txt].append(a_node)

    for f_node in figma_list:
        f_txt = (f_node.get('text_content') or "").strip().lower()
        f_clean = "".join(c for c in f_txt if c.isalnum())
        
        if len(f_clean) > 3 and f_clean in app_text_map:
            # Found a text match!
            
            if axis == 'y':
                f_val = (f_node['bounds']['y'] + f_node['bounds']['h'] / 2.0) * scale
            else:
                f_val = (f_node['bounds']['x'] + f_node['bounds']['w'] / 2.0) * scale
            
            # Check all candidates (duplicates possible)
            for a_node in app_text_map[f_clean]:
                if axis == 'y':
                    a_val = a_node['bounds']['y'] + a_node['bounds']['h'] / 2.0
                else:
                    a_val = a_node['bounds']['x'] + a_node['bounds']['w'] / 2.0
                
                diff = a_val - f_val
                offsets.append(diff)

    if not offsets: return 0
    
    # Return median offset
    offsets.sort()
    mid = len(offsets) // 2
    median = offsets[mid]
    
    # Only apply if significant (> 5px)
    if abs(median) > 5:
        return median
    return 0


def _find_matches(figma_list, app_list, scale):

    matched = []
    unmatched_f = []
    unmatched_a = app_list.copy()

    # --- 0. AUTO-SCALE DETECTION ---
    # Eğer verilen 'scale' parametresi hatalıysa (örn: farklı çözünürlükler),
    # metin eşleşmelerinden gerçek ölçeği bulmaya çalış.
    
    scale_x = scale
    scale_y = scale
    
    detected_scales = _calculate_auto_scale(figma_list, app_list)
    if detected_scales:
        det_x, det_y = detected_scales
        if abs(det_x - scale) > 0.01 or abs(det_y - scale) > 0.01:
            print(f"[Comparator] Auto-detected Scale: X={det_x:.3f}, Y={det_y:.3f} (vs provided {scale:.3f}). Using detected scales.")
            scale_x = det_x
            scale_y = det_y

    # --- 1. GLOBAL OFFSET COMPENSATION (Y & X) ---
    # Auto-crop farklılıklarından kaynaklanan kaymaları düzeltmek için
    # metin eşleşmelerine bakarak global ofsetleri hesapla.
    
    global_y_offset = _calculate_global_offset(figma_list, app_list, scale_y, axis='y')
    global_x_offset = _calculate_global_offset(figma_list, app_list, scale_x, axis='x')
    
    if global_y_offset != 0 or global_x_offset != 0:
        print(f"[Comparator] Global Offset Detected: X={global_x_offset}px, Y={global_y_offset}px. Applying compensation...")
        # App koordinatlarını düzelt (Kopyası üzerinde)
        unmatched_a = []
        for node in app_list:
            new_node = node.copy()
            new_node['bounds'] = node['bounds'].copy()
            new_node['bounds']['y'] -= global_y_offset 
            new_node['bounds']['x'] -= global_x_offset
            unmatched_a.append(new_node)


    # --- GHOST CONTAINER FILTRESI (Relaxed) ---
    # Metin içermeyen 'Container'ları analizden çıkar, ancak boyutu çok küçükse.
    # Büyük containerlar (örn: kartlar, arka planlar) korunmalı.
    filtered_figma_list = []
    for f_comp in figma_list:
        has_text = bool(f_comp.get('text_content') and f_comp.get('text_content').strip())
        c_type = f_comp.get('type', 'Container')
        w = f_comp['bounds']['w']
        h = f_comp['bounds']['h']
        
        # Çok küçük ve metinsiz ise atla (örn: 10x10 dekoratif)
        if c_type == 'Container' and not has_text and (w < 20 or h < 20):
            unmatched_f.append(f_comp)
            continue

        filtered_figma_list.append(f_comp)
    # --------------------------------

    # Y koordinatına göre sırala
    figma_sorted = sorted(filtered_figma_list, key=lambda c: c['bounds']['y'])

    # --- PASS 1: HIGH CONFIDENCE MATCHING ---
    # Kesin metin eşleşmesi veya çok yakın mesafe
    remaining_figma = []
    
    for f_comp in figma_sorted:
        f_bounds = f_comp['bounds']
        f_center_x = (f_bounds['x'] + f_bounds['w'] / 2.0) * scale_x
        f_center_y = (f_bounds['y'] + f_bounds['h'] / 2.0) * scale_y
        f_center_scaled = (f_center_x, f_center_y)
        
        f_text = (f_comp.get('text_content') or "").strip().lower()
        # Remove non-alphanumeric for cleaner comparison
        f_text_clean = "".join(c for c in f_text if c.isalnum())
        
        best_cand = None
        best_score = 999999
        
        # Pass 1 Thresholds
        PASS1_DIST = 300  # Increased to catch ~60-100px offsets
        
        for a_node in unmatched_a:
            a_bounds = a_node['bounds']
            a_center = _get_center(a_bounds)
            dist = _get_distance(f_center_scaled, a_center)
            
            a_text = (a_node.get('text') or a_node.get('text_content') or "").strip().lower()
            a_text_clean = "".join(c for c in a_text if c.isalnum())
            
            # Kural 1: Metin Birebir Aynıysa (veya çok benzerse) -> KESİN EŞLEŞME
            # Layout kaymalarını tolere etmek için mesafeyi çok açıyoruz.
            is_text_match = False
            if f_text_clean and a_text_clean and len(f_text_clean) > 2:
                 if f_text_clean == a_text_clean:
                     is_text_match = True
                 elif f_text_clean in a_text_clean or a_text_clean in f_text_clean:
                     # Partial match check: if one is substring of other and length diff isn't huge
                     if abs(len(f_text_clean) - len(a_text_clean)) < 5:
                         is_text_match = True
            
            if is_text_match and dist < 2500: # Huge distance tolerance for text matches
                best_cand = a_node
                best_score = 0 
                break 
            
            # Kural 2: Çok yakınsa ve şekil benziyorsa
            f_ratio = _get_aspect_ratio(f_bounds['w'], f_bounds['h'])
            a_ratio = _get_aspect_ratio(a_bounds['w'], a_bounds['h'])
            ratio_diff = abs(f_ratio - a_ratio)
            
            if dist < PASS1_DIST and ratio_diff < 1.5:
                score = dist + (ratio_diff * 100)
                if score < best_score:
                    best_score = score
                    best_cand = a_node
        
        if best_cand:
            matched.append((f_comp, best_cand))
            unmatched_a.remove(best_cand)
        else:
            remaining_figma.append(f_comp)

    # --- PASS 2: RELAXED MATCHING ---
    # Kalanlar için daha geniş arama (Distance < 800px)
    
    final_unmatched_f = []
    
    for f_comp in remaining_figma:
        f_bounds = f_comp['bounds']
        f_center_x = (f_bounds['x'] + f_bounds['w'] / 2.0) * scale_x
        f_center_y = (f_bounds['y'] + f_bounds['h'] / 2.0) * scale_y
        f_center_scaled = (f_center_x, f_center_y)
        f_ratio = _get_aspect_ratio(f_bounds['w'], f_bounds['h'])
        f_text = (f_comp.get('text_content') or "").strip().lower()

        best_cand = None
        best_score = 999999
        
        # Relaxed Thresholds
        PASS2_DIST = 2000 # Increased to catch even larger offsets
        
        for a_node in unmatched_a:
            a_bounds = a_node['bounds']
            a_center = _get_center(a_bounds)
            dist = _get_distance(f_center_scaled, a_center)
            
            if dist > PASS2_DIST: continue
            
            a_ratio = _get_aspect_ratio(a_bounds['w'], a_bounds['h'])
            ratio_diff = abs(f_ratio - a_ratio)
            
            shape_penalty = 0
            if ratio_diff > ASPECT_RATIO_TOLERANCE:
                shape_penalty = 800 # Increased penalty
            
            a_text = (a_node.get('text') or a_node.get('text_content') or "").strip().lower()
            a_text_clean = "".join(c for c in a_text if c.isalnum())
            f_text_clean = "".join(c for c in f_text if c.isalnum())

            text_bonus = 0
            if f_text_clean and a_text_clean:
                if f_text_clean in a_text_clean or a_text_clean in f_text_clean: 
                    text_bonus = 300 # Increased bonus
            
            # Type bonus
            type_bonus = 0
            if f_comp.get('type') == a_node.get('type'):
                type_bonus = 100

            score = dist + shape_penalty - text_bonus - type_bonus
            
            if score < best_score:
                best_score = score
                best_cand = a_node
        
        if best_cand and best_score < 1000: # Increased score threshold significantly
            matched.append((f_comp, best_cand))
            unmatched_a.remove(best_cand)
        else:
            print(f"[Match Fail] {f_comp.get('name')} - Best Score: {best_score}")
            final_unmatched_f.append(f_comp)

    # Merge initial skipped with final unmatched
    all_unmatched_f = unmatched_f + final_unmatched_f
    
    print(f"[Debug] Matched: {len(matched)}, Unmatched Figma: {len(all_unmatched_f)}, Unmatched App: {len(unmatched_a)}")
    return matched, all_unmatched_f, unmatched_a, scale_x, scale_y


def _generate_results(matches, un_f, un_a, f_w, a_w, scale_x, scale_y, tol):
    res = {
        "matched_components": [],
        "unmatched_figma": un_f,
        "unmatched_app": un_a,
        "scale_factor": scale_x # Just for display
    }

    summary = {"error_count": 0, "layout_success_count": 0, "warning_count": 0, "style_success_count": 0,
               "audit_count": 0, "total_matched": len(matches)}

    for i, (f_c, a_c) in enumerate(matches):
        ctype = f_c.get('type', 'Container')

        f_txt = f_c.get('text_content')
        a_txt = a_c.get('text') or a_c.get('text_content')

        f_props = {
            "bounds": f_c['bounds'],
            "styles": {
                "content": f_txt,
                "color": f_c.get('estimated_color'),
                "font_size": f_c.get('estimated_fontSize_dp'),
                "background_color": f_c.get('estimated_backgroundColor')
            }
        }
        a_props = {
            "bounds": a_c['bounds'],
            "styles": {
                "content": a_txt,
                "color": a_c.get('estimated_color'),
                "font_size": a_c.get('estimated_fontSize_dp'),
                "background_color": a_c.get('estimated_backgroundColor')
            }
        }

        dim = _check_dimensions(f_props, a_props, scale_x, scale_y, tol, ctype)

        spc = {"status": "n/a", "message": "—"}
        if i > 0:
            prev = res["matched_components"][-1]["raw_data"]
            spc = _check_vertical_spacing(prev, {"figma_analysis": f_props, "app_analysis": a_props}, scale_y, tol)

        pad = _check_horizontal_paddings(f_props, a_props, f_w, a_w, scale_x, tol, ctype)
        sty = _check_styles(f_props['styles'], a_props['styles'])

        l_status = 'fail' if 'fail' in [dim['status'], spc['status'], pad['status']] else 'pass'

        if l_status == 'fail':
            summary["error_count"] += 1
        else:
            summary["layout_success_count"] += 1

        if sty['status'] == 'audit':
            summary["warning_count"] += 1
        elif sty['status'] == 'pass':
            summary["style_success_count"] += 1

        res["matched_components"].append({
            "name": f_c.get('name', f"comp_{i}"),
            "overall_layout_status": l_status,
            "overall_style_status": sty['status'],
            "tests": {"dimensions": dim, "spacing": spc, "padding": pad, "style": sty},
            "raw_data": {"figma_analysis": f_props, "app_analysis": a_props}
        })

    res["summary"] = summary
    return res


# --- PUBLIC FUNCTIONS ---

def compare_layouts(figma_json, app_xml_path, figma_width, app_width, tolerance_px):
    """XML Modu"""
    app_nodes = _parse_adb_xml(app_xml_path)
    scale = app_width / figma_width if figma_width > 0 else 1.0
    matches, unf, una, sx, sy = _find_matches(figma_json or [], app_nodes, scale)
    return _generate_results(matches, unf, una, figma_width, app_width, sx, sy, tolerance_px)


def compare_layouts_ai(figma_json, app_json, figma_width, app_width, tolerance_px):
    """AI Modu"""
    scale = app_width / figma_width if figma_width > 0 else 1.0
    matches, unf, una, sx, sy = _find_matches(figma_json or [], app_json or [], scale)
    return _generate_results(matches, unf, una, figma_width, app_width, sx, sy, tolerance_px)