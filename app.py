import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output

# ============================================================
# DVST Final Project — The Silicon Hegemony
# Final Correct Dash App
# ============================================================

CLEANED_TRADE_PATH = "cleaned_trade.csv"
CLEANED_FAB_PATH = "cleaned_fab.csv"
CLEANED_COMPANIES_PATH = "cleaned_companies.csv"


def load_csv(path):
    try:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return pd.DataFrame()


df_trade = load_csv(CLEANED_TRADE_PATH)
df_fab = load_csv(CLEANED_FAB_PATH)
df_companies = load_csv(CLEANED_COMPANIES_PATH)

# ============================================================
# NORMALIZATION
# ============================================================

country_map = {
    "USA": "United States",
    "United States of America": "United States",
    "Korea, Republic of": "South Korea",
    "Republic of Korea": "South Korea",
    "Rep. of Korea": "South Korea",
    "China, Hong Kong SAR": "Hong Kong",
    "China, Macao SAR": "Macao",
    "Taipei, Chinese": "Taiwan",
    "China (mainland)": "China",
    "Viet Nam": "Vietnam",
    "Russian Federation": "Russia"
}

# ------------------ Trade ------------------
if not df_trade.empty:
    if "fobvalue" in df_trade.columns:
        df_trade["fobvalue"] = pd.to_numeric(df_trade["fobvalue"], errors="coerce").fillna(0)

    for col in ["reporterDesc", "partnerDesc"]:
        if col in df_trade.columns:
            df_trade[col] = df_trade[col].replace(country_map)

# ------------------ Fab ------------------
if not df_fab.empty:
    if "Country_Clean" in df_fab.columns:
        df_fab["Country"] = df_fab["Country_Clean"].astype(str).str.strip()
    else:
        loc_cols = [c for c in df_fab.columns if "location" in c.lower() or "plant" in c.lower()]
        if loc_cols:
            loc_col = loc_cols[0]
            df_fab["Country"] = (
                df_fab[loc_col]
                .astype(str)
                .str.split(",")
                .str[0]
                .str.strip()
            )
        else:
            df_fab["Country"] = "Unknown"

    df_fab["Country"] = df_fab["Country"].replace(country_map)
    df_fab["Country"] = df_fab["Country"].fillna("Unknown")

# ------------------ Companies ------------------
if not df_companies.empty:
    country_candidates = [c for c in df_companies.columns if "country" in c.lower()]
    mktcap_candidates = [c for c in df_companies.columns if "market" in c.lower() or "cap" in c.lower()]
    company_candidates = [c for c in df_companies.columns if "company" in c.lower() or "name" in c.lower()]

    country_col = country_candidates[0] if country_candidates else "Country"
    mktcap_col = mktcap_candidates[0] if mktcap_candidates else df_companies.columns[-1]
    company_col = company_candidates[0] if company_candidates else df_companies.columns[0]

    df_companies[country_col] = df_companies[country_col].replace(country_map)

    df_companies[mktcap_col] = (
        df_companies[mktcap_col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    df_companies[mktcap_col] = pd.to_numeric(df_companies[mktcap_col], errors="coerce")
    df_companies = df_companies.dropna(subset=[mktcap_col])
else:
    country_col = "Country"
    mktcap_col = "Market Cap (USD)"
    company_col = "Company"

# ============================================================
# AGGREGATIONS
# ============================================================

# Export summary
if not df_trade.empty and "reporterDesc" in df_trade.columns and "fobvalue" in df_trade.columns:
    export_by_country = (
        df_trade.groupby("reporterDesc", as_index=False)["fobvalue"]
        .sum()
        .rename(columns={"reporterDesc": "Country", "fobvalue": "ExportUSD"})
        .sort_values("ExportUSD", ascending=False)
    )
else:
    export_by_country = pd.DataFrame(columns=["Country", "ExportUSD"])

# Fab summary
if not df_fab.empty and "Country" in df_fab.columns:
    fab_counts = (
        df_fab.groupby("Country", as_index=False)
        .size()
        .rename(columns={"size": "FabCount"})
        .sort_values("FabCount", ascending=False)
    )
else:
    fab_counts = pd.DataFrame(columns=["Country", "FabCount"])

# Market cap summary
if not df_companies.empty and country_col in df_companies.columns and mktcap_col in df_companies.columns:
    marketcap_by_country = (
        df_companies.groupby(country_col, as_index=False)[mktcap_col]
        .sum()
        .rename(columns={country_col: "Country", mktcap_col: "MarketCapUSD"})
        .sort_values("MarketCapUSD", ascending=False)
    )
else:
    marketcap_by_country = pd.DataFrame(columns=["Country", "MarketCapUSD"])

# ============================================================
# FIGURE 1 — EXPORT CHOROPLETH
# ============================================================

if not export_by_country.empty:
    fig_choropleth = px.choropleth(
        export_by_country,
        locations="Country",
        locationmode="country names",
        color="ExportUSD",
        color_continuous_scale="Reds",
        title="Global Semiconductor Export Dominance (FOB Value)",
        labels={"ExportUSD": "Export Value (USD)"}
    )
    fig_choropleth.update_layout(
        title_font_size=18,
        margin=dict(l=10, r=10, t=50, b=10)
    )
else:
    fig_choropleth = go.Figure()
    fig_choropleth.add_annotation(
        text="No export data available.",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=18, color="red")
    )
    fig_choropleth.update_layout(
        title="Global Semiconductor Export Dominance (FOB Value)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=650
    )

# ============================================================
# FIGURE 2 — TRADE NETWORK (REAL EDGES)
# ============================================================

if not df_trade.empty and all(col in df_trade.columns for col in ["reporterDesc", "partnerDesc", "fobvalue"]):
    edge_df = df_trade[["reporterDesc", "partnerDesc", "fobvalue"]].copy()
    edge_df = edge_df.dropna()
    edge_df = edge_df[edge_df["reporterDesc"] != edge_df["partnerDesc"]]

    edge_df["fobvalue"] = pd.to_numeric(edge_df["fobvalue"], errors="coerce").fillna(0)

    # Aggregate repeated country pairs
    edge_df = (
        edge_df.groupby(["reporterDesc", "partnerDesc"], as_index=False)["fobvalue"]
        .sum()
    )

    # Compute total trade score per country
    out_trade = edge_df.groupby("reporterDesc")["fobvalue"].sum().reset_index()
    out_trade.columns = ["Country", "OutTrade"]

    in_trade = edge_df.groupby("partnerDesc")["fobvalue"].sum().reset_index()
    in_trade.columns = ["Country", "InTrade"]

    trade_score = pd.merge(out_trade, in_trade, on="Country", how="outer").fillna(0)
    trade_score["TradeScore"] = trade_score["OutTrade"] + trade_score["InTrade"]
    trade_score = trade_score.sort_values("TradeScore", ascending=False)

    top15 = trade_score.head(15)["Country"].tolist()

    # Keep only edges between top15 countries
    sub_edges = edge_df[
        edge_df["reporterDesc"].isin(top15) &
        edge_df["partnerDesc"].isin(top15)
    ].copy()

    sub_edges = sub_edges.sort_values("fobvalue", ascending=False).head(40)

    # Circular layout
    n = len(top15)
    pos = {}
    for i, node in enumerate(top15):
        angle = 2 * math.pi * i / n
        pos[node] = (math.cos(angle), math.sin(angle))

    fig_network = go.Figure()

    # Draw edges
    max_edge = sub_edges["fobvalue"].max() if not sub_edges.empty else 1
    for _, row in sub_edges.iterrows():
        u = row["reporterDesc"]
        v = row["partnerDesc"]
        w = row["fobvalue"]

        x0, y0 = pos[u]
        x1, y1 = pos[v]

        fig_network.add_trace(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(
                width=max(1, (w / max_edge) * 6),
                color="rgba(160,160,160,0.45)"
            ),
            hoverinfo="text",
            text=f"{u} → {v}<br>Trade Value: {w:,.0f} USD",
            showlegend=False
        ))

    # Draw nodes
    node_x = [pos[c][0] for c in top15]
    node_y = [pos[c][1] for c in top15]

    score_map = dict(zip(trade_score["Country"], trade_score["TradeScore"]))
    node_scores = [score_map.get(c, 0) for c in top15]
    max_score = max(node_scores) if len(node_scores) > 0 else 1

    fig_network.add_trace(go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=top15,
        textposition="top center",
        hovertemplate="<b>%{text}</b><extra></extra>",
        marker=dict(
            size=[18 + (s / max_score) * 25 for s in node_scores],
            color=node_scores,
            colorscale="YlOrRd",
            showscale=True,
            colorbar=dict(title="Trade Score"),
            line=dict(width=2, color="white")
        ),
        showlegend=False
    ))

    fig_network.update_layout(
        title="Global Semiconductor Trade Network — Top 15 Countries by Trade Volume",
        title_font_size=18,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-1.4, 1.4]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-1.4, 1.4]),
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#1a1a2e",
        font=dict(color="white"),
        height=650,
        margin=dict(l=20, r=20, t=60, b=20)
    )

else:
    fig_network = go.Figure()
    fig_network.add_annotation(
        text="No trade network data available.",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=18, color="red")
    )
    fig_network.update_layout(
        title="Global Semiconductor Trade Network",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=650
    )
# ============================================================
# FIGURE 3 — FINANCIAL DOMINANCE
# ============================================================

if not marketcap_by_country.empty:
    fig_financial = px.bar(
        marketcap_by_country.head(15),
        x="Country",
        y="MarketCapUSD",
        color="MarketCapUSD",
        color_continuous_scale="Viridis",
        title="Semiconductor Market Capitalization by Country",
        labels={"MarketCapUSD": "Market Cap (USD)"}
    )

    fig_financial.update_layout(
        title_font_size=18,
        xaxis_tickangle=-30,
        margin=dict(l=10, r=10, t=50, b=10)
    )
else:
    fig_financial = go.Figure()
    fig_financial.add_annotation(
        text="No financial data available.",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=18, color="red")
    )
    fig_financial.update_layout(
        title="Semiconductor Market Capitalization by Country",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=650
    )

# ============================================================
# FIGURE 4 — FAB DISTRIBUTION
# ============================================================

if not fab_counts.empty:
    fig_fabs = px.bar(
        fab_counts.head(20),
        x="Country",
        y="FabCount",
        color="FabCount",
        color_continuous_scale="Greens",
        title="Fabrication Plant Count by Country",
        labels={"FabCount": "Number of Fabs"}
    )

    fig_fabs.update_layout(
        title_font_size=18,
        xaxis_tickangle=-35,
        margin=dict(l=10, r=10, t=50, b=10)
    )
else:
    fig_fabs = go.Figure()
    fig_fabs.add_annotation(
        text="No fab data available.",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=18, color="red")
    )
    fig_fabs.update_layout(
        title="Fabrication Plant Count by Country",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=650
    )

# ============================================================
# FIGURE 5 — STRATEGY MATRIX
# ============================================================

merged = pd.merge(marketcap_by_country, fab_counts, on="Country", how="outer")
merged = pd.merge(merged, export_by_country, on="Country", how="outer")

for col in ["MarketCapUSD", "FabCount", "ExportUSD"]:
    if col not in merged.columns:
        merged[col] = 0

merged["MarketCapUSD"] = pd.to_numeric(merged["MarketCapUSD"], errors="coerce").fillna(0)
merged["FabCount"] = pd.to_numeric(merged["FabCount"], errors="coerce").fillna(0)
merged["ExportUSD"] = pd.to_numeric(merged["ExportUSD"], errors="coerce").fillna(0)

exclude_terms = [
    "World", "Other Asia, nes", "Areas, nes", "EU-27",
    "Europe, nes", "Unknown", "Special Categories"
]
merged = merged[~merged["Country"].isin(exclude_terms)]

# Keep anything with at least one real metric
merged = merged[
    (merged["MarketCapUSD"] > 0) |
    (merged["FabCount"] > 0) |
    (merged["ExportUSD"] > 0)
].copy()

def assign_archetype(row):
    c = row["Country"]
    if c == "United States":
        return "The Brains"
    elif c == "Taiwan":
        return "The Foundries"
    elif c in ["China", "Japan", "South Korea"]:
        return "The Workshops"
    elif c in ["Singapore", "Hong Kong", "Malaysia"]:
        return "The Nodes"
    else:
        return "The Specialists"

if not merged.empty:
    merged["Archetype"] = merged.apply(assign_archetype, axis=1)

    # Make sure zero values still appear
    merged["BubbleSize"] = merged["ExportUSD"].replace(0, 1)
    merged["FabCountPlot"] = merged["FabCount"].replace(0, 0.2)

    fig_strategy = px.scatter(
        merged,
        x="FabCountPlot",
        y="MarketCapUSD",
        size="BubbleSize",
        color="Archetype",
        hover_name="Country",
        hover_data={
            "FabCount": True,
            "MarketCapUSD": ":.2e",
            "ExportUSD": ":.2e",
            "Archetype": True,
            "FabCountPlot": False,
            "BubbleSize": False
        },
        title="Strategy Matrix: Fab Count vs Market Cap (Bubble = Export Value)",
        labels={
            "FabCountPlot": "Number of Fabrication Plants",
            "MarketCapUSD": "Total Market Capitalization (USD)",
            "BubbleSize": "Export FOB Value (USD)"
        },
        size_max=55,
        color_discrete_sequence=px.colors.qualitative.Bold
    )

    fig_strategy.update_traces(
        marker=dict(
            line=dict(width=1, color="black"),
            opacity=0.75
        )
    )

    fig_strategy.update_layout(
        title_font_size=18,
        plot_bgcolor="#f9f9f9",
        paper_bgcolor="white",
        xaxis=dict(gridcolor="#dddddd"),
        yaxis=dict(gridcolor="#dddddd"),
        legend_title="Archetype",
        height=650,
        margin=dict(l=10, r=10, t=50, b=10)
    )
else:
    fig_strategy = go.Figure()
    fig_strategy.add_annotation(
        text="No matching data available for Strategy Matrix.",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=18, color="red")
    )
    fig_strategy.update_layout(
        title="Strategy Matrix",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=650
    )

# ============================================================
# DASH APP LAYOUT
# ============================================================

app = Dash(__name__)
server = app.server

app.layout = html.Div(
    style={
        "fontFamily": "Arial, sans-serif",
        "maxWidth": "1300px",
        "margin": "0 auto",
        "padding": "20px"
    },
    children=[
        html.H1(
            "The Silicon Hegemony",
            style={"textAlign": "center", "color": "#1f2d3d"}
        ),
        html.P(
            "Interactive Dashboard — DVST Final Project",
            style={"textAlign": "center", "color": "gray", "marginBottom": "20px"}
        ),

        dcc.Tabs(
            id="tabs",
            value="tab-choropleth",
            children=[
                dcc.Tab(label="Export Map", value="tab-choropleth"),
                dcc.Tab(label="Trade Network", value="tab-network"),
                dcc.Tab(label="Financial Dominance", value="tab-financial"),
                dcc.Tab(label="Fab Counts", value="tab-fabs"),
                dcc.Tab(label="Strategy Matrix", value="tab-strategy")
            ]
        ),

        html.Div(id="tab-content", style={"padding": "20px"})
    ]
)

@app.callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab):
    if tab == "tab-choropleth":
        return html.Div([
            html.H3("Export Dominance Choropleth"),
            dcc.Graph(figure=fig_choropleth)
        ])

    elif tab == "tab-network":
        return html.Div([
            html.H3("Trade Network Overview"),
            dcc.Graph(figure=fig_network)
        ])

    elif tab == "tab-financial":
        return html.Div([
            html.H3("Financial Dominance"),
            dcc.Graph(figure=fig_financial)
        ])

    elif tab == "tab-fabs":
        return html.Div([
            html.H3("Global Fabrication Distribution"),
            dcc.Graph(figure=fig_fabs)
        ])

    elif tab == "tab-strategy":
        return html.Div([
            html.H3("Strategy Matrix"),
            dcc.Graph(figure=fig_strategy),
            html.P(
                "This matrix compares fabrication capacity, financial power, and export influence across countries."
            )
        ])

    return html.Div([html.P("Select a tab.")])

if __name__ == "__main__":
    print("Starting Dash app...")
    print("Open: http://127.0.0.1:8050")
    app.run(host="0.0.0.0", port=8050, debug=False)
