import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="QA Project Dashboard", layout="wide", page_icon="📊")

# -----------------------------------------------------------------------------
# 1. DATA LOADING & FALLBACK HANDLING
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data():
    # Read 'Projects' tab
    projects_raw = conn.read(worksheet="Projects", header=6)
    df_projects = projects_raw.dropna(subset=["Project Name"]).copy()
    
    # Dates
    df_projects["Start Date"] = pd.to_datetime(df_projects["Start Date"], errors="coerce")
    df_projects["Completion Date"] = pd.to_datetime(df_projects["Completion Date"], errors="coerce")

    # Read 'Ratings' tab
    ratings_raw = conn.read(worksheet="Ratings", header=6)
    df_ratings = ratings_raw.dropna(subset=["Project Name"]).copy()

    # Merge Release Candidates from Ratings into Projects if needed
    if "Number of Release Candidates" in df_ratings.columns:
        rc_data = df_ratings[["Project Name", "Number of Release Candidates"]]
        df_projects = pd.merge(df_projects, rc_data, on="Project Name", how="left")

    # Ensure duration columns exist (fill with default values if not yet in Sheet)
    for col in ["Estimated QA Days", "Actual QA Days", "QA Estimate rc Dependant"]:
        if col not in df_projects.columns:
            df_projects[col] = 0.0
        else:
            df_projects[col] = pd.to_numeric(df_projects[col], errors="coerce").fillna(0.0)

    if "Number of Release Candidates" not in df_projects.columns:
        df_projects["Number of Release Candidates"] = 0

    return df_projects, df_ratings

try:
    df_projects, df_ratings = load_data()
except Exception as e:
    st.error(f"Error loading Google Sheets data: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 2. TABBED NAVIGATION
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📋 Summary & QA Ratings", "📈 Testing Estimation vs Actuals"])

# =============================================================================
# TAB 1: SUMMARY & RATINGS
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
        df_filtered[[
            "Project Name", "Status", "Start Date", "Completion Date", 
            "Pre/Robustness", "Welding Inspection Required", "Number of Welds Tested", "QA Release Document"
        ]],
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

    # QA Rating Section
    st.subheader("⭐ QA Rating - Project Success Breakdown")
    col_form, col_chart = st.columns([1, 1])

    with col_form:
        selected_project = st.selectbox("Select Project:", df_projects["Project Name"].tolist())
        project_row = df_ratings[df_ratings["Project Name"] == selected_project]
        
        def get_val(col_name, default=3):
            if not project_row.empty and col_name in project_row.columns:
                val = project_row[col_name].values[0]
                if pd.notna(val):
                    try: return int(val)
                    except ValueError: return default
            return default

        with st.form("rating_form"):
            docs_score = st.slider("Documents Provided", 1, 5, get_val("Documents Provided"))
            robot_score = st.slider("Robot Availability", 1, 5, get_val("Robot Availability"))
            bundle_score = st.slider("Bundle Preparation", 1, 5, get_val("Bundle Preparation"))
            software_score = st.slider("Software Support", 1, 5, get_val("Software Support"))
            rc_count = st.number_input("Number of Release Candidates", min_value=0, max_value=20, value=get_val("Number of Release Candidates", 1))
            
            test_plan_options = ["Approved", "In Review", "Draft"]
            current_plan_val = project_row["Targeted Test Plan"].values[0] if not project_row.empty and "Targeted Test Plan" in project_row.columns and pd.notna(project_row["Targeted Test Plan"].values[0]) else "Draft"
            plan_index = test_plan_options.index(current_plan_val) if current_plan_val in test_plan_options else 2
            test_plan_status = st.selectbox("Targeted Test Plan", test_plan_options, index=plan_index)

            if st.form_submit_button("Sync Rating to Google Sheets"):
                if selected_project in df_ratings["Project Name"].values:
                    idx = df_ratings[df_ratings["Project Name"] == selected_project].index[0]
                    df_ratings.loc[idx, "Documents Provided"] = docs_score
                    df_ratings.loc[idx, "Robot Availability"] = robot_score
                    df_ratings.loc[idx, "Bundle Preparation"] = bundle_score
                    df_ratings.loc[idx, "Software Support"] = software_score
                    df_ratings.loc[idx, "Number of Release Candidates"] = rc_count
                    df_ratings.loc[idx, "Targeted Test Plan"] = test_plan_status
                else:
                    new_row = pd.DataFrame([{
                        "Project Name": selected_project,
                        "Documents Provided": docs_score,
                        "Robot Availability": robot_score,
                        "Bundle Preparation": bundle_score,
                        "Software Support": software_score,
                        "Number of Release Candidates": rc_count,
                        "Targeted Test Plan": test_plan_status
                    }])
                    df_ratings = pd.concat([df_ratings, new_row], ignore_index=True)

                conn.update(worksheet="Ratings", data=df_ratings)
                st.cache_data.clear()
                st.success(f"Updated Google Sheet for {selected_project}!")
                st.rerun()

    with col_chart:
        st.markdown(f"#### Performance Radar: **{selected_project}**")
        if not project_row.empty:
            categories = ["Documents Provided", "Robot Availability", "Bundle Preparation", "Software Support"]
            scores = [get_val(cat) for cat in categories]
            fig_radar = go.Figure(go.Scatterpolar(
                r=scores + [scores[0]],
                theta=categories + [categories[0]],
                fill='toself',
                line_color='#0068c9'
            ))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
            st.plotly_chart(fig_radar, use_container_width=True)

# =============================================================================
# TAB 2: ESTIMATION VS ACTUAL DURATION (COMBO CHART)
# =============================================================================
with tab2:
    st.title("📈 Testing Estimation versus Actual Duration")
    st.caption("Includes Release Candidate (RC) iterations tracking")

    # Create figure with dual Y-axes
    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])

    # Left Y-Axis: Grouped Bars
    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["Estimated QA Days"],
            name="Estimated QA Days",
            marker_color="#29b6f6"  # Bright Blue
        ),
        secondary_y=False,
    )

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["Actual QA Days"],
            name="Actual QA Days",
            marker_color="#ab47bc"  # Purple
        ),
        secondary_y=False,
    )

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["QA Estimate rc Dependant"],
            name="QA Estimate rc Dependant",
            marker_color="#9ccc65"  # Olive/Green
        ),
        secondary_y=False,
    )

    # Right Y-Axis: Line Overlay for Release Candidates
    fig_combo.add_trace(
        go.Scatter(
            x=df_projects["Project Name"],
            y=df_projects["Number of Release Candidates"],
            name="Release Candidates",
            mode="lines+markers",
            line=dict(color="#ff5722", width=2.5),  # Orange Line
            marker=dict(size=6)
        ),
        secondary_y=True,
    )

    # Styling Layout
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

    # Axis Labels
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