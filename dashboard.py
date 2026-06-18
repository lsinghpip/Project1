import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="COVID-19 Institutional Dashboard", page_icon="🦠", layout="wide")

# -----------------------------
# Load Data
# -----------------------------
@st.cache_data
def load_data(uploaded_file=None):
    if uploaded_file is not None:
        data = pd.read_csv(uploaded_file)
    else:
        data = pd.read_csv("covid19dashboard.csv")

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    numeric_cols = [
        "Latitude", "Longitude", "TotalConfirmed", "TotalDeaths",
        "DistinctPatientsTested", "NewInTheLast14Days"
    ]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=["Date", "InstitutionName", "Latitude", "Longitude"])
    data["Month"] = data["Date"].dt.to_period("M").astype(str)
    data["DeathRate"] = data.apply(
        lambda r: (r["TotalDeaths"] / r["TotalConfirmed"] * 100) if r["TotalConfirmed"] > 0 else 0,
        axis=1
    )
    data["TestingPositivityProxy"] = data.apply(
        lambda r: (r["TotalConfirmed"] / r["DistinctPatientsTested"] * 100) if r["DistinctPatientsTested"] > 0 else 0,
        axis=1
    )
    return data

uploaded = st.sidebar.file_uploader("Upload updated COVID CSV", type=["csv"])
df = load_data(uploaded)

# -----------------------------
# Title and Context
# -----------------------------
st.title("🦠 COVID-19 Institutional Dashboard")
st.markdown(
    """
    This dashboard explores COVID-19 activity across reporting institutions over time.  
    The main questions are: **Where were confirmed cases concentrated?**, **which institutions reported the highest burden?**,
    **how did activity change over time?**, and **how severe were outcomes based on deaths and recent cases?**
    """
)

# -----------------------------
# Sidebar Filters
# -----------------------------
st.sidebar.header("Dashboard Filters")

min_date = df["Date"].min().date()
max_date = df["Date"].max().date()

start_date, end_date = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")

institutions = sorted(df["InstitutionName"].dropna().unique())
selected_institutions = st.sidebar.multiselect(
    "Select institution(s)",
    institutions,
    default=institutions
)

min_confirmed = int(df["TotalConfirmed"].min())
max_confirmed = int(df["TotalConfirmed"].max())
confirmed_range = st.sidebar.slider(
    "Total confirmed case range",
    min_value=min_confirmed,
    max_value=max_confirmed,
    value=(min_confirmed, max_confirmed)
)

metric_choice = st.sidebar.selectbox(
    "Map bubble size metric",
    ["TotalConfirmed", "TotalDeaths", "DistinctPatientsTested", "NewInTheLast14Days"]
)

show_raw_data = st.sidebar.checkbox("Show filtered raw data")

# -----------------------------
# Apply Filters
# -----------------------------
filtered_df = df[
    (df["Date"].dt.date >= start_date) &
    (df["Date"].dt.date <= end_date) &
    (df["InstitutionName"].isin(selected_institutions)) &
    (df["TotalConfirmed"].between(confirmed_range[0], confirmed_range[1]))
].copy()

if filtered_df.empty:
    st.warning("No records match the selected filters. Please adjust the sidebar filters.")
    st.stop()

# Use latest record per institution for institution-level KPIs and map
latest_idx = filtered_df.groupby("InstitutionName")["Date"].idxmax()
latest_df = filtered_df.loc[latest_idx].copy()

# -----------------------------
# KPI Section
# -----------------------------
st.subheader("Key Performance Indicators")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("Institutions", latest_df["InstitutionName"].nunique())
kpi2.metric("Latest Confirmed Cases", f"{int(latest_df['TotalConfirmed'].sum()):,}")
kpi3.metric("Latest Deaths", f"{int(latest_df['TotalDeaths'].sum()):,}")
kpi4.metric("Recent Cases, Last 14 Days", f"{int(latest_df['NewInTheLast14Days'].sum()):,}")

# -----------------------------
# Layout: Main Visuals
# -----------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview", "Institution Comparison", "Time Trends", "Data Source & QUEST"
])

with tab1:
    st.subheader("Geographic Distribution of COVID-19 Activity")
    st.caption("Each bubble represents an institution. Larger bubbles indicate higher values for the selected map metric.")

    fig_map = px.scatter_mapbox(
        latest_df,
        lat="Latitude",
        lon="Longitude",
        size=metric_choice,
        color="TotalConfirmed",
        hover_name="InstitutionName",
        hover_data={
            "TotalConfirmed": ":,",
            "TotalDeaths": ":,",
            "DistinctPatientsTested": ":,",
            "NewInTheLast14Days": ":,",
            "Latitude": False,
            "Longitude": False
        },
        zoom=3,
        height=560,
        color_continuous_scale="Reds"
    )
    fig_map.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 10 Institutions by Confirmed Cases")
        top_confirmed = latest_df.sort_values("TotalConfirmed", ascending=False).head(10)
        fig_bar = px.bar(
            top_confirmed,
            x="TotalConfirmed",
            y="InstitutionName",
            orientation="h",
            text="TotalConfirmed",
            labels={"TotalConfirmed": "Confirmed Cases", "InstitutionName": "Institution"},
            template="plotly_white"
        )
        fig_bar.update_layout(yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.subheader("Share of Deaths by Institution")
        top_deaths = latest_df.sort_values("TotalDeaths", ascending=False).head(10)
        fig_pie = px.pie(
            top_deaths,
            values="TotalDeaths",
            names="InstitutionName",
            hole=0.45,
            template="plotly_white"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with tab2:
    st.subheader("Institution Comparison")
    st.caption("This section compares burden and severity across selected institutions using the most recent record in the selected date range.")

    comparison_metric = st.radio(
        "Choose comparison metric",
        ["TotalConfirmed", "TotalDeaths", "DistinctPatientsTested", "NewInTheLast14Days", "DeathRate"],
        horizontal=True
    )

    compare_df = latest_df.sort_values(comparison_metric, ascending=False)
    fig_compare = px.bar(
        compare_df,
        x="InstitutionName",
        y=comparison_metric,
        color=comparison_metric,
        text=comparison_metric,
        labels={"InstitutionName": "Institution", comparison_metric: comparison_metric.replace("Total", "Total ")},
        template="plotly_white"
    )
    fig_compare.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_compare, use_container_width=True)

    st.subheader("Correlation Heatmap")
    st.caption("This helps identify whether high case counts, deaths, testing, and recent activity tend to move together.")
    corr_cols = ["TotalConfirmed", "TotalDeaths", "DistinctPatientsTested", "NewInTheLast14Days", "DeathRate", "TestingPositivityProxy"]
    corr = latest_df[corr_cols].corr(numeric_only=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", ax=ax)
    ax.set_title("Correlation Between COVID-19 Measures")
    st.pyplot(fig)

with tab3:
    st.subheader("Time Series Analysis")
    st.caption("The line chart shows how confirmed cases changed over time for the selected institutions.")

    trend_level = st.selectbox("View trend by", ["Overall", "Institution"])

    if trend_level == "Overall":
        trend_df = filtered_df.groupby("Date", as_index=False)[["TotalConfirmed", "TotalDeaths", "NewInTheLast14Days"]].sum()
        fig_line = px.line(
            trend_df,
            x="Date",
            y=["TotalConfirmed", "TotalDeaths", "NewInTheLast14Days"],
            markers=False,
            template="plotly_white",
            labels={"value": "Count", "variable": "Metric"}
        )
    else:
        trend_df = filtered_df.groupby(["Date", "InstitutionName"], as_index=False)["TotalConfirmed"].sum()
        fig_line = px.line(
            trend_df,
            x="Date",
            y="TotalConfirmed",
            color="InstitutionName",
            template="plotly_white",
            labels={"TotalConfirmed": "Confirmed Cases", "InstitutionName": "Institution"}
        )
    st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("Monthly Recent Cases")
    monthly_df = filtered_df.groupby("Month", as_index=False)["NewInTheLast14Days"].sum()
    fig_area = px.area(
        monthly_df,
        x="Month",
        y="NewInTheLast14Days",
        template="plotly_white",
        labels={"NewInTheLast14Days": "New Cases in Last 14 Days", "Month": "Month"}
    )
    st.plotly_chart(fig_area, use_container_width=True)

    with st.expander("View time series data"):
        st.table(monthly_df.head(100))
        csv = monthly_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Monthly Data", csv, "monthly_recent_cases.csv", "text/csv")

with tab4:
    st.subheader("Project Documentation")
    st.markdown(
        """
        **Data source:** COVID-19 dashboard CSV file provided for the project.  
        **Date accessed:** Use the date you downloaded or received the dataset.  
        **License or terms:** Add the original public source license here if known.  
        **Refresh plan:** Replace the CSV with a newer file using the sidebar uploader, or update the `covid19dashboard.csv` file in the Streamlit app repository.
        """
    )

    st.subheader("QUEST Framework Used in This Dashboard")
    st.markdown(
        """
        **Q - Question:** Where and when was COVID-19 activity highest across institutions?  
        **U - Understand:** Review columns, clean dates, check missing values, and identify key measures.  
        **E - Explore:** Compare institutions, locations, trends, deaths, testing, and recent cases.  
        **S - Synthesize:** Use KPIs, maps, rankings, and trend charts to connect the evidence.  
        **T - Tell:** Present the findings as a short public-health style briefing for a non-technical audience.
        """
    )

    st.subheader("Dataset Preview")
    st.write(f"Rows: {len(df):,} | Columns: {len(df.columns):,} | Institutions: {df['InstitutionName'].nunique():,}")
    st.table(df.head(10))

if show_raw_data:
    with st.expander("Filtered Raw Data", expanded=True):
        st.dataframe(filtered_df, use_container_width=True)
        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Filtered Data", csv, "filtered_covid19_data.csv", "text/csv")
