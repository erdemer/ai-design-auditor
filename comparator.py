# comparator.py
import config
import math


def _list_to_dict(node_list):
    """AI'den gelen listeyi {'name': {...props}} sözlüğüne çevirir."""
    node_dict = {}
    for node in node_list:
        if 'name' in node and node['name'] and 'bounds' in node:
            node_dict[node['name']] = node
    return node_dict


def _check_dimensions(figma_props, app_props, scale_factor, tolerance, component_type="Container"):
    """
    Boyut (w, h) testi için yapılandırılmış bir sonuç döndürür.
    Eğer component_type == 'Text' ise, 'width' (genişlik) kontrolünü atlar.
    """
    diffs = []
    props_to_check = ['w', 'h']
    status = 'pass'

    if component_type == "Text":
        props_to_check = ['h']
        print(f"[Test/Boyut] 'Text' bileşeni bulundu, 'width' (genişlik) kontrolü atlanıyor.")

    for prop in props_to_check:
        if prop not in figma_props['bounds'] or prop not in app_props['bounds']:
            continue

        figma_val_dp = figma_props['bounds'][prop]
        expected_px = round(figma_val_dp * scale_factor)
        android_val_px = app_props['bounds'][prop]
        delta = abs(expected_px - android_val_px)

        if delta > tolerance:
            status = 'fail'
            diffs.append(
                f"{prop}: Beklenen={expected_px}px (Figma: {figma_val_dp}dp), "
                f"Gelen={android_val_px}px (Fark: {android_val_px - expected_px}px)"
            )

    message = "OK" if status == 'pass' else ", ".join(diffs)

    if component_type == "Text" and status == 'pass' and 'w' not in props_to_check:
        message = f"OK (Yükseklik: {app_props['bounds']['h']}px, Genişlik dinamik olduğu için atlandı)"

    return {"status": status, "message": message}


def _check_styles(figma_props, app_props):
    """
    Stil (font, color, bgColor, content) denetimi için
    yapılandırılmış bir sonuç döndürür.
    """
    figma_styles = {}
    app_styles = {}
    status = 'pass'

    if figma_props.get('text_content'): figma_styles['content'] = figma_props['text_content']
    if app_props.get('text_content'): app_styles['content'] = app_props['text_content']

    if figma_props.get('estimated_color'): figma_styles['color'] = figma_props['estimated_color']
    if figma_props.get('estimated_fontSize_dp'):
        figma_styles['font'] = f"{figma_props['estimated_fontSize_dp']:.1f}dp"
    if figma_props.get('estimated_backgroundColor'): figma_styles['bgColor'] = figma_props['estimated_backgroundColor']

    if app_props.get('estimated_color'): app_styles['color'] = app_props['estimated_color']
    if app_props.get('estimated_fontSize_dp'):
        app_styles['font'] = f"{app_props['estimated_fontSize_dp']:.1f}dp"
    if app_props.get('estimated_backgroundColor'): app_styles['bgColor'] = app_props['estimated_backgroundColor']

    if not figma_styles and not app_styles:
        return {"status": "n/a", "figma": {}, "app": {}}

    if figma_styles != app_styles:
        status = 'audit'

    return {"status": status, "figma": figma_styles, "app": app_styles}


def _check_horizontal_paddings(figma_props, app_props, figma_width, app_width, scale_factor, tolerance,
                               component_type="Container"):
    """
    Yatay (X-ekseni) boşlukları ekran kenarlarına göre karşılaştırır.
    Eğer 'Text' ise, 'Sağ Boşluk' kontrolü atlanır (genişlik dinamik olduğu için).
    """
    diffs = []
    status = 'pass'

    figma_x_dp = figma_props['bounds']['x']
    expected_x_px = round(figma_x_dp * scale_factor)
    app_x_px = app_props['bounds']['x']
    delta_x = abs(expected_x_px - app_x_px)

    if delta_x > tolerance:
        status = 'fail'
        diffs.append(
            f"Sol Boşluk: Beklenen={expected_x_px}px (Figma: {figma_x_dp:.1f}dp), "
            f"Gelen={app_x_px}px (Fark: {app_x_px - expected_x_px}px)"
        )

    app_right_px = app_width - (app_props['bounds']['x'] + app_props['bounds']['w'])

    if component_type != "Text":
        figma_right_dp = figma_width - (figma_props['bounds']['x'] + figma_props['bounds']['w'])
        expected_right_px = round(figma_right_dp * scale_factor)
        delta_right = abs(expected_right_px - app_right_px)

        if delta_right > tolerance:
            status = 'fail'
            diffs.append(
                f"Sağ Boşluk: Beklenen={expected_right_px}px (Figma: {figma_right_dp:.1f}dp), "
                f"Gelen={app_right_px}px (Fark: {app_right_px - expected_right_px}px)"
            )
    else:
        print(f"[Test/Hizalama] 'Text' bileşeni bulundu, 'Sağ Boşluk' kontrolü atlanıyor.")

    if status == 'pass':
        message = f"OK (Sol: {app_x_px}px"
        if component_type != "Text":
            message += f", Sağ: {app_right_px}px)"
        else:
            message += ", Sağ: atlandı)"
        return {"status": "pass", "message": message}
    else:
        return {"status": "fail", "message": ", ".join(diffs)}


def _check_vertical_spacing(prev_node_pair, current_node_pair, scale_factor, tolerance):
    """Dikey boşluk (padding/margin) testi için yapılandırılmış bir sonuç döndürür."""

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

    if delta <= tolerance:
        return {"status": "pass", "message": f"OK (Boşluk: {android_spacing_px}px)"}
    else:
        return {
            "status": "fail",
            "message": (
                f"HATA: Beklenen={expected_spacing_px}px (Figma: {figma_spacing_dp:.1f}dp), "
                f"Gelen={android_spacing_px}px (Fark: {android_spacing_px - expected_spacing_px}px)"
            )
        }


def compare_layouts(matched_pairs_json, figma_width, app_width, tolerance):
    """
    AI'den gelen 'hazır eşleşmiş' çift listesini alır ve
    her çift üzerinde DİNAMİK İÇERİK FARKINDALIĞIYLA testleri çalıştırır.
    """

    if not matched_pairs_json:
        return {"summary": {"error_count": 1, "warning_count": 0, "layout_success_count": 0, "audit_count": 0,
                            "style_success_count": 0},
                "errors": ["HATA: AI analizi boş döndü veya hiçbir eşleşme bulamadı."]}

    scale_factor = app_width / figma_width
    summary = {"warning_count": 0}
    final_report = {
        "summary": summary,
        "matched_components": [],
        "warnings": [],
        "scale_factor": scale_factor,
        "raw_dimensions": {"figma_width": figma_width, "app_width": app_width}
    }

    try:
        sorted_pairs = sorted(
            matched_pairs_json,
            key=lambda pair: pair['figma_analysis']['bounds']['y']
        )
    except KeyError:
        print("[Comparator] HATA: AI çıktısı 'figma_analysis.bounds.y' anahtarını içermiyor.")
        return {"summary": {"error_count": 1}, "errors": ["HATA: AI çıktısı bozuk."]}

    # 4. Testleri Çalıştır (Her çift için)
    for i in range(len(sorted_pairs)):
        current_pair = sorted_pairs[i]
        node_name = current_pair.get('name', f"unnamed_component_{i}")

        figma_props = current_pair['figma_analysis']
        app_props = current_pair['app_analysis']

        comp_type = figma_props.get('type', 'Container')

        dim_test = _check_dimensions(figma_props, app_props, scale_factor, tolerance, comp_type)
        style_test = _check_styles(figma_props, app_props)

        if i == 0:
            spacing_test = {"status": "n/a", "message": "İlk bileşen"}
        else:
            prev_pair = sorted_pairs[i - 1]
            spacing_test = _check_vertical_spacing(prev_pair, current_pair, scale_factor, tolerance)

        padding_test = _check_horizontal_paddings(
            figma_props, app_props, figma_width, app_width, scale_factor, tolerance, comp_type
        )

        layout_status = 'pass'
        if dim_test['status'] == 'fail' or spacing_test['status'] == 'fail' or padding_test['status'] == 'fail':
            layout_status = 'fail'

        final_report["matched_components"].append({
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
                "figma": figma_props,
                "app": app_props
            }
        })

    # 5. Adım: Final Özetini Hesapla
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