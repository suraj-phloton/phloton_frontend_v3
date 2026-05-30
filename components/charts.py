"""Charts for the dashboard."""
import streamlit as st
import altair as alt


# Phloton design tokens (kept in sync with css/control_streamlit_cloud_features.py)
PALETTE = {
    "teal":     "#00C9A7",
    "teal_dim": "rgba(0,201,167,0.55)",
    "navy":     "#0A1628",
    "text":     "#F0F4F8",
    "text_dim": "#9FB3C8",
    "grid":     "rgba(255,255,255,0.08)",
}


def _phloton_axis(title, **kw):
    return alt.Axis(
        title=title,
        labelColor=PALETTE["text_dim"],
        titleColor=PALETTE["text_dim"],
        titleFontWeight="normal",
        labelFontSize=10,
        titleFontSize=11,
        domain=False,
        tickColor=PALETTE["grid"],
        gridColor=PALETTE["grid"],
        gridDash=[2, 3],
        **kw,
    )


# ====================== Altair charts ======================

def draw_chart(chart_title: str = None, chart_data=None, y_axis_title: str = None, x_axis_title: str = "Datetime",topRange:int=50,bottomRange:int=0,agg:int=None, aggregate_or_value:str="value"):
    if chart_title:
        st.subheader(chart_title)
    if chart_data is None:
        st.error("No Data Available")
        return
    elif chart_data.empty:
        st.error("No Data Available")
        return

    if chart_data is not None and not chart_data.empty:
        st.markdown(
            f"**Agg**: {agg} min | **Min:** {chart_data[aggregate_or_value].min():.2f} **Max:** {chart_data[aggregate_or_value].max():.2f} **Average:** {chart_data[aggregate_or_value].mean():.2f} "
        )

        
    temperature_chart_an = (
            alt.Chart(data=chart_data)
            .mark_area( # type: ignore
                line={"color": PALETTE["teal"], "strokeWidth": 1.6},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color=PALETTE["teal_dim"], offset=1),
                        alt.GradientStop(color="rgba(0,201,167,0)", offset=0),
                    ],
                    x1=1, x2=1, y1=1, y2=0,
                ),
                interpolate="monotone",
                cursor="crosshair",
            )
            .encode(  # type: ignore
                x=alt.X(
                    shorthand="Datetime:T",
                    axis=_phloton_axis(
                        x_axis_title,
                        format="%Y-%m-%d %H:%M",
                        tickCount=8,
                        tickMinStep=5,
                    ),
                ),
                y=alt.Y(
                    f"{aggregate_or_value}:Q",
                    scale=alt.Scale(zero=False, domain=[bottomRange, topRange]),
                    axis=_phloton_axis(y_axis_title, tickCount=8),
                ),
                tooltip=[
                    alt.Tooltip("Datetime:T", format="%Y-%m-%d %H:%M:%S", title="Time"),
                    alt.Tooltip(f"{aggregate_or_value}:Q", format="0.2f", title=aggregate_or_value),
                ],
            )
            .properties(height=320, background="transparent")
            .configure_view(stroke=None)
            .interactive()
        )  # type: ignore

    st.altair_chart(temperature_chart_an, use_container_width=True)
