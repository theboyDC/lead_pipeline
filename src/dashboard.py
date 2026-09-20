"""Streamlit dashboard for exploring and analyzing leads stored in MongoDB.

Usage:
    streamlit run src/dashboard.py
"""
import sys
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# `streamlit run` executes this file directly (not via `python -m`), so the
# project root isn't on sys.path by default. Add it so `from src...` works
# regardless of the working directory this is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_collection  # noqa: E402
from src.export import flatten_record  # noqa: E402

REFRESH_INTERVAL_SECONDS = 30

# Dark, minimal palette — validated categorical/status steps from the shared
# data-viz reference palette (dark-surface column), not eyeballed.
PAGE = "#0d0d0d"
SURFACE = "#1a1a19"
INK_PRIMARY = "#ffffff"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRIDLINE = "#2c2c2a"
BASELINE = "#383835"
ACCENT = "#3987e5"  # categorical slot 1, dark

STATUS_OPTIONS = ["new", "contacted", "qualified", "rejected"]
STATUS_COLORS = {
    "new": INK_MUTED,
    "contacted": ACCENT,
    "qualified": "#0ca30c",  # status: good (dark)
    "rejected": "#d03b3b",  # status: critical (dark)
}

CSS = f"""
<style>
html, body, [class*="css"] {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}}
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{
    padding-top: 2.5rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}}
[data-testid="stSidebar"] {{
    background: {PAGE};
    border-right: 1px solid {GRIDLINE};
}}
[data-testid="stSidebar"] .stSlider, [data-testid="stSidebar"] .stMultiSelect,
[data-testid="stSidebar"] .stTextInput {{
    padding-bottom: 4px;
}}
.app-header {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 2px;
}}
.app-title {{
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: {INK_PRIMARY};
}}
.live-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {INK_MUTED};
}}
.live-dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #0ca30c;
    animation: pulse 2s infinite;
}}
@keyframes pulse {{
    0% {{ box-shadow: 0 0 0 0 rgba(12, 163, 12, 0.45); }}
    70% {{ box-shadow: 0 0 0 6px rgba(12, 163, 12, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(12, 163, 12, 0); }}
}}
.kpi-ticker {{
    display: flex;
    border-top: 1px solid {GRIDLINE};
    border-bottom: 1px solid {GRIDLINE};
    margin: 20px 0 32px 0;
}}
.kpi-cell {{
    flex: 1;
    padding: 18px 24px;
    border-right: 1px solid {GRIDLINE};
}}
.kpi-cell:last-child {{ border-right: none; }}
.kpi-value {{
    font-size: 32px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: {INK_PRIMARY};
    line-height: 1.1;
}}
.kpi-label {{
    margin-top: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {INK_MUTED};
}}
.eyebrow {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {INK_MUTED};
    border-bottom: 1px solid {ACCENT};
    display: inline-block;
    padding-bottom: 4px;
    margin: 8px 0 16px 0;
}}
</style>
"""


@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS)
def load_leads() -> pd.DataFrame:
    records = list(get_collection().find({}))
    rows = [flatten_record(r) for r in records]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
    df["status"] = df["status"].fillna("new")
    return df


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown('<div class="eyebrow">Filters</div>', unsafe_allow_html=True)
    min_score = st.sidebar.slider("Minimum lead score", 0, 4, 0)
    queries = sorted(df["source_query"].dropna().unique().tolist())
    selected_queries = st.sidebar.multiselect("Source query", queries, default=queries)
    name_search = st.sidebar.text_input("Search by name")

    filtered = df[df["lead_score"] >= min_score]
    if selected_queries:
        filtered = filtered[filtered["source_query"].isin(selected_queries)]
    if name_search:
        filtered = filtered[filtered["name"].str.contains(name_search, case=False, na=False)]
    return filtered


def render_kpis(df: pd.DataFrame) -> None:
    total = len(df)
    cells = [
        ("Leads", str(total)),
        ("Avg. score", f"{df['lead_score'].mean():.1f}" if total else "0.0"),
        ("Have phone", f"{df['phone'].notna().mean() * 100:.0f}%" if total else "0%"),
        ("Have website", f"{df['website'].notna().mean() * 100:.0f}%" if total else "0%"),
        ("Have email", f"{df['email'].notna().mean() * 100:.0f}%" if total else "0%"),
    ]
    cells_html = "".join(
        f'<div class="kpi-cell"><div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{label}</div></div>'
        for label, value in cells
    )
    st.markdown(f'<div class="kpi-ticker">{cells_html}</div>', unsafe_allow_html=True)


def _style_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.properties(background=SURFACE)
        .configure_view(strokeWidth=0)
        .configure_axis(
            domainColor=BASELINE,
            tickColor=BASELINE,
            gridColor=GRIDLINE,
            labelColor=INK_MUTED,
            titleColor=INK_SECONDARY,
            labelFontSize=11,
            titleFontSize=11,
            labelFont="system-ui",
            titleFont="system-ui",
        )
        .configure_title(color=INK_PRIMARY, fontSize=13, fontWeight=700, anchor="start", font="system-ui")
    )


def render_charts(df: pd.DataFrame) -> None:
    st.markdown('<div class="eyebrow">Insights</div>', unsafe_allow_html=True)
    left, right = st.columns(2)

    by_query = df["source_query"].value_counts().reset_index()
    by_query.columns = ["source_query", "count"]
    query_chart = _style_chart(
        alt.Chart(by_query)
        .mark_bar(color=ACCENT, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("count:Q", title="Leads"),
            y=alt.Y("source_query:N", sort="-x", title=None),
            tooltip=["source_query", "count"],
        )
        .properties(title="Leads by source query", height=260)
    )
    left.altair_chart(query_chart, width='stretch')

    by_score = df["lead_score"].value_counts().reset_index()
    by_score.columns = ["lead_score", "count"]
    score_chart = _style_chart(
        alt.Chart(by_score)
        .mark_bar(color=ACCENT, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("lead_score:O", title="Lead score"),
            y=alt.Y("count:Q", title="Leads"),
            tooltip=["lead_score", "count"],
        )
        .properties(title="Lead score distribution", height=260)
    )
    right.altair_chart(score_chart, width='stretch')


def render_table(df: pd.DataFrame) -> None:
    st.markdown(f'<div class="eyebrow">Leads ({len(df)})</div>', unsafe_allow_html=True)

    display_df = df[
        [
            "place_id",
            "name",
            "lead_score",
            "status",
            "phone",
            "website",
            "email",
            "source_query",
            "scraped_at",
        ]
    ].sort_values("lead_score", ascending=False)

    edited_df = st.data_editor(
        display_df,
        width='stretch',
        hide_index=True,
        key="leads_editor",
        column_order=[
            "name",
            "lead_score",
            "status",
            "phone",
            "website",
            "email",
            "source_query",
            "scraped_at",
        ],
        column_config={
            "name": st.column_config.TextColumn("Name", disabled=True),
            "lead_score": st.column_config.NumberColumn("Score", disabled=True),
            "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS, required=True),
            "phone": st.column_config.TextColumn("Phone", disabled=True),
            "website": st.column_config.TextColumn("Website", disabled=True),
            "email": st.column_config.TextColumn("Email", disabled=True),
            "source_query": st.column_config.TextColumn("Source query", disabled=True),
            "scraped_at": st.column_config.DatetimeColumn("Scraped at", disabled=True),
        },
    )

    changed = edited_df[edited_df["status"].values != display_df["status"].values]
    if not changed.empty:
        collection = get_collection()
        for _, row in changed.iterrows():
            collection.update_one({"place_id": row["place_id"]}, {"$set": {"status": row["status"]}})
        load_leads.clear()
        st.rerun(scope="fragment")


@st.fragment(run_every=REFRESH_INTERVAL_SECONDS)
def render_dashboard() -> None:
    df = load_leads()
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-title">Gauteng Tech Leads</div>
            <div class="live-pill"><span class="live-dot"></span>
                Auto-refresh {REFRESH_INTERVAL_SECONDS}s &middot; checked {datetime.now():%H:%M:%S}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info("No leads in the database yet. Run `python -m src.pipeline` first.")
        return

    filtered = render_filters(df)
    render_kpis(filtered)
    render_charts(filtered)
    render_table(filtered)


def main() -> None:
    st.set_page_config(page_title="Gauteng Tech Leads", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    render_dashboard()


if __name__ == "__main__":
    main()
