# report_generator.py
import webbrowser
import os
import datetime
import json
import base64
from io import BytesIO
import PIL.Image

# --- HTML ŞABLONU ({} kaçışları düzeltilmiş) ---
HTML_TEMPLATE = """
<html>
<head>
<title>AI Tasarım Denetim Raporu (Kontrol Listesi)</title>
<meta charset="UTF-8">
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: #121212;
        color: #E0E0E0;
        margin: 0;
        padding: 20px;
    }}
    h1 {{
        color: #FFFFFF;
        border-bottom: 2px solid #444;
    }}
    h2 {{
        color: #FFFFFF;
        margin-top: 30px;
        border-bottom: 1px solid #333;
    }}

    .summary-box {{
        background-color: #1E1E1E;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 16px;
        margin-top: 16px;
    }}
    .summary-box ul {{
        list-style: none;
        padding-left: 0;
        margin: 0;
    }}
    .summary-box li {{
        margin-bottom: 4px;
    }}

    table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
    }}
    th {{
        background-color: #1E1E1E;
        padding: 12px;
        text-align: left;
        border-bottom: 2px solid #444;
    }}
    td {{
        padding: 12px;
        border-bottom: 1px solid #333;
        vertical-align: top;
    }}

    tr.component-row {{
        cursor: pointer;
        transition: background-color 0.2s;
    }}
    tr.component-row:hover {{
        background-color: #2a2a2a;
    }}
    tr.component-row.active {{
        background-color: #3a3a3a;
        box-shadow: 0 0 8px #42A5F5;
    }}

    pre {{
        background-color: #0d0d0d;
        padding: 10px;
        border-radius: 4px;
        border: 1px solid #333;
        overflow-x: auto;
    }}

    .image-comparison-area {{
        margin-top: 20px;
    }}
    .image-pair {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }}
    .image-container {{
        flex: 1;
        position: relative;
        background-color: #1E1E1E;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #333;
    }}
    .image-container h3 {{
        margin-top: 0;
        margin-bottom: 10px;
        color: #FFFFFF;
    }}
    .image-container img {{
        max-width: 100%;
        display: block;
        border-radius: 4px;
    }}
    .highlight-canvas {{
        position: absolute;
        top: 32px;
        left: 10px;
        pointer-events: none;
    }}

    .legend {{
        margin-top: 10px;
        font-size: 0.9rem;
        color: #aaa;
    }}
    .legend span {{
        display: inline-block;
        margin-right: 15px;
    }}

    .badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 500;
    }}
    .badge-pass {{
        background-color: #1b5e20;
        color: #c8e6c9;
    }}
    .badge-fail {{
        background-color: #b71c1c;
        color: #ffcdd2;
    }}
    .badge-audit {{
        background-color: #f57f17;
        color: #fff8e1;
    }}
    .badge-na {{
        background-color: #424242;
        color: #e0e0e0;
    }}
    small.detail-text {{
        color: #bdbdbd;
        font-size: 0.8rem;
        display: block;
        margin-top: 4px;
    }}
</style>
<script>
    var activeRow = null;

    function clearAllCanvases() {{
        var canvases = document.querySelectorAll('.highlight-canvas');
        canvases.forEach(function(cv) {{
            var ctx = cv.getContext('2d');
            ctx.clearRect(0, 0, cv.width, cv.height);
        }});
    }}

    // figmaBoundsData: Figma AI'nin verdiği bounds
    // appBoundsData:   App AI'nin verdiği bounds (varsa)
    function highlightComponent(row, partIndex, figmaBoundsData, appBoundsData) {{
        var isOpening = !(activeRow === row);

        if (activeRow) {{
            activeRow.classList.remove('active');
        }}
        clearAllCanvases();

        if (isOpening) {{
            row.classList.add('active');
            activeRow = row;

            try {{
                var figmaBounds = JSON.parse(figmaBoundsData);
                var appBounds = null;
                if (appBoundsData && appBoundsData !== "null" && appBoundsData !== "") {{
                    appBounds = JSON.parse(appBoundsData);
                }}

                var figmaCanvas = document.getElementById('figma-canvas-part-' + partIndex);
                var appCanvas = document.getElementById('app-canvas-part-' + partIndex);
                var figmaImg = document.getElementById('figma-img-part-' + partIndex);
                var appImg = document.getElementById('app-img-part-' + partIndex);

                if (!figmaCanvas || !appCanvas || !figmaImg || !appImg) return;

                figmaCanvas.width = figmaImg.clientWidth;
                figmaCanvas.height = figmaImg.clientHeight;
                appCanvas.width = appImg.clientWidth;
                appCanvas.height = appImg.clientHeight;

                var figmaNaturalWidth = figmaImg.naturalWidth || figmaImg.clientWidth;
                var figmaScale = figmaImg.clientWidth / figmaNaturalWidth;

                var appNaturalWidth = appImg.naturalWidth || appImg.clientWidth;
                var appScale = appImg.clientWidth / appNaturalWidth;

                var scaleFactor = {scale_factor};

                var figmaCtx = figmaCanvas.getContext('2d');
                var appCtx = appCanvas.getContext('2d');

                // --- Figma tarafında AI'nin verdiği gerçek bounds ---
                if (figmaBounds && typeof figmaBounds.x !== "undefined") {{
                    figmaCtx.strokeStyle = 'red';
                    figmaCtx.lineWidth = 2;
                    figmaCtx.strokeRect(
                        figmaBounds.x * figmaScale,
                        figmaBounds.y * figmaScale,
                        figmaBounds.w * figmaScale,
                        figmaBounds.h * figmaScale
                    );
                }}

                // --- App tarafında, mümkünse AI'nin verdiği gerçek app bounds'u kullan ---
                if (appBounds && typeof appBounds.x !== "undefined") {{
                    appCtx.strokeStyle = 'red';
                    appCtx.lineWidth = 2;
                    appCtx.strokeRect(
                        appBounds.x * appScale,
                        appBounds.y * appScale,
                        appBounds.w * appScale,
                        appBounds.h * appScale
                    );
                }} else if (figmaBounds && typeof figmaBounds.x !== "undefined") {{
                    // Fallback: Eğer appBounds yoksa, figmaBounds'i scale_factor ile tahmin et
                    var appX = figmaBounds.x * scaleFactor * appScale;
                    var appY = figmaBounds.y * scaleFactor * appScale;
                    var appW = figmaBounds.w * scaleFactor * appScale;
                    var appH = figmaBounds.h * scaleFactor * appScale;

                    appCtx.strokeStyle = 'red';
                    appCtx.lineWidth = 2;
                    appCtx.strokeRect(appX, appY, appW, appH);
                }}
            }} catch (e) {{
                console.error("highlightComponent hatası:", e);
            }}
        }} else {{
            activeRow = null;
        }}
    }}
</script>
</head>
<body>
    <h1>AI Tasarım Denetim Raporu (Görsel Kontrol Listesi)</h1>
    <footer>Rapor Tarihi: {report_date}</footer>

    <div class="summary-box">
        <h2>Genel Özet</h2>
        <ul>
            <li><strong>Toplam Eşleşen Bileşen:</strong> {total_matched}</li>
            <li><strong>Layout Uyumu:</strong> %{layout_match_pct}</li>
            <li><strong>Stil Uyumu:</strong> %{style_match_pct}</li>
            <li><strong>Genel Uyum:</strong> %{overall_match_pct}</li>
            <li><strong>Toplam Hata:</strong> {error_count}</li>
            <li><strong>Toplam Uyarı:</strong> {warning_count}</li>
        </ul>
    </div>

    <h2>Görüntü Karşılaştırması</h2>
    <p style="color: #aaa;">Kontrol listesinden bir satıra tıkladığında, ilgili Figma bileşeni ve App'teki AI tespitlerine göre çizilen kutular kırmızı olarak vurgulanır.</p>
    <div class="image-comparison-area">
        {image_comparison_html}
    </div>

    <h2>Bileşen Karşılaştırma Tablosu (Figma ↔ App)</h2>
    <p style="color: #aaa;">
        Her satır, Figma'da AI'nin tespit ettiği bir bileşeni ve App tarafındaki karşılığını gösterir.<br>
        <span class="badge badge-pass">🟢 PASS</span>
        <span class="badge badge-fail">🔴 FAIL</span>
        <span class="badge badge-audit">🟡 AUDIT</span>
        <span class="badge badge-na">⚪ N/A</span>
    </p>
    {component_tables_html}

    <h2>Figma Bileşen Kontrol Listesi</h2>
    <p style="color: #aaa;">Aşağıdaki tabloda, Figma ekranındaki AI'nin tespit ettiği tüm bileşenler listelenmiştir. Bir satıra tıkladığında, üstteki Figma görüntüsünde ilgili bölge kırmızı kutu ile vurgulanır (App tarafı için AI bounds yoksa sadece Figma tarafı vurgulanır).</p>
    {all_tables_html}

</body>
</html>
"""


def _embed_image_as_base64(image_path):
    if not image_path or not os.path.exists(image_path):
        return ""
    try:
        img = PIL.Image.open(image_path)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"[Rapor] Resim base64'e çevrilemedi: {e}")
        return ""


def _generate_image_comparison_html(report_parts):
    html = ""
    for part_data in report_parts:
        part_index = part_data.get("part_index", 0)
        image_pair = part_data.get("image_pair", {})
        figma_path, app_path = image_pair.get("figma"), image_pair.get("app")
        if not figma_path or not app_path:
            continue

        figma_base64 = _embed_image_as_base64(figma_path)
        app_base64 = _embed_image_as_base64(app_path)

        html += f"<h2>Parça {part_index}</h2>"
        html += '<div class="image-pair">'
        html += '<div class="image-container">'
        html += f'  <h3>Figma Parçası {part_index}</h3>'
        html += f'  <img src="data:image/png;base64,{figma_base64}" alt="Figma" id="figma-img-part-{part_index}">'
        html += f'  <canvas id="figma-canvas-part-{part_index}" class="highlight-canvas"></canvas>'
        html += '</div>'
        html += '<div class="image-container">'
        html += f'  <h3>App Parçası {part_index}</h3>'
        html += f'  <img src="data:image/png;base64,{app_base64}" alt="App" id="app-img-part-{part_index}">'
        html += f'  <canvas id="app-canvas-part-{part_index}" class="highlight-canvas"></canvas>'
        html += '</div>'
        html += '</div>'
    return html


def _format_figma_spec(comp_spec):
    html = "<ul>"
    if comp_spec.get("type"):
        html += f"<li><strong>Tip:</strong> {comp_spec['type']}</li>"
    if comp_spec.get("bounds"):
        b = comp_spec["bounds"]
        html += f"<li><strong>Bounds:</strong> x={b.get('x')}, y={b.get('y')}, w={b.get('w')}, h={b.get('h')}</li>"
    if comp_spec.get("text_content"):
        html += f"<li><strong>Metin:</strong> {comp_spec['text_content']}</li>"
    if comp_spec.get("estimated_color"):
        html += f"<li><strong>Metin Rengi (tahmini):</strong> {comp_spec['estimated_color']}</li>"
    if comp_spec.get("estimated_fontSize_dp") is not None:
        html += f"<li><strong>Font Boyutu (tahmini):</strong> {comp_spec['estimated_fontSize_dp']} dp</li>"
    if comp_spec.get("estimated_backgroundColor"):
        html += f"<li><strong>Arka Plan Rengi (tahmini):</strong> {comp_spec['estimated_backgroundColor']}</li>"
    html += "</ul>"
    return html


def _generate_all_tables_html(report_parts):
    """Figma bileşenlerini (sadece Figma tarafı) listeleyen tablolar."""
    all_tables_html = ""
    for part_data in report_parts:
        part_index = part_data.get("part_index", 0)
        figma_spec_list = part_data.get("figma_spec", [])

        all_tables_html += f'<h2>Figma Kontrol Listesi (Parça {part_index})</h2>'
        all_tables_html += '<table><thead><tr>'
        all_tables_html += '<th>Bileşen (AI Tahmini)</th>'
        all_tables_html += '<th>Beklenen Teknik Özellikler (Figma\'dan)</th>'
        all_tables_html += '</tr></thead><tbody>'

        try:
            sorted_specs = sorted(
                figma_spec_list,
                key=lambda c: c.get("bounds", {}).get("y", 0)
            )
        except Exception:
            sorted_specs = figma_spec_list

        rows = []
        for comp in sorted_specs:
            bounds_json = json.dumps(comp.get("bounds", {}))
            bounds_json_attr = bounds_json.replace("'", "&#39;")
            # Figma-only: appBoundsData boş string
            rows.append(
                f'<tr class="component-row" onclick="highlightComponent(this, {part_index}, \'{bounds_json_attr}\', \'\')" '
                f'data-figma-bounds=\'{bounds_json_attr}\'>'
            )
            rows.append(f'  <td><strong>{comp.get("name", "isimsiz")}</strong></td>')
            rows.append(f'  <td>{_format_figma_spec(comp)}</td>')
            rows.append('</tr>')

        all_tables_html += "\n".join(rows)
        all_tables_html += '</tbody></table>'

    return all_tables_html


def _status_badge(status: str) -> str:
    s = (status or "").lower()
    if s == "pass":
        return '<span class="badge badge-pass">🟢 PASS</span>'
    if s == "fail":
        return '<span class="badge badge-fail">🔴 FAIL</span>'
    if s == "audit":
        return '<span class="badge badge-audit">🟡 AUDIT</span>'
    return '<span class="badge badge-na">⚪ N/A</span>'


def _bounds_text(bounds: dict) -> str:
    if not bounds:
        return "—"
    return f"x={bounds.get('x')}, y={bounds.get('y')}, w={bounds.get('w')}, h={bounds.get('h')}"


def _generate_component_comparison_tables_html(report_parts):
    """
    Figma ↔ App matched_components üzerinden component component karşılaştırma tablosu üretir.
    """
    html = ""
    for part_data in report_parts:
        part_index = part_data.get("part_index", 0)
        comp_results = part_data.get("comparison_results", {}) or {}
        matched = comp_results.get("matched_components", []) or []

        if not matched:
            continue

        html += f'<h2>Parça {part_index} - Bileşen Karşılaştırma</h2>'
        html += '<table><thead><tr>'
        html += '<th>Bileşen Adı</th>'
        html += '<th>Figma ↔ App Bounds</th>'
        html += '<th>Layout</th>'
        html += '<th>Stil</th>'
        html += '</tr></thead><tbody>'

        try:
            sorted_matched = sorted(
                matched,
                key=lambda m: m.get("figma_analysis", {}).get("bounds", {}).get("y", 0)
            )
        except Exception:
            sorted_matched = matched

        rows = []
        for mc in sorted_matched:
            figma_comp = mc.get("figma_analysis", {}) or {}
            app_comp = mc.get("app_analysis", {}) or {}
            name = (mc.get("name")
                    or figma_comp.get("name")
                    or app_comp.get("name")
                    or "isimsiz")

            figma_bounds = figma_comp.get("bounds", {}) or {}
            app_bounds = app_comp.get("bounds", {}) or {}

            layout_status = mc.get("overall_layout_status", "n/a")
            style_status = mc.get("overall_style_status", "n/a")

            tests = mc.get("tests", {}) or {}
            style_test = tests.get("styles", {}) or {}
            style_messages = style_test.get("messages", []) or []
            style_msg_html = "<br>".join(style_messages)

            figma_bounds_json = json.dumps(figma_bounds)
            figma_bounds_attr = figma_bounds_json.replace("'", "&#39;")

            app_bounds_json = json.dumps(app_bounds)
            app_bounds_attr = app_bounds_json.replace("'", "&#39;")

            rows.append(
                f'<tr class="component-row" '
                f'onclick="highlightComponent(this, {part_index}, \'{figma_bounds_attr}\', \'{app_bounds_attr}\')" '
                f'data-figma-bounds=\'{figma_bounds_attr}\' data-app-bounds=\'{app_bounds_attr}\'>'
            )
            rows.append(f'  <td><strong>{name}</strong></td>')
            rows.append(
                f'  <td>'
                f'<strong>Figma:</strong> {_bounds_text(figma_bounds)}<br>'
                f'<strong>App:</strong> {_bounds_text(app_bounds)}'
                f'</td>'
            )
            rows.append(f'  <td>{_status_badge(layout_status)}</td>')

            if style_msg_html:
                rows.append(
                    f'  <td>{_status_badge(style_status)}'
                    f'<small class="detail-text">{style_msg_html}</small>'
                    f'</td>'
                )
            else:
                rows.append(f'  <td>{_status_badge(style_status)}</td>')

            rows.append('</tr>')

        html += "\n".join(rows)
        html += '</tbody></table>'

    return html


def create_html_report(results, output_filename="report.html"):
    if not results.get("parts"):
        print("[Rapor] Uyarı: Hiç parça yok, boş bir rapor üretilecek.")
    summary = results.get("summary", {})

    image_comparison_html = _generate_image_comparison_html(results.get("parts", []))
    all_tables_html = _generate_all_tables_html(results.get("parts", []))
    component_tables_html = _generate_component_comparison_tables_html(results.get("parts", []))

    html_content = HTML_TEMPLATE.format(
        report_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        scale_factor=results.get("scale_factor", 0.0),
        error_count=summary.get("error_count", 0),
        audit_count=summary.get("audit_count", 0),
        layout_success_count=summary.get("layout_success_count", 0),
        style_success_count=summary.get("style_success_count", 0),
        warning_count=summary.get("warning_count", 0),
        total_matched=summary.get("total_matched", 0),
        layout_match_pct=summary.get("layout_match_pct", 0.0),
        style_match_pct=summary.get("style_match_pct", 0.0),
        overall_match_pct=summary.get("overall_match_pct", 0.0),
        image_comparison_html=image_comparison_html,
        component_tables_html=component_tables_html,
        all_tables_html=all_tables_html,
    )

    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(html_content)

        filepath = "file://" + os.path.realpath(output_filename)
        webbrowser.open(filepath, new=2)
        print(f"\n[Rapor] Görsel Kontrol Listesi başarıyla '{output_filename}' olarak oluşturuldu.")
    except Exception as e:
        print(f"\n[Rapor] HATA: HTML dashboard yazılırken bir hata oluştu: {e}")