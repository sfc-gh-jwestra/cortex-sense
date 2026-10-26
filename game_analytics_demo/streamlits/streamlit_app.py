"""Game Sales Dashboard over CORTEX_SENSE_DEMO.GAME_SALES, with cross-domain views joined to GAME_CATALOG."""

import re
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Game Sales Dashboard", page_icon=":video_game:", layout="wide")

S = "CORTEX_SENSE_DEMO.GAME_SALES"
C = "CORTEX_SENSE_DEMO.GAME_CATALOG"
GRAINS = ("month", "quarter", "year")
# Sales titles map to catalog games through the title-code xref; one row per title code, so dedupe first.
TITLE_MAP = f"SELECT DISTINCT title_id, catalog_game_id FROM {S}.TITLE_CODE_XREF"


@st.cache_resource
def get_conn():
    # Locally, SNOWFLAKE_DEFAULT_CONNECTION_NAME picks the connections.toml entry;
    # in Snowflake the embedded session is used.
    return st.connection("snowflake")


@st.cache_data(ttl=600, show_spinner=False)
def run(sql: str, params: dict | None = None) -> pd.DataFrame:
    # Queries are written with %(name)s placeholders; the connection binds positionally (qmark),
    # so rewrite each placeholder to ? and pass values in order of appearance.
    params = params or {}
    ordered = []

    def _sub(m):
        if m.group(1) == "grain":  # DATE_TRUNC needs a literal; value is whitelisted
            assert params["grain"] in GRAINS
            return f"'{params['grain']}'"
        ordered.append(params[m.group(1)])
        return "?"

    sql = re.sub(r"%\((\w+)\)s", _sub, sql)
    df = get_conn().query(sql, params=ordered or None, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    return df


def in_clause(col: str, values: list, prefix: str, params: dict) -> str:
    """Build a parameterized 'AND col IN (...)' clause; empty list = no filter."""
    if not values:
        return ""
    keys = []
    for i, v in enumerate(values):
        k = f"{prefix}{i}"
        params[k] = v
        keys.append(f"%({k})s")
    return f" AND {col} IN ({', '.join(keys)})"


def fmt_money(v: float) -> str:
    v = float(v or 0)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"${v / div:,.2f}{suf}"
    return f"${v:,.0f}"


def show(chart, df: pd.DataFrame, key: str):
    """Render a chart with a chart/table toggle."""
    view = st.segmented_control(
        "View", ["Chart", "Table"], default="Chart", key=key, label_visibility="collapsed"
    )
    if view == "Table":
        st.dataframe(df, hide_index=True)
    else:
        st.altair_chart(chart, width="stretch")


# --------------------------------------------------------------------------- sidebar
platforms_df = run(f"SELECT platform_id, platform_name FROM {S}.PLATFORMS ORDER BY platform_name")
regions = run(f"SELECT DISTINCT region FROM {S}.HARDWARE_SALES_TRANSACTIONS ORDER BY 1")["region"].tolist()

with st.sidebar:
    st.header("Filters")
    today = date(2026, 10, 8)
    rng = st.date_input(
        "Date range",
        value=(today - timedelta(days=3 * 365), today),
        min_value=date(2000, 1, 1),
        max_value=today,
    )
    if not isinstance(rng, tuple) or len(rng) != 2:
        st.info("Select an end date.")
        st.stop()
    start, end = rng
    sel_platforms = st.multiselect("Platforms", platforms_df["platform_name"].tolist())
    sel_regions = st.multiselect("Regions (hardware & customers)", regions)
    grain = st.radio("Time grain", GRAINS, horizontal=True)
    st.caption(f"Source: `{S}`")

plat_ids = platforms_df.loc[platforms_df["platform_name"].isin(sel_platforms), "platform_id"].astype(int).tolist()


def base_params() -> dict:
    return {"start": start, "end": end + timedelta(days=1), "grain": grain}


# --------------------------------------------------------------------------- queries
def q_streams():
    p = base_params()
    dp = in_clause("t.platform_id", plat_ids, "dp", p)
    hp = in_clause("h.platform_id", plat_ids, "hp", p)
    hr = in_clause("t.region", sel_regions, "hr", p)
    return run(
        f"""
        SELECT DATE_TRUNC(%(grain)s, t.transaction_timestamp)::date AS period, 'Digital' AS stream,
               SUM(t.gross_revenue) AS revenue, SUM(t.quantity) AS units
        FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
        WHERE t.transaction_timestamp >= %(start)s AND t.transaction_timestamp < %(end)s {dp}
        GROUP BY 1,2
        UNION ALL
        SELECT DATE_TRUNC(%(grain)s, t.sale_timestamp)::date, 'Hardware', SUM(t.gross_revenue), SUM(t.quantity)
        FROM {S}.HARDWARE_SALES_TRANSACTIONS t
        JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
        WHERE t.sale_timestamp >= %(start)s AND t.sale_timestamp < %(end)s {hp} {hr}
        GROUP BY 1,2
        UNION ALL
        SELECT DATE_TRUNC(%(grain)s, charge_timestamp)::date, 'Subscription', SUM(gross_revenue), COUNT(*)
        FROM {S}.SUBSCRIPTION_CHARGES
        WHERE charge_timestamp >= %(start)s AND charge_timestamp < %(end)s
        GROUP BY 1,2
        ORDER BY 1,2
        """,
        p,
    )


def q_kpis(s, e):
    p = {"start": s, "end": e}
    dp = in_clause("platform_id", plat_ids, "dp", p)
    hp = in_clause("h.platform_id", plat_ids, "hp", p)
    hr = in_clause("t.region", sel_regions, "hr", p)
    return run(
        f"""
        SELECT
          (SELECT COALESCE(SUM(gross_revenue),0) FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS
             WHERE transaction_timestamp >= %(start)s AND transaction_timestamp < %(end)s {dp}) AS digital,
          (SELECT COALESCE(SUM(net_developer_revenue),0) FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS
             WHERE transaction_timestamp >= %(start)s AND transaction_timestamp < %(end)s {dp}) AS digital_net,
          (SELECT COALESCE(SUM(t.gross_revenue),0) FROM {S}.HARDWARE_SALES_TRANSACTIONS t
             JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
             WHERE t.sale_timestamp >= %(start)s AND t.sale_timestamp < %(end)s {hp} {hr}) AS hardware,
          (SELECT COALESCE(SUM(t.quantity),0) FROM {S}.HARDWARE_SALES_TRANSACTIONS t
             JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
             WHERE t.sale_timestamp >= %(start)s AND t.sale_timestamp < %(end)s {hp} {hr}) AS hw_units,
          (SELECT COALESCE(SUM(gross_revenue),0) FROM {S}.SUBSCRIPTION_CHARGES
             WHERE charge_timestamp >= %(start)s AND charge_timestamp < %(end)s) AS subs,
          (SELECT COUNT(DISTINCT subscriber_id) FROM {S}.SUBSCRIPTION_CHARGES
             WHERE charge_timestamp >= %(start)s AND charge_timestamp < %(end)s) AS subscribers
        """,
        p,
    ).iloc[0]


def digital_where(p):
    return (
        "t.transaction_timestamp >= %(start)s AND t.transaction_timestamp < %(end)s"
        + in_clause("t.platform_id", plat_ids, "dp", p)
    )


def hardware_where(p):
    return (
        "t.sale_timestamp >= %(start)s AND t.sale_timestamp < %(end)s"
        + in_clause("h.platform_id", plat_ids, "hp", p)
        + in_clause("t.region", sel_regions, "hr", p)
    )


# --------------------------------------------------------------------------- layout
st.title(":video_game: Game Sales Dashboard")
st.caption(f"{start:%b %d, %Y} – {end:%b %d, %Y} · grain: {grain}")

tabs = st.tabs(
    ["Overview", "Digital", "Hardware", "Subscriptions", "Titles", "Customers & Platforms", "Franchises & genres"]
)

# ---------------- Overview
with tabs[0]:
    span = end - start
    cur = q_kpis(start, end + timedelta(days=1))
    prev = q_kpis(start - span - timedelta(days=1), start)

    def delta(a, b):
        return f"{(a - b) / b:+.1%} vs prior period" if b else None

    total, ptotal = cur.digital + cur.hardware + cur.subs, prev.digital + prev.hardware + prev.subs
    c = st.columns(4)
    c[0].metric("Total gross revenue", fmt_money(total), delta(total, ptotal), border=True)
    c[1].metric("Digital gross", fmt_money(cur.digital), delta(cur.digital, prev.digital), border=True)
    c[2].metric("Hardware gross", fmt_money(cur.hardware), delta(cur.hardware, prev.hardware), border=True)
    c[3].metric("Subscription gross", fmt_money(cur.subs), delta(cur.subs, prev.subs), border=True)
    c = st.columns(4)
    c[0].metric("Digital net to developers", fmt_money(cur.digital_net), delta(cur.digital_net, prev.digital_net), border=True)
    c[1].metric("Platform commission", fmt_money(cur.digital - cur.digital_net), border=True)
    c[2].metric("Hardware units sold", f"{int(cur.hw_units):,}", delta(cur.hw_units, prev.hw_units), border=True)
    c[3].metric("Paying subscribers", f"{int(cur.subscribers):,}", delta(cur.subscribers, prev.subscribers), border=True)

    streams = q_streams()
    left, right = st.columns([2, 1])
    with left, st.container(border=True):
        st.subheader("Revenue by stream")
        ch = alt.Chart(streams).mark_area().encode(
            x=alt.X("period:T", title=None),
            y=alt.Y("revenue:Q", title="Gross revenue", stack=True),
            color=alt.Color("stream:N", legend=alt.Legend(orient="bottom")),
            tooltip=["period:T", "stream", alt.Tooltip("revenue:Q", format="$,.0f")],
        )
        show(ch, streams, "ov_streams")
    with right, st.container(border=True):
        st.subheader("Revenue mix")
        mix = streams.groupby("stream", as_index=False)["revenue"].sum()
        ch = alt.Chart(mix).mark_arc(innerRadius=60).encode(
            theta="revenue:Q",
            color=alt.Color("stream:N", legend=alt.Legend(orient="bottom")),
            tooltip=["stream", alt.Tooltip("revenue:Q", format="$,.0f")],
        )
        show(ch, mix, "ov_mix")

    with st.container(border=True):
        st.subheader("Period-over-period growth by stream")
        g = streams.sort_values("period").copy()
        g["growth_pct"] = g.groupby("stream")["revenue"].pct_change() * 100
        g = g.dropna()
        ch = alt.Chart(g).mark_bar().encode(
            x=alt.X("period:T", title=None),
            y=alt.Y("growth_pct:Q", title="Growth %"),
            color="stream:N",
            xOffset="stream:N",
            tooltip=["period:T", "stream", alt.Tooltip("growth_pct:Q", format=".1f")],
        )
        show(ch, g, "ov_growth")

# ---------------- Digital
with tabs[1]:
    p = base_params()
    w = digital_where(p)
    by_plat = run(
        f"""SELECT DATE_TRUNC(%(grain)s, t.transaction_timestamp)::date AS period, pl.platform_name,
                   SUM(t.gross_revenue) AS gross_revenue, SUM(t.net_developer_revenue) AS net_revenue
            FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t JOIN {S}.PLATFORMS pl ON pl.platform_id = t.platform_id
            WHERE {w} GROUP BY 1,2 ORDER BY 1""",
        p,
    )
    with st.container(border=True):
        st.subheader("Digital gross revenue by platform")
        ch = alt.Chart(by_plat).mark_line(point=False).encode(
            x=alt.X("period:T", title=None), y=alt.Y("gross_revenue:Q", title="Gross revenue"),
            color=alt.Color("platform_name:N", title="Platform"),
            tooltip=["period:T", "platform_name", alt.Tooltip("gross_revenue:Q", format="$,.0f")],
        )
        show(ch, by_plat, "dg_plat")

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.subheader("Top 15 digital products")
        top = run(
            f"""SELECT dp.product_name, ti.title_name, SUM(t.gross_revenue) AS gross_revenue, SUM(t.quantity) AS units
                FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
                JOIN {S}.DIGITAL_PRODUCTS dp ON dp.digital_product_id = t.digital_product_id
                JOIN {S}.TITLES ti ON ti.title_id = dp.title_id  -- txn title_id is NULL for ~10%; product's is always set
                WHERE {w} GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15""",
            p,
        )
        ch = alt.Chart(top).mark_bar().encode(
            x=alt.X("gross_revenue:Q", title="Gross revenue"), y=alt.Y("product_name:N", sort="-x", title=None),
            tooltip=["product_name", "title_name", alt.Tooltip("gross_revenue:Q", format="$,.0f"), "units"],
        )
        show(ch, top, "dg_top")
    with b, st.container(border=True):
        st.subheader("Revenue by monetization type")
        mt = run(
            f"""SELECT rt.monetization_type, IFF(dp.is_consumable, 'Consumable', 'Durable') AS kind,
                       SUM(t.gross_revenue) AS gross_revenue
                FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
                JOIN {S}.DIGITAL_PRODUCTS dp ON dp.digital_product_id = t.digital_product_id
                JOIN {S}.REVENUE_TYPES rt ON rt.category_id = dp.category_id
                WHERE {w} GROUP BY 1,2 ORDER BY 3 DESC""",
            p,
        )
        ch = alt.Chart(mt).mark_bar().encode(
            x=alt.X("gross_revenue:Q", title="Gross revenue"), y=alt.Y("monetization_type:N", sort="-x", title=None),
            color=alt.Color("kind:N", legend=alt.Legend(orient="bottom")),
            tooltip=["monetization_type", "kind", alt.Tooltip("gross_revenue:Q", format="$,.0f")],
        )
        show(ch, mt, "dg_mt")

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.subheader("Platform commission by platform")
        com = run(
            f"""SELECT pl.platform_name, SUM(t.gross_revenue) AS gross_revenue,
                       SUM(t.gross_revenue - t.net_developer_revenue) AS commission,
                       AVG(t.platform_commission_pct) AS avg_commission_pct
                FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t JOIN {S}.PLATFORMS pl ON pl.platform_id = t.platform_id
                WHERE {w} GROUP BY 1 ORDER BY 2 DESC""",
            p,
        )
        ch = alt.Chart(com).mark_bar().encode(
            x=alt.X("platform_name:N", sort="-y", title=None), y=alt.Y("commission:Q", title="Commission paid"),
            tooltip=["platform_name", alt.Tooltip("commission:Q", format="$,.0f"),
                     alt.Tooltip("avg_commission_pct:Q", format=".2f")],
        )
        show(ch, com, "dg_com")
    with b, st.container(border=True):
        st.subheader("Top 15 titles by net developer revenue")
        tt = run(
            f"""SELECT ti.title_name, ti.studio, SUM(t.net_developer_revenue) AS net_revenue,
                       COUNT(DISTINCT t.player_id) AS buyers
                FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
                JOIN {S}.DIGITAL_PRODUCTS dp ON dp.digital_product_id = t.digital_product_id
                JOIN {S}.TITLES ti ON ti.title_id = dp.title_id
                WHERE {w} GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15""",
            p,
        )
        ch = alt.Chart(tt).mark_bar().encode(
            x=alt.X("net_revenue:Q", title="Net revenue"), y=alt.Y("title_name:N", sort="-x", title=None),
            color=alt.Color("studio:N", legend=None),
            tooltip=["title_name", "studio", alt.Tooltip("net_revenue:Q", format="$,.0f"), "buyers"],
        )
        show(ch, tt, "dg_titles")

    with st.container(border=True):
        st.subheader("Purchases by hour of day and weekday")
        hm = run(
            f"""SELECT DAYNAME(t.transaction_timestamp) AS weekday, DAYOFWEEKISO(t.transaction_timestamp) AS dow,
                       HOUR(t.transaction_timestamp) AS hour, COUNT(*) AS transactions
                FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t WHERE {w} GROUP BY 1,2,3""",
            p,
        )
        ch = alt.Chart(hm).mark_rect().encode(
            x=alt.X("hour:O", title="Hour"),
            y=alt.Y("weekday:N", sort=alt.EncodingSortField("dow"), title=None),
            color=alt.Color("transactions:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["weekday", "hour", "transactions"],
        )
        show(ch, hm, "dg_hm")

# ---------------- Hardware
with tabs[2]:
    p = base_params()
    w = hardware_where(p)
    trend = run(
        f"""SELECT DATE_TRUNC(%(grain)s, t.sale_timestamp)::date AS period, h.product_type,
                   SUM(t.gross_revenue) AS gross_revenue, SUM(t.quantity) AS units
            FROM {S}.HARDWARE_SALES_TRANSACTIONS t
            JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
            WHERE {w} GROUP BY 1,2 ORDER BY 1""",
        p,
    )
    with st.container(border=True):
        st.subheader("Hardware revenue by product type")
        metric = st.pills("Measure", ["gross_revenue", "units"], default="gross_revenue", key="hw_measure")
        ch = alt.Chart(trend).mark_bar().encode(
            x=alt.X("period:T", title=None), y=alt.Y(f"{metric or 'gross_revenue'}:Q", stack=True),
            color=alt.Color("product_type:N", legend=alt.Legend(orient="bottom")),
            tooltip=["period:T", "product_type", alt.Tooltip("gross_revenue:Q", format="$,.0f"), "units"],
        )
        show(ch, trend, "hw_trend")

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.subheader("Revenue by region")
        rg = run(
            f"""SELECT t.region, h.product_type, SUM(t.gross_revenue) AS gross_revenue
                FROM {S}.HARDWARE_SALES_TRANSACTIONS t
                JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
                WHERE {w} GROUP BY 1,2""",
            p,
        )
        ch = alt.Chart(rg).mark_bar().encode(
            x=alt.X("region:N", sort="-y", title=None), y=alt.Y("gross_revenue:Q", stack=True),
            color=alt.Color("product_type:N", legend=alt.Legend(orient="bottom")),
            tooltip=["region", "product_type", alt.Tooltip("gross_revenue:Q", format="$,.0f")],
        )
        show(ch, rg, "hw_region")
    with b, st.container(border=True):
        st.subheader("Revenue by manufacturer")
        mf = run(
            f"""SELECT h.manufacturer, SUM(t.gross_revenue) AS gross_revenue, SUM(t.quantity) AS units
                FROM {S}.HARDWARE_SALES_TRANSACTIONS t
                JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
                WHERE {w} GROUP BY 1 ORDER BY 2 DESC""",
            p,
        )
        ch = alt.Chart(mf).mark_arc(innerRadius=60).encode(
            theta="gross_revenue:Q", color=alt.Color("manufacturer:N", legend=alt.Legend(orient="bottom")),
            tooltip=["manufacturer", alt.Tooltip("gross_revenue:Q", format="$,.0f"), "units"],
        )
        show(ch, mf, "hw_mfr")

    with st.container(border=True):
        st.subheader("Top hardware products: realized price vs list price")
        hp_ = run(
            f"""SELECT h.product_name, h.product_type, h.list_price,
                       SUM(t.gross_revenue) / NULLIF(SUM(t.quantity),0) AS avg_selling_price,
                       SUM(t.quantity) AS units, SUM(t.gross_revenue) AS gross_revenue
                FROM {S}.HARDWARE_SALES_TRANSACTIONS t
                JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
                WHERE {w} GROUP BY 1,2,3 ORDER BY gross_revenue DESC LIMIT 25""",
            p,
        )
        ch = alt.Chart(hp_).mark_circle(opacity=0.8).encode(
            x=alt.X("list_price:Q", title="List price"), y=alt.Y("avg_selling_price:Q", title="Avg selling price"),
            size=alt.Size("units:Q", legend=None), color="product_type:N",
            tooltip=["product_name", alt.Tooltip("list_price:Q", format="$,.2f"),
                     alt.Tooltip("avg_selling_price:Q", format="$,.2f"), "units",
                     alt.Tooltip("gross_revenue:Q", format="$,.0f")],
        )
        show(ch, hp_, "hw_price")

# ---------------- Subscriptions
with tabs[3]:
    p = base_params()
    sw = "c.charge_timestamp >= %(start)s AND c.charge_timestamp < %(end)s"
    mrr = run(
        f"""SELECT DATE_TRUNC(%(grain)s, c.charge_timestamp)::date AS period, sp.plan_tier,
                   SUM(c.gross_revenue) AS revenue, COUNT(DISTINCT c.subscriber_id) AS subscribers
            FROM {S}.SUBSCRIPTION_CHARGES c JOIN {S}.SUBSCRIPTION_PLANS sp ON sp.plan_id = c.plan_id
            WHERE {sw} GROUP BY 1,2 ORDER BY 1""",
        p,
    )
    a, b = st.columns(2)
    with a, st.container(border=True):
        st.subheader("Subscription revenue by tier")
        ch = alt.Chart(mrr).mark_area().encode(
            x=alt.X("period:T", title=None), y=alt.Y("revenue:Q", stack=True),
            color=alt.Color("plan_tier:N", legend=alt.Legend(orient="bottom")),
            tooltip=["period:T", "plan_tier", alt.Tooltip("revenue:Q", format="$,.0f")],
        )
        show(ch, mrr, "sb_rev")
    with b, st.container(border=True):
        st.subheader("Paying subscribers by tier")
        ch = alt.Chart(mrr).mark_line().encode(
            x=alt.X("period:T", title=None), y=alt.Y("subscribers:Q"),
            color=alt.Color("plan_tier:N", legend=alt.Legend(orient="bottom")),
            tooltip=["period:T", "plan_tier", "subscribers"],
        )
        show(ch, mrr, "sb_subs")

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.subheader("Top plans")
        tp = run(
            f"""SELECT sp.plan_name, sp.plan_tier, sp.billing_cycle, sp.list_price,
                       SUM(c.gross_revenue) AS revenue, COUNT(DISTINCT c.subscriber_id) AS subscribers
                FROM {S}.SUBSCRIPTION_CHARGES c JOIN {S}.SUBSCRIPTION_PLANS sp ON sp.plan_id = c.plan_id
                WHERE {sw} GROUP BY 1,2,3,4 ORDER BY revenue DESC LIMIT 15""",
            p,
        )
        ch = alt.Chart(tp).mark_bar().encode(
            x=alt.X("revenue:Q"), y=alt.Y("plan_name:N", sort="-x", title=None), color="plan_tier:N",
            tooltip=["plan_name", "plan_tier", "billing_cycle", alt.Tooltip("revenue:Q", format="$,.0f"), "subscribers"],
        )
        show(ch, tp, "sb_top")
    with b, st.container(border=True):
        st.subheader("Average revenue per subscriber (ARPS)")
        arps = mrr.groupby("period", as_index=False)[["revenue", "subscribers"]].sum()
        arps["arps"] = arps["revenue"] / arps["subscribers"]
        ch = alt.Chart(arps).mark_line(point=True).encode(
            x=alt.X("period:T", title=None), y=alt.Y("arps:Q", title="ARPS"),
            tooltip=["period:T", alt.Tooltip("arps:Q", format="$,.2f"), "subscribers"],
        )
        show(ch, arps, "sb_arps")

# ---------------- Titles
with tabs[4]:
    p = {"start": start.replace(day=1), "end": end}
    tw = "m.revenue_month >= %(start)s AND m.revenue_month <= %(end)s"
    a, b = st.columns([3, 2])
    with a, st.container(border=True):
        st.subheader("Title leaderboard")
        lb = run(
            f"""SELECT t.title_name, t.studio, t.publisher_label, SUM(m.monthly_income) AS income
                FROM {S}.MONTHLY_REVENUE m JOIN {S}.TITLES t ON t.title_id = m.title_id
                WHERE {tw} GROUP BY 1,2,3 ORDER BY income DESC LIMIT 20""",
            p,
        )
        ch = alt.Chart(lb).mark_bar().encode(
            x=alt.X("income:Q"), y=alt.Y("title_name:N", sort="-x", title=None),
            color=alt.Color("publisher_label:N", legend=alt.Legend(orient="bottom", columns=3)),
            tooltip=["title_name", "studio", "publisher_label", alt.Tooltip("income:Q", format="$,.0f")],
        )
        show(ch, lb, "ti_lb")
    with b, st.container(border=True):
        st.subheader("Income by revenue source")
        rs = run(
            f"""SELECT m.revenue_source, SUM(m.monthly_income) AS income
                FROM {S}.MONTHLY_REVENUE m WHERE {tw} GROUP BY 1 ORDER BY 2 DESC""",
            p,
        )
        ch = alt.Chart(rs).mark_arc(innerRadius=60).encode(
            theta="income:Q", color=alt.Color("revenue_source:N", legend=alt.Legend(orient="bottom", columns=2)),
            tooltip=["revenue_source", alt.Tooltip("income:Q", format="$,.0f")],
        )
        show(ch, rs, "ti_src")

    with st.container(border=True):
        st.subheader("Revenue source trend")
        rst = run(
            f"""SELECT DATE_TRUNC('quarter', m.revenue_month)::date AS period, m.revenue_source,
                       SUM(m.monthly_income) AS income
                FROM {S}.MONTHLY_REVENUE m WHERE {tw} GROUP BY 1,2 ORDER BY 1""",
            p,
        )
        ch = alt.Chart(rst).mark_area().encode(
            x=alt.X("period:T", title=None), y=alt.Y("income:Q", stack="normalize", title="Share of income"),
            color=alt.Color("revenue_source:N", legend=alt.Legend(orient="bottom")),
            tooltip=["period:T", "revenue_source", alt.Tooltip("income:Q", format="$,.0f")],
        )
        show(ch, rst, "ti_srct")

    with st.container(border=True):
        st.subheader("Quarterly income heatmap — top 20 titles")
        qh = run(
            f"""WITH top AS (
                  SELECT title_id FROM {S}.QUARTERLY_REVENUE
                  WHERE DATE_FROM_PARTS(revenue_year, revenue_quarter*3-2, 1) BETWEEN %(start)s AND %(end)s
                  GROUP BY 1 ORDER BY SUM(quarterly_income) DESC LIMIT 20)
                SELECT t.title_name, q.revenue_year || '-Q' || q.revenue_quarter AS quarter, q.quarterly_income
                FROM {S}.QUARTERLY_REVENUE q JOIN top USING (title_id)
                JOIN {S}.TITLES t ON t.title_id = q.title_id
                WHERE DATE_FROM_PARTS(q.revenue_year, q.revenue_quarter*3-2, 1) BETWEEN %(start)s AND %(end)s""",
            p,
        )
        ch = alt.Chart(qh).mark_rect().encode(
            x=alt.X("quarter:O", title=None), y=alt.Y("title_name:N", title=None),
            color=alt.Color("quarterly_income:Q", scale=alt.Scale(scheme="blues"), title="Income"),
            tooltip=["title_name", "quarter", alt.Tooltip("quarterly_income:Q", format="$,.0f")],
        ).properties(height=500)
        show(ch, qh, "ti_hm")

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.subheader("Exclusive vs multi-platform titles")
        ex = run(
            # One row per title first, so each title's income is counted once.
            f"""SELECT exclusivity_type, COUNT(*) AS titles, SUM(income) AS income
                FROM (SELECT DISTINCT title_id, COALESCE(exclusivity_type, 'NONE') AS exclusivity_type, income
                      FROM {S}.VW_PLATFORM_EXCLUSIVITY)
                GROUP BY 1 ORDER BY income DESC"""
        )
        ch = alt.Chart(ex).mark_bar().encode(
            x=alt.X("exclusivity_type:N", sort="-y", title=None), y="income:Q",
            tooltip=["exclusivity_type", "titles", alt.Tooltip("income:Q", format="$,.0f")],
        )
        show(ch, ex, "ti_ex")
    with b, st.container(border=True):
        st.subheader("Lifetime income by studio")
        st_ = run(
            f"""SELECT t.studio, SUM(r.income) AS income, COUNT(*) AS titles
                FROM {S}.GAME_REVENUE r JOIN {S}.TITLES t ON t.title_id = r.title_id
                GROUP BY 1 ORDER BY 2 DESC LIMIT 15"""
        )
        ch = alt.Chart(st_).mark_bar().encode(
            x=alt.X("income:Q"), y=alt.Y("studio:N", sort="-x", title=None),
            tooltip=["studio", "titles", alt.Tooltip("income:Q", format="$,.0f")],
        )
        show(ch, st_, "ti_studio")

# ---------------- Customers & Platforms
with tabs[5]:
    p = base_params()
    cw = "a.account_created_date >= %(start)s AND a.account_created_date < %(end)s" + in_clause(
        "a.region", sel_regions, "cr", p
    ) + in_clause("a.platform_id", plat_ids, "cp", p)
    a, b = st.columns([2, 1])
    with a, st.container(border=True):
        st.subheader("New customer accounts by region")
        na = run(
            f"""SELECT DATE_TRUNC(%(grain)s, a.account_created_date)::date AS period, a.region, COUNT(*) AS accounts
                FROM {S}.CUSTOMER_ACCOUNTS a WHERE {cw} GROUP BY 1,2 ORDER BY 1""",
            p,
        )
        ch = alt.Chart(na).mark_bar().encode(
            x=alt.X("period:T", title=None), y=alt.Y("accounts:Q", stack=True),
            color=alt.Color("region:N", legend=alt.Legend(orient="bottom")),
            tooltip=["period:T", "region", "accounts"],
        )
        show(ch, na, "cu_new")
    with b, st.container(border=True):
        st.subheader("Account status")
        ss = run(
            f"""SELECT a.status, COUNT(*) AS accounts FROM {S}.CUSTOMER_ACCOUNTS a WHERE {cw} GROUP BY 1""", p
        )
        ch = alt.Chart(ss).mark_arc(innerRadius=60).encode(
            theta="accounts:Q", color=alt.Color("status:N", legend=alt.Legend(orient="bottom")),
            tooltip=["status", "accounts"],
        )
        show(ch, ss, "cu_status")

    with st.container(border=True):
        st.subheader("Accounts by platform")
        ap = run(
            f"""SELECT pl.platform_name, COUNT(*) AS accounts
                FROM {S}.CUSTOMER_ACCOUNTS a JOIN {S}.PLATFORMS pl ON pl.platform_id = a.platform_id
                WHERE {cw} GROUP BY 1 ORDER BY 2 DESC""",
            p,
        )
        ch = alt.Chart(ap).mark_bar().encode(
            x=alt.X("platform_name:N", sort="-y", title=None), y="accounts:Q", tooltip=["platform_name", "accounts"]
        )
        show(ch, ap, "cu_plat")

    with st.container(border=True):
        st.subheader("Platform revenue summary (VW_PLATFORM_REVENUE_SUMMARY)")
        pr = run(
            f"""SELECT DATE_TRUNC(%(grain)s, revenue_month)::date AS period, category_group,
                       SUM(gross_revenue) AS gross_revenue, SUM(platform_revenue) AS platform_revenue
                FROM {S}.VW_PLATFORM_REVENUE_SUMMARY
                WHERE revenue_month >= %(start)s AND revenue_month < %(end)s GROUP BY 1,2 ORDER BY 1""",
            p,
        )
        ch = alt.Chart(pr).mark_line().encode(
            x=alt.X("period:T", title=None), y=alt.Y("platform_revenue:Q", title="Platform revenue"),
            color=alt.Color("category_group:N", legend=alt.Legend(orient="bottom")),
            tooltip=["period:T", "category_group", alt.Tooltip("gross_revenue:Q", format="$,.0f"),
                     alt.Tooltip("platform_revenue:Q", format="$,.0f")],
        )
        show(ch, pr, "cu_pr")

# ---------------- Franchises & genres (cross-domain: GAME_SALES revenue x GAME_CATALOG attributes)
# Genre level -> (source join, genre column). Fixed choices only; never built from user input.
GENRE_LEVELS = {
    "Detailed": (
        f"JOIN {C}.GAME_GENRE_CLASSIFICATION gg ON gg.game_id = x.catalog_game_id AND gg.match_status = 'FULL'",
        "gg.genre",
    ),
    "Top level": (
        f"JOIN {C}.VW_GAME_GENRE_ROLLUP gg ON gg.game_id = x.catalog_game_id AND gg.rollup_depth = 1",
        "gg.rollup_genre",
    ),
}

with tabs[6]:
    p = {"start": start.replace(day=1), "end": end}
    mw = "m.revenue_month >= %(start)s AND m.revenue_month <= %(end)s"
    st.caption(
        f"Digital game revenue from `{S}.MONTHLY_REVENUE`, mapped to catalog games in `{C}` through "
        f"`TITLE_CODE_XREF` (deduplicated to one game per title). Respects the date range filter."
    )

    with st.container(border=True):
        st.subheader("Revenue by franchise")
        fr_sql = f"""WITH title_map AS ({TITLE_MAP})
            SELECT COALESCE(g.franchise_name, 'Unmapped') AS franchise,
                   SUM(m.monthly_income) AS income, COUNT(DISTINCT m.title_id) AS titles
            FROM {S}.MONTHLY_REVENUE m
            LEFT JOIN title_map x ON x.title_id = m.title_id
            LEFT JOIN {C}.GAMES g ON g.game_id = x.catalog_game_id
            WHERE {mw}
            GROUP BY 1 ORDER BY income DESC LIMIT 20"""
        fr = run(fr_sql, p)
        ch = alt.Chart(fr).mark_bar().encode(
            x=alt.X("income:Q", title="Income"), y=alt.Y("franchise:N", sort="-x", title=None),
            tooltip=["franchise", "titles", alt.Tooltip("income:Q", format="$,.0f")],
        )
        show(ch, fr, "fg_fr")
        st.caption("Titles without a catalog mapping are shown as Unmapped so the total still matches.")
        with st.expander("SQL", icon=":material/code:"):
            st.code(fr_sql, language="sql")

    with st.container(border=True):
        h, ctl = st.columns([3, 1], vertical_alignment="bottom")
        h.subheader("Top 5 genres by revenue, by year")
        level = ctl.segmented_control("Genre level", list(GENRE_LEVELS), default="Detailed", key="fg_level")
        level = level or "Detailed"
        genre_join, genre_col = GENRE_LEVELS[level]
        gy_sql = f"""WITH title_map AS ({TITLE_MAP}),
            genre_rev AS (
              SELECT YEAR(m.revenue_month) AS revenue_year, {genre_col} AS genre,
                     SUM(m.monthly_income) AS income, COUNT(DISTINCT gg.game_id) AS games
              FROM {S}.MONTHLY_REVENUE m
              JOIN title_map x ON x.title_id = m.title_id
              {genre_join}
              WHERE {mw}
              GROUP BY 1, 2)
            SELECT revenue_year, genre, income, games,
                   RANK() OVER (PARTITION BY revenue_year ORDER BY income DESC) AS genre_rank
            FROM genre_rev
            QUALIFY genre_rank <= 5
            ORDER BY revenue_year, genre_rank"""
        gy = run(gy_sql, p)
        gy["year"] = gy["revenue_year"].astype(str)
        ch = alt.Chart(gy).mark_bar().encode(
            x=alt.X("year:N", title=None), xOffset=alt.XOffset("genre_rank:O"),
            y=alt.Y("income:Q", title="Income"),
            color=alt.Color("genre:N", legend=alt.Legend(orient="bottom", columns=4)),
            tooltip=["year", "genre_rank", "genre", "games", alt.Tooltip("income:Q", format="$,.0f")],
        )
        show(ch, gy[["year", "genre_rank", "genre", "games", "income"]], "fg_gy")
        st.warning(
            "Genre revenue overlaps: a game belongs to several genres and its full revenue counts in each "
            "one, so genre totals add up to more than total revenue. Compare genres with each other, not as "
            "shares of the total.",
            icon=":material/info:",
        )
        with st.expander("SQL", icon=":material/code:"):
            st.code(gy_sql, language="sql")
