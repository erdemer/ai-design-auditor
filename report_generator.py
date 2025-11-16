# report_generator.py
import webbrowser
import os
import datetime
import json
import base64
from io import BytesIO
import PIL.Image

# --- HTML ŞABLONU (v4.8 - JS HATASI ve HTML TYPO DÜZELTİLDİ) ---
HTML_TEMPLATE = """
<html>
<head>
<title>AI Tasarım Denetim Raporu</title>
<meta charset="UTF-8">
<style>
    body {{ 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
        background-color: #121212; 
        color: #E0E0E0; 
        margin: 0; 
        padding: 20px; 
    }}
    h1 {{ color: #FFFFFF; border-bottom: 2px solid #444; }}
    h2 {{ color: #FFFFFF; margin-top: 30px; border-bottom: 1px solid #333; }}

    /* TAB (SEKME) STİLLERİ */
    .tab {{
        overflow: hidden;
        border-bottom: 1px solid #444;
        margin-top: 20px;
        margin-bottom: 10px;
    }}
    .tab button {{
        background-color: inherit;
        float: left;
        border: none;
        outline: none;
        cursor: pointer;
        padding: 14px 16px;
        transition: 0.3s;
        font-size: 16px;
        color: #888;
        font-weight: bold;
    }}
    .tab button:hover {{ background-color: #2a2a2a; color: #fff; }}
    .tab button.active {{ color: #fff; }}
    .tab button.active.error-tab {{ border-bottom: 3px solid #F44336; color: #F44336; }}
    .tab button.active.audit-tab {{ border-bottom: 3px solid #42A5F5; color: #42A5F5; }}
    .tab button.active.success-tab {{ border-bottom: 3px solid #66BB6A; color: #66BB6A; }}
    .tab button.active.warning-tab {{ border-bottom: 3px solid #FFA726; color: #FFA726; }}

    .tabcontent {{
        display: none;
        padding: 6px 12px;
        animation: fadeEffect 0.5s;
    }}
    @keyframes fadeEffect {{ from {{opacity: 0;}} to {{opacity: 1;}} }}

    /* TABLO STİLLERİ */
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ background-color: #1E1E1E; padding: 12px; text-align: left; border-bottom: 2px solid #444; }}
    td {{ padding: 12px; border-bottom: 1px solid #333; }}
    tr.component-row {{ cursor: pointer; transition: background-color 0.2s; }}
    tr.component-row:hover {{ background-color: #2a2a2a; }}
    tr.component-row.active {{ background-color: #3a3a3a; }}

    /* DETAY ALANI */
    .details-row {{ display: none; background-color: #1a1a1a; }}
    .details-row td {{ padding: 0; }}
    .details-content {{ display: flex; flex-wrap: wrap; padding: 15px; }}
    .details-col {{ flex: 1; min-width: 300px; padding: 0 15px; }}
    .details-col h4 {{ margin-top: 0; color: #AAAAAA; border-bottom: 1px solid #444; padding-bottom: 5px; }}

    .status-icon {{ font-size: 1.2em; }}
    .status-pass {{ color: #66BB6A; }} 
    .status-fail {{ color: #F44336; }} 
    .status-audit {{ color: #42A5F5; }} 
    .status-n-a {{ color: #888; }} 

    pre {{ background-color: #0d0d0d; padding: 10px; border-radius: 4px; font-size: 0.85em; white-space: pre-wrap; word-wrap: break-word; }}

    /* ÖZET KUTULARI (v4.2) */
    .summary {{ 
        display: grid; 
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
        gap: 20px; 
        margin-bottom: 20px; 
    }}
    .summary-box {{ background-color: #1E1E1E; padding: 15px; border-radius: 8px; text-align: center; }}
    .summary-box .count {{ font-size: 2.5em; font-weight: bold; }}
    .summary-box .label {{ font-size: 1em; color: #AAAAAA; }}
    .error .count {{ color: #F44336; }} .warning .count {{ color: #FFA726; }}
    .success .count {{ color: #66BB6A; }} .audit .count {{ color: #42A5F5; }}

    li.warning {{ background-color: #2a2a2a; border-left: 5px solid #FFA726; padding: 10px; list-style: none; margin: 5px 0; }}
    ul {{ padding-left: 20px; }}

    /* RESİM ALANI */
    .image-comparison-area {{ display: flex; flex-direction: column; gap: 20px; margin-top: 20px; }}
    .image-pair {{ display: flex; gap: 20px; }}
    .image-container {{ 
        flex: 1; position: relative; background-color: #1E1E1E; padding: 10px; border-radius: 8px; border: 1px solid #333; 
    }}
    .image-container h3 {{ margin-top: 0; text-align: center; }}
    .image-container img {{ width: 100%; height: auto; border-radius: 4px; }}
    .highlight-canvas {{
        position: absolute; top: 10px; left: 10px; width: calc(100% - 20px); height: calc(100% - 20px); pointer-events: none; 
    }}
</style>
</head>
<body>
    <h1>AI Tasarım Denetim Raporu</h1>
    <footer>Rapor Tarihi: {report_date} | Temel Ölçekleme: {scale_factor:.3f}x (App px / Figma dp)</footer>

    <div class="summary">
        <div class="summary-box error">
            <div class="count">{error_count}</div>
            <div class="label">Layout Hataları</div>
        </div>
        <div class="summary-box success">
            <div class="count">{layout_success_count}</div>
            <div class="label">Layout Başarılı</div>
        </div>
        <div class="summary-box audit">
            <div class="count">{audit_count}</div>
            <div class="label">Stil Farklılıkları</div>
        </div>
        <div class="summary-box success">
            <div class="count">{style_success_count}</div>
            <div class="label">Stil Başarılı (Birebir)</div>
        </div>
        <div class="summary-box warning">
            <div class="count">{warning_count}</div>
            <div class="label">Eşleşmeyen (Uyarı)</div>
        </div>
    </div>

    <h2>Görüntü Karşılaştırması (Kırpılmış Parçalar)</h2>
    <p style="color: #aaa;">Aşağıdaki sekmelerden bir satıra tıkladığınızda ilgili bileşen burada vurgulanacaktır.</p>
    <div class="image-comparison-area">
        {image_comparison_html}
    </div>

    <h2>Detaylı Analiz</h2>
    <div class="tab">
        <button class="tablinks active error-tab" onclick="openTab(event, 'LayoutErrors')">❌ Layout Hataları ({error_count})</button>
        <button class="tablinks audit-tab" onclick="openTab(event, 'StyleAudits')">🎨 Stil Farklılıkları ({audit_count})</button>
        <button class="tablinks success-tab" onclick="openTab(event, 'LayoutSuccesses')">✅ Layout Başarılı ({layout_success_count})</button>
        <button class="tablinks success-tab" onclick="openTab(event, 'StyleSuccesses')">✅ Stil Başarılı ({style_success_count})</button>
        <button class="tablinks warning-tab" onclick="openTab(event, 'Warnings')">⚠️ Eşleşmeyenler ({warning_count})</button>
    </div>

    <div id="LayoutErrors" class="tabcontent" style="display: block;">
        {layout_error_table}
    </div>

    <div id="StyleAudits" class="tabcontent">
        {style_audit_table}
    </div>

    <div id="LayoutSuccesses" class="tabcontent">
        {layout_success_table}
    </div>

    <div id="StyleSuccesses" class="tabcontent">
        {style_success_table}
    </div>

    <div id="Warnings" class="tabcontent">
        <ul>{warning_items}</ul>
    </div>

<script>
    // Sekme Değiştirme Fonksiyonu
    function openTab(evt, tabName) {{
        var i, tabcontent, tablinks;
        tabcontent = document.getElementsByClassName("tabcontent");
        for (i = 0; i < tabcontent.length; i++) {{
            tabcontent[i].style.display = "none";
        }}
        tablinks = document.getElementsByClassName("tablinks");
        for (i = 0; i < tablinks.length; i++) {{
            tablinks[i].className = tablinks[i].className.replace(" active", "");
        }}
        document.getElementById(tabName).style.display = "block";
        evt.currentTarget.className += " active";
    }}

    // Satır Aç/Kapa ve Vurgulama
    let activeRow = null;

    function toggleRow(row, partIndex) {{
        var detailsRow = row.nextElementSibling;
        var isOpening = detailsRow.style.display !== 'table-row';

        var allDetails = document.querySelectorAll('.details-row');
        allDetails.forEach(function(d) {{ d.style.display = 'none'; }});

        if (activeRow) {{ activeRow.classList.remove('active'); }}
        clearAllCanvases();

        if (isOpening) {{
            detailsRow.style.display = 'table-row';
            row.classList.add('active');
            activeRow = row;
            highlightComponent(row, partIndex);
        }} else {{
            activeRow = null;
        }}
    }}

    function highlightComponent(row, partIndex) {{
        try {{
            var figmaBounds = JSON.parse(row.dataset.figmaBounds);
            var appBounds = JSON.parse(row.dataset.appBounds);
            var figmaCanvas = document.getElementById('figma-canvas-part-' + partIndex);
            var appCanvas = document.getElementById('app-canvas-part-' + partIndex);
            var figmaImg = document.getElementById('figma-img-part-' + partIndex);

            // --- JAVASCRIPT HATA DÜZELTMESİ (v4.8) ---
            // 'app-img-part-'Gelen: Profil Düzente' + partIndex' YANLIŞTI
            var appImg = document.getElementById('app-img-part-' + partIndex); 
            // --- DÜZELTME BİTTİ ---

            if (!figmaCanvas || !appCanvas || !figmaImg || !appImg) {{
                console.error("Vurgulama için Canvas veya Resim elementi bulunamadı.");
                return;
            }}

            figmaCanvas.width = figmaImg.clientWidth;
            figmaCanvas.height = figmaImg.clientHeight;
            appCanvas.width = appImg.clientWidth;
            appCanvas.height = appImg.clientHeight;

            // Resmin doğal boyutunu (naturalWidth) al, eğer yüklenmemişse width'i kullan
            var figmaNaturalWidth = figmaImg.naturalWidth || figmaImg.width;
            var appNaturalWidth = appImg.naturalWidth || appImg.width;

            if (figmaNaturalWidth === 0 || appNaturalWidth === 0) {{
                console.error("Resim boyutları 0, vurgulama yapılamıyor.");
                return;
            }}

            var figmaScale = figmaCanvas.width / figmaNaturalWidth;
            var appScale = appCanvas.width / appNaturalWidth;

            var fCtx = figmaCanvas.getContext('2d');
            fCtx.strokeStyle = '#F44336'; // Kırmızı Vurgu
            fCtx.lineWidth = 3;
            fCtx.strokeRect(figmaBounds.x * figmaScale, figmaBounds.y * figmaScale, figmaBounds.w * figmaScale, figmaBounds.h * figmaScale);

            var aCtx = appCanvas.getContext('2d');
            aCtx.strokeStyle = '#F44336'; 
            aCtx.lineWidth = 3;
            aCtx.strokeRect(appBounds.x * appScale, appBounds.y * appScale, appBounds.w * appScale, appBounds.h * appScale);

        }} catch (e) {{ console.error("Kutucuk çizerken hata:", e); }}
    }}

    function clearAllCanvases() {{
        var allCanvases = document.querySelectorAll('.highlight-canvas');
        allCanvases.forEach(function(canvas) {{
            var context = canvas.getContext('2d');
            context.clearRect(0, 0, canvas.width, canvas.height);
        }});
    }}

    function setupCanvases() {{
        var allCanvases = document.querySelectorAll('.highlight-canvas');
        allCanvases.forEach(function(canvas) {{
            var img = document.getElementById(canvas.id.replace('canvas', 'img'));
            if (img) {{
                if (img.complete) {{
                    canvas.width = img.clientWidth; canvas.height = img.clientHeight;
                    img.naturalWidth = img.naturalWidth || img.width; img.naturalHeight = img.naturalHeight || img.height;
                }} else {{
                    img.onload = function() {{
                        canvas.width = img.clientWidth; canvas.height = img.clientHeight;
                        img.naturalWidth = img.naturalWidth || img.width; img.naturalHeight = img.naturalHeight || img.height;
                    }}
                }}
            }}
        }});
    }}

    window.addEventListener('load', setupCanvases);
    window.addEventListener('resize', setupCanvases);
</script>
</body>
</html>
"""


def _get_status_icon(status):
    if status == 'pass': return '<span class="status-icon status-pass" title="Başarılı">✅</span>'
    if status == 'fail': return '<span class="status-icon status-fail" title="Hatalı">❌</span>'
    if status == 'audit': return '<span class="status-icon status-audit" title="Denetle">🎨</span>'
    return '<span class="status-icon status-n-a" title="Uygulanamadı">N/A</span>'


def _format_style_details(style_data):
    if style_data['status'] == 'n/a': return "<p>Stil testi uygulanamadı.</p>"
    figma_styles, app_styles = style_data['figma'], style_data['app']
    html = "<ul>"
    all_keys = sorted(list(set(figma_styles.keys()) | set(app_styles.keys())))
    for key in all_keys:
        figma_val, app_val = figma_styles.get(key, "N/A"), figma_styles.get(key, "N/A")

        # 'content' anahtarı için özel olarak HTML escape etme
        if key == 'content':
            try:
                figma_val = figma_val.replace("&", "&amp;").replace("<", "&lt;").replace(">",
                                                                                         "&gt;") if figma_val else "N/A"
                app_val = app_val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if app_val else "N/A"
            except Exception:
                pass  # Eğer NoneType vb. ise

        status_icon = "✅" if figma_val == app_val else "🎨"
        html += f"<li><strong>{key}:</strong> {status_icon} Beklenen: {figma_val} | Gelen: {app_val}</li>"
    html += "</ul>"
    return html


def _embed_image_as_base64(image_path):
    try:
        with PIL.Image.open(image_path) as img:
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"[Rapor] HATA: Görüntü Base64'e çevrilirken hata: {e}")
        return ""


def _generate_image_comparison_html(report_parts):
    html = ""
    for part_data in report_parts:
        part_index = part_data.get("part_index", 0)
        image_pair = part_data.get("image_pair", {})
        figma_path, app_path = image_pair.get("figma"), image_pair.get("app")
        if not figma_path or not app_path: continue

        figma_base64 = _embed_image_as_base64(figma_path)
        app_base64 = _embed_image_as_base64(app_path)

        html += f"<h3>Parça {part_index}</h3>"
        html += '<div class="image-pair">'
        html += f'<div class="image-container"><img src="data:image/png;base64,{figma_base64}" alt="Figma" id="figma-img-part-{part_index}"><canvas id="figma-canvas-part-{part_index}" class="highlight-canvas"></canvas></div>'
        html += f'<div class="image-container"><img src="data:image/png;base64,{app_base64}" alt="App" id="app-img-part-{part_index}"><canvas id="app-canvas-part-{part_index}" class="highlight-canvas"></canvas></div>'
        html += '</div>'
    return html


def _create_row_html(comp, part_index):
    """Tek bir bileşen için HTML tablo satırlarını oluşturur."""
    figma_bounds_json = json.dumps(comp["raw_data"]["figma"].get("bounds", {}))
    app_bounds_json = json.dumps(comp["raw_data"]["app"].get("bounds", {}))

    row_html = f'<tr class="component-row" onclick="toggleRow(this, {part_index})" data-figma-bounds=\'{figma_bounds_json}\' data-app-bounds=\'{app_bounds_json}\'>'
    row_html += f'  <td><strong>{comp["name"]}</strong> (P{part_index})</td>'
    row_html += f'  <td>{_get_status_icon(comp["overall_layout_status"])}</td>'
    row_html += f'  <td>{_get_status_icon(comp["overall_style_status"])}</td>'
    row_html += '</tr>'

    tests = comp['tests']
    raw_data = comp['raw_data']

    row_html += '<tr class="details-row"><td colspan="3"><div class="details-content">'
    row_html += f'<div class="details-col"><h4>Layout Test ({_get_status_icon(comp["overall_layout_status"])})</h4>'
    row_html += f'<p><strong>Boyut:</strong> {tests["dimensions"]["message"]}</p>'
    row_html += f'<p><strong>Dikey:</strong> {tests["spacing"]["message"]}</p>'
    if "padding" in tests: row_html += f'<p><strong>Yatay:</strong> {tests["padding"]["message"]}</p>'
    row_html += '</div>'

    row_html += f'<div class="details-col"><h4>Stil Denetimi ({_get_status_icon(comp["overall_style_status"])})</h4>{_format_style_details(tests["style"])}</div>'

    # --- DÜZELTME BURADA (v4.7 - ensure_ascii) ---
    row_html += f'<div class="details-col"><h4>Ham Veri</h4>'
    row_html += f'<pre>Figma: {json.dumps(raw_data["figma"], indent=2, ensure_ascii=False)}\n'
    row_html += f'App: {json.dumps(raw_data["app"], indent=2, ensure_ascii=False)}</pre>'
    row_html += '</div>'

    row_html += '</div></td></tr>'

    return row_html


def _generate_table_content(report_parts, filter_type):
    """
    Belirli bir filtreye göre (error, audit, success) tablo içeriği oluşturur.
    """
    rows_html = ""
    has_data = False

    for part_data in report_parts:
        part_index = part_data.get("part_index", 0)
        comparison_results = part_data.get("comparison_results", {})

        for comp in comparison_results.get('matched_components', []):
            should_add = False

            layout_status = comp["overall_layout_status"]
            style_status = comp["overall_style_status"]

            if filter_type == "layout_error":
                if layout_status == 'fail':
                    should_add = True

            elif filter_type == "style_audit":
                # Stil farkı varsa, layout durumu ne olursa olsun göster (v4.3 Düzeltmesi)
                if style_status == 'audit':
                    should_add = True

            elif filter_type == "layout_success":
                # SADECE Layout başarılı olanları göster
                if layout_status == 'pass':
                    should_add = True

            elif filter_type == "style_success":
                # SADECE Stil başarılı olanları göster
                if style_status == 'pass':
                    should_add = True

            if should_add:
                rows_html += _create_row_html(comp, part_index)
                has_data = True

    if not has_data:
        return '<tr><td colspan="3" style="text-align:center; color:#888; padding:20px;">Bu kategoride kayıt bulunamadı.</td></tr>'

    header = '<table><thead><tr><th>Bileşen (Parça)</th><th>Layout</th><th>Stil</th></tr></thead><tbody>'
    footer = '</tbody></table>'
    return header + rows_html + footer


def create_html_report(results, output_filename="report.html"):
    summary = results.get('summary', {})

    # 1. Tabloları oluştur
    layout_error_table = _generate_table_content(results.get("parts", []), "layout_error")
    style_audit_table = _generate_table_content(results.get("parts", []), "style_audit")
    layout_success_table = _generate_table_content(results.get("parts", []), "layout_success")
    style_success_table = _generate_table_content(results.get("parts", []), "style_success")

    # 2. Resimler ve Uyarılar
    image_comparison_html = _generate_image_comparison_html(results.get("parts", []))
    warning_items = "".join([f"<li class='warning'>{item}</li>" for item in results.get('all_warnings', [])])
    if not warning_items: warning_items = "<li style='color:#888'>Eşleşmeyen bileşen yok.</li>"

    # 3. HTML'i Doldur ve Kaydet
    html_content = HTML_TEMPLATE.format(
        report_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        scale_factor=results.get('scale_factor', 0.0),

        error_count=summary.get('error_count', 0),
        audit_count=summary.get('audit_count', 0),
        layout_success_count=summary.get('layout_success_count', 0),
        style_success_count=summary.get('style_success_count', 0),
        warning_count=len(results.get('all_warnings', [])),

        image_comparison_html=image_comparison_html,
        layout_error_table=layout_error_table,
        style_audit_table=style_audit_table,
        layout_success_table=layout_success_table,
        style_success_table=style_success_table,
        warning_items=warning_items
    )

    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(html_content)

        filepath = 'file://' + os.path.realpath(output_filename)
        webbrowser.open(filepath, new=2)
        print(f"\n[Rapor] Dashboard başarıyla '{output_filename}' olarak oluşturuldu ve yeni bir sekmede açıldı.")
    except Exception as e:
        print(f"\n[Rapor] HATA: HTML dashboard yazılırken bir hata oluştu: {e}")