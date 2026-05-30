
hide_streamlit_style = """
        <style>
        # div[data-testid="stToolbar"] {
        # visibility: hidden;
        # height: 0%;
        # position: fixed;
        # }
        # div[data-testid="stDecoration"] {
        # visibility: hidden;
        # height: 0%;
        # position: fixed;
        # }
        # div[data-testid="stStatusWidget"] {  //hide streamlit runner
        # visibility: hidden;
        # height: 0%;
        # position: fixed;
        }
        # #MainMenu {
        # visibility: hidden;
        # height: 0%;
        # # }
        # header {
        # visibility: hidden;
        # height: 0%;
        # }
        # footer {
        # visibility: hidden;
        # height: 0%;
        # }

        /* ── Fix streamviz gauge text colour in dark mode ── */
[data-testid="stHtml"] text,
[data-testid="stHtml"] .gauge-text,
[data-testid="stHtml"] svg text {
    fill: #e8f5ee !important;
    color: #e8f5ee !important;
}

/* Fix all SVG text elements inside Streamlit components */
.stApp svg text {
    fill: #e8f5ee !important;
}

/* Fix the number value text specifically */
.stApp svg .value-text,
.stApp svg tspan {
    fill: #e8f5ee !important;
}

/* Fix label text under gauges */
[data-testid="stVerticalBlock"] p,
[data-testid="column"] p {
    color: #e8f5ee !important;
}


        </style>
        """
