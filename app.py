import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="QA Project Dashboard", layout="wide", page_icon="📊")

# -----------------------------------------------------------------------------
# 1. READ-ONLY DATA LOADER (FETCHES PROJECTS, RATINGS & DEFECTS TABS)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data():
    def fetch_sheet(worksheet_name):
        df = conn.read(worksheet=worksheet_name, header=6)
        
        # Clean column names
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
    
    # Try fetching Defects tab
    try:
        df_defects = fetch_sheet("Defects")
    except Exception:
        df_defects = pd.DataFrame(columns=["Project Name"])

    # Format Dates safely
    if "Start Date" in df_projects.columns:
        df_projects["Start Date"] = pd.to_datetime(df_projects["Start Date"], errors="coerce")
    if "Completion Date" in df_projects.columns:
        df_projects["Completion Date"] = pd.to_datetime(df_projects["Completion Date"], errors="coerce")

    # Merge Release Candidates count from Ratings sheet if not in Projects
    if "Number of Release Candidates" in df_ratings.columns and "Number of Release Candidates" not in df_projects.columns:
        rc_data = df_ratings[["Project Name", "Number of Release Candidates"]].drop_duplicates(subset=["Project Name"])
        df_projects = pd.merge(df_projects, rc_data, on="Project Name", how="left")

    # Coerce numeric floating-point fields in Projects
    float_cols = ["Estimated QA Days", "Actual QA Days", "QA Estimate rc Dependant"]
    for col in float_cols:
        if col in df_projects.columns:
            df_projects[col] = pd.to_numeric(df_projects[col], errors="coerce").fillna(0.0)
        else:
            df_projects[col] = 0.0

    # Coerce integer count fields in Projects (cast to whole numbers)
    int_cols = ["Number of Release Candidates", "Bugs Reported", "Bugs Resolved", "Number of Welds Tested", "Number of Tracers"]
    for col in int_cols:
        if col in df_projects.columns:
            df_projects[col] = pd.to_numeric(df_projects[col], errors="coerce").fillna(0).astype(int)
        else:
            df_projects[col] = 0

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

    return df_projects, df_ratings, df_defects

try:
    df_projects, df_ratings, df_defects = load_data()
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

tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Summary & QA Ratings", 
    "📈 Testing Estimation vs Actuals", 
    "🐞 Bug Tracking",
    "🔬 Welding & Defect Metrics"
])

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
    
    # Exclude Bug metrics and Duration metrics from Tab 1 inventory view
    hide_columns = [
        "Bugs Reported", "Bugs Resolved", 
        "Estimated QA Days", "Actual QA Days", "QA Estimate rc Dependant"
    ]
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

    # Configure columns
    column_configuration = {
        "Start Date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD"),
        "Completion Date": st.column_config.DateColumn("Completion Date", format="YYYY-MM-DD"),
        "Pre/Robustness": st.column_config.TextColumn("Pre/Robustness", width="large"),
        "Plate or Pipe Coupons": st.column_config.TextColumn("Plate or Pipe Coupons", width="medium"),
        "Tracers": st.column_config.TextColumn("Tracers (Used & Count)", width="medium"),
        "Welding Inspection Required": st.column_config.TextColumn("Welding Req?", width="medium"),
        "Number of Welds Tested": st.column_config.NumberColumn("Number of Welds Tested", format="%d"),
        "Number of Release Candidates": st.column_config.NumberColumn("Number of Release Candidates", format="%d"),
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

    categories = [
        "Software Documentation Provided", 
        "Product Documentation Provided", 
        "Robot Availability", 
        "Bundle Preparation", 
        "Software Support"
    ]

    # --- ROW 1: SELECTED PROJECT METRICS & RADAR CHART ---
    col_proj_metrics, col_proj_chart = st.columns([1, 1])

    with col_proj_metrics:
        st.markdown(f"#### Recorded Scores for **{selected_project}**")
        
        if not project_rating_row.empty:
            p_data = project_rating_row.iloc[0]
            
            m1, m2 = st.columns(2)
            m1.metric("Software Docs Provided", f"{p_data.get('Software Documentation Provided', 'N/A')} / 5")
            m2.metric("Product Docs Provided", f"{p_data.get('Product Documentation Provided', 'N/A')} / 5")
            
            m3, m4 = st.columns(2)
            m3.metric("Robot Availability", f"{p_data.get('Robot Availability', 'N/A')} / 5")
            m4.metric("Bundle Preparation", f"{p_data.get('Bundle Preparation', 'N/A')} / 5")
            
            m5, m6 = st.columns(2)
            m5.metric("Software Support", f"{p_data.get('Software Support', 'N/A')} / 5")
            m6.metric("Release Candidates", f"{int(p_data.get('Number of Release Candidates', 0))}")
            
            st.metric("Targeted Test Plan", f"{p_data.get('Targeted Test Plan', 'N/A')}")

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
            scores = []
            for cat in categories:
                val = project_rating_row.iloc[0].get(cat, 0)
                try: 
                    scores.append(float(val))
                except (ValueError, TypeError): 
                    scores.append(0.0)

            fig_radar = go.Figure(go.Scatterpolar(
                r=scores + [scores[0]],
                theta=categories + [categories[0]],
                fill='toself',
                name=selected_project,
                line_color='#0068c9'
            ))

            fig_radar.update_layout(
                polar=dict(
                    bgcolor="white",
                    radialaxis=dict(
                        visible=True,
                        range=[0, 5],
                        tickfont=dict(color="black", size=10),
                        gridcolor="#d3d3d3"
                    ),
                    angularaxis=dict(
                        tickfont=dict(color="white", size=10),
                        gridcolor="#444444"
                    )
                ),
                paper_bgcolor="rgba(0, 0, 0, 0)",
                plot_bgcolor="rgba(0, 0, 0, 0)",
                showlegend=False,
                margin=dict(l=40, r=40, t=30, b=30)
            )

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
                return f"{m:.1f}" if pd.notnull(m) else "N/A"
            return "N/A"

        a1, a2 = st.columns(2)
        a1.metric("Avg Software Docs", f"{safe_mean('Software Documentation Provided')} / 5")
        a2.metric("Avg Product Docs", f"{safe_mean('Product Documentation Provided')} / 5")

        a3, a4 = st.columns(2)
        a3.metric("Avg Robot Availability", f"{safe_mean('Robot Availability')} / 5")
        a4.metric("Avg Bundle Preparation", f"{safe_mean('Bundle Preparation')} / 5")

        a5, a6 = st.columns(2)
        a5.metric("Avg Software Support", f"{safe_mean('Software Support')} / 5")
        a6.metric("Avg Release Candidates", f"{safe_mean('Number of Release Candidates')}")

    with col_avg_chart:
        st.markdown(f"#### Past {avg_time_range} Average Performance Radar")
        
        avg_scores = []
        for cat in categories:
            if cat in df_ratings_avg.columns:
                mean_val = pd.to_numeric(df_ratings_avg[cat], errors="coerce").mean()
                avg_scores.append(float(mean_val) if pd.notnull(mean_val) else 0.0)
            else:
                avg_scores.append(0.0)

        fig_avg_radar = go.Figure(go.Scatterpolar(
            r=avg_scores + [avg_scores[0]],
            theta=categories + [categories[0]],
            fill='toself',
            name=f"{avg_time_range} Average",
            line_color='#ff9800',
            fillcolor='rgba(255, 152, 0, 0.35)'
        ))

        fig_avg_radar.update_layout(
            polar=dict(
                bgcolor="white",
                radialaxis=dict(
                    visible=True,
                    range=[0, 5],
                    tickfont=dict(color="black", size=10),
                    gridcolor="#d3d3d3"
                ),
                angularaxis=dict(
                    tickfont=dict(color="white", size=10),
                    gridcolor="#444444"
                )
            ),
            paper_bgcolor="rgba(0, 0, 0, 0)",
            plot_bgcolor="rgba(0, 0, 0, 0)",
            showlegend=False,
            margin=dict(l=40, r=40, t=30, b=30)
        )

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