# -*- coding: utf-8 -*-
"""Invoice preview + export (PDF/صورة) — WYSIWYG من نفس HTML المعروض."""

DEFAULT_ADDRESS = "25 شارع محمد علي وسط البلد"

# تحسين العرض على الموبايل + نفس شكل المعاينة في التصدير
MOBILE_INV_CSS = """
* { box-sizing: border-box; }
body {
    margin: 0;
    padding: 8px;
    font-family: 'Cairo', 'Tajawal', sans-serif;
    background: #ebe6dc;
    direction: rtl;
    -webkit-text-size-adjust: 100%;
}
#capture-area {
    width: 100%;
    max-width: 720px;
    margin: 0 auto;
    background: #fff;
    padding: 0;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(20, 61, 42, 0.12);
}
.export-bar {
    position: sticky;
    top: 0;
    z-index: 99;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    padding: 12px 10px;
    background: linear-gradient(135deg, #143d2a, #1a4d35);
    border-radius: 12px 12px 0 0;
    margin-bottom: 10px;
}
.export-bar button {
    font-family: 'Cairo', sans-serif;
    font-weight: 700;
    font-size: 14px;
    padding: 11px 16px;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    flex: 1 1 120px;
    max-width: 200px;
}
.btn-pdf { background: #c19b62; color: #143d2a; }
.btn-jpg { background: #fff; color: #143d2a; border: 2px solid #c19b62 !important; }
.btn-png { background: #f0f7f2; color: #143d2a; border: 2px solid #143d2a !important; }
.export-hint {
    width: 100%;
    text-align: center;
    color: #e8d5b5;
    font-size: 11px;
    margin-top: 4px;
}
@media (max-width: 640px) {
    body { padding: 4px; }
    #capture-area { border-radius: 10px; }
    .export-bar button { font-size: 13px; padding: 10px 8px; flex: 1 1 45%; }
    .inv-container, .kc-inv { padding: 16px !important; border-radius: 10px !important; }
    .inv-header, .kc-meta { flex-direction: column !important; gap: 14px !important; }
    .inv-details { text-align: right !important; direction: rtl !important; }
    .inv-details h1 { font-size: 32px !important; }
    .inv-company-info h2, .kc-title { font-size: 24px !important; }
    .inv-summary { justify-content: stretch !important; }
    .inv-summary-box, .kc-sum { width: 100% !important; max-width: 100% !important; }
    .inv-table, .kc-tbl { display: block; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .inv-table th, .inv-table td, .kc-tbl th, .kc-tbl td {
        padding: 10px 6px !important;
        font-size: 13px !important;
    }
    .inv-row, .kc-row { font-size: 14px !important; }
    .inv-row.net, .kc-net { font-size: 18px !important; }
}
"""


def wrap_invoice_document(inner_html, file_base, font_url):
    """معاينة + أزرار PDF / JPG / PNG — نفس الشكل بالظبط."""
    fb = file_base.replace("\\", "\\\\").replace("'", "\\'")
    from kobe_vast.arabic_text import INVOICE_AR_CSS

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{font_url}" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
{MOBILE_INV_CSS}
{INVOICE_AR_CSS}
</style>
</head>
<body>
<div class="export-bar" data-html2canvas-ignore="true">
    <button class="btn-pdf" onclick="downloadPDF()">📄 PDF</button>
    <button class="btn-jpg" onclick="downloadJPG()">🖼️ صورة JPG</button>
    <button class="btn-png" onclick="downloadPNG()">🖼️ صورة PNG</button>
    <div class="export-hint">التحميل بنفس شكل المعاينة — مناسب للموبايل</div>
</div>
<div id="capture-area">{inner_html}</div>
<script>
const FILE_BASE = '{fb}';

async function waitFonts() {{
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(r => setTimeout(r, 900));
}}

async function captureCanvas() {{
    await waitFonts();
    const el = document.getElementById('capture-area');
    return await html2canvas(el, {{
        scale: 2.5,
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#ffffff',
        letterRendering: true,
        logging: false,
        onclone: function(doc) {{
            const area = doc.getElementById('capture-area');
            if (area) {{
                area.style.width = area.scrollWidth + 'px';
                area.style.maxWidth = 'none';
            }}
            doc.querySelectorAll('.ar').forEach(function(n) {{
                n.style.fontFamily = "Cairo, Tajawal, sans-serif";
                n.style.direction = "rtl";
                n.style.unicodeBidi = "embed";
                n.style.textAlign = "right";
            }});
        }}
    }});
}}

function triggerDownload(dataUrl, filename) {{
    const link = document.createElement('a');
    link.download = filename;
    link.href = dataUrl;
    link.click();
}}

async function downloadJPG() {{
    try {{
        const canvas = await captureCanvas();
        triggerDownload(canvas.toDataURL('image/jpeg', 0.96), FILE_BASE + '.jpg');
    }} catch (e) {{ alert('تعذّر حفظ الصورة: ' + e); }}
}}

async function downloadPNG() {{
    try {{
        const canvas = await captureCanvas();
        triggerDownload(canvas.toDataURL('image/png'), FILE_BASE + '.png');
    }} catch (e) {{ alert('تعذّر حفظ PNG: ' + e); }}
}}

async function downloadPDF() {{
    try {{
        const canvas = await captureCanvas();
        const img = canvas.toDataURL('image/jpeg', 0.96);
        const {{ jsPDF }} = window.jspdf;
        const pdf = new jsPDF({{ orientation: 'p', unit: 'mm', format: 'a4' }});
        const pw = pdf.internal.pageSize.getWidth();
        const ph = pdf.internal.pageSize.getHeight();
        const margin = 8;
        const maxW = pw - margin * 2;
        const maxH = ph - margin * 2;
        const ratio = Math.min(maxW / canvas.width, maxH / canvas.height);
        const w = canvas.width * ratio;
        const h = canvas.height * ratio;
        pdf.addImage(img, 'JPEG', (pw - w) / 2, margin, w, h);
        pdf.save(FILE_BASE + '.pdf');
    }} catch (e) {{ alert('تعذّر حفظ PDF: ' + e); }}
}}
</script>
</body>
</html>"""
