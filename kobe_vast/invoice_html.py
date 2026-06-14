# -*- coding: utf-8 -*-
"""Invoice HTML builders — native RTL Arabic + mobile layout."""

from kobe_vast.invoice_export import DEFAULT_ADDRESS


def _addr(cfg):
    from kobe_vast.arabic_text import ar_html
    return ar_html(cfg.get("address") or DEFAULT_ADDRESS)


def build_green_invoice_html(res, cfg, font_url, logo_html_fn, default_company):
    from kobe_vast.arabic_text import INVOICE_AR_CSS, ar_html, ar_invoice_row

    rows = "".join(
        ar_invoice_row(i["item"], i.get("type", "-"), i["qty"], i["p"], i["t"])
        for i in res["cart"]
    )
    company = ar_html(cfg.get("company_name", default_company))
    address = _addr(cfg)
    phone = ar_html(cfg.get("phone", ""))
    client = ar_html(res["c"])
    pay = ar_html(res.get("pay", "—"))
    footer = ar_html(f"شكراً لثقتكم في {cfg.get('company_name', default_company)}")

    return f"""<style>
    @import url('{font_url}');
    {INVOICE_AR_CSS}
    .inv-container {{
        width:100%;margin:0 auto;font-family:'Cairo','Tajawal',sans-serif;
        background:#fff;padding:28px 24px;border:none;border-radius:0;
        box-shadow:none;direction:rtl;color:#333;
    }}
    .inv-header {{
        display:flex; justify-content:space-between; align-items:flex-start; gap:20px;
        border-bottom:4px solid #143d2a; padding-bottom:18px; margin-bottom:22px;
    }}
    .inv-company-info {{ text-align:right; flex:1.2; min-width:0; }}
    .inv-company-info h2 {{
        color:#143d2a; margin:8px 0 6px; font-weight:900; font-size:26px; line-height:1.25;
    }}
    .inv-company-info p {{ margin:5px 0; color:#555; font-size:14px; line-height:1.5; }}
    .inv-details {{ text-align:left; flex:0.8; direction:ltr; min-width:140px; }}
    .inv-details h1 {{ color:#c19b62; font-size:38px; margin:0 0 8px; line-height:1; font-weight:900; }}
    .inv-details p {{ margin:4px 0; font-size:14px; color:#444; }}
    .inv-badge {{
        display:inline-block; background:#143d2a; color:#c19b62; font-size:11px;
        font-weight:800; padding:4px 10px; border-radius:20px; margin-bottom:6px;
    }}
    .inv-bill-to {{
        background:linear-gradient(135deg,#f9fbf9,#f0f7f2); border-right:5px solid #143d2a;
        padding:16px 18px; border-radius:10px; margin-bottom:22px; border:1px solid #e0ebe4;
    }}
    .inv-bill-to h3 {{ margin:0; color:#143d2a; font-size:20px; font-weight:900; }}
    .inv-table {{ width:100%; border-collapse:collapse; margin-bottom:22px; }}
    .inv-table th {{
        background:#143d2a; color:#c19b62; padding:12px 8px; font-weight:900;
        text-align:center; font-size:14px;
    }}
    .inv-table th:first-child {{ text-align:right; }}
    .inv-table td {{ font-size:14px; }}
    .inv-summary {{ display:flex; justify-content:flex-end; }}
    .inv-summary-box {{
        width:100%; max-width:380px; background:#fcfaf5; border:2px solid #e8e0d0;
        border-radius:12px; padding:16px 18px;
    }}
    .inv-row {{
        display:flex; justify-content:space-between; align-items:center; gap:12px;
        padding:9px 0; border-bottom:1px dashed #e8e0d0;
        font-size:14px; color:#555; font-weight:600;
    }}
    .inv-row span:last-child {{ direction:ltr; unicode-bidi:embed; white-space:nowrap; }}
    .inv-row.net {{
        font-size:20px; font-weight:900; color:#143d2a;
        border-bottom:2px solid #c19b62; padding-bottom:12px; margin-bottom:4px;
    }}
    .inv-row.paid {{ color:#2e7d32; font-weight:800; }}
    .inv-row.rem {{ font-size:17px; font-weight:900; color:#d32f2f; }}
    .inv-row.pay {{
        border:none; border-top:2px solid #143d2a; margin-top:6px; padding-top:12px;
        font-size:15px; font-weight:900; color:#143d2a; background:#f0f7f2;
        border-radius:8px; padding:12px 10px;
    }}
    .inv-footer {{
        text-align:center; margin-top:28px; padding-top:16px;
        border-top:2px solid #eee; color:#777; font-size:13px; font-weight:700;
    }}
    </style>
    <div class="inv-container">
    <div class="inv-header">
        <div class="inv-company-info">{logo_html_fn()}
            <h2 class="ar">{company}</h2>
            <p class="ar"><b>📍 {ar_html('العنوان:')}</b> {address}</p>
            <p class="ar"><b>📞 {ar_html('الهاتف:')}</b> {phone}</p>
        </div>
        <div class="inv-details">
            <span class="inv-badge">KOBE GREEN</span>
            <h1 class="ar">{ar_html('فاتورة')}</h1>
            <p><b>#{res['no']}</b></p>
            <p class="ar"><b>{ar_html('تاريخ الإصدار:')}</b> {res['d']}</p>
        </div>
    </div>
    <div class="inv-bill-to">
        <h4 class="ar" style="margin:0 0 6px;color:#777;font-size:13px;">{ar_html('فاتورة إلى السادة:')}</h4>
        <h3 class="ar">{client}</h3>
    </div>
    <table class="inv-table">
        <thead><tr>
            <th class="ar" style="width:42%;">{ar_html('الصنف والبيان')}</th>
            <th class="ar">{ar_html('الكمية')}</th>
            <th class="ar">{ar_html('سعر الوحدة')}</th>
            <th class="ar">{ar_html('الإجمالي')}</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <div class="inv-summary">
        <div class="inv-summary-box">
            <div class="inv-row"><span class="ar">{ar_html('الإجمالي الفرعي:')}</span><span>{res['gross']:,.2f} {ar_html('ج.م')}</span></div>
            <div class="inv-row" style="color:#d32f2f;"><span class="ar">{ar_html('الخصم:')}</span><span>- {res['disc']:,.2f} {ar_html('ج.م')}</span></div>
            <div class="inv-row net"><span class="ar">{ar_html('الصافي المستحق:')}</span><span>{res['net']:,.2f} {ar_html('ج.م')}</span></div>
            <div class="inv-row paid"><span class="ar">{ar_html('المبلغ المدفوع:')}</span><span>{res['paid']:,.2f} {ar_html('ج.م')}</span></div>
            <div class="inv-row rem"><span class="ar">{ar_html('الرصيد المتبقي:')}</span><span>{res['rem']:,.2f} {ar_html('ج.م')}</span></div>
            <div class="inv-row pay"><span class="ar">{ar_html('طريقة الدفع:')}</span><span class="ar">{pay}</span></div>
        </div>
    </div>
    <div class="inv-footer ar">{footer} 🌱</div>
    </div>"""


def build_kc_invoice_html(res, cfg, font_url):
    from kobe_vast.arabic_text import INVOICE_AR_CSS, ar_html, kc_invoice_row

    rows = "".join(
        kc_invoice_row(i["item"], i.get("type", "-"), i["qty"], i["p"], i["t"])
        for i in res["cart"]
    )
    rem = res.get("rem", res["net"] - res.get("paid", 0))
    client = ar_html(res["c"])
    pay = ar_html(res.get("pay", "—"))
    phone = ar_html(cfg.get("phone", ""))
    address = _addr(cfg)

    return f"""<style>@import url('{font_url}');
    {INVOICE_AR_CSS}
    .kc-inv{{width:100%;font-family:'Cairo','Tajawal',sans-serif;background:#fff;padding:0;
    border-radius:0;overflow:hidden;box-shadow:none;direction:rtl;}}
    .kc-top{{background:linear-gradient(135deg,#f97316,#ea580c,#c2410c);padding:24px 20px;color:#fff;}}
    .kc-title{{font-size:36px;font-weight:900;margin:0;line-height:1.2;}}
    .kc-body{{padding:20px 18px;}}
    .kc-meta{{display:flex;justify-content:space-between;gap:14px;background:#fff7ed;
    border:2px solid #fed7aa;border-radius:12px;padding:16px;margin-bottom:18px;}}
    .kc-tbl{{width:100%;border-collapse:collapse;margin:16px 0;}}
    .kc-tbl th{{background:linear-gradient(90deg,#ea580c,#f97316);color:#fff;padding:12px 8px;font-weight:800;font-size:13px;}}
    .kc-tbl td{{font-size:13px;}}
    .kc-sum{{background:linear-gradient(135deg,#fff7ed,#ffedd5);border:2px solid #fdba74;
    border-radius:12px;padding:18px;width:100%;max-width:100%;}}
    .kc-row{{display:flex;justify-content:space-between;align-items:center;gap:10px;
    padding:9px 0;border-bottom:1px dashed #fdba74;font-weight:600;color:#78350f;font-size:14px;}}
    .kc-row span:last-child{{direction:ltr;unicode-bidi:embed;}}
    .kc-net{{font-size:22px;font-weight:900;color:#ea580c;border-bottom:3px solid #ea580c;padding-bottom:10px;}}
    .kc-pay{{border:none;border-top:3px solid #ea580c;margin-top:8px;padding-top:12px;font-size:16px;
    font-weight:900;color:#9a3412;background:#fff;padding:10px;border-radius:8px;}}
    .kc-footer{{text-align:center;padding:18px;background:#fff7ed;color:#c2410c;font-weight:800;
    border-top:3px solid #f97316;font-size:13px;}}
    .kc-addr{{text-align:center;color:#9a3412;margin-top:14px;font-size:13px;}}
    </style>
    <div class="kc-inv">
    <div class="kc-top">
        <div style="opacity:0.9;font-size:12px;font-weight:700;">🟧 KOBE CUP — RETAIL</div>
        <h1 class="kc-title ar">{ar_html('كوبي كاب')}</h1>
        <p class="ar" style="opacity:0.9;margin-top:4px;font-size:14px;">{ar_html('قهوة مختصة · تجزئة')}</p>
    </div>
    <div class="kc-body">
        <div class="kc-meta">
            <div style="min-width:0;flex:1;">
                <span class="ar" style="color:#9a3412;font-size:12px;">{ar_html('العميل')}</span>
                <h3 class="ar" style="margin:4px 0;color:#9a3412;font-size:18px;">{client}</h3>
            </div>
            <div style="text-align:left;direction:ltr;flex-shrink:0;">
                <span style="color:#9a3412;font-size:12px;">#{res['no']}</span><br>
                <span style="color:#78350f;font-size:13px;">{res['d']}</span>
            </div>
        </div>
        <table class="kc-tbl">
            <thead><tr>
                <th class="ar">{ar_html('الصنف')}</th>
                <th class="ar">{ar_html('الكمية')}</th>
                <th class="ar">{ar_html('السعر')}</th>
                <th class="ar">{ar_html('الإجمالي')}</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
        <div class="kc-sum">
            <div class="kc-row"><span class="ar">{ar_html('الإجمالي:')}</span><span>{res['gross']:,.2f} {ar_html('ج.م')}</span></div>
            <div class="kc-row" style="color:#dc2626;"><span class="ar">{ar_html('الخصم:')}</span><span>- {res['disc']:,.2f}</span></div>
            <div class="kc-row kc-net"><span class="ar">{ar_html('الصافي:')}</span><span>{res['net']:,.2f} {ar_html('ج.م')}</span></div>
            <div class="kc-row" style="color:#16a34a;"><span class="ar">{ar_html('المدفوع:')}</span><span>{res.get('paid', res['net']):,.2f}</span></div>
            <div class="kc-row" style="border:none;color:#dc2626;"><span class="ar">{ar_html('المتبقي:')}</span><span>{rem:,.2f}</span></div>
            <div class="kc-row kc-pay"><span class="ar">{ar_html('طريقة الدفع:')}</span><span class="ar">{pay}</span></div>
        </div>
        <p class="kc-addr ar">📍 {address}</p>
        <p class="ar" style="text-align:center;color:#9a3412;margin-top:8px;">📞 {phone}</p>
    </div>
    <div class="kc-footer ar">{ar_html('شكراً لتسوقكم من كوبي كاب')} ☕🟧</div>
    </div>"""
