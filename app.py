import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="QA Project Dashboard", layout="wide", page_icon="📊")

# -----------------------------------------------------------------------------
# 1. READ-ONLY DATA LOADER (FETCHES PROJECTS, RATINGS, DEFECTS, T2, & T2 RATINGS)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data():
    def fetch_sheet(worksheet_name, subset_col="Project Name"):
        df = conn.read(worksheet=worksheet_name, header=6)
        
        # Clean column names
        df.columns = df.columns.astype(str).str.replace('\xa0', ' ').str.strip()
        
        # Drop empty/unnamed columns
        df = df.loc[:, ~df.columns.str.lower().str.startswith("unnamed")]
        df = df.loc[:, ~df.columns.str.lower().str.startswith("nan")]
        
        # Filter out empty or invalid project/ticket rows based on the specific tab's primary key
        if subset_col in df.columns:
            df = df.dropna(subset=[subset_col]).copy()
            df[subset_col] = df[subset_col].astype(str).str.strip()
            df = df[~df[subset_col].str.lower().isin(["nan", "none", "", "null"])]
        
        return df

    # Fetch existing tabs using standard 'Project Name'
    df_projects = fetch_sheet("Projects")
    df_ratings = fetch_sheet("Ratings")
    
    # Try fetching Defects tab
    try:
        df_defects = fetch_sheet("Defects")
    except Exception:
        df_defects = pd.DataFrame(columns=["Project Name"])

    # Try fetching the new T2 tab using 'T2 Ticket'
    try:
        df_t2 = fetch_sheet("T2", subset_col="T2 Ticket")
    except Exception:
        df_t2 = pd.DataFrame(columns=["T2 Ticket", "Start Date", "Completion Date"])
        
    # Fetch the new T2 Ratings tab using 'T2 Ticket'
    try:
        df_t2_ratings = fetch_sheet("T2 Ratings", subset_col="T2 Ticket")
    except Exception:
        df_t2_ratings = pd.DataFrame(columns=["T2 Ticket"])

    # Standardize release candidate estimate column name if spelled out in Projects
    df_projects = df_projects.rename(columns={
        "QA Estimate release candidate Dependant": "QA Estimate rc Dependant",
        "QA Estimate Release Candidate Dependant": "QA Estimate rc Dependant"
    })

    # Standardize release candidate estimate column name in T2 (just in case)
    df_t2 = df_t2.rename(columns={
        "QA Estimate release candidate Dependant": "QA Estimate rc Dependant",
        "QA Estimate Release Candidate Dependant": "QA Estimate rc Dependant"
    })

    # Format Dates safely for Projects
    if "Start Date" in df_projects.columns:
        df_projects["Start Date"] = pd.to_datetime(df_projects["Start Date"], errors="coerce")
    if "Completion Date" in df_projects.columns:
        df_projects["Completion Date"] = pd.to_datetime(df_projects["Completion Date"], errors="coerce")
        
    # Format Dates safely for T2
    if "Start Date" in df_t2.columns:
        df_t2["Start Date"] = pd.to_datetime(df_t2["Start Date"], errors="coerce")
    if "Completion Date" in df_t2.columns:
        df_t2["Completion Date"] = pd.to_datetime(df_t2["Completion Date"], errors="coerce")

    # Merge Release Candidates count from Ratings sheet into Projects if missing
    if "Number of Release Candidates" in df_ratings.columns:
        if "Project Name" in df_ratings.columns:
            rc_data_proj = df_ratings[["Project Name", "Number of Release Candidates"]].drop_duplicates(subset=["Project Name"])
            if "Number of Release Candidates" not in df_projects.columns:
                df_projects = pd.merge(df_projects, rc_data_proj, on="Project Name", how="left")
                
    # Merge Release Candidates count from T2 Ratings sheet into T2 if missing
    if "Number of Release Candidates" in df_t2_ratings.columns:
        if "T2 Ticket" in df_t2_ratings.columns:
            rc_data_t2 = df_t2_ratings[["T2 Ticket", "Number of Release Candidates"]].drop_duplicates(subset=["T2 Ticket"])
            if "Number of Release Candidates" not in df_t2.columns:
                df_t2 = pd.merge(df_t2, rc_data_t2, on="T2 Ticket", how="left")

    # Coerce numeric floating-point fields in Projects (Round to 1 decimal)
    float_cols = ["Estimated QA Days", "Actual QA Days", "QA Estimate rc Dependant"]
    for col in float_cols:
        if col in df_projects.columns:
            df_projects[col] = pd.to_numeric(df_projects[col], errors="coerce").fillna(0.0).round(1)
        else:
            df_projects[col] = 0.0
            
        if col in df_t2.columns:
            df_t2[col] = pd.to_numeric(df_t2[col], errors="coerce").fillna(0.0).round(1)
        else:
            df_t2[col] = 0.0

    # Coerce integer count fields (cast to whole numbers)
    int_cols = ["Number of Release Candidates", "Bugs Reported", "Bugs Resolved", "Number of Welds Tested", "Number of Tracers"]
    for col in int_cols:
        if col in df_projects.columns:
            df_projects[col] = pd.to_numeric(df_projects[col], errors="coerce").fillna(0).astype(int)
        else:
            df_projects[col] = 0
            
        if col in df_t2.columns:
            df_t2[col] = pd.to_numeric(df_t2[col], errors="coerce").fillna(0).astype(int)
        else:
            df_t2[col] = 0

    # Coerce numeric fields in Defects sheet
    defect_list = [
        "Leg Size (under/over)", "Undercut", "Lack of Penetration", 
        "Lack of Fusion", "Underfill", "Cracking", "Porosity", 
        "Burn Through", "Bead Position", "Inclusion", "Excessive Reinforcement"
    ]
    weld_cols = ["Welds Passed", "Welds Failed"] + defect_list

    for col in weld_cols:
        if col in df_defects.columns:
            df_defects[col] = pd.to_numeric(df_defects[col], errors="coerce").fillna(0).astype(int)
        else:
            df_defects[col] = 0

    return df_projects, df_ratings, df_defects, df_t2, df_t2_ratings

try:
    df_projects, df_ratings, df_defects, df_t2, df_t2_ratings = load_data()
except Exception as e:
    st.error(f"Error loading dashboard data: {e}")
    st.stop()

# Helper function to format rating values or show "N/A" for blank cells
def fmt_rating(val):
    try:
        num = float(val)
        if pd.notnull(num):
            return f"{num:.1f} / 10" if num % 1 != 0 else f"{int(num)} / 10"
    except (ValueError, TypeError):
        pass
    return "N/A"

# -----------------------------------------------------------------------------
# 2. SIDEBAR REFRESH & TAB NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.title("QA Dashboard")
if st.sidebar.button("🔄 Refresh Data from Sheet"):
    st.cache_data.clear()
    st.rerun()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📋 Summary & QA Ratings", 
    "📈 Testing Estimation vs Actuals", 
    "🐞 Bug Tracking",
    "🔬 Welding & Defect Metrics",
    "⚠️ T2 Support & Ratings",
    "🚦 QA Bandwidth"
])

# =============================================================================
# REUSABLE FORMAT HELPER
# =============================================================================

def format_radar_layout(fig):
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0, 0, 0, 0)",
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickfont=dict(size=10),
                gridcolor="rgba(128, 128, 128, 0.25)",
            ),
            angularaxis=dict(
                tickfont=dict(size=10),
                gridcolor="rgba(128, 128, 128, 0.25)",
            ),
        ),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        showlegend=False,
        margin=dict(l=40, r=40, t=30, b=30),
    )

# =============================================================================
# TAB 1: SUMMARY & READ-ONLY RATINGS
# =============================================================================
with tab1:
    st.title("📋 Active & Closed Projects Summary")

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
    
    # Exclude Bug metrics from Tab 1 inventory view
    hide_columns = ["Bugs Reported", "Bugs Resolved"]
    cols_to_exclude = [c for c in hide_columns if c in df_filtered.columns]
    df_display = df_filtered.drop(columns=cols_to_exclude).copy()

    # Pre-process URLs so regex extracts custom link text only when a valid URL is present
    def format_release_link(val):
        val_str = str(val).strip()
        if val_str.startswith("http://") or val_str.startswith("https://"):
            if "#" not in val_str:
                return f"{val_str}#Open Release Form 🔗"
        return val_str

    for col_name in ["QA Release Document", "QA Release Form Link"]:
        if col_name in df_display.columns:
            df_display[col_name] = df_display[col_name].apply(format_release_link)

    # Combine Tracers Used (Yes/No) + Number of Tracers if both columns exist
    if "Tracers Used" in df_display.columns and "Number of Tracers" in df_display.columns:
        def format_tracers_combined(row):
            used = str(row["Tracers Used"]).strip()
            count = row["Number of Tracers"]
            if used.lower() == "yes" and count > 0:
                return f"Yes ({count})"
            elif used.lower() == "yes":
                return "Yes"
            return "No"
            
        df_display["Tracers"] = df_display.apply(format_tracers_combined, axis=1)

    # Reorder columns so Plate or Pipe Coupons and Tracers appear directly to the left of the QA Release link column
    link_col_names = ["QA Release Document", "QA Release Form Link"]
    target_link_col = next((c for c in link_col_names if c in df_display.columns), None)
    tracer_cols_to_move = [c for c in ["Plate or Pipe Coupons", "Tracers"] if c in df_display.columns]

    if target_link_col and tracer_cols_to_move:
        remaining_cols = [c for c in df_display.columns if c not in tracer_cols_to_move]
        if target_link_col in remaining_cols:
            idx = remaining_cols.index(target_link_col)
            ordered_cols = remaining_cols[:idx] + tracer_cols_to_move + remaining_cols[idx:]
            df_display = df_display[ordered_cols]

    # Configure columns, strictly enforcing 1 decimal place ("%.1f") on estimation fields
    column_configuration = {
        "Start Date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD"),
        "Completion Date": st.column_config.DateColumn("Completion Date", format="YYYY-MM-DD"),
        "Pre/Robustness": st.column_config.TextColumn("Pre/Robustness", width="large"),
        "Plate or Pipe Coupons": st.column_config.TextColumn("Plate or Pipe Coupons", width="medium"),
        "Tracers": st.column_config.TextColumn("Tracers (Used & Count)", width="medium"),
        "Welding Inspection Required": st.column_config.TextColumn("Welding Req?", width="medium"),
        "Number of Welds Tested": st.column_config.NumberColumn("Number of Welds Tested", format="%d"),
        "Number of Release Candidates": st.column_config.NumberColumn("Number of Release Candidates", format="%d"),
        "Estimated QA Days": st.column_config.NumberColumn("Estimated QA Days", format="%.1f"),
        "Actual QA Days": st.column_config.NumberColumn("Actual QA Days", format="%.1f"),
        "QA Estimate rc Dependant": st.column_config.NumberColumn("QA Estimate rc Dependant", format="%.1f"),
        "QA Estimate release candidate Dependant": st.column_config.NumberColumn("QA Estimate rc Dependant", format="%.1f"),
        "QA Release Document": st.column_config.LinkColumn(
            "QA Release Document",
            display_text=r"#(.*)$",
            width="medium"
        ),
    }

    if "QA Release Form Link" in df_display.columns:
        column_configuration["QA Release Form Link"] = st.column_config.LinkColumn(
            "QA Release Form Link",
            display_text=r"#(.*)$",
            width="medium"
        )

    # Highlight rules for Completed (Green) and Welding Inspection Required = Yes (Orange)
    def highlight_status(val):
        if str(val).strip().lower() == "completed":
            return "background-color: #2e7d32; color: #ffffff; font-weight: bold;"
        return ""

    def highlight_welding(val):
        if str(val).strip().lower() == "yes":
            return "background-color: #e65100; color: #ffffff; font-weight: bold;"
        return ""

    styler = df_display.style
    map_func = getattr(styler, "map", None) or getattr(styler, "applymap", None)

    if map_func:
        if "Status" in df_display.columns:
            styler = map_func(highlight_status, subset=["Status"])
        if "Welding Inspection Required" in df_display.columns:
            styler = map_func(highlight_welding, subset=["Welding Inspection Required"])

    st.dataframe(
        styler,
        column_config=column_configuration,
        width="stretch",
        hide_index=True
    )

    st.divider()

    st.subheader("⭐ QA Rating & Readiness Benchmarks")
    
    project_list = df_projects["Project Name"].tolist()
    selected_project = st.selectbox("Select Project to Inspect Ratings:", project_list)
    
    project_rating_row = df_ratings[df_ratings["Project Name"] == selected_project]
    project_main_row = df_projects[df_projects["Project Name"] == selected_project]

    # Complete 10 rating categories
    categories = [
        "Software Documentation Provided", 
        "Product Documentation Provided", 
        "Robot Availability", 
        "Bundle Preparation", 
        "Software Support",
        "Controls Support",
        "Product Support",
        "Welding Team Performance",
        "Stress on QA Resources",
        "QA Self-Reported Performance"
    ]

    # Process individual scores, safely handling blank (NaN) cells
    valid_scores = []
    radar_r = []

    if not project_rating_row.empty:
        p_data = project_rating_row.iloc[0]
        for cat in categories:
            val = p_data.get(cat, None)
            try:
                num_val = float(val)
                if pd.notnull(num_val):
                    valid_scores.append(num_val)
                    radar_r.append(num_val)
                else:
                    radar_r.append(None)
            except (ValueError, TypeError):
                radar_r.append(None)
        
        # Calculate mean using ONLY non-null valid scores
        proj_overall_avg = (sum(valid_scores) / len(valid_scores)) if valid_scores else 0.0
    else:
        proj_overall_avg = 0.0

    # Dynamic radar threshold coloring
    if proj_overall_avg > 8.8:
        radar_line_color = "#2e7d32"       # Green
        radar_fill_color = "rgba(46, 125, 50, 0.35)"
    elif proj_overall_avg >= 7.2:
        radar_line_color = "#ffb300"       # Yellow/Amber
        radar_fill_color = "rgba(255, 179, 0, 0.35)"
    else:
        radar_line_color = "#d32f2f"       # Red
        radar_fill_color = "rgba(211, 47, 47, 0.35)"

    # --- ROW 1: SELECTED PROJECT METRICS & RADAR CHART ---
    col_proj_metrics, col_proj_chart = st.columns([1, 1])

    with col_proj_metrics:
        st.markdown(f"#### Recorded Scores for **{selected_project}**")
        
        if not project_rating_row.empty:
            p_data = project_rating_row.iloc[0]
            
            m1, m2 = st.columns(2)
            m1.metric("Software Docs Provided", fmt_rating(p_data.get('Software Documentation Provided')))
            m2.metric("Product Docs Provided", fmt_rating(p_data.get('Product Documentation Provided')))
            
            m3, m4 = st.columns(2)
            m3.metric("Robot Availability", fmt_rating(p_data.get('Robot Availability')))
            m4.metric("Bundle Preparation", fmt_rating(p_data.get('Bundle Preparation')))
            
            m5, m6 = st.columns(2)
            m5.metric("Software Support", fmt_rating(p_data.get('Software Support')))
            m6.metric("Controls Support", fmt_rating(p_data.get('Controls Support')))

            m7, m8 = st.columns(2)
            m7.metric("Product Support", fmt_rating(p_data.get('Product Support')))
            m8.metric("Welding Team Perf", fmt_rating(p_data.get('Welding Team Performance')))

            m9, m10 = st.columns(2)
            m9.metric("Stress on QA Resources", fmt_rating(p_data.get('Stress on QA Resources')))
            m10.metric("QA Self-Reported Perf", fmt_rating(p_data.get('QA Self-Reported Performance')))

            m11, m12 = st.columns(2)
            m11.metric("Release Candidates", f"{int(p_data.get('Number of Release Candidates', 0))}")
            m12.metric("Targeted Test Plan", f"{p_data.get('Targeted Test Plan', 'N/A')}")

            st.metric("Overall Average Rating", f"{proj_overall_avg:.1f} / 10" if valid_scores else "N/A")

            # Render action button if a valid URL exists
            release_url = None
            if not project_main_row.empty:
                for link_col in ["QA Release Document", "QA Release Form Link"]:
                    if link_col in project_main_row.columns:
                        val = str(project_main_row.iloc[0][link_col]).strip()
                        if val.startswith("http://") or val.startswith("https://"):
                            release_url = val
                            break

            if release_url:
                st.link_button("📄 Open QA Release Form", release_url, width="stretch")

        else:
            st.warning("No rating record found in the Ratings sheet for this project.")

    with col_proj_chart:
        st.markdown(f"#### {selected_project} Performance Radar")
        if not project_rating_row.empty:
            r_closed = radar_r + [radar_r[0] if radar_r else None]
            theta_closed = categories + [categories[0]]

            fig_radar = go.Figure(
                go.Scatterpolar(
                    r=r_closed,
                    theta=theta_closed,
                    fill="toself",
                    connectgaps=True,
                    name=selected_project,
                    line_color=radar_line_color,
                    fillcolor=radar_fill_color,
                )
            )

            format_radar_layout(fig_radar)
            st.plotly_chart(fig_radar, width="stretch")

        else:
            st.info("No rating data available for this project.")

    st.divider()

    # --- ROW 2: DYNAMIC PORTFOLIO AVERAGE METRICS & RADAR CHART ---
    avg_time_range = st.selectbox(
        "Select Portfolio Benchmark Timeframe:",
        options=["30 Days", "3 Months", "6 Months", "1 Year"],
        index=3
    )

    # Calculate dynamic timeframe cutoff
    if avg_time_range == "30 Days":
        avg_cutoff = today_date - pd.Timedelta(days=30)
    elif avg_time_range == "3 Months":
        avg_cutoff = today_date - pd.Timedelta(days=90)
    elif avg_time_range == "6 Months":
        avg_cutoff = today_date - pd.Timedelta(days=180)
    else:
        avg_cutoff = today_date - pd.Timedelta(days=365)

    recent_project_names = df_projects[df_projects["Start Date"] >= avg_cutoff]["Project Name"].tolist()
    df_ratings_avg = df_ratings[df_ratings["Project Name"].isin(recent_project_names)]

    # Fallback to overall ratings if no projects fall inside the date window
    no_recent_data = False
    if df_ratings_avg.empty:
        df_ratings_avg = df_ratings.copy()
        no_recent_data = True

    col_avg_metrics, col_avg_chart = st.columns([1, 1])

    with col_avg_metrics:
        st.markdown(f"#### Past {avg_time_range} Portfolio Average Scores")
        if no_recent_data:
            st.caption(f"ℹ️ No projects found within the last {avg_time_range}. Displaying overall portfolio averages.")

        def safe_mean(col_name):
            if col_name in df_ratings_avg.columns:
                m = pd.to_numeric(df_ratings_avg[col_name], errors="coerce").mean()
                return f"{m:.1f} / 10" if pd.notnull(m) else "N/A"
            return "N/A"

        a1, a2 = st.columns(2)
        a1.metric("Avg Software Docs", safe_mean('Software Documentation Provided'))
        a2.metric("Avg Product Docs", safe_mean('Product Documentation Provided'))

        a3, a4 = st.columns(2)
        a3.metric("Avg Robot Availability", safe_mean('Robot Availability'))
        a4.metric("Avg Bundle Preparation", safe_mean('Bundle Preparation'))

        a5, a6 = st.columns(2)
        a5.metric("Avg Software Support", safe_mean('Software Support'))
        a6.metric("Avg Controls Support", safe_mean('Controls Support'))

        a7, a8 = st.columns(2)
        a7.metric("Avg Product Support", safe_mean('Product Support'))
        a8.metric("Avg Welding Team Perf", safe_mean('Welding Team Performance'))

        a9, a10 = st.columns(2)
        a9.metric("Avg Stress on QA", safe_mean('Stress on QA Resources'))
        a10.metric("Avg QA Self-Reported Perf", safe_mean('QA Self-Reported Performance'))

        if "Number of Release Candidates" in df_ratings_avg.columns:
            rc_m = pd.to_numeric(df_ratings_avg["Number of Release Candidates"], errors="coerce").mean()
            st.metric("Avg Release Candidates", f"{rc_m:.1f}" if pd.notnull(rc_m) else "N/A")

        # Compute overall portfolio average across all 10 rating factors (ignoring NaN)
        cat_means = []
        for cat in categories:
            if cat in df_ratings_avg.columns:
                m = pd.to_numeric(df_ratings_avg[cat], errors="coerce").mean()
                if pd.notnull(m):
                    cat_means.append(float(m))
        
        portfolio_overall_avg = (sum(cat_means) / len(cat_means)) if cat_means else 0.0

        st.metric("Overall Portfolio Average Rating", f"{portfolio_overall_avg:.1f} / 10" if cat_means else "N/A")

    with col_avg_chart:
        st.markdown(f"#### Past {avg_time_range} Average Performance Radar")
        
        avg_scores = []
        for cat in categories:
            if cat in df_ratings_avg.columns:
                mean_val = pd.to_numeric(df_ratings_avg[cat], errors="coerce").mean()
                avg_scores.append(float(mean_val) if pd.notnull(mean_val) else None)
            else:
                avg_scores.append(None)

        avg_r_closed = avg_scores + [avg_scores[0] if avg_scores else None]
        avg_theta_closed = categories + [categories[0]]

        fig_avg_radar = go.Figure(
            go.Scatterpolar(
                r=avg_r_closed,
                theta=avg_theta_closed,
                fill="toself",
                connectgaps=True,
                name=f"{avg_time_range} Average",
                line_color="#ff9800",
                fillcolor="rgba(255, 152, 0, 0.35)",
            )
        )

        format_radar_layout(fig_avg_radar)
        st.plotly_chart(fig_avg_radar, width="stretch")

# =============================================================================
# TAB 2: ESTIMATION VS ACTUAL DURATION (COMBO CHART)
# =============================================================================
with tab2:
    st.title("📈 Testing Estimation versus Actual Duration")
    st.caption("Blue = Original Estimate, Purple = Days QA spent testing, Green = Original Estimate multiplied by the release candidate (rc) number since a new test iteration is required for each rc")

    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["Estimated QA Days"],
            name="Estimated QA Days",
            marker_color="#29b6f6",
            text=df_projects["Estimated QA Days"],
            textposition="auto"
        ),
        secondary_y=False,
    )

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["Actual QA Days"],
            name="Actual QA Days",
            marker_color="#ab47bc",
            text=df_projects["Actual QA Days"],
            textposition="auto"
        ),
        secondary_y=False,
    )

    fig_combo.add_trace(
        go.Bar(
            x=df_projects["Project Name"],
            y=df_projects["QA Estimate rc Dependant"],
            name="QA Estimate rc Dependant",
            marker_color="#9ccc65",
            text=df_projects["QA Estimate rc Dependant"],
            textposition="auto"
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
        showgrid=True,
        rangemode="tozero"
    )
    fig_combo.update_yaxes(
        title_text="Release Candidates",
        secondary_y=True,
        showgrid=False,
        rangemode="tozero",
        tickformat="d"
    )

    st.plotly_chart(fig_combo, width="stretch")

# =============================================================================
# TAB 3: BUGS REPORTED VS RESOLVED (OVERLAY LOADING BARS)
# =============================================================================
with tab3:
    st.title("🐞 Bugs Reported and Bugs Resolved by Bundle")
    st.caption("Green bars represent the resolved reported bugs during the QA period, the red portion represents the bugs deferred to the next release or unresolved bugs")

    tot_reported = int(df_projects["Bugs Reported"].sum())
    tot_resolved = int(df_projects["Bugs Resolved"].sum())
    res_rate = (tot_resolved / tot_reported * 100) if tot_reported > 0 else 0.0

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Bugs Reported", f"{tot_reported}")
    kpi2.metric("Total Bugs Resolved", f"{tot_resolved}")
    kpi3.metric("Resolution Rate", f"{res_rate:.1f}%")

    st.divider()

    fig_bugs = go.Figure()

    # Maintains 0.5 bar width for both traces
    fig_bugs.add_trace(go.Bar(
        y=df_projects["Project Name"],
        x=df_projects["Bugs Reported"],
        name="Bugs Reported",
        orientation='h',
        marker_color="#ff5722",
        opacity=0.85,
        width=0.5
    ))

    fig_bugs.add_trace(go.Bar(
        y=df_projects["Project Name"],
        x=df_projects["Bugs Resolved"],
        name="Bugs Resolved",
        orientation='h',
        marker_color="#4caf50",
        width=0.5
    ))

    fig_bugs.update_layout(
        barmode="overlay",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        margin=dict(l=20, r=20, t=50, b=20),
        height=600,
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        yaxis=dict(autorange="reversed")
    )

    fig_bugs.update_xaxes(
        showgrid=True,
        rangemode="tozero",
        tickformat="d",
        dtick=1
    )

    st.plotly_chart(fig_bugs, width="stretch")

# =============================================================================
# TAB 4: WELDING PASS/FAIL PERCENTAGES & DEFECT BREAKDOWN (FROM DEFECTS TAB)
# =============================================================================
with tab4:
    st.title("🔬 Welding Inspection & Defect Metrics")
    st.caption("Joint pass/failure percentages and defect cause distribution")

    col_weld_chart, col_defect_chart = st.columns([1, 1])

    # --- LEFT CHART: 100% STACKED PASS/FAIL PERCENTAGES ---
    with col_weld_chart:
        st.subheader("Joint Pass/Failure Percentages")

        df_w = df_defects.copy()

        df_w["Total Welds"] = df_w["Welds Passed"] + df_w["Welds Failed"]
        
        def calc_pass(row):
            return (row["Welds Passed"] / row["Total Welds"] * 100) if row["Total Welds"] > 0 else 0.0

        def calc_fail(row):
            return (row["Welds Failed"] / row["Total Welds"] * 100) if row["Total Welds"] > 0 else 0.0

        df_w["Pass %"] = df_w.apply(calc_pass, axis=1)
        df_w["Fail %"] = df_w.apply(calc_fail, axis=1)

        df_w_active = df_w[df_w["Total Welds"] > 0]

        if not df_w_active.empty:
            fig_100_stack = go.Figure()

            fig_100_stack.add_trace(go.Bar(
                x=df_w_active["Project Name"],
                y=df_w_active["Fail %"],
                name="Fail %",
                marker_color="#d32f2f"
            ))

            fig_100_stack.add_trace(go.Bar(
                x=df_w_active["Project Name"],
                y=df_w_active["Pass %"],
                name="Pass %",
                marker_color="#388e3c"
            ))

            fig_100_stack.update_layout(
                barmode="stack",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0
                ),
                margin=dict(l=20, r=20, t=50, b=20),
                height=500,
                paper_bgcolor="rgba(0, 0, 0, 0)",
                plot_bgcolor="rgba(0, 0, 0, 0)"
            )

            fig_100_stack.update_yaxes(
                title_text="Percentage",
                range=[0, 100],
                ticksuffix="%",
                showgrid=True
            )

            st.plotly_chart(fig_100_stack, width="stretch")
        else:
            st.info("No welding pass/fail records found in the 'Defects' sheet.")

    # --- RIGHT CHART: DEFECT DISTRIBUTION PIE CHART ---
    with col_defect_chart:
        st.subheader("Defect Distribution (Failed Joints)")

        defect_list = [
            "Leg Size (under/over)", "Undercut", "Lack of Penetration", 
            "Lack of Fusion", "Underfill", "Cracking", "Porosity", 
            "Burn Through", "Bead Position", "Inclusion", "Excessive Reinforcement"
        ]

        valid_defects = [c for c in defect_list if c in df_defects.columns]

        if valid_defects:
            defect_totals = df_defects[valid_defects].sum()
            df_defects_summary = pd.DataFrame({
                "Defect Type": defect_totals.index,
                "Count": defect_totals.values
            })

            df_defects_active = df_defects_summary[df_defects_summary["Count"] > 0]

            if not df_defects_active.empty:
                fig_pie = go.Figure(go.Pie(
                    labels=df_defects_active["Defect Type"],
                    values=df_defects_active["Count"],
                    hole=0.35,
                    textinfo="label+percent",
                    marker=dict(colors=[
                        "#e53935", "#8e24aa", "#3949ab", "#039be5", 
                        "#00acc1", "#00897b", "#43a047", "#7cb342", 
                        "#c0ca33", "#fdd835", "#ffb300"
                    ])
                ))

                fig_pie.update_layout(
                    margin=dict(l=20, r=20, t=30, b=20),
                    height=500,
                    paper_bgcolor="rgba(0, 0, 0, 0)",
                    plot_bgcolor="rgba(0, 0, 0, 0)",
                    legend=dict(orientation="h", y=-0.1)
                )

                st.plotly_chart(fig_pie, width="stretch")
            else:
                st.info("No defect occurrences recorded in the 'Defects' sheet yet.")
        else:
            st.info("Defect tracking columns not found in the 'Defects' sheet.")



# =============================================================================
# TAB 5: RATING AND PERFORMANCE OF T2 TICKETS
# =============================================================================
with tab5:
    st.title("⚠️ T2 Performance & Ratings")

    time_range_t2 = st.radio(
        "Select Time Range:",
        options=["3 Months", "6 Months", "9 Months", "All Time"],
        index=3,
        horizontal=True,
        key="tab5_time_range"
    )

    today_date = pd.Timestamp(datetime.today().date())

    # Map df_t2 instead of df_projects
    if time_range_t2 == "3 Months":
        cutoff = today_date - pd.Timedelta(days=90)
        df_filtered_t2 = df_t2[df_t2["Start Date"] >= cutoff]
    elif time_range_t2 == "6 Months":
        cutoff = today_date - pd.Timedelta(days=180)
        df_filtered_t2 = df_t2[df_t2["Start Date"] >= cutoff]
    elif time_range_t2 == "9 Months":
        cutoff = today_date - pd.Timedelta(days=270)
        df_filtered_t2 = df_t2[df_t2["Start Date"] >= cutoff]
    else:
        df_filtered_t2 = df_t2.copy()

    st.subheader("T2 Inventory")
    
    # Exclude Bug metrics from Tab 5 inventory view
    hide_columns = ["Bugs Reported", "Bugs Resolved"]
    cols_to_exclude = [c for c in hide_columns if c in df_filtered_t2.columns]
    df_display_t2 = df_filtered_t2.drop(columns=cols_to_exclude).copy()

    def format_release_link(val):
        val_str = str(val).strip()
        if val_str.startswith("http://") or val_str.startswith("https://"):
            if "#" not in val_str:
                return f"{val_str}#Open Release Form 🔗"
        return val_str

    for col_name in ["QA T2 Release Document", "QA T2 Release Form Link", "QA Release Document"]:
        if col_name in df_display_t2.columns:
            df_display_t2[col_name] = df_display_t2[col_name].apply(format_release_link)

    if "Tracers Used" in df_display_t2.columns and "Number of Tracers" in df_display_t2.columns:
        def format_tracers_combined(row):
            used = str(row["Tracers Used"]).strip()
            count = row["Number of Tracers"]
            if used.lower() == "yes" and count > 0:
                return f"Yes ({count})"
            elif used.lower() == "yes":
                return "Yes"
            return "No"
            
        df_display_t2["Tracers"] = df_display_t2.apply(format_tracers_combined, axis=1)

    link_col_names = ["QA T2 Release Document", "QA T2 Release Form Link", "QA Release Document"]
    target_link_col = next((c for c in link_col_names if c in df_display_t2.columns), None)
    tracer_cols_to_move = [c for c in ["Plate or Pipe Coupons", "Tracers"] if c in df_display_t2.columns]

    if target_link_col and tracer_cols_to_move:
        remaining_cols = [c for c in df_display_t2.columns if c not in tracer_cols_to_move]
        if target_link_col in remaining_cols:
            idx = remaining_cols.index(target_link_col)
            ordered_cols = remaining_cols[:idx] + tracer_cols_to_move + remaining_cols[idx:]
            df_display_t2 = df_display_t2[ordered_cols]

    column_configuration_t2 = {
        "T2 Ticket": st.column_config.TextColumn("T2 Ticket"),
        "Start Date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD"),
        "Completion Date": st.column_config.DateColumn("Completion Date", format="YYYY-MM-DD"),
        "Plate or Pipe Coupons": st.column_config.TextColumn("Plate or Pipe Coupons"),
        "Tracers": st.column_config.TextColumn("Tracers (Used & Count)"),
        "Welding Inspection Required": st.column_config.TextColumn("Welding Req?"),
        "Number of Welds Tested": st.column_config.NumberColumn("Number of Welds Tested", format="%d"),
        "Number of Release Candidates": st.column_config.NumberColumn("Number of Release Candidates", format="%d"),
        "Estimated QA Days": st.column_config.NumberColumn("Estimated QA Days", format="%.1f"),
        "Actual QA Days": st.column_config.NumberColumn("Actual QA Days", format="%.1f"),
        "QA Estimate rc Dependant": st.column_config.NumberColumn("QA Estimate rc Dependant", format="%.1f"),
        "QA T2 Release Document": st.column_config.LinkColumn(
            "QA T2 Release Document",
            display_text=r"#(.*)$"
        ),
        "QA Release Document": st.column_config.LinkColumn(
            "QA Release Document",
            display_text=r"#(.*)$"
        )
    }

    if "QA T2 Release Form Link" in df_display_t2.columns:
        column_configuration_t2["QA T2 Release Form Link"] = st.column_config.LinkColumn(
            "QA T2 Release Form Link",
            display_text=r"#(.*)$"
        )

    def highlight_status(val):
        if str(val).strip().lower() == "completed":
            return "background-color: #2e7d32; color: #ffffff; font-weight: bold;"
        return ""

    def highlight_welding(val):
        if str(val).strip().lower() == "yes":
            return "background-color: #e65100; color: #ffffff; font-weight: bold;"
        return ""

    styler_t2 = df_display_t2.style
    map_func_t2 = getattr(styler_t2, "map", None) or getattr(styler_t2, "applymap", None)

    if map_func_t2:
        if "Status" in df_display_t2.columns:
            styler_t2 = map_func_t2(highlight_status, subset=["Status"])
        if "Welding Inspection Required" in df_display_t2.columns:
            styler_t2 = map_func_t2(highlight_welding, subset=["Welding Inspection Required"])

    st.dataframe(
        styler_t2,
        column_config=column_configuration_t2,
        width="stretch",
        hide_index=True
    )

    st.divider()
    st.subheader("⭐ QA Rating & Readiness Benchmarks")
    
    t2_project_list = df_t2["T2 Ticket"].tolist()
    
    if t2_project_list:
        selected_project_t2 = st.selectbox("Select Project to Inspect Ratings:", t2_project_list, key="tab5_proj_select")
        
        # CHANGED: Now pulling explicitly from df_t2_ratings instead of df_ratings
        project_rating_row_t2 = df_t2_ratings[df_t2_ratings["T2 Ticket"] == selected_project_t2]
        project_main_row_t2 = df_t2[df_t2["T2 Ticket"] == selected_project_t2]

        categories = [
            "Software Documentation Provided", 
            "Product Documentation Provided", 
            "Robot Availability", 
            "Bundle Preparation", 
            "Software Support",
            "Controls Support",
            "Product Support",
            "Welding Team Performance",
            "Stress on QA Resources",
            "QA Self-Reported Performance"
        ]

        valid_scores_t2 = []
        radar_r_t2 = []

        if not project_rating_row_t2.empty:
            p_data_t2 = project_rating_row_t2.iloc[0]
            for cat in categories:
                val = p_data_t2.get(cat, None)
                try:
                    num_val = float(val)
                    if pd.notnull(num_val):
                        valid_scores_t2.append(num_val)
                        radar_r_t2.append(num_val)
                    else:
                        radar_r_t2.append(None)
                except (ValueError, TypeError):
                    radar_r_t2.append(None)
            
            proj_overall_avg_t2 = (sum(valid_scores_t2) / len(valid_scores_t2)) if valid_scores_t2 else 0.0
        else:
            proj_overall_avg_t2 = 0.0

        if proj_overall_avg_t2 > 8.8:
            radar_line_color_t2 = "#2e7d32" 
            radar_fill_color_t2 = "rgba(46, 125, 50, 0.35)"
        elif proj_overall_avg_t2 >= 7.2:
            radar_line_color_t2 = "#ffb300"
            radar_fill_color_t2 = "rgba(255, 179, 0, 0.35)"
        else:
            radar_line_color_t2 = "#d32f2f"
            radar_fill_color_t2 = "rgba(211, 47, 47, 0.35)"

        col_proj_metrics_t2, col_proj_chart_t2 = st.columns([1, 1])

        with col_proj_metrics_t2:
            st.markdown(f"#### Recorded Scores for **{selected_project_t2}**")
            
            if not project_rating_row_t2.empty:
                p_data_t2 = project_rating_row_t2.iloc[0]
                
                m1, m2 = st.columns(2)
                m1.metric("Software Docs Provided", fmt_rating(p_data_t2.get('Software Documentation Provided')))
                m2.metric("Product Docs Provided", fmt_rating(p_data_t2.get('Product Documentation Provided')))
                
                m3, m4 = st.columns(2)
                m3.metric("Robot Availability", fmt_rating(p_data_t2.get('Robot Availability')))
                m4.metric("Bundle Preparation", fmt_rating(p_data_t2.get('Bundle Preparation')))
                
                m5, m6 = st.columns(2)
                m5.metric("Software Support", fmt_rating(p_data_t2.get('Software Support')))
                m6.metric("Controls Support", fmt_rating(p_data_t2.get('Controls Support')))

                m7, m8 = st.columns(2)
                m7.metric("Product Support", fmt_rating(p_data_t2.get('Product Support')))
                m8.metric("Welding Team Perf", fmt_rating(p_data_t2.get('Welding Team Performance')))

                m9, m10 = st.columns(2)
                m9.metric("Stress on QA Resources", fmt_rating(p_data_t2.get('Stress on QA Resources')))
                m10.metric("QA Self-Reported Perf", fmt_rating(p_data_t2.get('QA Self-Reported Performance')))

                m11, m12 = st.columns(2)
                m11.metric("Release Candidates", f"{int(p_data_t2.get('Number of Release Candidates', 0))}")
                m12.metric("Targeted Test Plan", f"{p_data_t2.get('Targeted Test Plan', 'N/A')}")

                st.metric("Overall Average Rating", f"{proj_overall_avg_t2:.1f} / 10" if valid_scores_t2 else "N/A")

                release_url_t2 = None
                if not project_main_row_t2.empty:
                    for link_col in ["QA T2 Release Document", "QA T2 Release Form Link", "QA Release Document"]:
                        if link_col in project_main_row_t2.columns:
                            val = str(project_main_row_t2.iloc[0][link_col]).strip()
                            if val.startswith("http://") or val.startswith("https://"):
                                release_url_t2 = val
                                break

                if release_url_t2:
                    st.link_button("📄 Open QA T2 Release Form", release_url_t2, width="stretch")
            else:
                st.warning("No rating record found in the T2 Ratings sheet for this project.")

        with col_proj_chart_t2:
            st.markdown(f"#### {selected_project_t2} Performance Radar")
            if not project_rating_row_t2.empty:
                r_closed_t2 = radar_r_t2 + [radar_r_t2[0] if radar_r_t2 else None]
                theta_closed_t2 = categories + [categories[0]]

                fig_radar_t2 = go.Figure(
                    go.Scatterpolar(
                        r=r_closed_t2,
                        theta=theta_closed_t2,
                        fill="toself",
                        connectgaps=True,
                        name=selected_project_t2,
                        line_color=radar_line_color_t2,
                        fillcolor=radar_fill_color_t2,
                    )
                ) 

                format_radar_layout(fig_radar_t2)
                st.plotly_chart(fig_radar_t2, width="stretch")

            else:
                st.info("No rating data available for this project.")

        st.divider()

        # --- ROW 2: DYNAMIC PORTFOLIO AVERAGE METRICS & RADAR CHART ---
        avg_time_range_t2 = st.selectbox(
            "Select Portfolio Benchmark Timeframe:",
            options=["30 Days", "3 Months", "6 Months", "1 Year"],
            index=3,
            key="tab5_bench_time"
        )

        if avg_time_range_t2 == "30 Days":
            avg_cutoff_t2 = today_date - pd.Timedelta(days=30)
        elif avg_time_range_t2 == "3 Months":
            avg_cutoff_t2 = today_date - pd.Timedelta(days=90)
        elif avg_time_range_t2 == "6 Months":
            avg_cutoff_t2 = today_date - pd.Timedelta(days=180)
        else:
            avg_cutoff_t2 = today_date - pd.Timedelta(days=365)

        recent_t2_project_names = df_t2[df_t2["Start Date"] >= avg_cutoff_t2]["T2 Ticket"].tolist()
        
        # CHANGED: Now pulling explicitly from df_t2_ratings instead of df_ratings
        df_ratings_avg_t2 = df_t2_ratings[df_t2_ratings["T2 Ticket"].isin(recent_t2_project_names)]

        no_recent_data_t2 = False
        if df_ratings_avg_t2.empty:
            df_ratings_avg_t2 = df_t2_ratings[df_t2_ratings["T2 Ticket"].isin(t2_project_list)].copy()
            no_recent_data_t2 = True

        col_avg_metrics_t2, col_avg_chart_t2 = st.columns([1, 1])

        with col_avg_metrics_t2:
            st.markdown(f"#### Past {avg_time_range_t2} T2 Average Scores")
            if no_recent_data_t2:
                st.caption(f"ℹ️ No projects found within the last {avg_time_range_t2}. Displaying overall T2 averages.")

            def safe_mean_t2(col_name):
                if col_name in df_ratings_avg_t2.columns:
                    m = pd.to_numeric(df_ratings_avg_t2[col_name], errors="coerce").mean()
                    return f"{m:.1f} / 10" if pd.notnull(m) else "N/A"
                return "N/A"

            a1, a2 = st.columns(2)
            a1.metric("Avg Software Docs", safe_mean_t2('Software Documentation Provided'))
            a2.metric("Avg Product Docs", safe_mean_t2('Product Documentation Provided'))

            a3, a4 = st.columns(2)
            a3.metric("Avg Robot Availability", safe_mean_t2('Robot Availability'))
            a4.metric("Avg Bundle Preparation", safe_mean_t2('Bundle Preparation'))

            a5, a6 = st.columns(2)
            a5.metric("Avg Software Support", safe_mean_t2('Software Support'))
            a6.metric("Avg Controls Support", safe_mean_t2('Controls Support'))

            a7, a8 = st.columns(2)
            a7.metric("Avg Product Support", safe_mean_t2('Product Support'))
            a8.metric("Avg Welding Team Perf", safe_mean_t2('Welding Team Performance'))

            a9, a10 = st.columns(2)
            a9.metric("Avg Stress on QA", safe_mean_t2('Stress on QA Resources'))
            a10.metric("Avg QA Self-Reported Perf", safe_mean_t2('QA Self-Reported Performance'))

            if "Number of Release Candidates" in df_ratings_avg_t2.columns:
                rc_m_t2 = pd.to_numeric(df_ratings_avg_t2["Number of Release Candidates"], errors="coerce").mean()
                st.metric("Avg Release Candidates", f"{rc_m_t2:.1f}" if pd.notnull(rc_m_t2) else "N/A")

            cat_means_t2 = []
            for cat in categories:
                if cat in df_ratings_avg_t2.columns:
                    m = pd.to_numeric(df_ratings_avg_t2[cat], errors="coerce").mean()
                    if pd.notnull(m):
                        cat_means_t2.append(float(m))
            
            portfolio_overall_avg_t2 = (sum(cat_means_t2) / len(cat_means_t2)) if cat_means_t2 else 0.0
            st.metric("Overall T2 Average Rating", f"{portfolio_overall_avg_t2:.1f} / 10" if cat_means_t2 else "N/A")

        with col_avg_chart_t2:
            st.markdown(f"#### Past {avg_time_range_t2} T2 Performance Radar")
            
            avg_scores_t2 = []
            for cat in categories:
                if cat in df_ratings_avg_t2.columns:
                    mean_val = pd.to_numeric(df_ratings_avg_t2[cat], errors="coerce").mean()
                    avg_scores_t2.append(float(mean_val) if pd.notnull(mean_val) else None)
                else:
                    avg_scores_t2.append(None)

            avg_r_closed_t2 = avg_scores_t2 + [avg_scores_t2[0] if avg_scores_t2 else None]
            avg_theta_closed_t2 = categories + [categories[0]]

            fig_avg_radar_t2 = go.Figure(
                go.Scatterpolar(
                    r=avg_r_closed_t2,
                    theta=avg_theta_closed_t2,
                    fill="toself",
                    connectgaps=True,
                    name=f"{avg_time_range_t2} Average",
                    line_color="#ff9800",
                    fillcolor="rgba(255, 152, 0, 0.35)",
                )
            )

            format_radar_layout(fig_avg_radar_t2)
            st.plotly_chart(fig_avg_radar_t2, width="stretch")

    else:
        st.info("No T2 data available yet in the spreadsheet.")


# =============================================================================
# TAB 6: QA BANDWIDTH GAUGE (IN PROGRESS WORKLOAD)
# =============================================================================
with tab6:
    st.title("🚦 QA Bandwidth")
    st.caption("Active project load across the QA team based strictly on 'In Progress' status.")

    # 1. Filter Specifically for 'In Progress' Projects
    if "Status" in df_projects.columns:
        in_progress_df = df_projects[df_projects["Status"].astype(str).str.strip().str.lower() == "in progress"]
        in_progress_count = len(in_progress_df)
    else:
        st.warning("⚠️ 'Status' column not found in Projects sheet. Defaulting count to 0.")
        in_progress_count = 0
        in_progress_df = pd.DataFrame()

    # 2. Dynamic Warning Banners (Green: 0-2, Orange: 3-4, Red: 5+)
    if in_progress_count >= 5:
        st.error(f"🚨 **HIGH BANDWIDTH WARNING:** The QA team currently has {in_progress_count} projects 'In Progress'. Approaching maximum capacity.")
    elif in_progress_count >= 3:
        st.warning(f"⚠️ **MODERATE BANDWIDTH:** The QA team currently has {in_progress_count} projects 'In Progress'.")

    # Scale max to 7 (or in_progress_count if it exceeds 7)
    gauge_max = max(7, in_progress_count)
    val_clamped = min(in_progress_count, gauge_max)

    # 3. Mathematical Geometry Setup
    import numpy as np

    fig_gauge = go.Figure()

    r_outer = 1.0
    r_inner = 0.65
    r_needle = 0.90

    def create_arc_polygon(v_start, v_end, max_v, r_in, r_out, steps=40):
        t_start = np.pi - (v_start / max_v) * np.pi
        t_end = np.pi - (v_end / max_v) * np.pi
        angles = np.linspace(t_start, t_end, steps)
        
        x_out = r_out * np.cos(angles)
        y_out = r_out * np.sin(angles)
        x_in = r_in * np.cos(angles[::-1])
        y_in = r_in * np.sin(angles[::-1])
        
        return np.concatenate([x_out, x_in, [x_out[0]]]), np.concatenate([y_out, y_in, [y_out[0]]])

    # 4. Proportional 3-Color Zones (0-3 Green, 3-5 Orange, 5-7 Red)
    zones = [
        (0, 3, "rgba(76, 175, 80, 0.65)"),        # Green: 0-3
        (3, 5, "rgba(255, 152, 0, 0.70)"),       # Orange: 3-5
        (5, gauge_max, "rgba(244, 67, 54, 0.75)") # Red: 5-7
    ]

    for z_start, z_end, z_color in zones:
        if z_start < gauge_max:
            actual_end = min(z_end, gauge_max)
            x_band, y_band = create_arc_polygon(z_start, actual_end, gauge_max, r_inner, r_outer)
            fig_gauge.add_trace(go.Scatter(
                x=x_band,
                y=y_band,
                fill="toself",
                fillcolor=z_color,
                line=dict(color="rgba(0,0,0,0.15)", width=1),
                hoverinfo="none",
                showlegend=False,
                mode="lines"
            ))

    # 5. Draw Ticks & Numeric Labels (0 to 7)
    for i in range(gauge_max + 1):
        th = np.pi - (i / gauge_max) * np.pi
        x0, y0 = r_outer * np.cos(th), r_outer * np.sin(th)
        x1, y1 = (r_outer + 0.04) * np.cos(th), (r_outer + 0.04) * np.sin(th)
        
        fig_gauge.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode="lines",
            line=dict(color="rgba(160, 160, 160, 0.7)", width=1.5),
            hoverinfo="none",
            showlegend=False
        ))
        
        label_r = r_outer + 0.12
        fig_gauge.add_annotation(
            x=label_r * np.cos(th),
            y=label_r * np.sin(th),
            text=str(i),
            showarrow=False,
            font=dict(size=14, color="#AAAAAA", family="Arial")
        )

    # 6. Draw Triangular Needle
    theta_needle = np.pi - (val_clamped / gauge_max) * np.pi

    tip_x = r_needle * np.cos(theta_needle)
    tip_y = r_needle * np.sin(theta_needle)

    w_base = 0.035
    b1_x = w_base * np.cos(theta_needle - np.pi / 2)
    b1_y = w_base * np.sin(theta_needle - np.pi / 2)
    b2_x = w_base * np.cos(theta_needle + np.pi / 2)
    b2_y = w_base * np.sin(theta_needle + np.pi / 2)

    fig_gauge.add_trace(go.Scatter(
        x=[b1_x, tip_x, b2_x, b1_x],
        y=[b1_y, tip_y, b2_y, b1_y],
        fill="toself",
        fillcolor="#D32F2F",
        line=dict(color="#B71C1C", width=1),
        hoverinfo="none",
        showlegend=False,
        mode="lines"
    ))

    # 7. Draw Pivot Hub Circle at (0, 0)
    hub_angles = np.linspace(0, 2 * np.pi, 30)
    hub_r = 0.065
    fig_gauge.add_trace(go.Scatter(
        x=hub_r * np.cos(hub_angles),
        y=hub_r * np.sin(hub_angles),
        fill="toself",
        fillcolor="#1E1E1E",
        line=dict(color="#333333", width=2),
        hoverinfo="none",
        showlegend=False,
        mode="lines"
    ))

    # 8. Titles and Digital Readout
    fig_gauge.add_annotation(
        x=0, y=1.28,
        text="<b>Projects In Progress</b>",
        showarrow=False,
        font=dict(size=20, color="#FAFAFA", family="Arial")
    )

    fig_gauge.add_annotation(
        x=0, y=-0.22,
        text=f"<span style='font-size:26px; font-weight:800; color:#FFFFFF;'>{in_progress_count}</span> <span style='font-size:12px; color:#AAAAAA; font-weight:600;'>IN PROGRESS</span>",
        showarrow=False,
        bgcolor="#15171C",
        bordercolor="#3E424B",
        borderwidth=1.5,
        borderpad=7,
        align="center"
    )

    # 9. Lock 1:1 Aspect Ratio
    fig_gauge.update_xaxes(range=[-1.25, 1.25], visible=False, scaleanchor="y", scaleratio=1)
    fig_gauge.update_yaxes(range=[-0.45, 1.40], visible=False)

    fig_gauge.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=450,
        margin=dict(l=20, r=20, t=10, b=10)
    )

    # 10. Render Layout (Dial Gauge + Full Categorized Status Inventory)
    col_gauge, col_list = st.columns([1.3, 1])

    with col_gauge:
        st.plotly_chart(fig_gauge, width="stretch")

    with col_list:
        st.subheader("All Projects by Status")

        if "Status" in df_projects.columns and not df_projects.empty:
            df_status_view = df_projects.dropna(subset=["Status"]).copy()
            
            # Stringify remaining values safely
            df_status_view["Clean_Status"] = df_status_view["Status"].astype(str).str.strip()

            # Remove explicitly "stringified" nulls so they aren't generated as a category
            valid_statuses = [
                s for s in df_status_view["Clean_Status"].unique() 
                if str(s).lower() not in ['nan', 'none', '<na>', '']
            ]

            
            def status_sort_key(status_name):
                if pd.isna(status_name):
                    return (3, "")
                s = str(status_name).strip().lower()
                if s == "in progress":
                    return (0, s)
                elif s == "completed":
                    return (2, s)
                return (1, s)

            unique_statuses = sorted(valid_statuses, key=status_sort_key)

            for status in unique_statuses:
                group = df_status_view[df_status_view["Clean_Status"] == status]
                is_in_progress = status.lower() == "in progress"

                # Expand 'In Progress' by default; keep other statuses collapsible
                with st.expander(f"**{status}** ({len(group)})", expanded=is_in_progress):
                    for _, row in group.iterrows():
                        proj_name = row.get("Project Name", "Unnamed")
                        if is_in_progress:
                            st.markdown(f"- :orange[**{proj_name}**]")
                        elif status.lower() == "completed":
                            st.markdown(f"- :green[{proj_name}]")
                        else:
                            st.markdown(f"- {proj_name}")
        else:
            st.info("No projects or status values found.")