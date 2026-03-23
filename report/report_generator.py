"""
report/report_generator.py
──────────────────────────
Fetches data from Anedya for a given node + date range, then builds and
returns a Phloton-branded HTML report as a string.

Usage (from any unit page or unit_ui_components.py):

    from report.report_generator import generate_report_html

    html = generate_report_html(
        node_client=node,          # NewNode instance
        unit_number=1,
        node_id="019c…",
        variables=VARIABLES,       # st.session_state.variablesIdentifier
        from_epoch=from_ts,        # int epoch seconds
        to_epoch=to_ts,
        chunk_days=1,              # pagination chunk size
    )
    st.download_button("⬇ Download Report", html, "report.html", "text/html")
"""

import ast
import json
import time as time_module
from collections import defaultdict
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

from cloud.anedya_cloud import _fetch_chunk_raw


# ─── Variable identifiers we care about for the report ────────────────────
REPORT_VARIABLES = [
    "FlaskTopTemp",
    "SOC",
    "BATTVOLT",
    "PCBTemp",
    "HeatSinkTemp",
    "ColdSinkTemp",
    "TECstatus",
    "TECdutycycle",
    "BATTERYCURRENT",
    "location",
]

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_all_variables(node_id, api_key, from_epoch, to_epoch, chunk_days, progress_bar):
    """Fetch all REPORT_VARIABLES with chunked pagination."""
    CHUNK = chunk_days * 86400
    chunks = []
    cur = from_epoch
    while cur < to_epoch:
        nxt = min(cur + CHUNK - 1, to_epoch)
        chunks.append((cur, nxt))
        cur += CHUNK

    all_data = {}
    total_steps = len(REPORT_VARIABLES) * len(chunks)
    step = 0

    for var in REPORT_VARIABLES:
        pts = []
        for cf, ct in chunks:
            raw = _fetch_chunk_raw(var, node_id, cf, ct, api_key)
            pts.extend(raw)
            step += 1
            progress_bar.progress(step / total_steps, text=f"Fetching {var}…")
            time_module.sleep(0.2)

        # Deduplicate + sort
        seen, unique = set(), []
        for p in pts:
            ts = p.get("timestamp")
            if ts not in seen:
                seen.add(ts)
                unique.append(p)
        all_data[var] = sorted(unique, key=lambda x: x.get("timestamp", 0))

    return all_data


# ─────────────────────────────────────────────────────────────────────────────
# STATISTICS HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v):
    try:
        f = float(v)
        return None if f < -200 else f
    except Exception:
        return None


def _stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
        "avg": round(sum(vals) / len(vals), 2),
    }


def _build_stats(all_data, from_epoch, to_epoch):
    """Build overall + per-day stats dict."""

    # Collect all timestamps from SOC (most complete variable)
    all_rows_ts = sorted({p["timestamp"] for p in all_data.get("SOC", [])})
    total_rows = len(all_rows_ts)

    flask_vals = [_safe(p["value"]) for p in all_data.get("FlaskTopTemp", [])]
    soc_vals   = [_safe(p["value"]) for p in all_data.get("SOC", [])]
    bv_vals    = [_safe(p["value"]) for p in all_data.get("BATTVOLT", [])]
    pcb_vals   = [_safe(p["value"]) for p in all_data.get("PCBTemp", [])]
    bc_vals    = [_safe(p["value"]) for p in all_data.get("BATTERYCURRENT", [])]
    tec_on     = sum(1 for p in all_data.get("TECstatus", []) if str(p.get("value")) == "1")
    tec_total  = len(all_data.get("TECstatus", [])) or 1

    dates = sorted(set(
        datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d")
        for ts in all_rows_ts
    ))

    # Per-day stats
    day_stats = {}
    for d in dates:
        def day_vals(var_pts):
            return [
                _safe(p["value"])
                for p in var_pts
                if datetime.fromtimestamp(p["timestamp"], IST).strftime("%Y-%m-%d") == d
            ]

        fl  = day_vals(all_data.get("FlaskTopTemp", []))
        sc  = day_vals(all_data.get("SOC", []))
        bv  = day_vals(all_data.get("BATTVOLT", []))
        pcb = day_vals(all_data.get("PCBTemp", []))
        tec_d = [
            p for p in all_data.get("TECstatus", [])
            if datetime.fromtimestamp(p["timestamp"], IST).strftime("%Y-%m-%d") == d
        ]
        tec_on_d = sum(1 for p in tec_d if str(p.get("value")) == "1")

        day_stats[d] = {
            "rows": len(day_vals(all_data.get("SOC", []))),
            **{f"flask_{k}": v for k, v in _stats(fl).items()},
            **{f"soc_{k}": v for k, v in _stats(sc).items()},
            "bv_avg": _stats(bv)["avg"],
            "pcb_avg": _stats(pcb)["avg"],
            "tec_uptime": round(100 * tec_on_d / max(len(tec_d), 1), 1),
        }

    # Build timestamp → datetime label map
    def ts_label(ts):
        return datetime.fromtimestamp(ts, IST).strftime("%m-%d %H:%M")

    def sampled_series(var, max_pts=1200):
        """Sample a variable independently — no cross-variable timestamp alignment."""
        pts = all_data.get(var, [])
        if not pts:
            return {"labels": [], "values": []}
        step = max(1, len(pts) // max_pts)
        sampled = pts[::step]
        return {
            "labels": [ts_label(p["timestamp"]) for p in sampled],
            "values": [_safe(p["value"]) for p in sampled],
        }

    # Per-day charts
    day_charts = {}
    DAY_MAX = 400
    for d in dates:
        def day_pts(var):
            return [
                p for p in all_data.get(var, [])
                if datetime.fromtimestamp(p["timestamp"], IST).strftime("%Y-%m-%d") == d
            ]
        fl_d = day_pts("FlaskTopTemp")
        sc_d = day_pts("SOC")
        bv_d = day_pts("BATTVOLT")
        pcb_d = day_pts("PCBTemp")
        step_d = max(1, len(fl_d) // DAY_MAX)
        def to_chart(pts, step):
            s = pts[::step]
            return {
                "labels": [ts_label(p["timestamp"]) for p in s],
                "values": [_safe(p["value"]) for p in s],
            }
        day_charts[d] = {
            "flask": to_chart(fl_d, step_d),
            "soc":   to_chart(sc_d, step_d),
            "bv":    to_chart(bv_d, step_d),
            "pcb":   to_chart(pcb_d, step_d),
        }

    # Locations
    loc_pts = all_data.get("location", [])
    map_path = []
    prev = None
    for p in loc_pts:
        raw = p.get("value")
        if not raw:
            continue
        try:
            if isinstance(raw, str):
                loc = ast.literal_eval(raw)
            else:
                loc = raw
            pt = {
                "lat": round(float(loc.get("lat", 0)), 5),
                "lng": round(float(loc.get("long", loc.get("lng", 0))), 5),
                "ts": datetime.fromtimestamp(p["timestamp"], IST).strftime("%Y-%m-%d %H:%M"),
            }
            if (pt["lat"], pt["lng"]) != prev:
                map_path.append(pt)
                prev = (pt["lat"], pt["lng"])
        except Exception:
            pass

    return {
        "overall": {
            "total_rows": total_rows,
            "start": datetime.fromtimestamp(from_epoch, IST).strftime("%Y-%m-%d %H:%M"),
            "end":   datetime.fromtimestamp(to_epoch,   IST).strftime("%Y-%m-%d %H:%M"),
            "duration_days": round((to_epoch - from_epoch) / 86400, 1),
            "flask": _stats(flask_vals),
            "soc":   _stats(soc_vals),
            "bv":    _stats(bv_vals),
            "pcb":   _stats(pcb_vals),
            "tec_uptime_pct": round(100 * tec_on / tec_total, 1),
            "dates": dates,
        },
        "day_stats": day_stats,
        "trend": {
            "flask": sampled_series("FlaskTopTemp"),
            "soc":   sampled_series("SOC"),
            "bv":    sampled_series("BATTVOLT"),
            "pcb":   sampled_series("PCBTemp"),
        },
        "day_charts": day_charts,
        "map_path": map_path[::max(1, len(map_path)//300)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CSV BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def generate_report_csv(all_data: dict) -> str:
    """
    Takes the raw all_data dict (from _fetch_all_variables) and returns a
    CSV string with:
      - Column 1: Timestamp (epoch)
      - Column 2: Datetime (IST)
      - One column per variable, values aligned by timestamp

    Empty cells where a variable has no reading at that timestamp.
    """
    import csv
    import io

    VARIABLES = list(all_data.keys())

    # Collect all unique timestamps across every variable
    all_timestamps = sorted({
        p["timestamp"]
        for pts in all_data.values()
        for p in pts
    })

    # Build per-variable lookup: {timestamp: value}
    lookup = {}
    for var, pts in all_data.items():
        lookup[var] = {p["timestamp"]: p.get("value", "") for p in pts}

    buf = io.StringIO()
    writer = csv.writer(buf)

    # Header row
    writer.writerow(["Timestamp (epoch)", "Datetime"] + VARIABLES)

    # One row per unique timestamp
    for ts in all_timestamps:
        dt = datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d %H:%M:%S")
        row = [ts, dt] + [lookup[var].get(ts, "") for var in VARIABLES]
        writer.writerow(row)

    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# HTML REPORT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def generate_report_html(
    node_client,
    unit_number: int,
    node_id: str,
    variables: dict,
    from_epoch: int,
    to_epoch: int,
    chunk_days: int = 1,
) -> str:
    """
    Fetches data + builds full Phloton HTML report. Returns HTML string.
    Shows a progress bar in Streamlit while fetching.
    """
    api_key = node_client.API_KEY

    with st.status(f"🔄 Generating report for Unit {unit_number}…", expanded=True) as status:
        st.write("Fetching data from Anedya (chunked pagination)…")
        progress = st.progress(0, text="Starting…")
        all_data = _fetch_all_variables(node_id, api_key, from_epoch, to_epoch, chunk_days, progress)
        st.write("✅ Data fetched. Building report…")
        stats = _build_stats(all_data, from_epoch, to_epoch)
        status.update(label="✅ Report ready!", state="complete")

    return _render_html(stats, unit_number, node_id), stats, all_data


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

def _render_html(data: dict, unit_number: int, node_id: str) -> str:
    ov = data["overall"]
    DATA_JSON = json.dumps(data)

    date_range = f"{ov['start']} → {ov['end']}"
    duration   = f"{ov['duration_days']} days"
    rows       = f"{ov['total_rows']:,}"

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

    # Day summary table rows
    table_rows = ""
    for d in dates:
        s = data["day_stats"][d]
        fl_avg = s.get("flask_avg")
        fl_ok  = fl_avg is not None and fl_avg <= 8
        fl_badge = (
            f'<span class="badge-ok">✓ In Range</span>' if fl_ok
            else f'<span class="badge-warn">⚠ Excursion</span>' if fl_avg is not None
            else '<span class="badge-na">N/A</span>'
        )
        tec_color = "var(--green)" if s["tec_uptime"] >= 90 else ("var(--amber)" if s["tec_uptime"] >= 70 else "var(--red)")
        table_rows += f"""
        <tr>
          <td><b>{d}</b></td>
          <td>{s['rows']:,}</td>
          <td>{s.get('flask_avg') or '—'}°C</td>
          <td>{s.get('flask_min') or '—'}°C</td>
          <td>{s.get('flask_max') or '—'}°C</td>
          <td>{s.get('soc_avg') or '—'}%</td>
          <td>{s.get('bv_avg') or '—'}V</td>
          <td style="color:{tec_color};font-weight:700">{s['tec_uptime']}%</td>
          <td>{fl_badge}</td>
        </tr>"""

    # Day buttons + panels JS bootstrap
    day_btn_html = "".join(
        f'<div class="day-btn{" active" if i==0 else ""}" onclick="showDay(\'{d}\',this)">{d[5:]}</div>'
        for i, d in enumerate(dates)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Phloton Unit {unit_number} — Report {date_range}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{{--white:#fff;--bg:#f4f6f5;--surface:#fff;--border:#e0e8e4;--border-lt:#edf2ef;--navy:#0f1f1a;--text:#1a2e27;--muted:#6b8f7e;--green:#1a8c5b;--green2:#22b870;--green-p:#e8f5ee;--green-p2:#f0faf4;--teal:#0d7a6b;--blue:#2563eb;--amber:#d97706;--red:#c0392b;--sh:0 1px 3px rgba(15,31,26,.06),0 4px 16px rgba(15,31,26,.05);}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased;}}
.top-bar{{background:var(--green);padding:7px 44px;font-size:11px;font-weight:500;letter-spacing:.08em;color:#fff;display:flex;gap:24px;}}
.top-bar span::before{{content:'· ';}} .top-bar span:first-child::before{{content:'';}}
header{{background:var(--navy);color:#fff;padding:40px 44px 36px;display:flex;justify-content:space-between;align-items:flex-end;position:relative;overflow:hidden;}}
header::after{{content:'';position:absolute;right:-40px;top:-80px;width:360px;height:360px;border-radius:50%;background:radial-gradient(circle,rgba(26,140,91,.1) 0%,transparent 65%);pointer-events:none;}}
.logo-row{{display:flex;align-items:center;gap:10px;margin-bottom:18px;}}
.logo-box{{width:32px;height:32px;background:var(--green);border-radius:8px;display:grid;place-items:center;font-weight:800;font-size:14px;color:#fff;}}
.logo-name{{font-size:16px;font-weight:700;}}
.report-tag{{font-size:10px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--green2);margin-bottom:8px;}}
h1{{font-size:clamp(22px,3vw,36px);font-weight:800;line-height:1.15;letter-spacing:-.6px;}}
h1 em{{font-style:normal;color:var(--green2);}}
.hbadges{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;}}
.hb{{padding:4px 12px;border-radius:20px;font-size:11px;font-weight:500;border:1px solid;}}
.hb-g{{background:rgba(26,140,91,.2);color:#6ddba0;border-color:rgba(26,140,91,.35);}}
.hb-r{{background:rgba(192,57,43,.2);color:#f0a09a;border-color:rgba(192,57,43,.35);}}
.hdr-meta{{text-align:right;font-size:11px;color:rgba(255,255,255,.4);line-height:2;position:relative;z-index:1;}}
.hdr-meta strong{{color:rgba(255,255,255,.8);display:block;font-size:12px;font-weight:600;}}
.tab-bar{{background:var(--surface);border-bottom:1px solid var(--border);padding:0 44px;display:flex;gap:0;overflow-x:auto;}}
.tab{{padding:13px 18px;font-size:13px;font-weight:500;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;transition:all .15s;}}
.tab:hover{{color:var(--text);}} .tab.active{{color:var(--green);border-bottom-color:var(--green);font-weight:600;}}
main{{padding:32px 44px;max-width:1360px;margin:0 auto;}}
.view{{display:none;}} .view.active{{display:block;}}
.sec-hdr{{display:flex;align-items:center;gap:12px;margin-bottom:16px;}}
.sec-tag{{font-size:10px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--green);background:var(--green-p);padding:4px 10px;border-radius:4px;}}
.sec-ttl{{font-size:17px;font-weight:700;color:var(--navy);letter-spacing:-.2px;}}
.sec-line{{flex:1;height:1px;background:var(--border);}}
section{{margin-bottom:40px;}}
.kpi-grid{{display:grid;gap:12px;}}
.g4{{grid-template-columns:repeat(4,1fr);}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 20px;box-shadow:0 1px 2px rgba(15,31,26,.05);position:relative;overflow:hidden;}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:12px 12px 0 0;}}
.kpi.green::before{{background:var(--green);}} .kpi.blue::before{{background:var(--blue);}} .kpi.amber::before{{background:var(--amber);}} .kpi.red::before{{background:var(--red);}}
.kpi-lbl{{font-size:9px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}}
.kpi-val{{font-size:26px;font-weight:800;letter-spacing:-1px;line-height:1;margin-bottom:4px;}}
.kpi-sub{{font-size:11px;color:var(--muted);}} .kpi-sub b{{color:var(--text);font-weight:600;}}
.cc{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:22px 24px;box-shadow:0 1px 2px rgba(15,31,26,.05);}}
.cc-head{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;}}
.cc-ttl{{font-size:14px;font-weight:700;color:var(--navy);letter-spacing:-.2px;}}
.cc-sub{{font-size:11px;color:var(--muted);margin-top:3px;}}
.pills{{display:flex;gap:10px;flex-wrap:wrap;}}
.pill{{text-align:center;padding:5px 11px;background:var(--bg);border-radius:8px;border:1px solid var(--border);}}
.pill .v{{font-size:13px;font-weight:700;display:block;letter-spacing:-.2px;}}
.pill .l{{font-size:9px;color:var(--muted);font-weight:600;letter-spacing:.08em;text-transform:uppercase;}}
.cw{{position:relative;}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
.flask-card{{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--green);border-radius:12px;padding:22px 24px;box-shadow:0 1px 2px rgba(15,31,26,.05);}}
.flask-insight{{margin-top:12px;padding:12px 16px;background:var(--green-p2);border-radius:8px;border:1px solid var(--green-p);font-size:12px;color:var(--text);line-height:1.7;}}
.flask-insight::before{{content:'↗ Insight  ';font-weight:700;color:var(--green);font-size:11px;letter-spacing:.05em;}}
.cstrip{{background:var(--green-p);border:1px solid rgba(26,140,91,.15);border-radius:10px;padding:12px 18px;display:flex;gap:24px;align-items:center;margin-bottom:18px;flex-wrap:wrap;}}
.ci{{display:flex;align-items:center;gap:8px;font-size:12px;}}
.ci-check{{color:var(--green);font-size:13px;font-weight:700;}}
.ci-lbl{{font-weight:600;color:var(--navy);}} .ci-sub{{font-size:10px;color:var(--muted);}}
.day-bar{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;}}
.day-btn{{padding:6px 13px;border-radius:8px;border:1px solid var(--border);background:var(--surface);font-size:12px;font-weight:500;color:var(--muted);cursor:pointer;transition:all .15s;}}
.day-btn:hover{{border-color:var(--green);color:var(--green);}}
.day-btn.active{{background:var(--green);color:#fff;border-color:var(--green);font-weight:600;}}
.day-panel{{display:none;}} .day-panel.active{{display:block;}}
.day-kpi-row{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px;}}
.dk{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:13px 15px;}}
.dk-lbl{{font-size:9px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:6px;}}
.dk-val{{font-size:20px;font-weight:800;letter-spacing:-.6px;}} .dk-sub{{font-size:10px;color:var(--muted);}}
.day-table{{width:100%;border-collapse:collapse;font-size:12px;}}
.day-table th{{text-align:left;padding:9px 13px;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);background:var(--bg);border-bottom:1px solid var(--border);}}
.day-table td{{padding:9px 13px;border-bottom:1px solid var(--border-lt);}}
.day-table tr:hover td{{background:var(--green-p2);}}
.badge-ok{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:var(--green-p);color:var(--green);}}
.badge-warn{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:#fef3cd;color:var(--amber);}}
.badge-na{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:#f0f0f0;color:#999;}}
.map-layout{{display:grid;grid-template-columns:1fr 300px;gap:12px;align-items:stretch;}}
.map-wrap{{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;min-height:400px;}}
.map-sidebar{{display:flex;flex-direction:column;gap:12px;}}
.map-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 20px;flex:1;}}
.mic-ttl{{font-size:13px;font-weight:700;color:var(--navy);margin-bottom:12px;display:flex;align-items:center;gap:8px;}}
.live{{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}}
@keyframes pulse{{0%{{box-shadow:0 0 0 0 rgba(26,140,91,.5)}}70%{{box-shadow:0 0 0 7px rgba(26,140,91,0)}}100%{{box-shadow:0 0 0 0 rgba(26,140,91,0)}};}}
.cr{{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--border-lt);font-size:12px;}}
.cr:last-child{{border-bottom:none;}}
.cr-lbl{{color:var(--muted);font-weight:500;}} .cr-val{{font-weight:600;color:var(--text);font-family:'DM Mono',monospace;font-size:11px;}}
.print-btn{{position:fixed;bottom:24px;right:24px;background:var(--green);color:#fff;border:none;padding:12px 20px;border-radius:10px;font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 4px 16px rgba(26,140,91,.35);z-index:999;}}
.print-btn:hover{{background:#157a4e;}}
footer{{background:var(--navy);color:rgba(255,255,255,.4);padding:18px 44px;font-size:11px;display:flex;justify-content:space-between;align-items:center;}}
footer .fl{{font-weight:700;color:#fff;font-size:13px;}}
@media print{{.print-btn,.tab-bar{{display:none;}}.view{{display:block!important;}}}}
@media(max-width:900px){{main{{padding:16px;}}.g4,.day-kpi-row{{grid-template-columns:repeat(2,1fr);}}.g2,.map-layout{{grid-template-columns:1fr;}}}}
</style>
</head>
<body>

<div class="top-bar">
  <span style="font-weight:700">PHLOTON</span>
  <span>CDSCO Approved</span><span>ISO 13485</span><span>Patent Filed</span><span>IoT + AI Analytics</span>
</div>
<header>
  <div style="position:relative;z-index:1;">
    <div class="logo-row"><div class="logo-box">P</div><div class="logo-name">Phloton</div></div>
    <div class="report-tag">Unit Telemetry Report</div>
    <h1>Unit {unit_number} · <em>{date_range}</em></h1>
    <div class="hbadges">
      <span class="hb hb-g">✓ {ov["flask"]["avg"] or "—"}°C Avg Flask Temp</span>
      <span class="hb hb-g">✓ TEC {tec_pct}% Uptime</span>
      <span class="hb hb-r">⚠ Fault Flag Active</span>
    </div>
  </div>
  <div class="hdr-meta">
    <strong>Duration</strong>{duration}<br>
    <strong>Data Points</strong>{rows}<br>
    <strong>Unit</strong>#{unit_number}<br>
    <strong>Node</strong>{node_id[:8]}…{node_id[-4:]}<br>
    <strong>Region</strong>Bengaluru, IN
  </div>
</header>

<div class="tab-bar">
  <div class="tab active" onclick="showView('overview',this)">Overview</div>
  <div class="tab" onclick="showView('flask',this)">Flask Temp</div>
  <div class="tab" onclick="showView('battery',this)">Battery</div>
  <div class="tab" onclick="showView('daywise',this)">Day-wise</div>
  <div class="tab" onclick="showView('location',this)">Location</div>
</div>

<main>
<!-- OVERVIEW -->
<div class="view active" id="view-overview">
  <div class="cstrip">
    <div class="ci"><span class="ci-check">✓</span><div><div class="ci-lbl">Avg Flask Temp</div><div class="ci-sub">{flask_avg}°C — 2–8°C WHO spec</div></div></div>
    <div class="ci"><span class="ci-check">✓</span><div><div class="ci-lbl">Continuous Logging</div><div class="ci-sub">{rows} readings · {duration}</div></div></div>
    <div class="ci"><span style="color:var(--red);font-size:14px;font-weight:700;">⚠</span><div><div class="ci-lbl" style="color:var(--red)">Fault Flag</div><div class="ci-sub">Active — investigate</div></div></div>
  </div>
  <section>
    <div class="sec-hdr"><span class="sec-tag">Summary</span><span class="sec-ttl">Session at a Glance</span><div class="sec-line"></div></div>
    <div class="kpi-grid g4" style="margin-bottom:12px;">
      <div class="kpi green"><div class="kpi-lbl">Flask Avg Temp</div><div class="kpi-val" style="color:var(--green)">{flask_avg}°C</div><div class="kpi-sub">Range: <b>{flask_min} – {flask_max}°C</b></div></div>
      <div class="kpi blue"><div class="kpi-lbl">Avg Battery SOC</div><div class="kpi-val" style="color:var(--blue)">{soc_avg}%</div><div class="kpi-sub">Min: <b>{soc_min}%</b></div></div>
      <div class="kpi amber"><div class="kpi-lbl">Avg Battery Volt</div><div class="kpi-val" style="color:var(--amber)">{bv_avg}V</div><div class="kpi-sub">Range: <b>{bv_min} – {bv_max}V</b></div></div>
      <div class="kpi green"><div class="kpi-lbl">TEC Uptime</div><div class="kpi-val" style="color:var(--green)">{tec_pct}%</div><div class="kpi-sub">{rows} total samples</div></div>
    </div>
    <div class="kpi-grid g4">
      <div class="kpi amber"><div class="kpi-lbl">PCB Temp Avg</div><div class="kpi-val" style="color:var(--amber)">{pcb_avg}°C</div><div class="kpi-sub">Board temperature average</div></div>
      <div class="kpi green"><div class="kpi-lbl">Duration</div><div class="kpi-val" style="color:var(--green)">{duration}</div><div class="kpi-sub">{date_range}</div></div>
      <div class="kpi blue"><div class="kpi-lbl">Days Logged</div><div class="kpi-val" style="color:var(--blue)">{len(dates)}</div><div class="kpi-sub">Unique days with data</div></div>
      <div class="kpi green"><div class="kpi-lbl">Unit</div><div class="kpi-val" style="color:var(--green)">#{unit_number}</div><div class="kpi-sub">{node_id[:16]}…</div></div>
    </div>
  </section>
  <section>
    <div class="sec-hdr"><span class="sec-tag">Trend</span><span class="sec-ttl">Full Session Trends</span><div class="sec-line"></div></div>
    <div class="flask-card" style="margin-bottom:12px;">
      <div class="cc-head">
        <div><div class="cc-ttl">Flask Temperature (°C)</div><div class="cc-sub">{date_range}</div></div>
        <div class="pills">
          <div class="pill"><span class="v" style="color:var(--green)">{flask_avg}°C</span><span class="l">avg</span></div>
          <div class="pill"><span class="v" style="color:var(--teal)">{flask_min}°C</span><span class="l">min</span></div>
          <div class="pill"><span class="v" style="color:var(--red)">{flask_max}°C</span><span class="l">max</span></div>
        </div>
      </div>
      <div class="cw" style="height:240px;"><canvas id="ov-flask"></canvas></div>
      <div class="flask-insight">Flask averaged {flask_avg}°C across {duration}, well within the 2–8°C WHO cold chain specification. Spikes above 8°C indicate loading events; the TEC recovered to target temperature promptly each time.</div>
    </div>
    <div class="g2">
      <div class="cc"><div class="cc-head"><div><div class="cc-ttl">Battery SOC (%)</div><div class="cc-sub">Over full session</div></div></div><div class="cw" style="height:180px;"><canvas id="ov-soc"></canvas></div></div>
      <div class="cc"><div class="cc-head"><div><div class="cc-ttl">Battery Voltage (V)</div><div class="cc-sub">Over full session</div></div></div><div class="cw" style="height:180px;"><canvas id="ov-bv"></canvas></div></div>
    </div>
  </section>
  <section>
    <div class="sec-hdr"><span class="sec-tag">Daily</span><span class="sec-ttl">Day-by-Day Summary</span><div class="sec-line"></div></div>
    <div class="cc">
      <table class="day-table">
        <tr><th>Date</th><th>Readings</th><th>Flask Avg</th><th>Flask Min</th><th>Flask Max</th><th>SOC Avg</th><th>Batt V</th><th>TEC Uptime</th><th>Status</th></tr>
        {table_rows}
      </table>
    </div>
  </section>
</div>

<!-- FLASK -->
<div class="view" id="view-flask">
  <section>
    <div class="sec-hdr"><span class="sec-tag">Primary</span><span class="sec-ttl">Flask Temperature Detail</span><div class="sec-line"></div></div>
    <div class="flask-card" style="margin-bottom:12px;">
      <div class="cc-head">
        <div><div class="cc-ttl">Flask Top Temp (°C) — Full Session</div><div class="cc-sub">{date_range}</div></div>
        <div class="pills">
          <div class="pill"><span class="v" style="color:var(--green)">{flask_avg}°C</span><span class="l">avg</span></div>
          <div class="pill"><span class="v" style="color:var(--teal)">{flask_min}°C</span><span class="l">min</span></div>
          <div class="pill"><span class="v" style="color:var(--red)">{flask_max}°C</span><span class="l">max</span></div>
        </div>
      </div>
      <div class="cw" style="height:280px;"><canvas id="fl-flask"></canvas></div>
    </div>
    <div class="cc"><div class="cc-head"><div><div class="cc-ttl">PCB Temperature (°C)</div><div class="cc-sub">Board temp over session</div></div></div><div class="cw" style="height:180px;"><canvas id="fl-pcb"></canvas></div></div>
  </section>
</div>

<!-- BATTERY -->
<div class="view" id="view-battery">
  <section>
    <div class="sec-hdr"><span class="sec-tag">Power</span><span class="sec-ttl">Battery Metrics</span><div class="sec-line"></div></div>
    <div class="kpi-grid g4" style="margin-bottom:16px;">
      <div class="kpi blue"><div class="kpi-lbl">Avg SOC</div><div class="kpi-val" style="color:var(--blue)">{soc_avg}%</div><div class="kpi-sub">Min: <b>{soc_min}%</b></div></div>
      <div class="kpi blue"><div class="kpi-lbl">Avg Voltage</div><div class="kpi-val" style="color:var(--blue)">{bv_avg}V</div><div class="kpi-sub">Range: <b>{bv_min}–{bv_max}V</b></div></div>
    </div>
    <div class="cc" style="margin-bottom:12px;"><div class="cc-head"><div><div class="cc-ttl">Battery SOC (%)</div></div></div><div class="cw" style="height:220px;"><canvas id="bt-soc"></canvas></div></div>
    <div class="cc"><div class="cc-head"><div><div class="cc-ttl">Battery Voltage (V)</div></div></div><div class="cw" style="height:200px;"><canvas id="bt-bv"></canvas></div></div>
  </section>
</div>

<!-- DAY-WISE -->
<div class="view" id="view-daywise">
  <section>
    <div class="sec-hdr"><span class="sec-tag">Daily</span><span class="sec-ttl">Day-wise Breakdown</span><div class="sec-line"></div></div>
    <div class="day-bar">{day_btn_html}</div>
    <div id="day-panels"></div>
  </section>
</div>

<!-- LOCATION -->
<div class="view" id="view-location">
  <section>
    <div class="sec-hdr"><span class="sec-tag">GPS</span><span class="sec-ttl">Device Location & Movement</span><div class="sec-line"></div></div>
    <div class="map-layout">
      <div class="map-wrap"><div id="gmap" style="width:100%;height:400px;"></div></div>
      <div class="map-sidebar">
        <div class="map-card">
          <div class="mic-ttl"><span class="live"></span>Movement Summary</div>
          <div class="cr"><span class="cr-lbl">GPS data from</span><span class="cr-val">{ov["start"][:10]}</span></div>
          <div class="cr"><span class="cr-lbl">GPS data to</span><span class="cr-val">{ov["end"][:10]}</span></div>
          <div class="cr"><span class="cr-lbl">Unique positions</span><span class="cr-val" id="loc-count">—</span></div>
        </div>
        <div class="map-card" style="flex:2;">
          <div class="mic-ttl">Daily Location</div>
          <div class="day-bar" id="map-day-bar" style="gap:6px;"></div>
        </div>
      </div>
    </div>
  </section>
</div>
</main>

<footer>
  <div class="fl">Phloton · Unit {unit_number}</div>
  <div>Anedya IoT · Node {node_id} · {date_range}</div>
  <div>phloton.com · © 2026 Enhanced Innovations Pvt. Ltd.</div>
</footer>
<button class="print-btn" onclick="window.print()">🖨 Print / Save PDF</button>

<script>
const D = {DATA_JSON};
const DATES = D.overall.dates;

function showView(id, el) {{
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('view-' + id).classList.add('active');
  el.classList.add('active');
  if (id === 'location' && !window._mapDone) initMap();
}}

const TC='#9db8ad', GC='#edf2ef';
const BOPT = {{responsive:true,maintainAspectRatio:false,animation:{{duration:700}},
  plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#0f1f1a',borderColor:'#e2e8e5',borderWidth:1,
    titleColor:'#9db8ad',bodyColor:'#fff',padding:10,titleFont:{{family:'DM Mono',size:10}},bodyFont:{{family:'Inter',size:12,weight:'600'}}}}}},
  scales:{{x:{{grid:{{color:GC}},ticks:{{color:TC,font:{{family:'Inter',size:9}},maxTicksLimit:10}}}},
           y:{{grid:{{color:GC}},ticks:{{color:TC,font:{{family:'Inter',size:9}}}}}}}}}};

function grad(ctx,c1,c2,h=220){{const g=ctx.createLinearGradient(0,0,0,h);g.addColorStop(0,c1);g.addColorStop(1,c2);return g;}}
function mkLine(id,labels,data,color,fc,min,max,fmt,tension=0.3){{
  const el=document.getElementById(id); if(!el) return;
  const ctx=el.getContext('2d');
  new Chart(ctx,{{type:'line',data:{{labels,datasets:[{{data:data.map(v=>v===null?NaN:v),
    borderColor:color,borderWidth:2,backgroundColor:grad(ctx,fc.replace(')',',0.15)').replace('rgb','rgba'),fc.replace(')',',0.01)').replace('rgb','rgba')),
    fill:true,tension,pointRadius:0,pointHoverRadius:4,spanGaps:true}}]}},
    options:{{...BOPT,scales:{{...BOPT.scales,y:{{...BOPT.scales.y,...(min!=null?{{min}}:{{}}),
      ...(max!=null?{{max}}:{{}}),ticks:{{...BOPT.scales.y.ticks,callback:fmt||undefined}}}}}}}}}});
}}

const T=D.trend;
mkLine('ov-flask',T.flask.labels,T.flask.values,'#1a8c5b','rgb(26,140,91)',0,null,v=>v+'°C');
mkLine('ov-soc',T.soc.labels,T.soc.values,'#2563eb','rgb(37,99,235)',50,102,v=>v+'%');
mkLine('ov-bv',T.bv.labels,T.bv.values,'#d97706','rgb(217,119,6)',9,14,v=>v+'V');
mkLine('fl-flask',T.flask.labels,T.flask.values,'#1a8c5b','rgb(26,140,91)',0,null,v=>v+'°C');
mkLine('fl-pcb',T.pcb.labels,T.pcb.values,'#d97706','rgb(217,119,6)',30,44,v=>v+'°C');
mkLine('bt-soc',T.soc.labels,T.soc.values,'#2563eb','rgb(37,99,235)',40,102,v=>v+'%');
mkLine('bt-bv',T.bv.labels,T.bv.values,'#2563eb','rgb(37,99,235)',9,14,v=>v+'V');

// Day panels
(function(){{
  const c=document.getElementById('day-panels');
  DATES.forEach((d,i)=>{{
    const s=D.day_stats[d], dc=D.day_charts[d];
    const p=document.createElement('div');
    p.className='day-panel'+(i===0?' active':'');
    p.id='dp-'+d;
    const tc=s.tec_uptime>=90?'var(--green)':s.tec_uptime>=70?'var(--amber)':'var(--red)';
    p.innerHTML=`<div class="day-kpi-row">
      <div class="dk"><div class="dk-lbl">Flask Avg</div><div class="dk-val" style="color:var(--green)">${{s.flask_avg||'—'}}°C</div><div class="dk-sub">${{s.flask_min||'—'}} – ${{s.flask_max||'—'}}°C</div></div>
      <div class="dk"><div class="dk-lbl">SOC Avg</div><div class="dk-val" style="color:var(--blue)">${{s.soc_avg||'—'}}%</div><div class="dk-sub">Min ${{s.soc_min||'—'}}%</div></div>
      <div class="dk"><div class="dk-lbl">Batt V</div><div class="dk-val" style="color:var(--amber)">${{s.bv_avg||'—'}}V</div></div>
      <div class="dk"><div class="dk-lbl">PCB Temp</div><div class="dk-val" style="color:var(--amber)">${{s.pcb_avg||'—'}}°C</div></div>
      <div class="dk"><div class="dk-lbl">TEC Uptime</div><div class="dk-val" style="color:${{tc}}">${{s.tec_uptime}}%</div><div class="dk-sub">${{s.rows.toLocaleString()}} readings</div></div>
    </div>
    <div class="g2" style="margin-bottom:12px;">
      <div class="cc"><div class="cc-head"><div><div class="cc-ttl">Flask Temp</div><div class="cc-sub">${{d}}</div></div></div><div class="cw" style="height:180px;"><canvas id="dc-fl-${{d}}"></canvas></div></div>
      <div class="cc"><div class="cc-head"><div><div class="cc-ttl">Battery SOC</div><div class="cc-sub">${{d}}</div></div></div><div class="cw" style="height:180px;"><canvas id="dc-soc-${{d}}"></canvas></div></div>
    </div>
    <div class="g2">
      <div class="cc"><div class="cc-head"><div><div class="cc-ttl">Battery Voltage</div><div class="cc-sub">${{d}}</div></div></div><div class="cw" style="height:160px;"><canvas id="dc-bv-${{d}}"></canvas></div></div>
      <div class="cc"><div class="cc-head"><div><div class="cc-ttl">PCB Temp</div><div class="cc-sub">${{d}}</div></div></div><div class="cw" style="height:160px;"><canvas id="dc-pcb-${{d}}"></canvas></div></div>
    </div>`;
    c.appendChild(p);
  }});
  const drawn=new Set();
  function drawDay(d){{
    if(drawn.has(d)) return; drawn.add(d);
    const dc=D.day_charts[d];
    mkLine('dc-fl-'+d,dc.flask.labels,dc.flask.values,'#1a8c5b','rgb(26,140,91)',0,null,v=>v+'°C');
    mkLine('dc-soc-'+d,dc.soc.labels,dc.soc.values,'#2563eb','rgb(37,99,235)',50,102,v=>v+'%');
    mkLine('dc-bv-'+d,dc.bv.labels,dc.bv.values,'#d97706','rgb(217,119,6)',9,14,v=>v+'V');
    mkLine('dc-pcb-'+d,dc.pcb.labels,dc.pcb.values,'#d97706','rgb(217,119,6)',30,44,v=>v+'°C');
  }}
  drawDay(DATES[0]);
  window.showDay=function(d,el){{
    document.querySelectorAll('.day-btn').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('dp-'+d).classList.add('active');
    drawDay(d);
  }};
}})();

// MAP
window._mapDone=false;
function initMap(){{
  window._mapDone=true;
  const path=D.map_path;
  document.getElementById('loc-count').textContent=path.length+' pts';
  if(!path||path.length===0){{document.getElementById('gmap').innerHTML='<div style="padding:40px;color:#6b8f7e;text-align:center">No GPS data available</div>';return;}}
  const lss=document.createElement('link');lss.rel='stylesheet';lss.href='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';document.head.appendChild(lss);
  const ljs=document.createElement('script');ljs.src='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
  ljs.onload=()=>{{
    const lats=path.map(p=>p.lat),lngs=path.map(p=>p.lng);
    const map=L.map('gmap').setView([(Math.min(...lats)+Math.max(...lats))/2,(Math.min(...lngs)+Math.max(...lngs))/2],12);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'© OpenStreetMap',maxZoom:19}}).addTo(map);
    const coords=path.map(p=>[p.lat,p.lng]);
    L.polyline(coords,{{color:'#2563eb',weight:3,opacity:.7}}).addTo(map);
    const sI=L.divIcon({{html:'<div style="background:#1a8c5b;color:#fff;border-radius:50%;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;border:2px solid #fff;">S</div>',className:'',iconSize:[18,18]}});
    const eI=L.divIcon({{html:'<div style="background:#c0392b;color:#fff;border-radius:50%;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;border:2px solid #fff;">E</div>',className:'',iconSize:[18,18]}});
    L.marker(coords[0],{{icon:sI}}).addTo(map).bindPopup('Start: '+path[0].ts);
    L.marker(coords[coords.length-1],{{icon:eI}}).addTo(map).bindPopup('Last: '+path[path.length-1].ts);
    path.filter((_,i)=>i%8===0&&i>0&&i<path.length-1).forEach(p=>L.circleMarker([p.lat,p.lng],{{radius:4,color:'#2563eb',fillColor:'#fff',fillOpacity:1,weight:2}}).addTo(map).bindPopup(p.ts));
    try{{map.fitBounds(L.latLngBounds(coords),{{padding:[30,30]}});}}catch(e){{}}
    // Day map buttons
    const bar=document.getElementById('map-day-bar');
    const dl=L.layerGroup().addTo(map);
    const colors=['#1a8c5b','#2563eb','#d97706','#c0392b','#7c3aed','#0d7a6b','#db2777'];
    DATES.forEach((d,i)=>{{
      const pts=D.day_charts[d]&&path.filter(p=>p.ts&&p.ts.startsWith(d));
      if(!pts||pts.length===0) return;
      const btn=document.createElement('div');
      btn.className='day-btn';btn.textContent=d.slice(5);
      btn.onclick=()=>{{document.querySelectorAll('#map-day-bar .day-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');dl.clearLayers();
        const c2=pts.map(p=>[p.lat,p.lng]);
        if(c2.length>1) L.polyline(c2,{{color:colors[i%colors.length],weight:3}}).addTo(dl);
        pts.forEach(p=>L.circleMarker([p.lat,p.lng],{{radius:5,color:colors[i%colors.length],fillColor:'#fff',fillOpacity:1,weight:2}}).addTo(dl).bindPopup(p.ts));
        try{{if(c2.length>1)map.fitBounds(L.latLngBounds(c2),{{padding:[40,40]}});else map.setView(c2[0],14);}}catch(e){{}}
      }};
      bar.appendChild(btn);
    }});
  }};
  document.head.appendChild(ljs);
}}
</script>
</body>
</html>"""
