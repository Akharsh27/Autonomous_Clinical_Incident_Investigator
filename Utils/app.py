import streamlit as st
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trigger import run_investigation

# Page Configuration
st.set_page_config(
    page_title="Clinical Incident Investigator",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .report-header {
        color: #1f77b4;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .section-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        border-left: 4px solid #1f77b4;
    }
    .vital-normal {
        color: #2ecc71;
        font-weight: bold;
    }
    .vital-critical {
        color: #e74c3c;
        font-weight: bold;
    }
    .action-box {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #ffc107;
        margin: 20px 0;
    }
    </style>
""", unsafe_allow_html=True)

# Main Title
st.title("🏥 Clinical Incident Investigator")
st.markdown("---")

# Sidebar for patient selection
st.sidebar.header("📋 Patient Selection")

# Patient ID Dropdown
patient_ids = [f"P00{i}" for i in range(1, 7)]  # P001 to P006
selected_patient = st.sidebar.selectbox(
    "Select Patient ID:",
    options=patient_ids,
    index=0,
    help="Choose a patient to investigate"
)

# Investigation Button
st.sidebar.markdown("---")
if st.sidebar.button("🔍 Run Investigation", use_container_width=True, type="primary"):
    st.session_state.run_investigation = True
else:
    if "run_investigation" not in st.session_state:
        st.session_state.run_investigation = False

# Main content area
if st.session_state.run_investigation:
    st.info(f"🔄 Running investigation for patient {selected_patient}...")
    
    try:
        # Run the investigation
        report = run_investigation(selected_patient)
        
        # Store in session state to avoid re-running
        st.session_state.last_report = report
        st.session_state.last_patient = selected_patient
        
        st.success("✅ Investigation completed successfully!")
        
    except Exception as e:
        st.error(f"❌ Error running investigation: {str(e)}")
        st.session_state.run_investigation = False

# Display report if available
if hasattr(st.session_state, 'last_report') and st.session_state.last_report:
    report = st.session_state.last_report
    patient = st.session_state.last_patient
    
    st.markdown(f"<div class='report-header'>📊 Investigation Report - {patient}</div>", unsafe_allow_html=True)
    
    # Create tabs for different sections
    tabs = st.tabs(["👤 Patient Overview", "🫀 Vitals", "💊 Treatment", "📝 Clinical", "⚡ Action Plan"])
    
    # Patient Overview Tab
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div class='section-box'><b>Patient ID:</b> {report.get('patient_id', 'N/A')}</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='section-box'><b>Timestamp:</b> {report.get('timestamp', 'N/A')}</div>", unsafe_allow_html=True)
    
    # Vitals Tab
    with tabs[1]:
        vitals = report.get("vitals", {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            anomaly = vitals.get("vitals_anomaly")
            severity = vitals.get("severity", "normal")
            severity_class = "vital-critical" if severity == "critical" else "vital-normal"
            st.markdown(f"<div class='section-box'><b>Severity:</b> <span class='{severity_class}'>{severity.upper()}</span></div>", unsafe_allow_html=True)
        
        with col2:
            bp = vitals.get("blood_pressure", "N/A")
            st.markdown(f"<div class='section-box'><b>Blood Pressure:</b> {bp}</div>", unsafe_allow_html=True)
        
        with col3:
            if anomaly:
                st.markdown(f"<div class='section-box' style='border-left-color: #e74c3c;'><b>⚠️ Anomaly:</b> {anomaly}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='section-box'><b>✅ Status:</b> No anomalies detected</div>", unsafe_allow_html=True)
    
    # Treatment Tab
    with tabs[2]:
        treatment = report.get("treatment", {})
        if treatment:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"<div class='section-box'><b>Recent Treatment:</b> {treatment.get('recent_treatment', 'N/A')}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div class='section-box'><b>Time:</b> {treatment.get('time', 'N/A')}</div>", unsafe_allow_html=True)
        else:
            st.info("No treatment data available for this patient.")
    
    # Clinical Tab
    with tabs[3]:
        clinical = report.get("clinical", {})
        if clinical:
            st.markdown("### Clinical Data")
            for key, value in clinical.items():
                if value:
                    st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
        else:
            st.info("No clinical data available for this patient.")
    
    # Action Plan Tab
    with tabs[4]:
        action = report.get("action", "No action recommended")
        st.markdown(f"<div class='action-box'>{action}</div>", unsafe_allow_html=True)
    
    # Full Report JSON (expandable)
    with st.expander("📄 Full Report (JSON)"):
        st.json(report)
    
    # Download Report
    col1, col2, col3 = st.columns(3)
    with col1:
        report_json = json.dumps(report, indent=2)
        st.download_button(
            label="📥 Download Report (JSON)",
            data=report_json,
            file_name=f"clinical_report_{patient}.json",
            mime="application/json"
        )
    
    with col2:
        report_text = f"""
CLINICAL INCIDENT INVESTIGATION REPORT
Patient ID: {report.get('patient_id', 'N/A')}
Timestamp: {report.get('timestamp', 'N/A')}

VITALS:
{json.dumps(report.get('vitals', {}), indent=2)}

TREATMENT:
{json.dumps(report.get('treatment', {}), indent=2)}

CLINICAL:
{json.dumps(report.get('clinical', {}), indent=2)}

ACTION PLAN:
{report.get('action', 'No action recommended')}
"""
        st.download_button(
            label="📥 Download Report (TXT)",
            data=report_text,
            file_name=f"clinical_report_{patient}.txt",
            mime="text/plain"
        )

else:
    # Initial State - No report yet
    st.markdown("""
    ### 👋 Welcome to Clinical Incident Investigator
    
    This system analyzes patient clinical data and provides insights for better decision-making.
    
    **How to use:**
    1. Select a patient ID from the sidebar (P001-P006)
    2. Click the "Run Investigation" button
    3. Review the detailed analysis and recommendations
    
    **Features:**
    - 🫀 Vitals Analysis
    - 💊 Treatment History Review
    - 📝 Clinical Notes Integration
    - ⚡ AI-Powered Recommendations
    - 💾 Report Download Capabilities
    """)

# Footer
st.markdown("---")
st.markdown("🏥 Clinical Incident Investigator | Powered by LangGraph & Gemini AI")
