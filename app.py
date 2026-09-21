import streamlit as st
import pandas as pd
import plotly.express as px

# Page configuration
st.set_page_config(
    page_title="QA Project Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("QA Project Insights Dashboard")

# Navigation Tabs
tab1, tab2 = st.tabs(["📋 Summary & QA Ratings", "📈 Testing Metrics & Estimation"])

with tab1:
    st.header("Active & Closed Projects Summary")
    
    # Filter Controls
    col1, col2 = st.columns([1, 3])
    with col1:
        time_range = st.radio("Select Timeframe:", ["3 Months", "6 Months", "9 Months", "All"])
    
    st.info("Project table and rating form will render here.")

with tab2:
    st.header("Estimation vs. Actual Performance")
    st.info("Plotly estimation and bug tracking charts will render here.")