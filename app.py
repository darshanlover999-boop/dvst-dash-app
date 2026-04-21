import os
import subprocess
import sys

try:
    import pandas  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas==2.0.3"])
    import pandas  # noqa: F401

import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output
CLEANED_COMPANIES_PATH = "cleaned_companies.csv"
CLEANED_FAB_PATH = "cleaned_fab.csv"
CLEANED_TRADE_PATH = "cleaned_trade.csv"


def load_data(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext in [".xls", ".xlsx"]:
        engine = "xlrd" if ext == ".xls" else "openpyxl"
        df = pd.read_excel(path, engine=engine)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_col(df, keywords, required=True):
    cols = list(df.columns)
    for col in cols:
        c = col.lower().strip()
        if all(k in c for k in keywords):
            return col
    for col in cols:
        c = col.lower().strip()
        if any(k in c for k in keywords):
            return col
    if required:
        raise ValueError(f"Could not find column using keywords {keywords}. Available columns: {cols}")
    return None


def to_numeric_clean(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.replace("$", "", regex=False).str.strip(),
        errors="coerce"
    )


def normalize_country_names(series):
    country_map = {
        "USA": "United States",
        "United States of America": "United States",
        "U.S.A.": "United States",
        "Korea, Republic of": "South Korea",
        "Republic of Korea": "South Korea",
        "Rep. of Korea": "South Korea",
        "Korea, South": "South Korea",
        "Taipei, Chinese": "Taiwan",
        "China mainland": "China",
        "Russian Federation": "Russia",
        "Viet Nam": "Vietnam",
        "UK": "United Kingdom",
        "Hong Kong SAR": "Hong Kong",
        "China, Hong Kong SAR": "Hong Kong",
        "China, Macao SAR": "Macao",
    }
    return series.astype(str).str.strip().replace(country_map)


def extract_country_from_location(series):
    cleaned = series.astype(str).str.strip().str.split(",").str[0].str.strip()
    replacements = {"nan": pd.NA, "None": pd.NA}
    cleaned = cleaned.replace(replacements)
    return normalize_country_names(cleaned)


df_companies = load_data(CLEANED_COMPANIES_PATH)
df_fab = load_data(CLEANED_FAB_PATH)
df_trade = load_data(CLEANED_TRADE_PATH)

company_col = find_col(df_companies, ["company"], required=False)
country_col = find_col(df_companies, ["country"])
market_cap_col = find_col(df_companies, ["market", "cap"])

if company_col is None:
    company_col = find_col(df_companies, ["name"], required=False)

df_companies[country_col] = normalize_country_names(df_companies[country_col])
df_companies[market_cap_col] = to_numeric_clean(df_companies[market_cap_col])
df_companies = df_companies.dropna(subset=[country_col, market_cap_col])

market_cap_by_country = (
    df_companies.groupby(country_col, dropna=False)[market_cap_col]
    .sum()
    .reset_index()
    .rename(columns={country_col: "Country", market_cap_col: "MarketCapUSD"})
    .sort_values("MarketCapUSD", ascending=False)
)

if "CountryClean" in df_fab.columns:
    df_fab["Country"] = normalize_country_names(df_fab["CountryClean"])
else:
    location_candidates = [
        c for c in df_fab.columns
        if any(x in c.lower() for x in ["plant location", "location", "country", "region", "plant"])
    ]
    if not location_candidates:
        raise ValueError(f"Could not identify fab location/country column. Available columns: {list(df_fab.columns)}")
    fab_location_col = location_candidates[0]
    df_fab["Country"] = extract_country_from_location(df_fab[fab_location_col])

fab_counts = (
    df_fab.dropna(subset=["Country"])
    .groupby("Country")
    .size()
    .reset_index(name="FabCount")
    .sort_values("FabCount", ascending=False)
)
fab_counts = fab_counts[fab_counts["FabCount"] >= 2]

reporter_col = "reporterDesc" if "reporterDesc" in df_trade.columns else find_col(df_trade, ["reporter"], required=False)
if reporter_col is None:
    reporter_col = df_trade.columns[0]

fob_col = "fobvalue" if "fobvalue" in df_trade.columns else find_col(df_trade, ["fob"], required=False)
if fob_col is None:
    fob_col = find_col(df_trade, ["value"])

df_trade[reporter_col] = normalize_country_names(df_trade[reporter_col])
df_trade[fob_col] = pd.to_numeric(df_trade[fob_col], errors="coerce").fillna(0)

export_by_country = (
    df_trade.groupby(reporter_col, dropna=False)[fob_col]
    .sum()
    .reset_index()
    .rename(columns={reporter_col: "Country", fob_col: "ExportUSD"})
    .sort_values("ExportUSD", ascending=False)
)

merged = market_cap_by_country.merge(fab_counts, on="Country", how="outer")
merged = merged.merge(export_by_country, on="Country", how="outer")
merged[["MarketCapUSD", "FabCount", "ExportUSD"]] = merged[["MarketCapUSD", "FabCount", "ExportUSD"]].fillna(0)
merged = merged[merged["Country"].notna()]
merged["FabCount"] = merged["FabCount"].astype(int)


def archetype(row):
    if row["MarketCapUSD"] >= 1e12:
        return "The Brains"
    if row["MarketCapUSD"] >= 5e11:
        return "The Foundries"
    if row["FabCount"] >= 50:
        return "The Workshops"
    if row["ExportUSD"] >= 1e11:
        return "The Distributors"
    return "The Specialists"


merged["Archetype"] = merged.apply(archetype, axis=1)

alignment_df = pd.DataFrame([
    ["Data Cleaning Pipeline", "Pandas, regex", "Demo/Report"],
    ["Choropleth Map", "Geospatial viz", "Demo/Viva"],
    ["Network Graph", "Network analysis", "Presentation"],
    ["Financial Bar + Treemap", "Financial viz", "Presentation"],
    ["Strategy Scatter Matrix", "Multivariate bubble", "Demo/Viva"],
    ["Manim Animation 1", "Math animation", "Presentation"],
    ["Manim Animation 2", "Storytelling", "Presentation"],
    ["Dash App", "Dashboard design", "Demo/Viva"],
], columns=["Module", "DVST Topic / Tool", "Assessment"])

app = Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H1("The Silicon Hegemony Interactive Dashboard", style={
        "textAlign": "center", "color": "#1f2d3d", "fontFamily": "Arial", "marginBottom": "6px"
    }),
    html.P("DVST Final Project Dashboard", style={
        "textAlign": "center", "color": "#666", "fontFamily": "Arial", "marginTop": "0"
    }),

    dcc.Tabs(id="tabs", value="tab-market", children=[
        dcc.Tab(label="Market Cap", value="tab-market"),
        dcc.Tab(label="Export Map", value="tab-choropleth"),
        dcc.Tab(label="Fab Counts", value="tab-fab"),
        dcc.Tab(label="Strategy Matrix", value="tab-strategy"),
        dcc.Tab(label="Course Alignment", value="tab-alignment"),
    ]),

    html.Div(id="tab-content", style={"padding": "20px"})
], style={
    "fontFamily": "Arial, sans-serif",
    "maxWidth": "1280px",
    "margin": "0 auto"
})


@app.callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab):
    if tab == "tab-market":
        top_market = market_cap_by_country.head(15).copy()
        fig = px.bar(
            top_market,
            x="Country",
            y="MarketCapUSD",
            color="MarketCapUSD",
            color_continuous_scale="Viridis",
            title="Semiconductor Market Capitalization by Country",
            labels={"MarketCapUSD": "Market Cap (USD)", "Country": "Country"}
        )
        fig.update_layout(xaxis_tickangle=-30, height=600)
        return dcc.Graph(figure=fig)

    elif tab == "tab-choropleth":
        export_map = export_by_country.copy()
        fig = px.choropleth(
            export_map,
            locations="Country",
            locationmode="country names",
            color="ExportUSD",
            color_continuous_scale="Reds",
            title="Global Semiconductor Export Dominance (FOB Value)",
            labels={"ExportUSD": "Export Value (USD)"}
        )
        fig.update_layout(height=600)
        return dcc.Graph(figure=fig)

    elif tab == "tab-fab":
        top_fabs = fab_counts.head(15).copy()
        fig = px.bar(
            top_fabs,
            x="Country",
            y="FabCount",
            color="FabCount",
            color_continuous_scale="Greens",
            title="Fabrication Plant Count by Country",
            labels={"FabCount": "Number of Fabs", "Country": "Country"}
        )
        fig.update_layout(xaxis_tickangle=-30, height=600)
        return dcc.Graph(figure=fig)

    elif tab == "tab-strategy":
        strategy_df = merged[merged["FabCount"] > 0].copy()
        fig = px.scatter(
            strategy_df,
            x="FabCount",
            y="MarketCapUSD",
            size="ExportUSD",
            color="Archetype",
            text="Country",
            hover_data={
                "Country": True,
                "FabCount": True,
                "MarketCapUSD": ":.2e",
                "ExportUSD": ":.2e",
                "Archetype": True,
            },
            title="Strategy Matrix: Fab Count vs Market Cap (bubble = export value)",
            labels={
                "FabCount": "Number of Fabrication Plants",
                "MarketCapUSD": "Total Market Capitalization (USD)",
                "ExportUSD": "Export FOB Value (USD)",
            },
            size_max=60,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig.update_traces(textposition="top center")
        fig.update_layout(
            height=620,
            plot_bgcolor="#f9f9f9",
            paper_bgcolor="white",
            xaxis=dict(gridcolor="#dddddd"),
            yaxis=dict(gridcolor="#dddddd")
        )
        return dcc.Graph(figure=fig)

    elif tab == "tab-alignment":
        fig = px.imshow(
            [[1, 1, 1] for _ in range(len(alignment_df))],
            x=["Included", "Mapped", "Assessed"],
            y=alignment_df["Module"],
            text_auto=True,
            color_continuous_scale="Viridis",
            title="Course Topic Alignment"
        )
        fig.update_traces(
            text=[[ "Yes", alignment_df.iloc[i, 1], alignment_df.iloc[i, 2] ] for i in range(len(alignment_df))],
            texttemplate="%{text}"
        )
        fig.update_layout(height=600)
        return dcc.Graph(figure=fig)

    return html.Div("No tab selected.")


if __name__ == "__main__":
    print("Starting Dash app...")
    print("Open your browser at http://127.0.0.1:8050")
    app.run(debug=False, host="0.0.0.0", port=8050)
