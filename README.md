# QA Project Dashboard

An interactive, multi-dimensional Quality Assurance operations dashboard built with **Streamlit**, **Plotly**, and **Google Sheets**. It aggregates testing velocity, retrospective readiness scores, welding defect metrics, support tickets, and live QA engineering bandwidth across standard projects and T2 tickets.

---

## Features

### 1. Summary & QA Ratings

* **Filtered Project Inventory:** View projects filtered by timeframes (3, 6, 9 Months, or All Time) with dynamic link embedding for QA Release Forms.
* **Conditional Formatting:** Automated table styling highlighting completed releases (Green) and items requiring welding inspections (Orange).
* **10-Point Readiness Benchmark:** Dynamic radar chart tracking:
* Documentation (Software & Product)
* Hardware & Tooling (Robot Availability, Bundle Preparation)
* Cross-functional Support (Software, Controls, Product, Welding)
* QA Team Health (Stress on QA Resources, QA Self-Evaluation)


* **Portfolio Baseline:** Side-by-side rolling benchmark comparison against portfolio averages.

### 2. Testing Estimation vs. Actuals

* **Iterative Multi-Axis Tracking:** Interactive dual-axis combo chart plotting:
* Estimated QA Days vs. Actual QA Days.
* Release Candidate (RC) dependent estimates (`Original Estimate × RC Count`).
* Secondary y-axis overlay tracking the raw volume of release candidates.



### 3. Bug Tracking & Resolution

* **Overlay Progress Bars:** Horizontal overlay bar chart displaying reported vs. resolved bugs per release bundle.
* **KPI Header:** High-level summary metrics tracking total reported defects, total resolved defects, and overall resolution rate.

### 4. Welding & Defect Analytics

* **Pass/Fail Distribution:** 100% stacked bar chart visualizing joint pass vs. fail rates across tested projects.
* **Defect Root Cause Breakdown:** Donut chart categorizing failure types (Leg Size, Undercut, Lack of Penetration/Fusion, Porosity, Cracking, Burn Through, etc.).

### 5. T2 Support & Retrospectives

* **Dedicated Support Tracking:** Full retrospective audit for T2 tickets with independent inventory tables, release document links, and 10-point radar readiness scoring.

### 6. Unified QA Bandwidth Gauge

* **Cross-Sheet Aggregation:** Unifies active workload by combining both `Projects` and `T2` records.
* **Custom Geometric Dial:** Semi-circular Plotly dial with a dynamic needle and color-coded capacity thresholds:
* **0 – 3 (Green):** Safe capacity
* **3 – 4 (Orange):** Moderate load warning
* **4 – 6+ (Red):** Critical capacity alert


* **Categorized Status Inventory:** Collapsible drawers listing all active, completed, and backlog items tagged by source type (`[Project]` or `[T2]`).

---

## Data Architecture

The dashboard connects to a Google Sheets workbook using `streamlit-gsheets`. The workbook expects header rows starting at row index `7` (`header=6`) across the following worksheets:

| Sheet Name | Primary Key | Key Expected Columns |
| --- | --- | --- |
| **`Projects`** | `Project Name` | `Status`, `Start Date`, `Completion Date`, `Estimated QA Days`, `Actual QA Days`, `QA Estimate rc Dependant`, `QA Release Document`, `Welding Inspection Required` |
| **`Ratings`** | `Project Name` | 10 scoring criteria columns (0–10 scale), `Number of Release Candidates`, `Targeted Test Plan` |
| **`Defects`** | `Project Name` | `Welds Passed`, `Welds Failed`, specific defect count columns (`Cracking`, `Porosity`, `Undercut`, etc.) |
| **`T2`** | `T2 Ticket` | `Status`, `Start Date`, `Completion Date`, `Estimated QA Days`, `Actual QA Days`, `QA Estimate rc Dependant`, `QA T2 Release Document` |
| **`T2 Ratings`** | `T2 Ticket` | 10 scoring criteria columns (0–10 scale), `Number of Release Candidates`, `Targeted Test Plan` |

---

## Tech Stack

* **Frontend / Framework:** [Streamlit](https://streamlit.io/)
* **Visualization:** [Plotly](https://plotly.com/python/) (`graph_objects`, `subplots`)
* **Data Manipulation:** [Pandas](https://pandas.pydata.org/), [NumPy](https://numpy.org/)
* **Data Connector:** [st-gsheets-connection](https://github.com/streamlit/gsheets-connection)

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/qa-project-dashboard.git
cd qa-project-dashboard

```

### 2. Create and Activate a Virtual Environment

```bash
python -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

```

#### `requirements.txt`

```text
streamlit>=1.30.0
st-gsheets-connection>=0.1.0
pandas>=2.0.0
plotly>=5.18.0
numpy>=1.24.0

```

### 4. Configure Google Sheets Secrets

Create a secrets file at `.streamlit/secrets.toml`:

```toml
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit"
# If using a public read-only sheet:
# type = "public"

# If using a private Google Service Account:
# type = "service_account"
# project_id = "your-project-id"
# private_key_id = "your-key-id"
# private_key = "-----BEGIN PRIVATE KEY-----\n..."
# client_email = "your-sa@project.iam.gserviceaccount.com"
# client_id = "..."

```

---

## Running the Application

Launch the local development server:

```bash
streamlit run app.py

```

Open your browser to `http://localhost:8501`.

---

## Bandwidth Gauge Calibration

The bandwidth gauge threshold logic is defined in **Tab 6**. To recalibrate the zones or maximum capacity, modify the parameters below:

```python
# Set the baseline maximum capacity (default: 6)
gauge_max = max(6, in_progress_count)

# Adjust arc partition boundaries (v_start, v_end, color)
zones = [
    (0, 3, "rgba(76, 175, 80, 0.65)"),        # Green
    (3, 4, "rgba(255, 152, 0, 0.70)"),       # Orange
    (4, gauge_max, "rgba(244, 67, 54, 0.75)") # Red
]

```
