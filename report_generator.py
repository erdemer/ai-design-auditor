# report_generator.py
import webbrowser
import os
import datetime
import json
import base64
from io import BytesIO
import PIL.Image

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
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th {{ background-color: #1E1E1E; padding: 12px; text-align: left; border-bottom: 2px solid #444; }}
    td {{ padding: 12px; border-bottom: 1px solid #333; }}
    tr.component-row {{ cursor: pointer; transition: background-color 0.2s; }}
    tr.component-row:hover {{ background-color: #2a2a2a; }}
    tr.component-row.active {{ background-color: #3a3a3a; }}
    .details-row {{ display: none; background-color: #1a1a1a; }}
    .details-row td {{ padding: 0; }}
    .details-content {{ display: flex; flex-wrap: wrap; padding: 15px; }}
    .details-col {{ flex: 1; min-width: 300px; padding: 0 15px; }}
    .details-col h4 {{ margin-top: 0; color: #AAAAAA; border-bottom: 1px solid #444; padding-bottom: 5px; }}
    .status-icon {{ font-size: 1.2em; }}
    .status-pass {{ color: #66BB6A; }} .status-fail {{ color: #F44336; }}
    .status-audit {{ color: #42A5F5; }} .status-n-a {{ color: #888; }}
    pre {{ background-color: #0d0d0d; padding: 10px; border-radius: 4px; font-size: 0.85em; white-space: pre-wrap; word-wrap: break-word; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 20px; }}
    .summary-box {{ background-color: #1E1E1E; padding: 15px; border-radius: 8px; text-align: center; flex-grow: 1; }}
    .summary-box .count {{ font-size: 2.5em; font-weight: bold; }}
    .summary-box .label {{ font-size: 1em; color: #AAAAAA; }}
    .error .count {{ color: #F44336; }} .warning .count {{ color: #FFA726; }}
    .success .count {{ color: #66BB6A; }} .audit .count {{ color: #42A5F5; }}
    details {{ background-color: #1E1E1E; border: 1px solid #333; border-radius: 6px; margin-top: 10px; }}
    summary {{ padding: 12px; cursor: pointer; font-weight: bold; color: #FFA726; }}
    li.warning {{ background-color: #2a2a2a; border-left: 5px solid #FFA726; padding: 10px; list-style: none; margin: 5px 0; }}
    ul {{ padding-left: 20px; }}
    .image-comparison-area {{ display: flex; flex-direction: column; gap: 20px; margin-top: 20px; }}
    .image-pair {{ display: flex; gap: 20px; }}
    .image-container {{ 
        flex: 1; 
        position: relative; 
        background-color: #1E1E1E; 
        padding: 10px; 
        border-radius: 8px; 
        border: 1px solid #333; 
    }}
    .image-container h3 {{ margin-top: 0; text-align: center; }}
    .image-container img {{ 
        width: 100%; 
        height: auto; 
        border-radius: 4px; 
    }}
    .highlight-canvas {{
        position: absolute;
        top: 10px; 
        left: 10px; 
        width: calc(100% - 20px); 
        height: calc(100% - 20px);
        pointer-events: none; 
    }}
</style>
</head>
<body>
    <h1>AI Tasarım Denetim Raporu</h1>
    <footer>Rapor Tarihi: {report_date} | Temel Ölçekleme: {scale_factor:.3f}x (App px / Figma dp)</footer>

    <div class.summary">
        <div class="summary-box error"><div class="count">{error_count}</div><div class="label">Toplam Layout Hatası</div></div>
        <div class.summary-box audit"><div class.count">{audit_count}</div><div class="label">Toplam Stil Farklılığı</div></div>
        <div class.summary-box success"><div class="count">{success_count}</div><div class="label">Toplam Başarılı</div></div>
        <div class.summary-box warning"><div class="count">{warning_count}</div><div class="label">Toplam Eşleşmeyen</div></div>
    </div>

    <h2>Görüntü Karşılaştırması (Kırpılmış Parçalar)</h2>
    <p style="color: #aaa;">Bir bileşenin yerini görmek için aşağıdaki tablolardan bir satıra tıklayın.</p>
    <div class="image-comparison-area">
        {image_comparison_html}
    </div>

    {all_tables_html}

    <details>
        <summary>⚠️ Eşleşmeyen Bileşenler (Tüm Parçalar) - {warning_count} adet</summary>
        <ul>{warning_items}</ul>
    </details>

<script>
    let activeRow = null;

    function toggleRow(row, partIndex) {{
        var detailsRow = row.nextElementSibling;
        var isOpening = detailsRow.style.display !== 'table-row';

        var allDetails = document.querySelectorAll('.details-row');
        allDetails.forEach(function(d) {{ d.style.display = 'none'; }});

        if (activeRow) {{
            activeRow.classList.remove('active');
        }}

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
            var appImg = document.getElementById('app-img-part-' + partIndex);

            if (!figmaCanvas || !appCanvas || !figmaImg || !appImg) return;

            figmaCanvas.width = figmaImg.clientWidth;
            figmaCanvas.height = figmaImg.clientHeight;
            appCanvas.width = appImg.clientWidth;
            appCanvas.height = appImg.clientHeight;

            var figmaScale = figmaCanvas.width / (figmaImg.naturalWidth || figmaImg.width);
            var appScale = appCanvas.width / (appImg.naturalWidth || appImg.width);

            var fCtx = figmaCanvas.getContext('2d');
            fCtx.strokeStyle = 'red';
            fCtx.lineWidth = 2;
            fCtx.strokeRect(
                figmaBounds.x * figmaScale,
                figmaBounds.y * figmaScale,
                figmaBounds.w * figmaScale,
                figmaBounds.h * figmaScale
            );

            var aCtx = appCanvas.getContext('2d');
            aCtx.strokeStyle = 'red';
            aCtx.lineWidth = 2;
            aCtx.strokeRect(
                appBounds.x * appScale,
                appBounds.y * appScale,
                appBounds.w * appScale,
                appBounds.h * appScale
            );

        }} catch (e) {{
            console.error("Kutucuk çizilirken hata oluştu:", e);
        }}
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
            var partIndex = canvas.id.split('-').pop();
            var img = document.getElementById(canvas.id.replace('canvas', 'img'));
            if (img) {{
                // Resmin yüklenmesini bekle (tarayıcılar için)
                if (img.complete) {{
                    canvas.width = img.clientWidth;
                    canvas.height = img.clientHeight;
                    img.naturalWidth = img.naturalWidth || img.width; 
                    img.naturalHeight = img.naturalHeight || img.height;
                }} else {{
                    img.onload = function() {{
                        canvas.width = img.clientWidth;
                        canvas.height = img.clientHeight;
                        img.naturalWidth = img.naturalWidth || img.width; 
                        img.naturalHeight = img.naturalHeight || img.height;
                    }}
                }}
            }}
        }});
    }}

    window.onload = setupCanvases;
    window.onresize = setupCanvases;

</script>
</body>
</html>
"""


def _get_status_icon(status):
    """Test durumu (status) için bir HTML ikonu döndürür."""
    if status == 'pass': return '<span class="status-icon status-pass" title="Başarılı">✅</span>'
    if status == 'fail': return '<span class="status-icon status-fail" title="Hatalı">❌</span>'
    if status == 'audit': return '<span class="status-icon status-audit" title="Denetle">🎨</span>'
    return '<span class="status-icon status-n-a" title="Uygulanamadı">N/A</span>'


def _format_style_details(style_data):
    """Stil denetimi için güzel bir HTML listesi oluşturur."""
    if style_data['status'] == 'n/a': return "<p>Stil testi uygulanamadı.</p>"
    figma_styles, app_styles = style_data['figma'], style_data['app']
    html = "<ul>"
    all_keys = sorted(list(set(figma_styles.keys()) | set(app_styles.keys())))
    for key in all_keys:
        figma_val, app_val = figma_styles.get(key, "N/A"), app_styles.get(key, "N/A")
        status_icon = "✅" if figma_val == app_val else "🎨"
        html += f"<li><strong>{key}:</strong> {status_icon} Beklenen: {figma_val} | Gelen: {app_val}</li>"
    html += "</ul>"
    return html


def _embed_image_as_base64(image_path):
    """Bir görüntüyü Base64 string olarak kodlar (HTML'e gömmek için)."""
    try:
        with PIL.Image.open(image_path) as img:
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return img_str
    except Exception as e:
        print(f"[Rapor] HATA: Görüntü Base64'e çevrilirken hata: {e}")
        return ""


def _generate_image_comparison_html(report_parts):
    """Raporun en üstündeki resim çiftlerini (KANVASLI) oluşturur."""
    html = ""
    # 'report_parts' artık 'results.get("parts", [])' listesidir
    for part_data in report_parts:
        part_index = part_data.get("part_index", 0)

        # --- DÜZELTME BURADA ---
        # 'pair["figma"]' yerine 'part_data["image_pair"]["figma"]' kullan
        image_pair = part_data.get("image_pair", {})
        figma_path = image_pair.get("figma")
        app_path = image_pair.get("app")

        if not figma_path or not app_path:
            continue
        # --- DÜZELTME BİTTİ ---

        figma_base64 = _embed_image_as_base64(figma_path)
        app_base64 = _embed_image_as_base64(app_path)

        html += f"<h3>Parça {part_index}</h3>"
        html += '<div class="image-pair">'
        # Figma Resim Konteyneri (Resim + Kanvas)
        html += '<div class="image-container">'
        html += f'  <img src="data:image/png;base64,{figma_base64}" alt="Figma Parça {part_index}" id="figma-img-part-{part_index}">'
        html += f'  <canvas id="figma-canvas-part-{part_index}" class="highlight-canvas"></canvas>'
        html += '</div>'
        # App Resim Konteyneri (Resim + Kanvas)
        html += '<div class="image-container">'
        html += f'  <img src="data:image/png;base64,{app_base64}" alt="App Parça {part_index}" id="app-img-part-{part_index}">'
        html += f'  <canvas id="app-canvas-part-{part_index}" class="highlight-canvas"></canvas>'
        html += '</div>'
        html += '</div>'
    return html


def _generate_all_tables_html(report_parts):
    """Her parça için ayrı bir tıklanabilir tablo oluşturur."""
    all_tables_html = ""
    for part_data in report_parts:
        part_index = part_data.get("part_index", 0)
        comparison_results = part_data.get("comparison_results", {})

        all_tables_html += f'<h2>Bileşen Karşılaştırma Tablosu (Parça {part_index})</h2>'
        all_tables_html += '<table><thead><tr>'
        all_tables_html += '<th>Bileşen Adı (AI Tahmini)</th>'
        all_tables_html += '<th>Layout (Boyut/Boşluk)</th>'
        all_tables_html += '<th>Stil (Font/Renk)</th>'
        all_tables_html += '</tr></thead><tbody>'

        table_rows = []
        for comp in comparison_results.get('matched_components', []):
            figma_bounds_json = json.dumps(comp["raw_data"]["figma"].get("bounds", {}))
            app_bounds_json = json.dumps(comp["raw_data"]["app"].get("bounds", {}))

            table_rows.append(f'<tr class="component-row" '
                              f'onclick="toggleRow(this, {part_index})" '
                              f'data-figma-bounds=\'{figma_bounds_json}\' '
                              f'data-app-bounds=\'{app_bounds_json}\'>')
            table_rows.append(f'  <td><strong>{comp["name"]}</strong></td>')
            table_rows.append(f'  <td>{_get_status_icon(comp["overall_layout_status"])}</td>')
            table_rows.append(f'  <td>{_get_status_icon(comp["overall_style_status"])}</td>')
            table_rows.append('</tr>')

            tests = comp['tests']
            raw_data = comp['raw_data']
            table_rows.append('<tr class="details-row"><td colspan="3">')
            table_rows.append('  <div class="details-content">')

            table_rows.append('    <div class="details-col">')
            table_rows.append(
                f'      <h4>Layout Test Sonuçları ({_get_status_icon(comp["overall_layout_status"])})</h4>')
            table_rows.append(f'      <p><strong>Boyut (w, h):</strong> {tests["dimensions"]["message"]}</p>')
            table_rows.append(f'      <p><strong>Dikey Boşluk (Üst):</strong> {tests["spacing"]["message"]}</p>')
            if "padding" in tests:
                table_rows.append(
                    f'      <p><strong>Yatay Boşluk (Sol/Sağ):</strong> {tests["padding"]["message"]}</p>')
            table_rows.append('    </div>')

            table_rows.append('    <div class="details-col">')
            table_rows.append(f'      <h4>Stil Denetimi ({_get_status_icon(comp["overall_style_status"])})</h4>')
            table_rows.append(_format_style_details(tests["style"]))
            table_rows.append('    </div>')

            table_rows.append('    <div class="details-col">')
            table_rows.append('      <h4>Ham AI Verisi (Figma)</h4>')
            table_rows.append(f'      <pre>{json.dumps(raw_data["figma"], indent=2)}</pre>')
            table_rows.append('      <h4>Ham AI Verisi (App)</h4>')
            table_rows.append(f'      <pre>{json.dumps(raw_data["app"], indent=2)}</pre>')
            table_rows.append('    </div>')

            table_rows.append('  </div></td></tr>')

        all_tables_html += "\n".join(table_rows)
        all_tables_html += '</tbody></table>'

    return all_tables_html


def create_html_report(results, output_filename="report.html"):
    """
    Tüm 'results' JSON'unu alır ve interaktif bir HTML dashboard oluşturur.
    """

    summary = results.get('summary', {})

    # 1. Görüntüleri oluştur
    image_comparison_html = _generate_image_comparison_html(results.get("parts", []))

    # 2. Tüm tabloları oluştur
    all_tables_html = _generate_all_tables_html(results.get("parts", []))

    # 3. Uyarı (Warnings) Listesini Oluştur
    warning_items = "".join([f"<li class='warning'>{item}</li>" for item in results.get('all_warnings', [])])

    # 4. HTML'i Doldur ve Kaydet
    html_content = HTML_TEMPLATE.format(
        report_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        scale_factor=results.get('scale_factor', 0.0),
        error_count=summary.get('error_count', 0),
        audit_count=summary.get('audit_count', 0),
        success_count=summary.get('success_count', 0),
        warning_count=summary.get('warning_count', 0),
        image_comparison_html=image_comparison_html,
        all_tables_html=all_tables_html,
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