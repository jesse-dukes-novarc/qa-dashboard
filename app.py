import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="QA Project Dashboard", layout="wide", page_icon="📊")

# -----------------------------------------------------------------------------
# 1. GOOGLE SHEETS CONNECTION & DATA LOADING
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data():
    # Read 'Projects' tab, skipping top 6 header/KPI rows
    projects_raw = conn.read(worksheet="Projects", header=6)
    # Filter out empty rows where Project Name is missing
    df_projects = projects_raw.dropna(subset=["Project Name"]).copy()
    
    # Format dates
    df_projects["Start Date"] = pd.to_datetime(df_projects["Start Date"], errors="coerce")
    df_projects["Completion Date"] = pd.to_datetime(df_projects["Completion Date"], errors="coerce")

    # Read 'Ratings' tab, skipping top 6 header/KPI rows
    ratings_raw = conn.read(worksheet="Ratings", header=6)
    df_ratings = ratings_raw.dropna(subset=["Project Name"]).copy()

    return df_projects, df_ratings

try:
    df_projects, df_ratings = load_data()
except Exception as e:
    st.error(f"Error loading Google Sheets data: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 2. HEADER & TIMEFRAME FILTERS
# -----------------------------------------------------------------------------
st.title("📋 QA Active & Closed Projects Summary")

col_filter1, col_filter2 = st.columns([1, 3])
with col_filter1:
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

# -----------------------------------------------------------------------------
# 3. PROJECT SUMMARY TABLE
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 4. QA SUCCESS RATING SYSTEM & WRITE-BACK
# -----------------------------------------------------------------------------
st.subheader("⭐ QA Rating - Project Success Breakdown")

col_form, col_chart = st.columns([1, 1])

project_list = df_projects["Project Name"].tolist()

with col_form:
    st.markdown("#### Evaluate or Update Project")
    selected_project = st.selectbox("Select Project:", project_list)

    # Extract existing scores for selected project from df_ratings
    project_row = df_ratings[df_ratings["Project Name"] == selected_project]
    
    def get_val(col_name, default=3):
        if not project_row.empty and col_name in project_row.columns:
            val = project_row[col_name].values[0]
            if pd.notna(val):
                try:
                    return int(val)
                except ValueError:
                    return default
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

        submit_button = st.form_submit_button("Sync Rating to Google Sheets")

        if submit_button:
            # Update local dataframe record
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

            # Write back updated table to Google Sheets
            try:
                conn.update(worksheet="Ratings", data=df_ratings)
                st.cache_data.clear()
                st.success(f"Updated Google Sheet for {selected_project}!")
                st.rerun()
            except Exception as err:
                st.error(f"Failed to write to Google Sheets: {err}")

# Right Column: Radar Chart
with col_chart:
    st.markdown(f"#### Performance Radar: **{selected_project}**")
    
    if not project_row.empty:
        categories = ["Documents Provided", "Robot Availability", "Bundle Preparation", "Software Support"]
        scores = [get_val(cat) for cat in categories]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=scores + [scores[0]],
            theta=categories + [categories[0]],
            fill='toself',
            name=selected_project,
            line_color='#0068c9'
        ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
            showlegend=False,
            margin=dict(l=40, r=40, t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No rating record found for this project in the sheet.")