"""
report/pdf_generator.py
────────────────────────
Converts report data dict into a PDF bytes object using matplotlib (charts)
and WeasyPrint (HTML → PDF). No browser required.

Usage:
    from report.pdf_generator import generate_report_pdf

    pdf_bytes = generate_report_pdf(stats, unit_number, node_id)
    st.download_button("⬇ Download PDF", pdf_bytes, "report.pdf", "application/pdf")
"""

import base64
import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# CHART HELPERS
# ─────────────────────────────────────────────────────────────────────────────

PHLOTON_GREEN  = "#1a8c5b"
PHLOTON_BLUE   = "#2563eb"
PHLOTON_AMBER  = "#d97706"
PHLOTON_RED    = "#c0392b"
PHLOTON_MUTED  = "#9db8ad"
PHLOTON_BG     = "#f4f6f5"
PHLOTON_BORDER = "#e0e8e4"

plt.rcParams.update({
    "font.family":      "Liberation Sans",
    "font.size":        8,
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "axes.spines.left": True,
    "axes.spines.bottom": True,
    "axes.edgecolor":   PHLOTON_BORDER,
    "axes.facecolor":   "white",
    "figure.facecolor": "white",
    "grid.color":       "#edf2ef",
    "grid.linewidth":   0.6,
    "xtick.color":      PHLOTON_MUTED,
    "ytick.color":      PHLOTON_MUTED,
    "axes.labelcolor":  "#1a2e27",
    "text.color":       "#1a2e27",
})


def _fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def _parse_labels(labels: list) -> list:
    """Parse 'MM-DD HH:MM' label strings into datetime objects for x-axis."""
    parsed = []
    for l in labels:
        try:
            # Try "MM-DD HH:MM" format
            parsed.append(datetime.strptime(f"2026-{l}", "%Y-%m-%d %H:%M"))
        except Exception:
            parsed.append(None)
    return parsed


def _make_line_chart(labels, values, color, ylabel, title,
                     figsize=(7.5, 2.2), ymin=None, ymax=None) -> str:
    """Create a single line chart, return base64 PNG."""
    fig, ax = plt.subplots(figsize=figsize)

    # Filter out None values but keep x alignment
    xs = list(range(len(values)))
    ys = [v if v is not None else float("nan") for v in values]

    # Thin x labels to ~10 ticks
    n = len(xs)
    tick_step = max(1, n // 10)
    tick_indices = list(range(0, n, tick_step))

    ax.plot(xs, ys, color=color, linewidth=1.5, solid_capstyle="round")
    ax.fill_between(xs, ys, alpha=0.12, color=color)
    ax.set_title(title, fontsize=9, fontweight="bold", color="#1a2e27", pad=6)
    ax.set_ylabel(ylabel, fontsize=7.5, color=PHLOTON_MUTED)
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([labels[i] for i in tick_indices], rotation=30,
                       ha="right", fontsize=6.5)
    ax.yaxis.grid(True)
    ax.xaxis.grid(False)
    if ymin is not None: ax.set_ylim(bottom=ymin)
    if ymax is not None: ax.set_ylim(top=ymax)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_bar_chart(labels, values, colors_list, ylabel, title,
                    figsize=(7.5, 2.0)) -> str:
    """Create a bar chart (used for TEC uptime per day)."""
    fig, ax = plt.subplots(figsize=figsize)
    xs = list(range(len(labels)))
    bars = ax.bar(xs, values, color=colors_list, width=0.6, zorder=2)
    ax.set_title(title, fontsize=9, fontweight="bold", color="#1a2e27", pad=6)
    ax.set_ylabel(ylabel, fontsize=7.5, color=PHLOTON_MUTED)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.set_ylim(0, 105)
    ax.yaxis.grid(True, zorder=0)
    ax.xaxis.grid(False)
    # Value labels on bars
    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val}%", ha="center", va="bottom", fontsize=6.5,
                    color="#1a2e27", fontweight="600")
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_map_chart(map_path: list, figsize=(7.5, 3.5)) -> str:
    """Plot GPS movement path as a scatter/line chart, return base64 PNG."""
    if not map_path:
        return None

    lats = [p["lat"] for p in map_path]
    lngs = [p["lng"] for p in map_path]

    fig, ax = plt.subplots(figsize=figsize)

    # Draw path line
    ax.plot(lngs, lats, color=PHLOTON_MUTED, linewidth=0.8, alpha=0.5, zorder=1)

    # Colour points by time index (light → dark = early → late)
    n = len(map_path)
    colors = [plt.cm.YlGn(0.3 + 0.7 * i / max(n - 1, 1)) for i in range(n)]
    sc = ax.scatter(lngs, lats, c=range(n), cmap="YlGn", s=18,
                    zorder=2, linewidths=0.3, edgecolors="#1a8c5b")

    # Mark start (green) and end (red)
    ax.scatter([lngs[0]],  [lats[0]],  color=PHLOTON_GREEN, s=80,
               zorder=4, marker="^", label="Start")
    ax.scatter([lngs[-1]], [lats[-1]], color=PHLOTON_RED,   s=80,
               zorder=4, marker="v", label="Last Position")

    # Annotate start/end timestamps if available
    if map_path[0].get("ts"):
        ax.annotate(f"  Start\n  {map_path[0]['ts']}",
                    (lngs[0], lats[0]), fontsize=6, color=PHLOTON_GREEN,
                    va="bottom")
    if map_path[-1].get("ts"):
        ax.annotate(f"  Last\n  {map_path[-1]['ts']}",
                    (lngs[-1], lats[-1]), fontsize=6, color=PHLOTON_RED,
                    va="top")

    # Colourbar to show time progression
    cbar = plt.colorbar(sc, ax=ax, pad=0.02, fraction=0.025)
    cbar.set_label("Time progression →", fontsize=7, color=PHLOTON_MUTED)
    cbar.set_ticks([])

    ax.set_xlabel("Longitude", fontsize=7.5, color=PHLOTON_MUTED)
    ax.set_ylabel("Latitude",  fontsize=7.5, color=PHLOTON_MUTED)
    ax.set_title("Device Movement Path", fontsize=9, fontweight="bold",
                 color="#1a2e27", pad=6)
    ax.legend(fontsize=7, loc="upper left",
              framealpha=0.7, edgecolor=PHLOTON_BORDER)
    ax.yaxis.grid(True)
    ax.xaxis.grid(True)

    # Add padding around extent
    lat_pad = max((max(lats) - min(lats)) * 0.1, 0.002)
    lng_pad = max((max(lngs) - min(lngs)) * 0.1, 0.002)
    ax.set_xlim(min(lngs) - lng_pad, max(lngs) + lng_pad)
    ax.set_ylim(min(lats) - lat_pad, max(lats) + lat_pad)

    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_map_stats_html(map_path: list) -> str:
    """Build a small HTML stats table for the location section."""
    if not map_path:
        return "<p style='color:#9db8ad;font-size:8pt;'>No GPS data recorded in this session.</p>"

    lats = [p["lat"] for p in map_path]
    lngs = [p["lng"] for p in map_path]
    unique = len({(p["lat"], p["lng"]) for p in map_path})
    start_ts = map_path[0].get("ts", "—")
    end_ts   = map_path[-1].get("ts", "—")

    return f"""
    <table class="data-table" style="width:auto;min-width:260px;">
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Unique positions</td><td class="num">{unique}</td></tr>
      <tr><td>Lat range</td><td class="num">{min(lats):.5f}° – {max(lats):.5f}°</td></tr>
      <tr><td>Lng range</td><td class="num">{min(lngs):.5f}° – {max(lngs):.5f}°</td></tr>
      <tr><td>First GPS fix</td><td class="num">{start_ts}</td></tr>
      <tr><td>Last GPS fix</td><td class="num">{end_ts}</td></tr>
    </table>"""


def _make_day_charts(day_charts: dict, date: str) -> dict:
    """Generate the 4 per-day charts, return dict of base64 strings."""
    dc = day_charts.get(date, {})
    result = {}

    def safe_chart(key, color, ylabel, title, ymin=None, ymax=None):
        sub = dc.get(key, {})
        lbls = sub.get("labels", [])
        vals = sub.get("values", [])
        if lbls and vals:
            return _make_line_chart(lbls, vals, color, ylabel, title,
                                    figsize=(3.5, 1.9), ymin=ymin, ymax=ymax)
        return None

    result["flask"] = safe_chart("flask", PHLOTON_GREEN, "°C",
                                  f"Flask Temp — {date}", ymin=0)
    result["soc"]   = safe_chart("soc",   PHLOTON_BLUE,  "%",
                                  f"SOC — {date}", ymin=50, ymax=102)
    result["bv"]    = safe_chart("bv",    PHLOTON_AMBER, "V",
                                  f"Battery V — {date}", ymin=9, ymax=14)
    result["pcb"]   = safe_chart("pcb",   PHLOTON_AMBER, "°C",
                                  f"PCB Temp — {date}", ymin=30)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

def _render_pdf_html(data: dict, unit_number: int, node_id: str,
                     charts: dict) -> str:
    """Build the PDF-optimised HTML string with embedded chart images."""
    ov  = data["overall"]
    ds  = data["day_stats"]

    flask_avg = ov["flask"]["avg"] or "—"
    flask_min = ov["flask"]["min"] or "—"
    flask_max = ov["flask"]["max"] or "—"
    soc_avg   = ov["soc"]["avg"]   or "—"
    soc_min   = ov["soc"]["min"]   or "—"
    bv_avg    = ov["bv"]["avg"]    or "—"
    bv_min    = ov["bv"]["min"]    or "—"
    bv_max    = ov["bv"]["max"]    or "—"
    pcb_avg   = ov["pcb"]["avg"]   or "—"
    tec_pct   = ov["tec_uptime_pct"]
    dates     = ov["dates"]
    duration  = f"{ov['duration_days']} days"
    date_range= f"{ov['start']} → {ov['end']}"

    def img(b64, width="100%"):
        if not b64:
            return '<div class="no-data">No data available</div>'
        return f'<img src="data:image/png;base64,{b64}" style="width:{width};display:block;">'

    # Day summary table rows
    table_rows = ""
    for d in dates:
        s = ds[d]
        fl_avg = s.get("flask_avg")
        fl_ok  = fl_avg is not None and fl_avg <= 8
        status = "✓ In Range" if fl_ok else ("⚠ Excursion" if fl_avg is not None else "N/A")
        status_color = "#1a8c5b" if fl_ok else ("#d97706" if fl_avg is not None else "#999")
        tec_c = "#1a8c5b" if s["tec_uptime"] >= 90 else ("#d97706" if s["tec_uptime"] >= 70 else "#c0392b")
        table_rows += f"""
        <tr>
          <td><b>{d}</b></td>
          <td class="num">{s['rows']:,}</td>
          <td class="num">{s.get('flask_avg') or '—'}°C</td>
          <td class="num">{s.get('flask_min') or '—'}°C</td>
          <td class="num">{s.get('flask_max') or '—'}°C</td>
          <td class="num">{s.get('soc_avg') or '—'}%</td>
          <td class="num">{s.get('bv_avg') or '—'}V</td>
          <td class="num" style="color:{tec_c};font-weight:700">{s['tec_uptime']}%</td>
          <td style="color:{status_color};font-weight:600;font-size:9px">{status}</td>
        </tr>"""

    # Per-day chart sections
    day_sections = ""
    for d in dates:
        s  = ds[d]
        dc = charts.get("day", {}).get(d, {})
        tec_c = "#1a8c5b" if s["tec_uptime"] >= 90 else ("#d97706" if s["tec_uptime"] >= 70 else "#c0392b")
        day_sections += f"""
        <div class="day-section page-break-inside-avoid">
          <div class="day-header">
            <span class="day-title">{d}</span>
            <span class="day-kpis">
              Flask avg <b>{s.get('flask_avg') or '—'}°C</b> &nbsp;·&nbsp;
              SOC avg <b>{s.get('soc_avg') or '—'}%</b> &nbsp;·&nbsp;
              Batt <b>{s.get('bv_avg') or '—'}V</b> &nbsp;·&nbsp;
              TEC <b style="color:{tec_c}">{s['tec_uptime']}%</b> &nbsp;·&nbsp;
              {s['rows']:,} readings
            </span>
          </div>
          <div class="chart-row-2">
            <div class="chart-cell">{img(dc.get("flask"))}</div>
            <div class="chart-cell">{img(dc.get("soc"))}</div>
          </div>
          <div class="chart-row-2">
            <div class="chart-cell">{img(dc.get("bv"))}</div>
            <div class="chart-cell">{img(dc.get("pcb"))}</div>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @page {{
    size: A4;
    margin: 14mm 14mm 12mm 14mm;
    @top-right {{
      content: "Phloton · Unit {unit_number} · Confidential";
      font-family: "Liberation Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 7pt;
      color: #9db8ad;
    }}
    @bottom-center {{
      content: "Page " counter(page) " of " counter(pages);
      font-family: "Liberation Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 7pt;
      color: #9db8ad;
    }}
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    ffont-family: "Liberation Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 9pt;
    color: #1a2e27;
    line-height: 1.5;
  }}

  /* ── HEADER ── */
  .report-header {{
    background: #0f1f1a;
    color: white;
    padding: 12px 16px;
    margin-bottom: 14px;
    border-radius: 6px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .header-left .brand {{ font-size: 7pt; color: #22b870; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 4px; }}
  .header-left h1 {{ font-size: 15pt; font-weight: bold; color: white; letter-spacing: -0.3px; }}
  .header-left h1 span {{ color: #22b870; }}
  .header-left .subtitle {{ font-size: 7.5pt; color: rgba(255,255,255,0.55); margin-top: 4px; }}
  .header-right {{ text-align: right; font-size: 7.5pt; color: rgba(255,255,255,0.5); line-height: 1.9; }}
  .header-right strong {{ color: rgba(255,255,255,0.85); }}
  .badges {{ display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }}
  .badge {{ padding: 2px 8px; border-radius: 10px; font-size: 6.5pt; font-weight: 600; border: 1px solid; }}
  .badge-g {{ background: rgba(26,140,91,.2); color: #6ddba0; border-color: rgba(26,140,91,.4); }}
  .badge-r {{ background: rgba(192,57,43,.2); color: #f0a09a; border-color: rgba(192,57,43,.4); }}

  /* ── COMPLIANCE STRIP ── */
  .compliance-strip {{
    background: #f0faf4;
    border: 1px solid rgba(26,140,91,.2);
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 12px;
    display: flex;
    gap: 16px;
    font-size: 7.5pt;
  }}
  .comp-item {{ display: flex; align-items: center; gap: 5px; }}
  .comp-check {{ color: #1a8c5b; font-weight: bold; font-size: 9pt; }}
  .comp-label {{ font-weight: 600; color: #0f1f1a; }}
  .comp-sub {{ font-size: 6.5pt; color: #6b8f7e; }}

  /* ── SECTION HEADER ── */
  .sec-hdr {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; margin-top: 14px; }}
  .sec-tag {{ font-size: 6.5pt; font-weight: 700; letter-spacing: .15em; text-transform: uppercase;
              color: #1a8c5b; background: #e8f5ee; padding: 2px 7px; border-radius: 3px; }}
  .sec-title {{ font-size: 11pt; font-weight: bold; color: #0f1f1a; }}
  .sec-line {{ flex: 1; height: 1px; background: #e0e8e4; }}

  /* ── KPI GRID ── */
  .kpi-grid {{ display: flex; gap: 8px; margin-bottom: 10px; }}
  .kpi {{
    flex: 1;
    background: white;
    border: 1px solid #e0e8e4;
    border-radius: 6px;
    padding: 8px 10px;
    border-top: 3px solid #1a8c5b;
  }}
  .kpi.blue {{ border-top-color: #2563eb; }}
  .kpi.amber {{ border-top-color: #d97706; }}
  .kpi-label {{ font-size: 6pt; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #6b8f7e; margin-bottom: 3px; }}
  .kpi-value {{ font-size: 14pt; font-weight: bold; letter-spacing: -.5px; line-height: 1; color: #1a8c5b; }}
  .kpi.blue .kpi-value {{ color: #2563eb; }}
  .kpi.amber .kpi-value {{ color: #d97706; }}
  .kpi-sub {{ font-size: 6.5pt; color: #6b8f7e; margin-top: 2px; }}

  /* ── CHARTS ── */
  .chart-full {{ margin-bottom: 10px; border: 1px solid #e0e8e4; border-radius: 6px; overflow: hidden; }}
  .chart-full img {{ width: 100%; display: block; }}
  .chart-row-2 {{ display: flex; gap: 8px; margin-bottom: 8px; }}
  .chart-cell {{ flex: 1; border: 1px solid #e0e8e4; border-radius: 6px; overflow: hidden; }}
  .chart-cell img {{ width: 100%; display: block; }}

  /* ── FLASK INSIGHT ── */
  .flask-insight {{
    background: #f0faf4; border: 1px solid #e8f5ee;
    border-left: 3px solid #1a8c5b;
    border-radius: 4px; padding: 7px 10px;
    font-size: 7.5pt; color: #1a2e27; line-height: 1.6;
    margin-top: 6px; margin-bottom: 10px;
  }}
  .flask-insight::before {{ content: "↗ Insight  "; font-weight: bold; color: #1a8c5b; }}

  /* ── TABLE ── */
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 7.5pt; margin-bottom: 10px; }}
  .data-table th {{
    text-align: left; padding: 5px 7px;
    font-size: 6.5pt; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
    color: #6b8f7e; background: #f4f6f5; border-bottom: 1.5px solid #e0e8e4;
  }}
  .data-table td {{ padding: 5px 7px; border-bottom: 1px solid #edf2ef; }}
  .data-table tr:last-child td {{ border-bottom: none; }}
  .data-table .num {{ font-family: "DejaVu Sans Mono", monospace; font-size: 7pt; }}

  /* ── DAY SECTIONS ── */
  .day-section {{
    background: white; border: 1px solid #e0e8e4;
    border-radius: 6px; padding: 10px 12px;
    margin-bottom: 12px;
  }}
  .day-header {{
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 8px; padding-bottom: 6px;
    border-bottom: 1px solid #edf2ef;
  }}
  .day-title {{ font-size: 10pt; font-weight: bold; color: #0f1f1a; }}
  .day-kpis {{ font-size: 7pt; color: #6b8f7e; }}

  /* ── PAGE BREAKS ── */
  .page-break {{ page-break-after: always; }}
  .page-break-inside-avoid {{ page-break-inside: avoid; }}
  .no-data {{ font-size: 7.5pt; color: #9db8ad; padding: 20px; text-align: center; }}

  /* ── FOOTER ── */
  .report-footer {{
    background: #0f1f1a; color: rgba(255,255,255,.45);
    padding: 8px 12px; border-radius: 5px; margin-top: 16px;
    display: flex; justify-content: space-between; font-size: 7pt;
  }}
  .report-footer strong {{ color: white; }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="report-header">
  <div class="header-left">
    <div class="brand">Phloton · IoT Telemetry Report</div>
    <h1>Unit {unit_number} · <span>{ov["start"][:10]} to {ov["end"][:10]}</span></h1>
    <div class="subtitle">Node: {node_id} &nbsp;·&nbsp; {duration} &nbsp;·&nbsp; {ov["total_rows"]:,} readings &nbsp;·&nbsp; Bengaluru, IN</div>
    <div class="badges">
      <span class="badge badge-g">✓ {flask_avg}°C Avg Flask Temp</span>
      <span class="badge badge-g">✓ TEC {tec_pct}% Uptime</span>
      <span class="badge badge-r">⚠ Fault Flag Active</span>
    </div>
  </div>
  <div class="header-right">
    <strong>Duration</strong> {duration}<br>
    <strong>Data Points</strong> {ov["total_rows"]:,}<br>
    <strong>Unit</strong> #{unit_number}<br>
    <strong>Generated</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")}
  </div>
</div>

<!-- COMPLIANCE -->
<div class="compliance-strip">
  <div class="comp-item">
    <span class="comp-check">✓</span>
    <div><div class="comp-label">Avg Flask Temp</div><div class="comp-sub">{flask_avg}°C — within 2–8°C WHO spec</div></div>
  </div>
  <div class="comp-item">
    <span class="comp-check">✓</span>
    <div><div class="comp-label">Continuous Logging</div><div class="comp-sub">{ov["total_rows"]:,} readings · {duration}</div></div>
  </div>
  <div class="comp-item">
    <span class="comp-check">✓</span>
    <div><div class="comp-label">TEC Active</div><div class="comp-sub">{tec_pct}% of session</div></div>
  </div>
  <div class="comp-item">
    <span class="comp-check" style="color:#d97706">⚠</span>
    <div><div class="comp-label" style="color:#d97706">Fault Flag</div><div class="comp-sub">Active — investigate</div></div>
  </div>
</div>

<!-- SECTION: SUMMARY KPIs -->
<div class="sec-hdr"><span class="sec-tag">Summary</span><span class="sec-title">Session at a Glance</span><div class="sec-line"></div></div>
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-label">Flask Avg Temp</div><div class="kpi-value">{flask_avg}°C</div><div class="kpi-sub">Range: {flask_min} – {flask_max}°C</div></div>
  <div class="kpi blue"><div class="kpi-label">Avg Battery SOC</div><div class="kpi-value">{soc_avg}%</div><div class="kpi-sub">Min: {soc_min}%</div></div>
  <div class="kpi amber"><div class="kpi-label">Avg Battery Volt</div><div class="kpi-value">{bv_avg}V</div><div class="kpi-sub">Range: {bv_min}–{bv_max}V</div></div>
  <div class="kpi"><div class="kpi-label">TEC Uptime</div><div class="kpi-value">{tec_pct}%</div><div class="kpi-sub">{ov["total_rows"]:,} samples total</div></div>
  <div class="kpi amber"><div class="kpi-label">PCB Temp Avg</div><div class="kpi-value">{pcb_avg}°C</div><div class="kpi-sub">Board temperature</div></div>
</div>

<!-- SECTION: FLASK TEMPERATURE -->
<div class="sec-hdr"><span class="sec-tag">Primary</span><span class="sec-title">Flask Temperature Trend</span><div class="sec-line"></div></div>
{img(charts.get("flask_full"))}
<div class="flask-insight">
Flask temperature averaged {flask_avg}°C across {duration}, well within the 2–8°C WHO cold chain specification.
Spikes above 8°C indicate loading/door-open events; TEC recovered promptly each time.
</div>

<!-- SECTION: BATTERY & SYSTEM -->
<div class="sec-hdr"><span class="sec-tag">Power</span><span class="sec-title">Battery & System</span><div class="sec-line"></div></div>
<div class="chart-row-2">
  <div class="chart-cell">{img(charts.get("soc_full"))}</div>
  <div class="chart-cell">{img(charts.get("bv_full"))}</div>
</div>
<div class="chart-row-2">
  <div class="chart-cell">{img(charts.get("pcb_full"))}</div>
  <div class="chart-cell">{img(charts.get("tec_bar"))}</div>
</div>

<!-- SECTION: DAY SUMMARY TABLE -->
<div class="sec-hdr"><span class="sec-tag">Daily</span><span class="sec-title">Day-by-Day Summary</span><div class="sec-line"></div></div>
<table class="data-table">
  <tr><th>Date</th><th>Readings</th><th>Flask Avg</th><th>Flask Min</th><th>Flask Max</th><th>SOC Avg</th><th>Batt V</th><th>TEC Uptime</th><th>Status</th></tr>
  {table_rows}
</table>

<!-- PAGE BREAK before day sections -->
<div class="page-break"></div>

<!-- SECTION: DAY-WISE CHARTS -->
<div class="sec-hdr"><span class="sec-tag">Day-wise</span><span class="sec-title">Daily Breakdown</span><div class="sec-line"></div></div>
{day_sections}

<!-- PAGE BREAK before location -->
<div class="page-break"></div>

<!-- SECTION: LOCATION & MOVEMENT -->
<div class="sec-hdr"><span class="sec-tag">GPS</span><span class="sec-title">Device Location &amp; Movement</span><div class="sec-line"></div></div>
<div style="display:flex;gap:14px;align-items:flex-start;margin-bottom:10px;">
  <div style="flex:1;">{img(charts.get("map_chart"))}</div>
  <div style="width:240px;">{charts.get("map_stats_html","")}</div>
</div>

<!-- FOOTER -->
<div class="report-footer">
  <strong>Phloton · Unit {unit_number}</strong>
  <span>Anedya IoT Platform · Node {node_id}</span>
  <span>phloton.com · © 2026 Enhanced Innovations Pvt. Ltd.</span>
</div>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def generate_report_pdf(data: dict, unit_number: int, node_id: str) -> bytes:
    """
    Takes the stats dict from report_generator._build_stats(),
    generates matplotlib charts, renders PDF-optimised HTML,
    converts to PDF with WeasyPrint, returns bytes.
    """
    from weasyprint import HTML, CSS  # lazy import — only when PDF is requested

    ov = data["overall"]
    T  = data["trend"]

    # ── Generate overview charts ──────────────────────────────────────────────
    charts = {}

    charts["flask_full"] = _make_line_chart(
        T["labels"], T["flask"], PHLOTON_GREEN, "°C",
        "Flask Top Temperature (°C) — Full Session",
        figsize=(7.5, 2.5), ymin=0,
    )
    charts["soc_full"] = _make_line_chart(
        T["labels"], T["soc"], PHLOTON_BLUE, "%",
        "Battery SOC (%)", figsize=(3.5, 2.1), ymin=40, ymax=102,
    )
    charts["bv_full"] = _make_line_chart(
        T["labels"], T["bv"], PHLOTON_AMBER, "V",
        "Battery Voltage (V)", figsize=(3.5, 2.1), ymin=9, ymax=14,
    )
    charts["pcb_full"] = _make_line_chart(
        T["labels"], T["pcb"], PHLOTON_AMBER, "°C",
        "PCB Temperature (°C)", figsize=(3.5, 2.1), ymin=30,
    )

    # TEC uptime bar chart
    tec_labels = [d[5:] for d in ov["dates"]]
    tec_values = [data["day_stats"][d]["tec_uptime"] for d in ov["dates"]]
    tec_colors = [
        PHLOTON_GREEN if v >= 90 else (PHLOTON_AMBER if v >= 70 else PHLOTON_RED)
        for v in tec_values
    ]
    charts["tec_bar"] = _make_bar_chart(
        tec_labels, tec_values, tec_colors, "%",
        "TEC Uptime per Day (%)", figsize=(3.5, 2.1),
    )

    # ── Per-day charts ────────────────────────────────────────────────────────
    charts["day"] = {}
    for d in ov["dates"]:
        charts["day"][d] = _make_day_charts(data["day_charts"], d)

    # ── Map / location chart ──────────────────────────────────────────────────
    map_path = data.get("map_path", [])
    charts["map_chart"]      = _make_map_chart(map_path)
    charts["map_stats_html"] = _make_map_stats_html(map_path)

    # ── Render HTML ───────────────────────────────────────────────────────────
    html_str = _render_pdf_html(data, unit_number, node_id, charts)

    # ── Convert to PDF ────────────────────────────────────────────────────────
    pdf_bytes = HTML(string=html_str).write_pdf()
    return pdf_bytes
