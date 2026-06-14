"""Generate docs/USER_MANUAL.pdf using ReportLab, matching the notebook-07 report style."""
import os, sys
from pathlib import Path

# ── ensure we can run from any cwd ───────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, Preformatted,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors

# ── Palette (identical to notebook 07) ───────────────────────────────────────
NAVY      = HexColor("#0f172a")
BLUE      = HexColor("#2E75B6")
BLUE_LT   = HexColor("#dbeafe")
BLUE_ROW  = HexColor("#EBF3FB")
GREY_BDR  = HexColor("#e2e8f0")
SLATE     = HexColor("#64748b")
CHARCOAL  = HexColor("#1e293b")
GREEN     = HexColor("#166534")
GREEN_LT  = HexColor("#dcfce7")
AMBER     = HexColor("#92400e")
AMBER_LT  = HexColor("#fef3c7")
CODE_BG   = HexColor("#f1f5f9")
CODE_FG   = HexColor("#0f172a")

W, H   = letter
MARGIN = 0.75 * inch
CW     = W - 2 * MARGIN

ss = getSampleStyleSheet()


def sty(name, **kw):
    return ParagraphStyle(name, parent=ss["Normal"], **kw)


S = {
    "h1":    sty("h1",   fontName="Helvetica-Bold", fontSize=15, textColor=BLUE,
                          spaceBefore=0, spaceAfter=6, leading=20),
    "h2":    sty("h2",   fontName="Helvetica-Bold", fontSize=11.5, textColor=CHARCOAL,
                          spaceBefore=12, spaceAfter=4, leading=15),
    "h3":    sty("h3",   fontName="Helvetica-Bold", fontSize=10, textColor=SLATE,
                          spaceBefore=8, spaceAfter=3, leading=13),
    "body":  sty("body", fontName="Helvetica", fontSize=9.5, textColor=CHARCOAL,
                          spaceBefore=2, spaceAfter=4, leading=13.5),
    "small": sty("small",fontName="Helvetica", fontSize=8.5, textColor=SLATE,
                          spaceBefore=2, spaceAfter=3, leading=12),
    "mono":  sty("mono", fontName="Courier", fontSize=8, textColor=CODE_FG,
                          spaceBefore=2, spaceAfter=2, leading=11.5,
                          leftIndent=6, rightIndent=6),
    "cell":  sty("cell", fontName="Helvetica", fontSize=8.5, textColor=CHARCOAL, leading=11),
    "cellb": sty("cellb",fontName="Helvetica-Bold", fontSize=8.5, textColor=CHARCOAL, leading=11),
    "hdr":   sty("hdr",  fontName="Helvetica-Bold", fontSize=8.5,
                          textColor=HexColor("#1e3a5f"), leading=11),
    "ct":    sty("ct",   fontName="Helvetica-Bold", fontSize=30, textColor=white,
                          alignment=TA_CENTER, leading=38),
    "cs":    sty("cs",   fontName="Helvetica", fontSize=14,
                          textColor=HexColor("#94a3b8"), alignment=TA_CENTER, leading=18),
    "cm":    sty("cm",   fontName="Helvetica", fontSize=9.5,
                          textColor=HexColor("#64748b"), alignment=TA_CENTER, leading=13),
    "cmsub": sty("cmsub",fontName="Helvetica-Bold", fontSize=10,
                          textColor=HexColor("#7dd3fc"), alignment=TA_CENTER, leading=14),
}


def sp(n=8):
    return Spacer(1, n)


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=GREY_BDR,
                       spaceAfter=6, spaceBefore=6)


def h1(text):
    return [
        Paragraph(text, S["h1"]),
        HRFlowable(width="100%", thickness=2, color=BLUE,
                    spaceAfter=8, spaceBefore=2),
    ]


def h2(text):
    return [Paragraph(text, S["h2"])]


def h3(text):
    return [Paragraph(text, S["h3"])]


def p(text):
    return Paragraph(text, S["body"])


def sm(text):
    return Paragraph(text, S["small"])


def code_block(lines):
    """Monospaced code block with light grey background."""
    joined = "\n".join(lines) if isinstance(lines, list) else lines
    inner = Preformatted(joined, S["mono"])
    tbl = Table([[inner]], colWidths=[CW - 0.1 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX",        (0, 0), (-1, -1), 0.5, GREY_BDR),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    return [tbl, sp(8)]


def dtable(headers, rows, widths, row_colors=None):
    data = [[Paragraph(h, S["hdr"]) for h in headers]]
    for ri, row in enumerate(rows):
        data.append([Paragraph(str(c), S["cell"]) for c in row])
    tbl = Table(data, colWidths=widths)
    cmds = [
        ("BACKGROUND",   (0, 0), (-1, 0),   BLUE_LT),
        ("GRID",         (0, 0), (-1, -1),  0.4, GREY_BDR),
        ("TOPPADDING",   (0, 0), (-1, -1),  4),
        ("BOTTOMPADDING",(0, 0), (-1, -1),  4),
        ("LEFTPADDING",  (0, 0), (-1, -1),  5),
        ("RIGHTPADDING", (0, 0), (-1, -1),  5),
        ("VALIGN",       (0, 0), (-1, -1),  "TOP"),
    ]
    for ri in range(1, len(rows) + 1):
        if row_colors and ri - 1 < len(row_colors):
            cmds.append(("BACKGROUND", (0, ri), (-1, ri), row_colors[ri - 1]))
        elif ri % 2 == 0:
            cmds.append(("BACKGROUND", (0, ri), (-1, ri), BLUE_ROW))
    tbl.setStyle(TableStyle(cmds))
    return [tbl, sp(8)]


def callout(text, bg=AMBER_LT, border=AMBER):
    tbl = Table([[p(text)]], colWidths=[CW - 0.1 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), bg),
        ("LINEBEFORE",   (0, 0), (0, -1),  3, border),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [tbl, sp(8)]


# ── Page templates ────────────────────────────────────────────────────────────
def on_first(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 3.4 * inch, W, 3.4 * inch, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, H - 3.4 * inch, W, 0.06 * inch, fill=1, stroke=0)
    canvas.restoreState()


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(MARGIN, H - 0.52 * inch, CW, 0.30 * inch, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.drawString(MARGIN + 6, H - 0.385 * inch, "EU Gas Storage Analysis — User Manual")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(W - MARGIN - 4, H - 0.385 * inch, "v1.0 · June 2026")
    canvas.setStrokeColor(GREY_BDR)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN, 0.52 * inch, W - MARGIN, 0.52 * inch)
    canvas.setFillColor(SLATE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(W - MARGIN, 0.36 * inch, f"Page {doc.page}")
    canvas.drawString(MARGIN, 0.36 * inch, "github.com/maziez11-lgtm/eu-gas-storage-analysis")
    canvas.restoreState()


# ════════════════════════════════════════════════════════════════════════════════
# BUILD STORY
# ════════════════════════════════════════════════════════════════════════════════
story = []

# ── COVER ─────────────────────────────────────────────────────────────────────
story += [
    sp(2.9 * inch),
    Paragraph("EU Gas Storage Analysis", S["ct"]),
    sp(6),
    Paragraph("User Manual", S["cs"]),
    sp(10),
    HRFlowable(width="28%", thickness=1, color=BLUE, spaceAfter=12, hAlign="CENTER"),
    Paragraph("Version 1.0 · June 2026", S["cm"]),
    sp(6),
    Paragraph(
        "11 Notebooks · PDF Report · Python Analysis Modules",
        S["cmsub"],
    ),
    sp(8),
    Paragraph(
        "Storage · TTF Curve · Spreads · Volatility · LNG",
        S["cm"],
    ),
    PageBreak(),
]

# ── 1. INTRODUCTION ───────────────────────────────────────────────────────────
story += h1("1  Introduction")
story += [
    p(
        "<b>EU Gas Storage Analysis</b> is a Python + Jupyter toolkit for tracking European "
        "natural gas storage fundamentals, analysing TTF forward curve dynamics, and generating "
        "publication-ready market intelligence reports. It pulls live data from the GIE AGSI+ "
        "and ALSI+ APIs and the Databento TTF futures feed, then surfaces the analysis through "
        "11 linked notebooks and a ReportLab PDF report."
    ),
    sp(6),
    p(
        "<b>Who it is for:</b> energy traders monitoring EU injection/withdrawal pace and winter "
        "adequacy; analysts building storage-to-price regression models and spread strategies; "
        "researchers studying seasonal gas market dynamics and LNG import trends."
    ),
    sp(8),
]
story += h2("What you get")
story += dtable(
    ["Deliverable", "Description"],
    [
        ["11 Jupyter notebooks",
         "Storage EDA, seasonal decomposition, injection pace, winter adequacy, TTF curve, "
         "calendar spreads, price volatility, GARCH/HMM regimes, LNG analysis"],
        ["Automated PDF report",
         "Notebook 07 exports an 8-section PDF (storage snapshot, TTF curve, "
         "W-S spread, regression, injection pace, winter adequacy, spread analysis, "
         "volatility, LNG)"],
        ["Python modules in src/",
         "Reusable functions: AGSIClient, ALSIClient, DatabentoTTFClient, "
         "rolling_volatility, garch_volatility, spread_analysis, adequacy model"],
    ],
    [1.8 * inch, 4.95 * inch],
)

# ── 2. QUICK START ────────────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("2  Quick Start  (5 minutes)")
story += h2("Prerequisites")
story += [p("Python 3.11+, pip, JupyterLab"), sp(4)]
story += h2("Installation")
story += code_block([
    "# Clone",
    "git clone https://github.com/maziez11-lgtm/eu-gas-storage-analysis",
    "cd eu-gas-storage-analysis",
    "",
    "# Install dependencies (~2 min)",
    "pip install -r requirements.txt",
    "",
    "# Add API keys (see Section 3)",
    "cp .env.example .env",
    "# Edit .env: add AGSI_API_KEY and DATABENTO_API_KEY",
    "",
    "# Launch JupyterLab",
    "jupyter lab",
])
story += h2("First Run")
story += dtable(
    ["Step", "Action", "Expected output"],
    [
        ["1", "Open 01_data_ingestion.ipynb → paste AGSI key → Kernel → Restart & Run All",
         "✅ Storage: 1826 rows | fill: 72.4%"],
        ["2", "Open 07_ttf_storage_analysis.ipynb → paste Databento key in cell 2 → Restart & Run All",
         "✅ Report: data/processed/gas_storage_ttf_report.pdf"],
        ["3", "In NB 07 last cell click '📄 Download'", "PDF opens / downloads"],
    ],
    [0.4 * inch, 3.4 * inch, 2.95 * inch],
)
story += callout(
    "<b>Tip:</b> API keys are pasted directly into the notebook config cell "
    "(AGSI_API_KEY = \"paste_key_here\"). There is no dotenv runtime dependency.",
    bg=BLUE_LT, border=BLUE,
)

# ── 3. API KEYS ───────────────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("3  API Keys")
story += dtable(
    ["Service", "URL", "Cost", "What it provides"],
    [
        ["AGSI+",     "agsi.gie.eu",    "Free",
         "EU gas storage: fill rate, injection, withdrawal (TWh / GWh/day)"],
        ["ALSI+",     "agsi.gie.eu",    "Free (same key as AGSI)",
         "EU LNG terminal storage: fill rate, send-out (TWh / GWh/day)"],
        ["Databento", "databento.com",  "$125 free credits; full history ~$0.01",
         "TTF futures M1–M24 daily settlement prices (€/MWh)"],
    ],
    [0.9 * inch, 1.4 * inch, 1.55 * inch, 2.9 * inch],
)
story += h2("AGSI+ / ALSI+ key")
story += [
    p("1. Register at <b>agsi.gie.eu</b>"),
    p("2. Log in → profile → copy API key"),
    p("3. Paste into <b>.env</b> as <b>AGSI_API_KEY=your_key_here</b>"),
    p("4. The same key works for both AGSI (gas storage) and ALSI (LNG)"),
    sp(6),
]
story += h2("Databento key")
story += [
    p("1. Register at <b>databento.com/signup</b> (credit card required; not charged within free credits)"),
    p("2. Portal → API Keys → copy key starting with <b>db-</b>"),
    p("3. Paste into <b>.env</b> as <b>DATABENTO_API_KEY=db-xxx...</b>"),
    sp(8),
]
story += code_block([
    "# .env",
    "AGSI_API_KEY=your_agsi_key_here",
    "DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
])
story += callout(
    "<b>Note:</b> Notebooks 01–06 and 11 need only the AGSI key. "
    "Notebooks 07–10 additionally need the Databento key to fetch the TTF forward curve.",
    bg=BLUE_LT, border=BLUE,
)

# ── 4. NOTEBOOKS REFERENCE ────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("4  Notebooks Reference")
story += [p("Run order: NB 01 must run first. NB 07 before NB 06, 08, 09, 10. NB 11 is independent."), sp(6)]
story += dtable(
    ["#", "Notebook", "Purpose", "Prerequisites", "Key outputs", "Runtime"],
    [
        ["01", "data_ingestion",       "Fetch & cache AGSI+ EU + country storage",
         "AGSI key",                   "eu_aggregate_full.parquet",              "2–5 min"],
        ["02", "eda_storage_levels",   "YoY fill, 5yr bands, country heatmap",
         "NB 01",                      "Interactive Plotly charts",              "30 s"],
        ["03", "seasonal_analysis",    "STL decomposition, injection season summary, YoY delta",
         "NB 01",                      "STL chart, season table",                "1 min"],
        ["04", "injection_pace_tracker","90% Nov 1 target — required rate, achievability",
         "NB 01",                      "Required GWh/day, trajectory chart",     "30 s"],
        ["05", "winter_adequacy",      "4 demand × 3 injection scenarios, depletion",
         "NB 01",                      "Depletion curves, days-of-supply table", "30 s"],
        ["06", "ttf_correlation",      "Rolling 30/60/90d fill vs TTF M1 correlation",
         "NB 01, NB 07",              "Correlation series, scatter, OLS",        "30 s"],
        ["07", "ttf_storage_analysis", "Integrated: curve, W-S spread, regression, PDF export",
         "NB 01, Databento key",      "PDF report, ttf_curve.csv",              "3–5 min"],
        ["08", "time_spread_analysis", "Calendar spreads with real month labels",
         "NB 07",                      "Spread matrix, regime table, streaks",   "1 min"],
        ["09", "ttf_price_analysis",   "Rolling vol, GARCH(1,1), price by fill, HMM regimes",
         "NB 07, NB 01",              "Vol chart, regime labels, dist. table",   "2 min"],
        ["10", "spread_deep_dive",     "Roll yield, seasonality, animated curve slider",
         "NB 07, NB 01",              "Roll yield series, animated chart",       "1 min"],
        ["11", "lng_storage_analysis", "EU LNG fill, send-out, gas+LNG buffer",
         "NB 01, ALSI key",           "eu_lng_full.parquet, LNG charts",         "2–5 min"],
    ],
    [0.22*inch, 1.55*inch, 1.85*inch, 1.05*inch, 1.55*inch, 0.6*inch],
)

# ── 5. KEY CONCEPTS ───────────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("5  Key Concepts")

story += h2("Storage Fill Rate")
story += code_block(["fill (%) = gasInStorage (TWh) / workingGasVolume (TWh) × 100"])
story += [
    p("The EU regulatory target is <b>90% fill by November 1</b> each year (EU Regulation 2022/1032). "
      "At 90% the EU holds ~950–1,000 TWh entering winter."),
    sp(4),
]
story += dtable(
    ["API column", "Unit", "Description"],
    [
        ["gasInStorage",     "TWh",     "Working gas currently in storage"],
        ["workingGasVolume", "TWh",     "Total usable capacity"],
        ["injection",        "GWh/day", "Gas injected (positive flow)"],
        ["withdrawal",       "GWh/day", "Gas withdrawn (positive flow)"],
        ["full",             "% (0–100)","Fill rate — auto-computed if absent"],
    ],
    [1.5 * inch, 0.9 * inch, 4.35 * inch],
)
story += [p("<b>Unit conversion:</b> injection and withdrawal are GWh/day; gasInStorage is TWh. "
            "To convert TWh → GWh multiply by 1,000."), sp(8)]

story += h2("TTF Forward Curve")
story += [p("TTF (Title Transfer Facility) is the primary European gas benchmark. "
            "Columns M1–M12 represent monthly settlement prices (€/MWh), "
            "where M1 = front month and M12 = 12 months forward."), sp(4)]
story += dtable(
    ["Term", "Months", "Season"],
    [
        ["M1",     "Front month (nearest delivery)", "Rolls ~3 days before expiry"],
        ["Summer", "Q2 + Q3",                        "April – September"],
        ["Winter", "Q4 + Q1 next year",              "October – March"],
        ["W–S spread", "Winter price − Summer price", "Key injection signal"],
    ],
    [1.2 * inch, 2.4 * inch, 3.15 * inch],
)

story += h2("Contango vs Backwardation")
story += dtable(
    ["Regime", "M1 – M2", "Signal", "Storage economics"],
    [
        ["Contango",      "Negative", "Ample near-term supply",       "Injection profitable (buy spot, sell forward)"],
        ["Flat",          "~0 (±€0.15)", "Balanced",                  "Marginal injection economics"],
        ["Backwardation", "Positive", "Near-term tight; winter priced","Injection uneconomic; withdraw to sell now"],
    ],
    [1.1 * inch, 0.9 * inch, 1.7 * inch, 3.05 * inch],
)
story += [p("<b>Injection breakeven:</b> Winter–Summer spread must exceed ~€5/MWh to cover "
            "underground storage costs (operations, gas losses, financing)."), sp(4),
          p("<b>Roll yield:</b> (M1 − M2) / M1 × (252 / holding_days) × 100. "
            "Positive = backwardation premium. Negative = contango roll cost."), sp(8)]

story += h2("Winter Adequacy Model")
story += dtable(
    ["Scenario", "Net withdrawal", "Cold spell", "Use case"],
    [
        ["Mild",    "4,500 GWh/day", "None",                  "Unusually warm winter"],
        ["Normal",  "6,000 GWh/day", "None",                  "Historical average demand"],
        ["Cold",    "7,500 GWh/day", "14 days at 1.8×",       "Cold winter with snap"],
        ["Extreme", "9,000 GWh/day", "21 days at 2.0×",       "2021-style cold event"],
    ],
    [0.9 * inch, 1.2 * inch, 1.4 * inch, 3.25 * inch],
)
story += [p("Daily supply offsets: ~400 GWh/day LNG + ~800 GWh/day pipeline (configurable). "
            "Model runs 151 days, Nov 1 → Mar 31."), sp(8)]

story += h2("Rolling Correlation")
story += dtable(
    ["Range", "Interpretation"],
    [
        ["r < −0.7",        "Storage is the dominant price driver — normal regime"],
        ["−0.7 to −0.3",   "Moderate influence; LNG / geopolitics competing"],
        ["r > −0.3",        "Storage has lost explanatory power (supply shock, disruption)"],
    ],
    [1.5 * inch, 5.25 * inch],
)

story += h2("LNG Columns (ALSI+)")
story += dtable(
    ["Column", "Unit", "Description"],
    [
        ["gasInStorage", "TWh",     "LNG in terminal tanks"],
        ["dtmi",         "TWh",     "Declared total maximum inventory (capacity)"],
        ["sendOut",      "GWh/day", "Regasified gas sent to the grid"],
        ["full",         "%",       "Fill rate = gasInStorage / dtmi × 100"],
    ],
    [1.5 * inch, 0.9 * inch, 4.35 * inch],
)

# ── 6. EXAMPLE OUTPUTS ────────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("6  Example Outputs")

story += h2("Notebook 01 — Data Ingestion")
story += code_block([
    "✅ Root: /home/user/eu-gas-storage-analysis",
    "Fetching EU aggregate...",
    "  DE: 1826 rows | 2020-01-01 → 2025-11-14",
    "  FR: 1826 rows | 2020-01-01 → 2025-11-14",
    "  ...",
    "✅ Storage: 1826 rows | 2020-01-01 → 2025-11-14",
    "   Analysis date  : 2025-11-14",
    "   Fill rate      : 72.4%",
    "   Storage        : 928.1 TWh",
    "   Capacity       : 1082.6 TWh",
])

story += h2("Notebook 07 — Integrated Analysis")
story += code_block([
    "✅ Root: /home/user/eu-gas-storage-analysis",
    "✅ Storage: 1826 rows | latest: 2025-11-14 | fill: 72.4%",
    "✅ TTF curve loaded: 1512 rows | 2020-01-01 → 2025-11-14",
    "   M1: €38.42/MWh  M3: €41.18/MWh  M6: €44.91/MWh  M12: €46.23/MWh",
    "   Winter-Summer spread: +€6.49/MWh (contango)",
    "",
    "OLS: log(TTF M1) ~ α + β × fill%",
    "  α = 5.8241  β = -0.0243  R² = 0.614",
    "  A 1pp increase in fill = 2.43% decrease in TTF (R²=0.61)",
    "",
    "Injection scenarios: Low=6,240 / Avg=8,810 / High=11,380 GWh/day",
    "  Low  → Nov 1: 79.3%  ⚠  -10.7pp vs target",
    "  Avg  → Nov 1: 89.6%  ✓   -0.4pp vs target",
    "  High → Nov 1: 97.2%  ✓   +7.2pp vs target",
    "",
    "✅ 9 charts saved",
    "✅ Report: data/processed/gas_storage_ttf_report.pdf  [847 KB]",
])

story += h2("Notebook 08 — Time Spread Analysis")
story += code_block([
    "Analysis date: 2025-11-14",
    "TTF rows: 1512  |  Storage rows: 1826",
    "",
    "Spread matrix: 66 column pairs built",
    "Latest M1-M2  spread: -€2.77/MWh  (contango)",
    "Latest M1-M12 spread: -€7.81/MWh",
    "",
    "Longest streaks:",
    "  start       end         regime        days",
    "  2021-09-14  2022-06-28  backwardation  287",
    "  2022-07-01  2023-04-11  backwardation  284",
    "  2020-01-01  2021-09-13  contango       621",
])

story += h2("Notebook 09 — TTF Price Volatility")
story += code_block([
    "Analysis date: 2025-11-14  |  TTF rows: 1512, Storage rows: 1826",
    "",
    "Latest vol_21d: 34.7%   vol_63d: 28.3%",
    "GARCH(1,1) fitted on 1511 log-returns.",
    "Latest GARCH cond. vol: 31.2% (annualised)",
    "",
    "regime_label",
    "Low       412",
    "Medium    680",
    "High      420",
    "dtype: int64",
    "",
    "Price distribution by fill bucket:",
    "  bucket_label  count   mean  median    p10    p90",
    "  20-36%           87   89.4    84.1   44.2  148.3",
    "  36-52%          210   72.1    68.4   32.8  121.6",
    "  52-68%          531   42.7    38.9   24.1   74.2",
    "  68-84%          512   31.8    29.4   19.6   52.7",
    "  84-100%         172   27.3    25.8   17.4   43.1",
])

story += h2("Notebook 11 — LNG Storage")
story += code_block([
    "✅ Root: /home/user/eu-gas-storage-analysis",
    "Setup complete. Run cell 1 to fetch LNG data.",
    "",
    "✅ Saved 1681 rows → data/processed/eu_lng_full.parquet",
    "          gasInStorage  sendOut   dtmi  full",
    "date",
    "2025-11-14         7.21    312.4   8.24  87.5",
    "",
    "Analysis date: 2025-11-14",
    "Latest LNG fill: 87.5%",
    "1-year avg send-out: 287 GWh/day",
    "",
    "Correlation (gas fill vs LNG fill): 0.341",
])

# ── 7. WORKFLOWS ──────────────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("7  Workflows")

story += h2("Workflow 1 — Weekly Market Brief  (10 min)")
story += dtable(
    ["Step", "Action"],
    [
        ["1 — Fetch data",    "Open 01_data_ingestion.ipynb → Kernel → Restart & Run All → confirm latest date"],
        ["2 — Generate report","Open 07_ttf_storage_analysis.ipynb → Restart & Run All → wait for PDF"],
        ["3 — Download",      "Last cell: click '📄 Download' link — or open data/processed/gas_storage_ttf_report.pdf"],
    ],
    [1.5 * inch, 5.25 * inch],
)
story += [p("Output: 8-section PDF covering storage snapshot, TTF curve, W-S spread, regression, "
            "injection pace, winter adequacy, time spreads, volatility, LNG."), sp(8)]

story += h2("Workflow 2 — Winter Adequacy Tracking  (5 min)")
story += dtable(
    ["Step", "Action", "Alert trigger"],
    [
        ["1", "Run NB 01 (data fetch)", ""],
        ["2", "Open 04_injection_pace_tracker → Run All",
         "Achievable: False → cannot reach 90%; check max-injection scenario"],
        ["3", "Open 05_winter_adequacy → Run All",
         "storage_depleted: True in Normal scenario → high stress"],
        ["4", "Cross-check NB 07, Section 4 (injection chart)",
         "Current path below 90% target line → accelerate injection"],
    ],
    [0.35 * inch, 3.1 * inch, 3.3 * inch],
)
story += [p("<b>Trigger:</b> run weekly Apr–Oct; daily if fill rate drops >2pp in a week."), sp(8)]

story += h2("Workflow 3 — Spread & Roll Yield Analysis  (10 min)")
story += dtable(
    ["Step", "Action", "Key metric"],
    [
        ["1", "Run NB 07 (required — fetches TTF curve)", ""],
        ["2", "NB 08 → Run All — read Section 1 W-S spread, Section 3 regime",
         "W-S > €8/MWh → significant winter risk priced"],
        ["3", "NB 10 → Run All — Section 2 roll yield, Section 4 seasonality",
         "Positive roll yield → backwardation premium"],
        ["4", "NB 10, Section 5 — animated curve slider: scrub to historical stress dates",
         "Compare curve shape vs Sep 2021, Aug 2022"],
    ],
    [0.35 * inch, 3.3 * inch, 3.1 * inch],
)
story += [sp(8)]

story += h2("Workflow 4 — Historical Curve Comparison  (5 min)")
story += code_block([
    "# In NB 07 Section 6 (Interactive Curve Tool):",
    "CURVE_DATE = date(2022, 8, 26)   # TTF peak above €300/MWh",
    "# Run the cell → see historical curve vs today's shape",
    "",
    "# Or in NB 10 Section 5 — animated slider:",
    "# Click ▶ Play or drag to comparison date",
])
story += [sp(8)]

story += h2("Workflow 5 — Incremental Data Update  (3 min)")
story += code_block([
    "from src.agsi_client.databento_client import DatabentoTTFClient",
    "",
    "# TTF curve — fetch only new rows since last CSV date",
    "ttf_client = DatabentoTTFClient(api_key='your_key')",
    "df = ttf_client.update_ttf_csv('data/raw/ttf_curve.csv', n_months=12)",
    "# Logs: 'Last date: 2025-11-07 | Fetching from 2025-11-08'",
    "# Logs: '+5 new rows'",
    "# Logs: '✅ Saved 1517 rows → data/raw/ttf_curve.csv'",
    "",
    "# Storage — just re-run NB 01 (cache handles deduplication, 12h TTL)",
])
story += [p("<b>Schedule:</b> run update_ttf_csv daily after ~18:00 CET (ICE settlement time)."), sp(4),]

# ── 8. DATA FILES ─────────────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("8  Data Files")
story += dtable(
    ["Filename", "Location", "Created by", "Contents", "~Rows"],
    [
        ["eu_aggregate_full.parquet", "data/processed/", "NB 01",
         "EU daily: gasInStorage, injection, withdrawal, workingGasVolume, full", "1,500–2,000"],
        ["eu_lng_full.parquet",       "data/processed/", "NB 11",
         "EU LNG daily: gasInStorage, sendOut, dtmi, full",                        "1,500–2,000"],
        ["ttf_curve.csv",             "data/raw/",       "NB 07",
         "TTF forward curve: columns M1–M12, daily settlement (€/MWh)",            "1,500–2,000"],
        ["gas_storage_ttf_report.pdf","data/processed/", "NB 07",
         "8-section PDF report",                                                    "—"],
        ["*.parquet (cache)",         "data/cache/",     "Auto (AGSIClient)",
         "Per-request AGSI API response cache, 12h TTL",                           "—"],
        ["*.parquet (cache)",         "data/cache/alsi/","Auto (ALSIClient)",
         "Per-request ALSI API response cache, 12h TTL",                           "—"],
    ],
    [1.5 * inch, 1.1 * inch, 0.85 * inch, 2.8 * inch, 0.7 * inch],
)
story += h2("Loading parquet files")
story += code_block([
    "import pandas as pd",
    "",
    "df = pd.read_parquet('data/processed/eu_aggregate_full.parquet')",
    "df.index = pd.to_datetime(df.index).tz_localize(None)   # strip tz",
    "df = df.sort_index()",
])
story += h2("Cache management")
story += code_block([
    "# Force fresh fetch (bypass cache)",
    "df = client.get_eu_aggregate(start='2020-01-01', use_cache=False)",
    "",
    "# Clear all cache files",
    "client.clear_cache()",
])

# ── 9. TROUBLESHOOTING ────────────────────────────────────────────────────────
story.append(PageBreak())
story += h1("9  Troubleshooting")
story += dtable(
    ["Error / Symptom", "Cause", "Fix"],
    [
        ["TypeError: Cannot join tz-naive and tz-aware DatetimeIndex",
         "API returns UTC-aware timestamps; storage parquet may be tz-naive",
         "Add .tz_localize(None): df.index = pd.to_datetime(df.index).tz_localize(None)"],

        ["ModuleNotFoundError: No module named 'src'",
         "Notebook opened from wrong directory; project root not in sys.path",
         "Run the path-fix cell at the top of every notebook first (the for _c in [...] block)"],

        ["reversed() argument must be a sequence (Python 3.14+)",
         "Python 3.14 tightened reversed() protocol; some Plotly internals affected",
         "Replace reversed(x) with x[::-1] in any custom code; src/visualization/plots.py already uses slice notation"],

        ["ALSI sendOut / dtmi columns missing or all NaN",
         "Not all LNG terminals report all fields to GIE",
         "ALSIClient._parse() coerces to NaN; guard with lat.get('sendOut', float('nan'))"],

        ["Only 300 rows returned from AGSI / ALSI",
         "API paginates at 300 rows per page",
         "Clients handle pagination automatically. If truncated, verify API key — invalid keys often return one empty page"],

        ["FileNotFoundError: eu_aggregate_full.parquet",
         "Notebook 01 has not been run yet",
         "Run 01_data_ingestion.ipynb (Kernel → Restart & Run All) before any other notebook"],

        ["FileNotFoundError: ttf_curve.csv",
         "Notebook 07 cell 2 (Databento fetch) has not been run",
         "Open NB 07, run cell 2 with a valid DATABENTO_API_KEY"],

        ["ImportError: No module named 'arch'",
         "Optional GARCH dependency not installed",
         "pip install arch  (already in requirements.txt — re-run pip install -r requirements.txt)"],

        ["Charts blank / kaleido error in PDF export",
         "kaleido not installed or incompatible version",
         "pip install kaleido==0.2.1  (must match Plotly version)"],

        ["Cache returning stale data",
         "12h TTL not yet expired",
         "Pass use_cache=False to any client method, or call client.clear_cache()"],
    ],
    [1.85 * inch, 1.75 * inch, 3.15 * inch],
)

# ── FOOTER ────────────────────────────────────────────────────────────────────
story += [
    sp(20), hr(),
    sm("EU Gas Storage Analysis · github.com/maziez11-lgtm/eu-gas-storage-analysis · "
       "Data: GIE AGSI+ · GIE ALSI+ · Databento NDEX.IMPACT"),
]

# ── BUILD PDF ─────────────────────────────────────────────────────────────────
OUT = ROOT / "docs" / "USER_MANUAL.pdf"
doc = SimpleDocTemplate(
    str(OUT),
    pagesize=letter,
    leftMargin=MARGIN, rightMargin=MARGIN,
    topMargin=0.80 * inch, bottomMargin=0.70 * inch,
    title="EU Gas Storage Analysis — User Manual",
    author="eu-gas-storage-analysis",
)
doc.build(story, onFirstPage=on_first, onLaterPages=on_page)
print(f"✅ PDF: {OUT}")
print(f"   Size: {OUT.stat().st_size / 1024:.0f} KB")
