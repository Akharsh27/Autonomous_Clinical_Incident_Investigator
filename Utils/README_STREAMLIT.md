# Clinical Incident Investigator - Streamlit UI

## Quick Start

### Running the Streamlit App

Navigate to the Utils directory and run:

```bash
cd /Users/akharshreddy/Autonomous_Clinical_Incident_Investigator/Utils
conda activate hack_env
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Features

- **Patient Selection**: Dropdown menu to select from P001-P006
- **One-Click Investigation**: Run the clinical analysis workflow
- **Tabbed Results Display**:
  - 👤 Patient Overview
  - 🫀 Vitals Analysis
  - 💊 Treatment History
  - 📝 Clinical Notes
  - ⚡ Recommended Action Plan
- **Report Download**: Export as JSON or TXT format
- **Full JSON View**: Expandable detailed report

### How the UI Works

1. Select a patient ID from the sidebar dropdown (P001-P006)
2. Click "🔍 Run Investigation" button
3. Wait for the analysis to complete
4. View results in organized tabs
5. Download the report if needed

### Architecture

- **trigger.py**: Contains the LangGraph workflow with the `run_investigation(patient_id)` function
- **app.py**: Streamlit UI that calls the investigation function and displays results
- **Datasets**: Uses CSV files for patient vitals, treatment history, and clinical notes

### Data Flow

```
User selects Patient in UI 
  ↓
Clicks "Run Investigation"
  ↓
app.py calls run_investigation(patient_id)
  ↓
trigger.py executes LangGraph workflow
  ↓
Results returned to app.py
  ↓
Formatted and displayed in Streamlit UI
```

### Modifications Made

**trigger.py changes:**
- Added `run_investigation(patient_id: str)` function that accepts dynamic patient IDs
- Maintained all existing node logic (Vitals, Treatment, Clinical, Correlation, Solution, Report)
- Still supports standalone execution: `python trigger.py`

**app.py (New file):**
- Clean, professional Streamlit UI
- Patient ID dropdown (P001-P006)
- Multi-tab report display
- Report download functionality (JSON & TXT)
- Session state management for efficient reuse
