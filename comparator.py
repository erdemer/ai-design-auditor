# comparator.py (FULL VERSION - GHOST FILTER + FUZZY MATCH)
import config
import math
import xml.etree.ElementTree as ET

# --- 1. HATA/UYARI TOLERANS AYARLARI ---
DIM_TOLERANCE_PCT = 0.15  # %15 Boyut sapmasına kadar OK
POS_TOLERANCE_PCT = 0.12  # %12 Konum sapmasına kadar OK
MIN_PIXEL_BUFFER = 16  # Küçük objeler için minimum 16px tolerans

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


# --- TEST FONKSİYONLARI ---

def _check_dimensions(figma_props, app_props, scale_factor, tolerance_unused, component_type="Container"):
    status = 'pass'
    diffs = []

    # Text ise Width kontrolünü atla
    props = ['w', 'h']
    if component_type == "Text": props = ['h']

    scores = []
    for prop in props:
        if prop not in figma_props['bounds'] or prop not in app_props['bounds']: continue

        f_val = figma_props['bounds'][prop]
        expected = round(f_val * scale_factor)
        actual = app_props['bounds'][prop]

        is_ok = _is_within_tolerance(expected, actual, DIM_TOLERANCE_PCT)
        sim = _get_similarity_score(expected, actual)
        scores.append(sim)

        if not is_ok:
            status = 'fail'
            diffs.append(f"{prop.upper()}: Beklenen≈{expected}px, Gelen={actual}px (Uyum: %{sim})")

    avg_score = int(sum(scores) / len(scores)) if scores else 0
    msg = f"OK (Uyum: %{avg_score})" if status == 'pass' else f"UYUMSUZ: {', '.join(diffs)}"

    return {"status": status, "message": msg}


def _check_horizontal_paddings(figma_props, app_props, figma_w, app_w, scale, tol, ctype="Container"):
    diffs, status = [], 'pass'
    if 'x' not in figma_props['bounds'] or 'x' not in app_props['bounds']:
        return {"status": "fail", "message": "X verisi yok"}

    # Sol
    f_x = figma_props['bounds']['x']
    exp_x = round(f_x * scale)
    act_x = app_props['bounds']['x']

    if not _is_within_tolerance(exp_x, act_x, POS_TOLERANCE_PCT):
        status = 'fail'
        diffs.append(f"Sol: {exp_x}px vs {act_x}px")

    # Sağ (Text hariç)
    if ctype != "Text" and 'w' in figma_props['bounds'] and 'w' in app_props['bounds']:
        f_r = figma_w - (f_x + figma_props['bounds']['w'])
        exp_r = round(f_r * scale)
        act_r = app_w - (act_x + app_props['bounds']['w'])

        if not _is_within_tolerance(exp_r, act_r, POS_TOLERANCE_PCT):
            status = 'fail'
            diffs.append(f"Sağ: {exp_r}px vs {act_r}px")

    if status == 'pass': return {"status": "pass", "message": "OK"}
    return {"status": "fail", "message": "Hizalama: " + ", ".join(diffs)}


def _check_vertical_spacing(prev, curr, scale, tol):
    f_prev = prev['figma_analysis']['bounds']
    f_curr = curr['figma_analysis']['bounds']
    a_prev = prev['app_analysis']['bounds']
    a_curr = curr['app_analysis']['bounds']

    f_bottom = f_prev['y'] + f_prev['h']
    f_space = f_curr['y'] - f_bottom

    a_bottom = a_prev['y'] + a_prev['h']
    a_space = a_curr['y'] - a_bottom

    exp_space = round(f_space * scale)
    exp_space = max(0, exp_space)
    a_space = max(0, a_space)

    if _is_within_tolerance(exp_space, a_space, POS_TOLERANCE_PCT):
        return {"status": "pass", "message": f"OK ({a_space}px)"}
    return {"status": "fail", "message": f"Dikey Boşluk: Beklenen≈{exp_space}px, Gelen={a_space}px"}


def _check_styles(f_style, a_style):
    if not f_style and not a_style: return {"status": "n/a"}
    msgs = []
    status = 'pass'

    # Metin
    f_txt = str(f_style.get('content') or "").strip().lower()
    a_txt = str(a_style.get('content') or "").strip().lower()
    if f_txt and a_txt and f_txt != a_txt:
        msgs.append(f"Metin: '{f_txt}' vs '{a_txt}'")
        status = 'audit'

        # Renk
    f_col = f_style.get('color')
    a_col = a_style.get('color')
    if f_col and a_col:
        if f_col.strip('#').upper()[:6] != a_col.strip('#').upper()[:6]:
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

def _find_matches(figma_list, app_list, scale):
    matched = []
    unmatched_f = []
    unmatched_a = app_list.copy()

    # --- GHOST CONTAINER FILTRESI ---
    # Metin içermeyen 'Container'ları analizden çıkar.
    # Bunlar genellikle arka plan, boşluk veya dekoratif kutulardır.
    filtered_figma_list = []
    for f_comp in figma_list:
        has_text = bool(f_comp.get('text_content') and f_comp.get('text_content').strip())
        c_type = f_comp.get('type', 'Container')

        if c_type == 'Container' and not has_text:
            # Eşleşmeye sokma ama raporda "Görünmeyen" olarak kalsın
            unmatched_f.append(f_comp)
            continue

        filtered_figma_list.append(f_comp)
    # --------------------------------

    # Y koordinatına göre sırala
    figma_sorted = sorted(filtered_figma_list, key=lambda c: c['bounds']['y'])

    for f_comp in figma_sorted:
        f_bounds = f_comp['bounds']

        # Figma -> App Scale
        f_center_x = (f_bounds['x'] + f_bounds['w'] / 2.0) * scale
        f_center_y = (f_bounds['y'] + f_bounds['h'] / 2.0) * scale
        f_center_scaled = (f_center_x, f_center_y)

        f_ratio = _get_aspect_ratio(f_bounds['w'], f_bounds['h'])

        best_cand = None
        best_score = 999999

        for a_node in unmatched_a:
            a_bounds = a_node['bounds']
            a_center = _get_center(a_bounds)

            # A) Mesafe Kontrolü
            dist = _get_distance(f_center_scaled, a_center)
            if dist > MAX_MATCH_DISTANCE: continue

            # B) Şekil Kontrolü (Dikdörtgen vs Kare)
            a_ratio = _get_aspect_ratio(a_bounds['w'], a_bounds['h'])
            ratio_diff = abs(f_ratio - a_ratio)

            shape_penalty = 0
            if ratio_diff > ASPECT_RATIO_TOLERANCE:
                shape_penalty = 500  # Ağır ceza

            # C) Metin Bonusu
            f_text = (f_comp.get('text_content') or "").strip().lower()
            a_text = (a_node.get('text') or a_node.get('text_content') or "").strip().lower()
            text_bonus = 0
            if f_text and a_text:
                if f_text == a_text:
                    text_bonus = 250
                elif f_text in a_text:
                    text_bonus = 100

            score = dist + shape_penalty - text_bonus

            if score < best_score:
                best_score = score
                best_cand = a_node

        # Eşik Değeri
        if best_cand and best_score < 300:
            matched.append((f_comp, best_cand))
            unmatched_a.remove(best_cand)
        else:
            print(f"[Match Fail] {f_comp.get('name')} - Best Score: {best_score}")
            unmatched_f.append(f_comp)

    print(f"[Debug] Matched: {len(matched)}, Unmatched Figma: {len(unmatched_f)}, Unmatched App: {len(unmatched_a)}")
    return matched, unmatched_f, unmatched_a


def _generate_results(matches, un_f, un_a, f_w, a_w, scale, tol):
    res = {
        "matched_components": [],
        "unmatched_figma": un_f,
        "unmatched_app": un_a,
        "scale_factor": scale
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

        dim = _check_dimensions(f_props, a_props, scale, tol, ctype)

        spc = {"status": "n/a", "message": "—"}
        if i > 0:
            prev = res["matched_components"][-1]["raw_data"]
            spc = _check_vertical_spacing(prev, {"figma_analysis": f_props, "app_analysis": a_props}, scale, tol)

        pad = _check_horizontal_paddings(f_props, a_props, f_w, a_w, scale, tol, ctype)
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
    matches, unf, una = _find_matches(figma_json or [], app_nodes, scale)
    return _generate_results(matches, unf, una, figma_width, app_width, scale, tolerance_px)


def compare_layouts_ai(figma_json, app_json, figma_width, app_width, tolerance_px):
    """AI Modu"""
    scale = app_width / figma_width if figma_width > 0 else 1.0
    matches, unf, una = _find_matches(figma_json or [], app_json or [], scale)
    return _generate_results(matches, unf, una, figma_width, app_width, scale, tolerance_px)