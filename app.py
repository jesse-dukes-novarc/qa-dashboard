import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="QA Project Dashboard", layout="wide", page_icon="📊")

# -----------------------------------------------------------------------------
# 1. READ-ONLY DATA LOADER (FIXED ROW 7 HEADERS)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data():
    def fetch_sheet(worksheet_name):
        # Read worksheet specifying row 7 (index 6) as the fixed header row
        df = conn.read(worksheet=worksheet_name, header=6)
        
        # Clean column names (strip hidden spaces / unicode non-breaking spaces)
        df.columns = df.columns.astype(str).str.replace('\xa0', ' ').str.strip()
        
        # Drop empty/unnamed columns
        df = df.loc[:, ~df.columns.str.lower().str.startswith("unnamed")]
        df = df.loc[:, ~df.columns.str.lower().str.startswith("nan")]
        
        # Filter out empty or invalid project rows
        df = df.dropna(subset=["Project Name"]).copy()
        df["Project Name"] = df["Project Name"].astype(str).str.strip()
        df = df[~df["Project Name"].str.lower().isin(["nan", "none", "", "null"])]
        
        return df

    df_projects = fetch_sheet("Projects")
    df_ratings = fetch_sheet("Ratings")

    # Format Dates safely
    if "Start Date" in df_projects.columns:
        df_projects["Start Date"] = pd.to_datetime(df_projects["Start Date"], errors="coerce")
    if "Completion Date" in df_projects.columns:
        df_projects["Completion Date"] = pd.to_datetime(df_projects["Completion Date"], errors="coerce")

    # Merge Release Candidates count from Ratings sheet if not in Projects
    if "Number of Release Candidates" in df_ratings.columns and "Number of Release Candidates" not in df_projects.columns:
        rc_data = df_ratings[["Project Name", "Number of Release Candidates"]].drop_duplicates(subset=["Project Name"])
        df_projects = pd.merge(df_projects, rc_data, on="Project Name", how="left")

    # Coerce numeric fields and resolve #VALUE! formula errors to 0.0
    duration_cols = ["Estimated QA Days", "Actual QA Days", "QA Estimate rc Dependant", "Number of Release Candidates"]
    for col in duration_cols:
        if col in df_projects.columns:
            df_projects[col] = pd.to_numeric(df_projects[col], errors="coerce").fillna(0.0)
        else:
            df_projects[col] = 0.0

    return df_projects, df_ratings

try:
    df_projects, df_ratings = load_data()
except Exception as e:
    st.error(f"Error loading dashboard data: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 2. SIDEBAR REFRESH & TAB NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.title("QA Dashboard")
if st.sidebar.button("🔄 Refresh Data from Sheet"):
    st.cache_data.clear()
    st.rerun()

tab1, tab2 = st.tabs(["📋 Summary & QA Ratings", "📈 Testing Estimation vs Actuals"])

# =============================================================================
# TAB 1: SUMMARY & READ-ONLY RATINGS
# =============================================================================
with tab1:
    st.title("📋 QA Active & Closed Projects Summary")

    time_range = st.radio(
        "Select Time Range:",
        options=["3 Months", "6 Months", "9 Months", "All Time"],
        index=3,
        horizontal=True
    )

    today_date = pd.Timestamp(datetime.today().date())

    if time_range == "3 Months":
        cutoff = today_date - pd.Timedelta(days=90)
        df_filtered = df_projects[df_projects["Start Date"] >= cutoff]
    elif time_range == "6 Months":
        cutoff = today_date - pd.Timedelta(days=180)
        df_filtered = df_projects[df_projects["Start Date"] >= cutoff]
    elif time_range == "9 Months":
        cutoff = today_date - pd.Timedelta(days=270)
        df_filtered = df_projects[df_projects["Start Date"] >= cutoff]
    else:
        df_filtered = df_projects.copy()

    st.subheader("Project Inventory")
    
    st.dataframe(
        df_filtered,
        column_config={
            "Start Date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD"),
            "Completion Date": st.column_config.DateColumn("Completion Date", format="YYYY-MM-DD"),
            "Welding Inspection Required": st.column_config.TextColumn("Welding Req?"),
            "QA Release Document": st.column_config.TextColumn("Release Status"),
        },
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("⭐ QA Rating - Readiness Breakdown")
    
    project_list = df_projects["Project Name"].tolist()
    selected_project = st.selectbox("Select Project to Inspect Ratings:", project_list)
    
    project_rating_row = df_ratings[df_ratings["Project Name"] == selected_project]

    col_metrics, col_chart = st.columns([1, 1])

    with col_metrics:
        st.markdown(f"#### Recorded Scores for **{selected_project}**")
        
        if not project_rating_row.empty:
            p_data = project_rating_row.iloc[0]
            
            m1, m2 = st.columns(2)
            m1.metric("Documents Provided", f"{p_data.get('Documents Provided', 'N/A')} / 5")
            m2.metric("Robot Availability", f"{p_data.get('Robot Availability', 'N/A')} / 5")
            
            m3, m4 = st.columns(2)
            m3.metric("Bundle Preparation", f"{p_data.get('Bundle Preparation', 'N/A')} / 5")
            m4.metric("Software Support", f"{p_data.get('Software Support', 'N/A')} / 5")
            
            m5, m6 = st.columns(2)
            m5.metric("Release Candidates", f"{p_data.get('Number of Release Candidates', 'N/A')}")
            m6.metric("Targeted Test Plan", f"{p_data.get('Targeted Test Plan', 'N/A')}")
        else:
            st.warning("No rating record found in the Ratings sheet for this project.")

    with col_chart:
        st.markdown("#### Performance Radar")
        if not project_rating_row.empty:
            categories = ["Documents Provided", "Robot Availability", "Bundle Preparation", "Software Support"]
            
            scores = []
            for cat in categories:
                val = project_rating_row.iloc[0].get(cat, 0)
                try: scores.append(float(val))
                except (ValueError, TypeError): scores.append(0.0)

    fig_radar = go.Figure(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name=selected_project,
     line_color='#0068c9'
    ))

    fig_radar.update_layout(
       polar=dict(
           # Transparent chart background for dark mode
           bgcolor="rgba(0, 0, 0, 0)",
           radialaxis=dict(
               visible=True,
               range=[0, 5],
               # 1. Scale numbers color (0, 1, 2, 3, 4, 5)
               tickfont=dict(color="black", size=12),
               gridcolor="#444444"  # Optional: grid line color
            ),
            angularaxis=dict(
                # 2. Outer category labels color (Documents Provided, etc.)
                tickfont=dict(color="black", size=12)
            )
      ),
      paper_bgcolor="rgba(0, 0, 0, 0)",
      plot_bgcolor="rgba(0, 0, 0, 0)",
      showlegend=False,
      margin=dict(l=40, r=40, t=20, b=20)
    )

    st.plotly_chart(fig_radar, use_container_width=True)

# =============================================================================
# TAB 2: ESTIMATION VS ACTUAL DURATION (COMBO CHART)
# =============================================================================
with tab2:
    st.title("📈 Testing Estimation versus Actual Duration")
    st.caption("Includes Release Candidate (RC) iterations tracking")

    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["Estimated QA Days"],
            name="Estimated QA Days",
            marker_color="#29b6f6"
        ),
        secondary_y=False,
    )

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["Actual QA Days"],
            name="Actual QA Days",
            marker_color="#ab47bc"
        ),
        secondary_y=False,
    )

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["QA Estimate rc Dependant"],
            name="QA Estimate rc Dependant",
            marker_color="#9ccc65"
        ),
        secondary_y=False,
    )

    fig_combo.add_trace(
        go.Scatter(
            x=df_projects["Project Name"],
            y=df_projects["Number of Release Candidates"],
            name="Release Candidates",
            mode="lines+markers",
            line=dict(color="#ff5722", width=2.5),
            marker=dict(size=6)
        ),
        secondary_y=True,
    )

    fig_combo.update_layout(
        barmode="group",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        margin=dict(l=20, r=20, t=50, b=20),
        height=550
    )

    fig_combo.update_yaxes(
        title_text="Estimated QA Days | Actual QA Days | QA Estimate rc Dependant",
        secondary_y=False,
        showgrid=True
    )
    fig_combo.update_yaxes(
        title_text="Release Candidates",
        secondary_y=True,
        showgrid=False
    )

    st.plotly_chart(fig_combo, use_container_width=True)