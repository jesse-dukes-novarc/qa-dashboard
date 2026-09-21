import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="QA Project Dashboard", layout="wide", page_icon="📊")

# -----------------------------------------------------------------------------
# 1. MOCK DATA INITIALIZATION
# -----------------------------------------------------------------------------
@st.cache_data
def get_sample_project_data():
    today = datetime.today()
    projects = [
        {
            "Project Name": "2F ABB",
            "Status": "Closed",
            "Start Date": (today - timedelta(days=110)).date(),
            "Completion Date": (today - timedelta(days=20)).date(),
            "Pre/Robustness": "Robustness",
            "Welding Inspection Required": True,
            "Number of Welds Tested": 45,
            "QA Release Document": "https://example.com/docs/2f-abb"
        },
        {
            "Project Name": "NovHub 4.1.0",
            "Status": "Active",
            "Start Date": (today - timedelta(days=60)).date(),
            "Completion Date": None,
            "Pre/Robustness": "Pre-Robustness",
            "Welding Inspection Required": False,
            "Number of Welds Tested": 0,
            "QA Release Document": "https://example.com/docs/novhub"
        },
        {
            "Project Name": "MIG Auto 1.3",
            "Status": "Closed",
            "Start Date": (today - timedelta(days=220)).date(),
            "Completion Date": (today - timedelta(days=150)).date(),
            "Pre/Robustness": "Robustness",
            "Welding Inspection Required": True,
            "Number of Welds Tested": 110,
            "QA Release Document": "https://example.com/docs/mig-auto"
        },
        {
            "Project Name": "NovSync 2.0",
            "Status": "Active",
            "Start Date": (today - timedelta(days=25)).date(),
            "Completion Date": None,
            "Pre/Robustness": "Pre-Robustness",
            "Welding Inspection Required": True,
            "Number of Welds Tested": 15,
            "QA Release Document": "https://example.com/docs/novsync"
        }
    ]
    return pd.DataFrame(projects)

# Session state to store ratings temporarily in memory
if "ratings_db" not in st.session_state:
    st.session_state.ratings_db = {
        "2F ABB": {
            "Documents Provided": 4,
            "Robot Availability": 5,
            "Bundle Preparation": 3,
            "Software Support": 4,
            "Number of Release Candidates": 2,
            "Targeted Test Plan": 5
        }
    }

df_projects = get_sample_project_data()

# -----------------------------------------------------------------------------
# 2. HEADER & TIMEFRAME FILTERS
# -----------------------------------------------------------------------------
st.title("📋 QA Active & Closed Projects Summary")

col_filter1, col_filter2 = st.columns([1, 3])
with col_filter1:
    time_range = st.radio(
        "Select Time Range:",
        options=["3 Months", "6 Months", "9 Months", "All Time"],
        index=1,
        horizontal=True
    )

# Filter Logic based on Start Date
today_date = datetime.today().date()
if time_range == "3 Months":
    cutoff = today_date - timedelta(days=90)
    df_filtered = df_projects[df_projects["Start Date"] >= cutoff]
elif time_range == "6 Months":
    cutoff = today_date - timedelta(days=180)
    df_filtered = df_projects[df_projects["Start Date"] >= cutoff]
elif time_range == "9 Months":
    cutoff = today_date - timedelta(days=270)
    df_filtered = df_projects[df_projects["Start Date"] >= cutoff]
else:
    df_filtered = df_projects.copy()

# -----------------------------------------------------------------------------
# 3. PROJECT SUMMARY TABLE (WITH HYPERLINKS)
# -----------------------------------------------------------------------------
st.subheader("Project Inventory")

# Customizing display table with clickable links
st.dataframe(
    df_filtered,
    column_config={
        "QA Release Document": st.column_config.LinkColumn(
            "QA Release Document",
            display_text="View Document 🔗"
        ),
        "Start Date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD"),
        "Completion Date": st.column_config.DateColumn("Completion Date", format="YYYY-MM-DD"),
        "Welding Inspection Required": st.column_config.CheckboxColumn("Welding Req?"),
    },
    use_container_width=True,
    hide_index=True
)

st.divider()

# -----------------------------------------------------------------------------
# 4. QA SUCCESS RATING SYSTEM
# -----------------------------------------------------------------------------
st.subheader("⭐ QA Rating - Success Rating Per Specific Project")

col_form, col_chart = st.columns([1, 1])

# Left Column: Post-Project Evaluation Form
with col_form:
    st.markdown("#### Submit Project Evaluation")
    completed_projects = df_projects["Project Name"].tolist()
    selected_project = st.selectbox("Select Project to Rate/View:", completed_projects)
    
    # Retrieve existing rating if available
    existing = st.session_state.ratings_db.get(selected_project, {})

    with st.form("rating_form"):
        docs_score = st.slider("Documents Provided", 1, 5, existing.get("Documents Provided", 3))
        robot_score = st.slider("Robot Availability", 1, 5, existing.get("Robot Availability", 3))
        bundle_score = st.slider("Bundle Preparation", 1, 5, existing.get("Bundle Preparation", 3))
        software_score = st.slider("Software Support", 1, 5, existing.get("Software Support", 3))
        rc_score = st.slider("Number of Release Candidates", 1, 5, existing.get("Number of Release Candidates", 3))
        test_plan_score = st.slider("Targeted Test Plan", 1, 5, existing.get("Targeted Test Plan", 3))
        
        submit_button = st.form_submit_button("Save Rating")
        
        if submit_button:
            st.session_state.ratings_db[selected_project] = {
                "Documents Provided": docs_score,
                "Robot Availability": robot_score,
                "Bundle Preparation": bundle_score,
                "Software Support": software_score,
                "Number of Release Candidates": rc_score,
                "Targeted Test Plan": test_plan_score
            }
            st.success(f"Rating updated for {selected_project}!")
            st.rerun()

# Right Column: Radar Chart Visualization
with col_chart:
    st.markdown(f"#### Performance Breakdown: **{selected_project}**")
    
    current_rating = st.session_state.ratings_db.get(selected_project)
    
    if current_rating:
        categories = list(current_rating.keys())
        values = list(current_rating.values())
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]],  # Close the radar loop
            theta=categories + [categories[0]],
            fill='toself',
            name=selected_project,
            line_color='#1f77b4'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 5])
            ),
            showlegend=False,
            margin=dict(l=40, r=40, t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No rating submitted for this project yet. Fill out the form on the left to generate the radar chart.")