# comparator.py
import config
import math
import xml.etree.ElementTree as ET  # <-- XML okumak için YENİ import


def _effective_tolerance(expected_px, base_tolerance, ratio=0.08):
    """Beklenen piksel değeri büyüdükçe toleransı esnet.

    Örnek:
      - base_tolerance = 10
      - ratio = 0.08 → %8 sapmaya kadar tolere et
    Sonuç:
      eff = max(base_tolerance, expected_px * ratio)
    """
    if expected_px is None:
        return base_tolerance
    try:
        rel = abs(float(expected_px)) * ratio
    except (TypeError, ValueError):
        return base_tolerance
    return max(float(base_tolerance), rel)


# --- YARDIMCI TEST FONKSİYONLARI (v6.2 - Değişiklik yok) ---
# Bunlar 'figma_props' ve 'app_props' aldığı için V8 ile de uyumludur.

def _check_dimensions(figma_props, app_props, scale_factor, tolerance, component_type="Container"):
    """Boyut (w, h) testi. 'Text' ise 'width' atlanır. Tolerans, bileşen boyutuna göre esnetilir."""
    diffs = []
    props_to_check = ['w', 'h']
    status = 'pass'

    if component_type == "Text":
        # Text bileşenlerinde genişlik çoğunlukla dinamik akar; sadece yükseklik kontrol edilsin.
        props_to_check = ['h']
        print(f"[Test/Boyut] 'Text' bileşeni bulundu, 'width' (genişlik) kontrolü atlanıyor.")

    for prop in props_to_check:
        if prop not in figma_props['bounds'] or prop not in app_props['bounds']:
            continue

        figma_val_dp = figma_props['bounds'][prop]
        expected_px = round(figma_val_dp * scale_factor)
        android_val_px = app_props['bounds'][prop]
        delta = abs(expected_px - android_val_px)

        eff_tol = _effective_tolerance(expected_px, tolerance)

        if delta > eff_tol:
            status = 'fail'
            diffs.append(
                f"{prop}: Beklenen={expected_px}px (Figma: {figma_val_dp}dp), "
                f"Gelen={android_val_px}px (Fark: {android_val_px - expected_px}px, Tol: ±{eff_tol:.1f}px)"
            )

    if status == 'pass':
        message = "OK"
        if component_type == "Text" and 'w' not in props_to_check and 'h' in app_props.get('bounds', {}):
            message = f"OK (Yükseklik: {app_props['bounds']['h']}px, Genişlik dinamik olduğu için atlandı)"
    else:
        message = ", ".join(diffs)

    return {"status": status, "message": message}


def _check_styles(figma_styles, app_styles):
    """
    Stil karşılaştırması, artık her zaman 'audit' ya da 'pass'/'n/a' döndürüyor:
      - Kullanıcıya "buraya manuel bak" dedirtmek için.
    """
    if not figma_styles and not app_styles:
        return {"status": "n/a", "figma": figma_styles, "app": app_styles}

    # Eğer Figma'da stiller varsa, bu her zaman bir 'denetim' (audit) gerektirir
    status = 'audit' if figma_styles else 'n/a'

    if figma_styles.get('content') and app_styles.get('content'):
        if figma_styles['content'] != app_styles['content']:
            print(
                f"[Stil/Denetim] Metin içeriği farklı: Figma='{figma_styles['content']}', App='{app_styles['content']}'")
        else:
            # İçerikler aynıysa, 'audit' durumunu 'pass'e çekebiliriz
            # (Diğer stiller hala manuel denetim gerektirse de)
            status = 'pass'

    return {"status": status, "figma": figma_styles, "app": app_styles}


def _check_horizontal_paddings(figma_props, app_props, figma_width, app_width, scale_factor, tolerance,
                               component_type="Container"):
    """Yatay (X-ekseni) boşlukları. 'Text' ise 'Sağ Boşluk' atlanır. Tolerans, padding büyüklüğüne göre esner."""
    diffs, status = [], 'pass'

    if 'x' not in figma_props['bounds'] or 'x' not in app_props['bounds']:
        return {"status": "fail", "message": "Yatay Boşluk: 'x' bilgisi eksik."}

    # Sol boşluk (screen left)
    figma_x_dp = figma_props['bounds']['x']
    expected_x_px = round(figma_x_dp * scale_factor)
    app_x_px = app_props['bounds']['x']
    delta_x = abs(expected_x_px - app_x_px)

    left_tol = _effective_tolerance(expected_x_px, tolerance)

    if delta_x > left_tol:
        status = 'fail'
        diffs.append(
            f"Sol Boşluk: Beklenen={expected_x_px}px (Figma: {figma_x_dp}dp), "
            f"Gelen={app_x_px}px (Fark: {app_x_px - expected_x_px}px, Tol: ±{left_tol:.1f}px)"
        )

    if 'w' not in figma_props['bounds'] or 'w' not in app_props['bounds']:
        return {"status": "fail", "message": "Yatay Boşluk: 'w' (genişlik) bilgisi eksik."}

    app_right_px = app_width - (app_props['bounds']['x'] + app_props['bounds']['w'])

    if component_type != "Text":
        # Sağ boşluk (screen right)
        figma_right_dp = figma_width - (figma_props['bounds']['x'] + figma_props['bounds']['w'])
        expected_right_px = round(figma_right_dp * scale_factor)
        delta_right = abs(expected_right_px - app_right_px)

        right_tol = _effective_tolerance(expected_right_px, tolerance)

        if delta_right > right_tol:
            status = 'fail'
            diffs.append(
                f"Sağ Boşluk: Beklenen={expected_right_px}px (Figma: {figma_right_dp}dp), "
                f"Gelen={app_right_px}px (Fark: {app_right_px - expected_right_px}px, Tol: ±{right_tol:.1f}px)"
            )

    if status == 'pass':
        message = f"OK (Sol: {app_x_px}px, Sağ: {'atlandı' if component_type == 'Text' else f'{app_right_px}px'})"
        return {"status": "pass", "message": message}
    return {"status": "fail", "message": ", ".join(diffs)}


def _check_vertical_spacing(prev_node_pair, current_node_pair, scale_factor, tolerance):
    """Dikey boşluk (padding/margin) testi için yapılandırılmış bir sonuç döndürür.

    İki bileşenin alt/üst hizaları arasındaki boşluğu, Figma'daki spacing'e göre değerlendirir.
    Tolerans, boşluk büyüklüğüne göre esnetilir.
    """

    # v8.0: Anahtarlar 'figma_analysis' ve 'app_analysis'
    figma_props_prev = prev_node_pair['figma_analysis']['bounds']
    figma_props_current = current_node_pair['figma_analysis']['bounds']
    android_props_prev = prev_node_pair['app_analysis']['bounds']
    android_props_current = current_node_pair['app_analysis']['bounds']

    figma_prev_bottom = figma_props_prev['y'] + figma_props_prev['h']
    figma_spacing_dp = figma_props_current['y'] - figma_prev_bottom

    android_prev_bottom = android_props_prev['y'] + android_props_prev['h']
    android_current_top = android_props_current['y']
    android_spacing_px = android_current_top - android_prev_bottom

    expected_spacing_px = round(figma_spacing_dp * scale_factor)
    delta = abs(expected_spacing_px - android_spacing_px)

    eff_tol = _effective_tolerance(expected_spacing_px, tolerance)

    if delta <= eff_tol:
        return {
            "status": "pass",
            "message": f"OK (Boşluk: {android_spacing_px}px, Fark: {delta}px, Tol: ±{eff_tol:.1f}px)"
        }
    else:
        return {
            "status": "fail",
            "message": (
                f"HATA: Beklenen={expected_spacing_px}px (Figma: {figma_spacing_dp:.1f}dp), "
                f"Gelen={android_spacing_px}px (Fark: {android_spacing_px - expected_spacing_px}px, Tol: ±{eff_tol:.1f}px)"
            )
        }


def _parse_adb_xml(xml_path):
    """
    ADB ile alınan UI hiyerarşi XML'ini parse eder ve her bir view için
    {x, y, w, h, text, resource_id, class_name} gibi bilgileri döndürür.
    """
    nodes = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for node in root.iter('node'):
            # Sadece görünür (visible-to-user) ve kutucuğu (bounds) olanları al
            if node.get('visible-to-user') == 'true' and node.get('bounds'):

                # Bounds'ları [x1,y1][x2,y2] formatından {x,y,w,h} formatına çevir
                bounds_str = node.get('bounds')
                b = bounds_str.replace("][", ",").strip("[]").split(",")
                x1, y1, x2, y2 = map(int, b)
                bounds = {'x': x1, 'y': y1, 'w': x2 - x1, 'h': y2 - y1}

                # Sadece ekran içinde olanları al
                if bounds['w'] <= 0 or bounds['h'] <= 0:
                    continue

                # Metin, id, class gibi ek bilgiler
                text = node.get('text') or ""
                res_id = node.get('resource-id') or ""
                class_name = node.get('class') or ""

                nodes.append({
                    "bounds": bounds,
                    "text": text,
                    "resource_id": res_id,
                    "class_name": class_name
                })

    except Exception as e:
        print(f"[ADB/XML] Hata: {e}")

    print(f"[ADB/XML] Toplam {len(nodes)} adet görünür node parse edildi.")
    return nodes


def _get_center(bounds):
    """
    Bir bileşenin merkez noktasını döndürür.
    """
    return (
        bounds['x'] + bounds['w'] / 2.0,
        bounds['y'] + bounds['h'] / 2.0
    )


def _get_distance(center1, center2):
    """
    İki nokta arasındaki Öklid uzaklığını hesaplar.
    """
    return math.sqrt(
        (center1[0] - center2[0]) ** 2 +
        (center1[1] - center2[1]) ** 2
    )


def _find_nearest_anchor(figma_comp, figma_anchor_map):
    """
    Figma bileşenine en yakın "anchor" (ör: header_title, main_button, avatar) bileşenini bulur.
    Bu anchor'a göre diğer bileşenlerin göreceli konumlarını değerlendiririz.
    """
    figma_center = _get_center(figma_comp['bounds'])

    nearest_name = None
    nearest_dist = None

    for anchor_name, anchor in figma_anchor_map.items():
        center = _get_center(anchor['bounds'])
        dist = _get_distance(figma_center, center)
        if nearest_dist is None or dist < nearest_dist:
            nearest_dist = dist
            nearest_name = anchor_name

    return nearest_name, nearest_dist


def compare_layouts(figma_json, app_xml_path, figma_width, app_width, tolerance_px):
    """
    Figma JSON'u ve ADB XML'i birlikte kullanarak layout karşılaştırması yapar.
    - Figma JSON: AI'den gelen bileşen listesi
    - app_xml_path: ADB'den çekilmiş UI hiyerarşisi XML dosyası
    """

    # 1) ADB XML'den app bileşenlerini parse et
    app_nodes = _parse_adb_xml(app_xml_path)

    # 2) Figma bileşenlerini (AI output) al
    figma_components = figma_json or []
    print(f"[Karşılaştırma] Figma tarafında {len(figma_components)} bileşen var.")

    # 3) Bazı Figma bileşenlerini "anchor" olarak işaretleyelim
    # Örneğin, header_title, primary_button, avatar vs.
    figma_anchor_map = {}
    for comp in figma_components:
        name = comp.get('name', '')
        if any(key in name for key in ['header', 'title', 'avatar', 'primary_button']):
            figma_anchor_map[name] = comp

    print(f"[Anchor] {len(figma_anchor_map)} adet anchor candidate bulundu.")

    # 4) Figma bileşenlerini dikey konuma göre sırala
    figma_sorted = sorted(figma_components, key=lambda c: c['bounds']['y'])

    matched_pairs = []
    unmatched_figma = []
    unmatched_app = app_nodes.copy()  # başta hepsi unmatched

    # 5) Her Figma bileşeni için, ADB node'ları arasında en yakın (mesafe + text benzerliği) adayı bul
    scale_factor = app_width / figma_width if figma_width > 0 else 1.0

    for figma_comp in figma_sorted:
        f_center = _get_center(figma_comp['bounds'])

        best_candidate = None
        best_score = None

        for app_node in unmatched_app:
            a_center = _get_center(app_node['bounds'])
            dist = _get_distance(f_center, a_center)

            # Text benzerliği (basit)
            figma_text = (figma_comp.get('text_content') or "").strip().lower()
            app_text = (app_node.get('text') or "").strip().lower()

            text_sim = 1.0 if figma_text and figma_text == app_text else 0.0

            # Skor: mesafe küçük olsun, text benzerliği yüksek olsun
            score = dist - (text_sim * 50)  # text aynıysa avantaj sağla

            if best_score is None or score < best_score:
                best_score = score
                best_candidate = app_node

        if best_candidate:
            matched_pairs.append((figma_comp, best_candidate))
            unmatched_app.remove(best_candidate)
        else:
            unmatched_figma.append(figma_comp)

    print(f"[Eşleşme] {len(matched_pairs)} adet Figma ↔ App bileşen eşleşti.")
    print(f"[Eşleşme] {len(unmatched_figma)} adet Figma bileşeni karşılıksız kaldı.")
    print(f"[Eşleşme] {len(unmatched_app)} adet App node'u Figma tarafında karşılıksız kaldı.")

    # 6) Şimdi her eşleşen çift için detaylı testler çalıştır
    result = {
        "matched_components": [],
        "unmatched_figma": unmatched_figma,
        "unmatched_app": unmatched_app,
    }

    summary = {
        "layout_errors": 0,
        "layout_success": 0,
        "style_audits": 0,
        "style_success": 0,
    }

    for i, (figma_comp, app_comp) in enumerate(matched_pairs):
        comp_type = figma_comp.get('type', 'Container')

        # Bileşenlerin ham özellikleri
        figma_props = {
            "bounds": figma_comp['bounds'],
            "styles": {
                "content": figma_comp.get('text_content')
            }
        }
        app_props = {
            "bounds": app_comp['bounds'],
            "styles": {
                "content": app_comp.get('text')
            }
        }

        # 6.1) Boyut testi
        dim_test = _check_dimensions(figma_props, app_props, scale_factor, tolerance_px, comp_type)

        # 6.2) Spacing testi (bir önceki eşleşen ile)
        if i == 0:
            spacing_test = {"status": "n/a", "message": "İlk bileşen olduğu için spacing hesaplanmadı."}
        else:
            prev_pair = result["matched_components"][-1]["raw_data"]
            spacing_test = _check_vertical_spacing(prev_pair, {"figma_analysis": figma_props, "app_analysis": app_props},
                                                   scale_factor, tolerance_px)

        # 6.3) Padding testi
        padding_test = _check_horizontal_paddings(
            figma_props, app_props, figma_width, app_width, scale_factor, tolerance_px, comp_type
        )

        # 6.4) Stil testi
        style_test = _check_styles(figma_props["styles"], app_props["styles"])

        # 6.5) Genel layout sonucu
        layout_status = 'pass'
        if dim_test['status'] == 'fail' or spacing_test['status'] == 'fail' or padding_test['status'] == 'fail':
            layout_status = 'fail'

        result["matched_components"].append({
            "name": figma_comp.get('name', f"component_{i}"),
            "overall_layout_status": layout_status,
            "overall_style_status": style_test['status'],
            "tests": {
                "dimensions": dim_test,
                "spacing": spacing_test,
                "padding": padding_test,
                "style": style_test
            },
            "raw_data": {
                "figma_analysis": figma_props,
                "app_analysis": app_props
            }
        })

        if layout_status == 'fail':
            summary["layout_errors"] += 1
        else:
            summary["layout_success"] += 1

        if style_test['status'] == 'audit':
            summary["style_audits"] += 1
        elif style_test['status'] == 'pass':
            summary["style_success"] += 1

    result["summary"] = summary
    return result


def compare_ai_results(figma_parts, app_parts, figma_width, app_width, tolerance_px):
    """
    Yeni V8 pipeline: figma_parts ve app_parts zaten AI ve/veya XML ile zenginleştirilmiş
    bileşen listelerini içeriyor.
    """
    scale_factor = app_width / figma_width if figma_width > 0 else 1.0

    final_report = {
        "matched_components": [],
        "unmatched_figma": [],
        "unmatched_app": [],
        "summary": {}
    }

    summary = final_report["summary"]
    summary.update({
        "layout_errors": 0,
        "layout_success": 0,
        "style_audits": 0,
        "style_success": 0,
    })

    if not figma_parts or not app_parts:
        print("[V8] Uyarı: Figma veya App parçaları boş, karşılaştırma yapılamıyor.")
        return final_report

    # Şimdilik varsayım: Index bazlı eşleşme
    # (İlerde daha akıllı eşleştirme yapılabilir)
    matched_count = min(len(figma_parts), len(app_parts))

    for part_index in range(matched_count):
        figma_part = figma_parts[part_index]
        app_part = app_parts[part_index]

        figma_components = figma_part.get("components", [])
        app_components = app_part.get("components", [])

        figma_sorted = sorted(figma_components, key=lambda c: c['bounds']['y'])
        app_sorted = sorted(app_components, key=lambda c: c['bounds']['y'])

        local_pairs = []
        local_unmatched_figma = []
        local_unmatched_app = app_sorted.copy()

        for i, figma_comp in enumerate(figma_sorted):
            if i < len(app_sorted):
                app_comp = app_sorted[i]
                local_pairs.append((figma_comp, app_comp))
                if app_comp in local_unmatched_app:
                    local_unmatched_app.remove(app_comp)
            else:
                local_unmatched_figma.append(figma_comp)

        part_result = {
            "part_index": part_index,
            "matched_components": [],
            "unmatched_figma": local_unmatched_figma,
            "unmatched_app": local_unmatched_app,
        }

        for i, (figma_comp, app_comp) in enumerate(local_pairs):
            comp_type = figma_comp.get('type', 'Container')
            node_name = figma_comp.get('name', f"component_{i}")

            figma_props = figma_comp
            app_props = app_comp

            dim_test = _check_dimensions(figma_props, app_props, scale_factor, tolerance_px, comp_type)

            if i == 0:
                spacing_test = {"status": "n/a", "message": "İlk bileşen olduğu için spacing hesaplanmadı."}
            else:
                prev_pair = part_result["matched_components"][-1]["raw_data"]
                spacing_test = _check_vertical_spacing(
                    prev_pair, {"figma_analysis": figma_props, "app_analysis": app_props},
                    scale_factor, tolerance_px
                )

            padding_test = _check_horizontal_paddings(
                figma_props, app_props, figma_width, app_width, scale_factor, tolerance_px, comp_type
            )

            style_test = _check_styles(
                {"content": figma_comp.get("text_content")},
                {"content": app_comp.get("text_content")}
            )

            layout_status = 'pass'
            if dim_test['status'] == 'fail' or spacing_test['status'] == 'fail' or padding_test['status'] == 'fail':
                layout_status = 'fail'

            part_result["matched_components"].append({
                "name": node_name,
                "overall_layout_status": layout_status,
                "overall_style_status": style_test['status'],
                "tests": {
                    "dimensions": dim_test,
                    "spacing": spacing_test,
                    "padding": padding_test,
                    "style": style_test
                },
                "raw_data": {
                    "figma_analysis": figma_props,
                    "app_analysis": app_props
                }
            })

        final_report["matched_components"].extend(part_result["matched_components"])
        final_report.setdefault("parts", []).append(part_result)

    total_layout_errors = 0
    total_layout_success = 0
    total_audits = 0
    total_style_success = 0

    for comp in final_report["matched_components"]:
        if comp["overall_layout_status"] == 'fail':
            total_layout_errors += 1
        elif comp["overall_layout_status"] == 'pass':
            total_layout_success += 1

        if comp["overall_style_status"] == 'audit':
            total_audits += 1
        elif comp["overall_style_status"] == 'pass':
            total_style_success += 1

    summary["error_count"] = total_layout_errors
    summary["layout_success_count"] = total_layout_success
    summary["audit_count"] = total_audits
    summary["style_success_count"] = total_style_success
    summary["total_matched"] = len(final_report["matched_components"])

    return final_report