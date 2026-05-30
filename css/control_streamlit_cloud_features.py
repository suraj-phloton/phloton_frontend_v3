"""
Phloton — global CSS overlay.

Imports Inter, defines design tokens, hides Streamlit's default chrome,
and styles widgets / cards / sidebar to match the app.phloton.com
look-and-feel.
"""

hide_streamlit_style = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">

<style>
/* ──────────────────────────────────────────────────────────────────────── */
/*  DESIGN TOKENS                                                           */
/* ──────────────────────────────────────────────────────────────────────── */
:root {
  --teal:        #00C9A7;
  --teal-dark:   #00A88A;
  --teal-glow:   rgba(0, 201, 167, 0.18);

  --navy:        #0A1628;
  --navy-light:  #12203A;
  --navy-mid:    #1B2D4D;
  --navy-line:   rgba(255, 255, 255, 0.08);
  --navy-line-2: rgba(255, 255, 255, 0.04);

  --text:        #F0F4F8;
  --text-dim:    #9FB3C8;
  --text-mute:   #627D98;

  --ok:          #00C9A7;
  --warn:        #F59E0B;
  --bad:         #F43F5E;

  --radius:      12px;
  --radius-sm:   8px;
  --shadow-1:    0 4px 12px rgba(0,0,0,0.18);
  --shadow-2:    0 12px 32px rgba(0,0,0,0.32);

  --font-sans:   "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-display:"Space Grotesk", "Inter", sans-serif;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  GLOBAL                                                                  */
/* ──────────────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
  font-family: var(--font-sans) !important;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "ss01", "cv11";
  letter-spacing: -0.01em;
}

.stApp {
  background:
    radial-gradient(ellipse 90% 60% at 50% -10%, rgba(0,201,167,0.06), transparent 70%),
    var(--navy);
}

/* Display headings use Space Grotesk like the marketing site */
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: var(--font-display) !important;
  font-weight: 700;
  letter-spacing: -0.02em;
}
h1 { font-size: 2rem;   line-height: 1.15; }
h2 { font-size: 1.4rem; line-height: 1.2;  }
h3 { font-size: 1.1rem; line-height: 1.25; }

p, .stMarkdown p, span, label, div {
  color: var(--text);
}
small, .stCaption {
  color: var(--text-dim) !important;
}

/* Tighter content padding on wide layouts */
.block-container {
  padding-top: 1.5rem;
  padding-bottom: 4rem;
  max-width: 1280px;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  HIDE STREAMLIT DEFAULT CHROME                                           */
/* ──────────────────────────────────────────────────────────────────────── */
#MainMenu,
header[data-testid="stHeader"],
footer,
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"] {
  visibility: hidden !important;
  height: 0 !important;
  position: fixed !important;
}

/* Reclaim the empty header strip */
[data-testid="stAppViewContainer"] > .main {
  padding-top: 0;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  SIDEBAR                                                                 */
/* ──────────────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--navy-light) !important;
  border-right: 1px solid var(--navy-line);
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
  color: var(--text);
}
[data-testid="stSidebar"] hr {
  border-color: var(--navy-line);
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  CARDS (container with border) + KPI metrics                             */
/* ──────────────────────────────────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--navy-light);
  border: 1px solid var(--navy-line) !important;
  border-radius: var(--radius);
  padding: 1.1rem 1.25rem !important;
  box-shadow: var(--shadow-1);
}

[data-testid="stMetric"] {
  background: var(--navy-light);
  border: 1px solid var(--navy-line);
  border-radius: var(--radius);
  padding: 1rem 1.1rem;
  box-shadow: var(--shadow-1);
}
[data-testid="stMetricLabel"] {
  color: var(--text-dim) !important;
  font-size: 0.72rem !important;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}
[data-testid="stMetricValue"] {
  color: var(--text) !important;
  font-family: var(--font-display) !important;
  font-size: 1.7rem !important;
  font-weight: 700 !important;
}
[data-testid="stMetricDelta"] {
  font-size: 0.8rem !important;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  BUTTONS                                                                 */
/* ──────────────────────────────────────────────────────────────────────── */
.stButton > button,
.stDownloadButton > button {
  background: var(--teal);
  color: var(--navy);
  border: none;
  border-radius: 999px;
  padding: 0.55rem 1.15rem;
  font-weight: 600;
  font-size: 0.88rem;
  letter-spacing: -0.005em;
  transition: transform 0.12s ease, background 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 6px 18px var(--teal-glow);
}
.stButton > button:hover,
.stDownloadButton > button:hover {
  background: var(--teal-dark);
  transform: translateY(-1px);
  box-shadow: 0 10px 24px var(--teal-glow);
}
.stButton > button:active,
.stDownloadButton > button:active {
  transform: translateY(0);
}
.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
}

/* Secondary button — wrap with st.markdown('<div class="secondary-btn">…') */
.secondary-btn .stButton > button {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--navy-line);
  box-shadow: none;
}
.secondary-btn .stButton > button:hover {
  background: var(--navy-mid);
  border-color: var(--teal);
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  INPUTS                                                                  */
/* ──────────────────────────────────────────────────────────────────────── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stDateInput input,
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
  background: var(--navy-light) !important;
  border: 1px solid var(--navy-line) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text) !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.stTextInput input:focus,
.stTextArea textarea:focus,
.stNumberInput input:focus,
[data-baseweb="input"] > div:focus-within,
[data-baseweb="select"] > div:focus-within {
  border-color: var(--teal) !important;
  box-shadow: 0 0 0 3px var(--teal-glow) !important;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  TABS                                                                    */
/* ──────────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.25rem;
  border-bottom: 1px solid var(--navy-line);
}
.stTabs [data-baseweb="tab"] {
  background: transparent;
  color: var(--text-dim);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  padding: 0.6rem 1rem;
  font-weight: 500;
}
.stTabs [aria-selected="true"] {
  color: var(--text);
  background: var(--navy-light);
  border-bottom: 2px solid var(--teal);
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  EXPANDERS                                                               */
/* ──────────────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: var(--navy-light);
  border: 1px solid var(--navy-line);
  border-radius: var(--radius);
}
[data-testid="stExpander"] summary {
  color: var(--text);
  font-weight: 600;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  DIVIDERS, SCROLLBARS, ALERTS                                            */
/* ──────────────────────────────────────────────────────────────────────── */
hr, [data-testid="stHorizontalDivider"] {
  border: none;
  border-top: 1px solid var(--navy-line);
}
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb {
  background: var(--navy-mid);
  border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-mute); }
::-webkit-scrollbar-track { background: transparent; }

[data-testid="stAlert"] {
  border-radius: var(--radius);
  border: 1px solid var(--navy-line);
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  GAUGES (streamviz) — preserve the original colour fix                   */
/* ──────────────────────────────────────────────────────────────────────── */
[data-testid="stHtml"] text,
[data-testid="stHtml"] .gauge-text,
[data-testid="stHtml"] svg text,
.stApp svg text,
.stApp svg .value-text,
.stApp svg tspan {
  fill: var(--text) !important;
  color: var(--text) !important;
}
[data-testid="stVerticalBlock"] p,
[data-testid="column"] p {
  color: var(--text) !important;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  TIGHTEN VERTICAL RHYTHM (lets us drop the V_SPACE &nbsp; hack)          */
/* ──────────────────────────────────────────────────────────────────────── */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
  gap: 0.85rem;
}
.block-container [data-testid="stMarkdownContainer"] p { margin-bottom: 0.4rem; }
</style>
"""
