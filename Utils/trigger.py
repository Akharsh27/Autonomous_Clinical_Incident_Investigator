# langgraph_gemini_pipeline_patient_csv.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from datetime import datetime
import json
import pandas as pd
from dotenv import load_dotenv

# ----------------------
# Load Environment Variables from .env file
# ----------------------
env_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(env_path, ".env"))

# ----------------------
# Import Configurations
# ----------------------
from configs import VITALS_DF, TREATMENT_DF, CLINICAL_DF, KNOWLEDGE_BASE_DF

# ----------------------
# Set Service Account from Environment
# ----------------------
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please check your .env file.")
os.environ["GEMINI_API_KEY"] = gemini_api_key

# ----------------------
# Initialize Gemini 2.5 Flash LLM
# ----------------------
llm = init_chat_model(
    model="gemini-2.5-flash",
    model_provider="google_genai",
    model_kwargs={"thinking_config": {"thinking_budget": 0}}
)

# ----------------------
# State Definition
# ----------------------
class State(TypedDict):
    messages: Annotated[list, add_messages]
    patient_id: str
    vitals: dict
    treatment: dict
    clinical: dict
    correlation: dict
    kb_context: str  # New field for Grounding Data
    solution_agent: dict
    report: dict

# ----------------------
# Helper functions
# ----------------------
def get_vitals(patient_id):
    df = VITALS_DF[VITALS_DF["patient_id"] == patient_id]
    if df.empty:
        return {"oxygen": [], "heart_rate": [], "blood_pressure": []}
    return {
        "oxygen": df["oxygen"].tolist(),
        "heart_rate": df["heart_rate"].tolist(),
        "blood_pressure": df["blood_pressure"].tolist()
    }

def get_treatments(patient_id):
    df = TREATMENT_DF[TREATMENT_DF["patient_id"] == patient_id]
    if df.empty:
        return []
    return df[["drug", "time"]].to_dict(orient="records")

def get_clinical_notes(patient_id):
    if "patient_id" in CLINICAL_DF.columns:
        df = CLINICAL_DF[CLINICAL_DF["patient_id"] == patient_id]
    else:
        df = CLINICAL_DF

    if df.empty:
        return []

    # The original dataset may have a single text column named 'c'
    if "event_description" in df.columns and "timestamp" in df.columns:
        notes = df.sort_values("timestamp")["event_description"].tolist()
    elif "c" in df.columns:
        notes = df["c"].astype(str).tolist()
    else:
        notes = df.iloc[:, 0].astype(str).tolist()

    return notes

# ----------------------
# Node Functions
# ----------------------
def VitalsNode(state: State):
    pid = state.get("patient_id")
    dataset = get_vitals(pid)
    oxygen = dataset["oxygen"][-1] if dataset["oxygen"] else None
    hr = dataset["heart_rate"][-1] if dataset["heart_rate"] else None
    bp = dataset["blood_pressure"][-1] if dataset["blood_pressure"] else None
    anomaly = None
    if oxygen is not None and hr is not None and (oxygen < 90 or hr > 110):
        anomaly = f"Sudden oxygen drop to {oxygen}% and HR spike to {hr}"
    vitals_data = {"vitals_anomaly": anomaly, "severity": "critical" if anomaly else "normal", "blood_pressure": bp}
    state["vitals"] = vitals_data
    return {"vitals": vitals_data}

def TreatmentNode(state: State):
    pid = state.get("patient_id")
    treatments = get_treatments(pid)
    if not treatments:
        return {"treatment": {}}
    recent = treatments[-1]
    treatment_data = {"recent_treatment": recent["drug"], "time": recent["time"]}
    state["treatment"] = treatment_data
    return {"treatment": treatment_data}

def ClinicalNode(state: State):
    pid = state.get("patient_id")
    notes = get_clinical_notes(pid)
    treatments = get_treatments(pid)
    recent_treatment = treatments[-1]["drug"] if treatments else None
    treatment_time = treatments[-1]["time"] if treatments else None

    if not notes:
        clinical_data = {"symptoms": None, "insight": None}
    else:
        notes_text = "\n".join(notes)
        prompt = f"""
You are a clinical assistant analyzing a specific patient's data. 
Patient ID: {pid}

Recent clinical events:
{notes_text}

Most recent treatment:
Drug: {recent_treatment}, Time: {treatment_time}

Based on the above, extract in JSON format:
- recent_treatment: the most recent drug administered
- time: time of administration
- insight: any relevant clinical insight connecting the recent treatment to possible vitals anomalies

Output strictly in JSON like this:
{{
  "recent_treatment": "...",
  "time": "...",
  "insight": "..."
}}
"""
        response = llm.invoke(state.get("messages", [{"role": "user", "content": prompt}]))
        try:
            clinical_data = json.loads(response)
        except:
            clinical_data = {"recent_treatment": recent_treatment, "time": treatment_time, "insight": response}

    state["clinical"] = clinical_data
    return {"clinical": clinical_data}

def CorrelationNode(state: State):
    vitals = state.get("vitals", {})
    clinical = state.get("clinical", {})
    treatment = state.get("treatment", {})
    
    # Simple logic to find relevant SOPs from the Knowledge Base
    # We look for keywords from the 'insight' or 'recent_treatment' in the KB
    recent_drug = treatment.get("recent_treatment", "").lower()
    insight_text = str(clinical.get("insight", "")).lower()
    
    # Filter KB for matches (assuming columns: 'condition_trigger' and 'recommended_action')
    relevant_rows = KNOWLEDGE_BASE_DF[
        KNOWLEDGE_BASE_DF.apply(lambda row: 
            str(row['condition_trigger']).lower() in insight_text or 
            str(row['drug_context']).lower() in recent_drug, 
        axis=1)
    ]
    
    if not relevant_rows.empty:
        kb_text = "\n".join(relevant_rows['recommended_action'].astype(str).tolist())
    else:
        kb_text = "No specific protocol found in Knowledge Base. Use general clinical judgment."

    merged = {
        "header": "Merged Patient Data",
        "vitals": vitals,
        "clinical": clinical,
        "treatment": treatment
    }

    return {
        "correlation": merged,
        "kb_context": kb_text  # Passing the CSV data to the state
    }

def SolutionNode(state: State):
    clinical = state.get("clinical", {})
    vitals = state.get("vitals", {})
    kb_context = state.get("kb_context", "Standard monitoring")

    # Helper to clean objects for JSON
    def _safe(obj):
        if hasattr(obj, "content"): return str(obj.content)
        if isinstance(obj, dict): return {k: _safe(v) for k, v in obj.items()}
        return obj

    prompt = f"""
You are a Clinical Decision Support System. 

GROUNDING PROTOCOLS (From Knowledge Base):
{kb_context}

CURRENT PATIENT DATA:
Vitals: {json.dumps(_safe(vitals))}
Clinical Insight: {json.dumps(_safe(clinical))}

TASK:
Based strictly on the GROUNDING PROTOCOLS above, suggest the immediate action plan. 
If the protocols mention specific dosages or steps for these vitals/symptoms, prioritize them.
"""
    response = llm.invoke([{"role": "user", "content": prompt}])
    
    # Extract content safely
    solution_text = response.content if hasattr(response, "content") else str(response)
    
    return {"solution_agent": {"solution": solution_text}}

def FinalReportNode(state: State):
    corr = state.get("correlation")
    sol = state.get("solution_agent")

    def extract_text(obj):
        if hasattr(obj, "content"):
            return obj.content
        return obj

    report = {
        "patient_id": state.get("patient_id"),
        "header": corr.get("header"),
        "vitals": corr.get("vitals"),
        "clinical": {k: extract_text(v) for k, v in corr.get("clinical", {}).items()},
        "treatment": corr.get("treatment"),
        "action": extract_text(sol.get("solution")),
        "timestamp": datetime.now().isoformat()
    }
    state["report"] = report
    return {"report": report}

# ----------------------
# Build LangGraph
# ----------------------
graph_builder = StateGraph(State)
graph_builder.add_node("vitals", VitalsNode)
graph_builder.add_node("treatment", TreatmentNode)
graph_builder.add_node("clinical", ClinicalNode)
graph_builder.add_node("correlation", CorrelationNode)
graph_builder.add_node("solution", SolutionNode)
graph_builder.add_node("report", FinalReportNode)

graph_builder.add_edge(START, "vitals")
graph_builder.add_edge("vitals", "treatment")
graph_builder.add_edge("treatment", "clinical")
graph_builder.add_edge("clinical", "correlation")
graph_builder.add_edge("correlation", "solution")
graph_builder.add_edge("solution", "report")
graph_builder.add_edge("report", END)

graph = graph_builder.compile()

# ----------------------
# Trigger Function - Callable from external apps
# ----------------------
def run_investigation(patient_id: str) -> dict:
    """
    Run the clinical investigation workflow for a given patient ID.
    
    Args:
        patient_id: The patient ID (e.g., 'P001', 'P002', etc.)
    
    Returns:
        dict: The final report with all analysis results
    """
    state = State({
        "patient_id": patient_id,
        "messages": [{"role": "user", "content": f"Start investigation for {patient_id}"}]
    })
    updated_state = graph.invoke(state)
    return updated_state.get("report", {})

if __name__ == "__main__":
    report = run_investigation("P001")
    print("\n\nFinal Report:\n", json.dumps(report, indent=2))