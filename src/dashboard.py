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

PRIMARY_HUE = "#256abf"


REFRESH_INTERVAL_SECONDS = 30


@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS)
def load_leads() -> pd.DataFrame:
    records = list(get_collection().find({}))
    rows = [flatten_record(r) for r in records]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
    return df


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
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
    cols = st.columns(5)
    cols[0].metric("Leads", total)
    cols[1].metric("Avg. score", f"{df['lead_score'].mean():.1f}" if total else "0.0")
    cols[2].metric("Have phone", f"{df['phone'].notna().mean() * 100:.0f}%" if total else "0%")
    cols[3].metric("Have website", f"{df['website'].notna().mean() * 100:.0f}%" if total else "0%")
    cols[4].metric("Have email", f"{df['email'].notna().mean() * 100:.0f}%" if total else "0%")


def render_charts(df: pd.DataFrame) -> None:
    left, right = st.columns(2)

    by_query = df["source_query"].value_counts().reset_index()
    by_query.columns = ["source_query", "count"]
    query_chart = (
        alt.Chart(by_query)
        .mark_bar(color=PRIMARY_HUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("count:Q", title="Leads"),
            y=alt.Y("source_query:N", sort="-x", title=None),
            tooltip=["source_query", "count"],
        )
        .properties(title="Leads by source query")
    )
    left.altair_chart(query_chart, use_container_width=True)

    by_score = df["lead_score"].value_counts().reset_index()
    by_score.columns = ["lead_score", "count"]
    score_chart = (
        alt.Chart(by_score)
        .mark_bar(color=PRIMARY_HUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("lead_score:O", title="Lead score"),
            y=alt.Y("count:Q", title="Leads"),
            tooltip=["lead_score", "count"],
        )
        .properties(title="Lead score distribution")
    )
    right.altair_chart(score_chart, use_container_width=True)


def render_table(df: pd.DataFrame) -> None:
    st.subheader(f"Leads ({len(df)})")
    st.dataframe(
        df[
            [
                "name",
                "lead_score",
                "address",
                "phone",
                "website",
                "email",
                "source_query",
                "scraped_at",
            ]
        ].sort_values("lead_score", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


@st.fragment(run_every=REFRESH_INTERVAL_SECONDS)
def render_dashboard() -> None:
    df = load_leads()
    st.caption(f"Auto-refreshes every {REFRESH_INTERVAL_SECONDS}s · last checked {datetime.now():%H:%M:%S}")
    if df.empty:
        st.info("No leads in the database yet. Run `python -m src.pipeline` first.")
        return

    filtered = render_filters(df)
    render_kpis(filtered)
    st.divider()
    render_charts(filtered)
    st.divider()
    render_table(filtered)


def main() -> None:
    st.set_page_config(page_title="JHB Tech Startup Leads", layout="wide")
    st.title("Johannesburg Tech Startup Leads")
    render_dashboard()


if __name__ == "__main__":
    main()
