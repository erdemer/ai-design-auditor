# comparator.py
import config
import math


# --- YARDIMCI FONKSİYONLARDA (HELPERS) DEĞİŞİKLİK YOK ---
# Bu fonksiyonlar (check_dimensions, check_styles, vb.)
# V5'teki ile aynıdır, çünkü AI'nin yeni çıktısıyla
# (figma_analysis & app_analysis) birebir uyumludurlar.

def _check_dimensions(figma_props, app_props, scale_factor, tolerance):
    """Boyut (w, h) testi için yapılandırılmış bir sonuç döndürür."""
    diffs = []
    props_to_check = ['w', 'h']
    status = 'pass'

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
    return {"status": status, "message": message}


def _check_styles(figma_props, app_props):
    """Stil (font, color, bgColor) denetimi için yapılandırılmış bir sonuç döndürür."""
    figma_styles = {}
    app_styles = {}
    status = 'pass'

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


def _check_horizontal_paddings(figma_props, app_props, figma_width, app_width, scale_factor, tolerance):
    """Yatay (X-ekseni) boşlukları ekran kenarlarına göre karşılaştırır."""
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

    figma_right_dp = figma_width - (figma_props['bounds']['x'] + figma_props['bounds']['w'])
    expected_right_px = round(figma_right_dp * scale_factor)

    app_right_px = app_width - (app_props['bounds']['x'] + app_props['bounds']['w'])
    delta_right = abs(expected_right_px - app_right_px)

    if delta_right > tolerance:
        status = 'fail'
        diffs.append(
            f"Sağ Boşluk: Beklenen={expected_right_px}px (Figma: {figma_right_dp:.1f}dp), "
            f"Gelen={app_right_px}px (Fark: {app_right_px - expected_right_px}px)"
        )

    if status == 'pass':
        return {"status": "pass", "message": f"OK (Sol: {app_x_px}px, Sağ: {app_right_px}px)"}
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


# --- YENİ ANA FONKSİYON (v6.0) ---
def compare_layouts(matched_pairs_json, figma_width, app_width, tolerance):
    """
    AI'den gelen 'hazır eşleşmiş' çift listesini alır ve
    her çift üzerinde testleri çalıştırarak DASHBOARD için zengin JSON'u döndürür.
    """

    if not matched_pairs_json:
        return {"summary": {"error_count": 1, "warning_count": 0, "success_count": 0, "audit_count": 0},
                "errors": ["HATA: AI analizi boş döndü veya hiçbir eşleşme bulamadı."]}

    # 1. Ölçekleme
    scale_factor = app_width / figma_width

    # 2. Rapor Yapılarını Başlat
    summary = {"error_count": 0, "success_count": 0, "warning_count": 0, "audit_count": 0}
    final_report = {
        "summary": summary,
        "matched_components": [],
        "warnings": [],  # AI artık uyarı üretmiyor, bu liste boş kalacak
        "scale_factor": scale_factor,
        "raw_dimensions": {"figma_width": figma_width, "app_width": app_width}
    }

    # 3. Çiftleri Figma'daki 'y' pozisyonuna göre sırala
    try:
        sorted_pairs = sorted(
            matched_pairs_json,
            key=lambda pair: pair['figma_analysis']['bounds']['y']
        )
    except KeyError:
        print("[Comparator] HATA: AI çıktısı 'figma_analysis.bounds.y' anahtarını içermiyor.")
        return {"summary": {"error_count": 1}, "errors": ["HATA: AI çıktısı bozuk."]}

    total_components = len(sorted_pairs)
    total_layout_errors = 0
    total_audits = 0

    # 4. Testleri Çalıştır (Her çift için)
    for i in range(len(sorted_pairs)):
        current_pair = sorted_pairs[i]
        node_name = current_pair.get('name', f"unnamed_component_{i}")

        figma_props = current_pair['figma_analysis']
        app_props = current_pair['app_analysis']

        # Test 1: Boyut (w, h)
        dim_test = _check_dimensions(figma_props, app_props, scale_factor, tolerance)

        # Test 2: Stil (font, color, bgColor)
        style_test = _check_styles(figma_props, app_props)

        # Test 3: Dikey Boşluk (Spacing)
        if i == 0:
            spacing_test = {"status": "n/a", "message": "İlk bileşen"}
        else:
            prev_pair = sorted_pairs[i - 1]
            spacing_test = _check_vertical_spacing(prev_pair, current_pair, scale_factor, tolerance)

        # Test 4: Yatay Boşluk (Padding-L/R)
        padding_test = _check_horizontal_paddings(
            figma_props, app_props, figma_width, app_width, scale_factor, tolerance
        )

        # Genel Layout durumu
        layout_status = 'pass'
        if dim_test['status'] == 'fail' or spacing_test['status'] == 'fail' or padding_test['status'] == 'fail':
            layout_status = 'fail'
            total_layout_errors += 1

        if style_test['status'] == 'audit':
            total_audits += 1

        # Rapor kartını oluştur
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

    # Özet sayılarını tamamla
    summary["error_count"] = total_layout_errors
    summary["audit_count"] = total_audits
    summary["success_count"] = total_components - total_layout_errors
    # 'warnings' artık AI tarafından filtrelendiği için 0 olmalı
    summary["warning_count"] = 0

    return final_report