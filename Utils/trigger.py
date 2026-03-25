import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from datetime import datetime
import json
from dotenv import load_dotenv

# ----------------------
# Load ENV
# ----------------------
env_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(env_path, ".env"))

from configs import VITALS_DF, TREATMENT_DF, CLINICAL_DF, KNOWLEDGE_BASE_DF

# ----------------------
# LLM
# ----------------------
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

llm = init_chat_model(
    model="gemini-2.5-flash",
    model_provider="google_genai",
)

# ----------------------
# STATE
# ----------------------
class State(TypedDict):
    messages: Annotated[list, add_messages]
    patient_id: str
    plan: dict
    vitals: dict
    treatment: dict
    clinical: dict
    correlation: dict
    kb_context: str
    solution: str
    report: dict

# ----------------------
# HELPERS
# ----------------------
def get_vitals(pid):
    df = VITALS_DF[VITALS_DF["patient_id"] == pid]
    return {
        "oxygen": df["oxygen"].tolist(),
        "heart_rate": df["heart_rate"].tolist(),
        "blood_pressure": df["blood_pressure"].tolist()
    } if not df.empty else {}

def get_treatments(pid):
    df = TREATMENT_DF[TREATMENT_DF["patient_id"] == pid]
    return df.to_dict("records") if not df.empty else []

def get_clinical_notes(pid):
    df = CLINICAL_DF[CLINICAL_DF["patient_id"] == pid] if "patient_id" in CLINICAL_DF.columns else CLINICAL_DF
    if df.empty:
        return []

    if "event_description" in df.columns:
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp")
        return df["event_description"].astype(str).tolist()

    if "c" in df.columns:
        return df["c"].astype(str).tolist()

    # Fallback for unknown schema
    return df.iloc[:, -1].astype(str).tolist()


def get_data_availability(pid):
    has_vitals = not VITALS_DF[VITALS_DF["patient_id"] == pid].empty
    has_treatments = not TREATMENT_DF[TREATMENT_DF["patient_id"] == pid].empty
    has_clinical = len(get_clinical_notes(pid)) > 0
    return {
        "has_vitals": has_vitals,
        "has_treatments": has_treatments,
        "has_clinical": has_clinical,
    }


def clean_json_block(text: str) -> str:
    content = (text or "").strip()
    content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"^```\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    return content.strip()


def parse_llm_json(text: str) -> dict:
    content = clean_json_block(text)

    # 1) Direct parse
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    # 2) Parse first fenced JSON block if present
    fenced = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text or "", flags=re.IGNORECASE)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

    # 3) Parse first object-like block
    obj = re.search(r"(\{[\s\S]*\})", content)
    if obj:
        try:
            parsed = json.loads(obj.group(1))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

    return {}


def plan_agents_with_llm(pid: str, availability: dict) -> dict:
    allowed_agents = ["vitals", "treatment", "clinical"]

    vitals = get_vitals(pid)
    treatments = get_treatments(pid)
    notes = get_clinical_notes(pid)

    latest_vitals = {
        "oxygen": vitals.get("oxygen", [])[-1] if vitals.get("oxygen") else None,
        "heart_rate": vitals.get("heart_rate", [])[-1] if vitals.get("heart_rate") else None,
        "blood_pressure": vitals.get("blood_pressure", [])[-1] if vitals.get("blood_pressure") else None,
    }
    latest_treatment = treatments[-1] if treatments else {}
    notes_preview = notes[-3:] if notes else []

    planner_prompt = f"""
You are the Commander agent for a clinical investigation workflow.

Patient ID: {pid}
Data availability: {json.dumps(availability)}
Latest vitals snapshot: {json.dumps(latest_vitals)}
Latest treatment snapshot: {json.dumps(latest_treatment)}
Recent clinical notes (last 3): {json.dumps(notes_preview)}

Task:
Choose which specialist agents to call from this fixed list: {allowed_agents}
- vitals: only for physiologic anomaly/severity context
- treatment: only for medication/timing context
- clinical: only for symptom/insight extraction from notes

Hard rules:
- Select only from {allowed_agents}
- Do not select an agent if its corresponding data is unavailable
- Return strict JSON only

Output schema:
{{
  "selected_agents": ["vitals", "treatment", "clinical"],
  "reason": "short explanation",
  "priority": "high|medium|low"
}}
"""

    try:
        response = llm.invoke([{"role": "user", "content": planner_prompt}])
        parsed = parse_llm_json(response.content)
    except Exception:
        parsed = {}

    selected = parsed.get("selected_agents", []) if isinstance(parsed, dict) else []
    if not isinstance(selected, list):
        selected = []

    # Sanitize LLM output to only valid, available agents
    available_map = {
        "vitals": availability.get("has_vitals", False),
        "treatment": availability.get("has_treatments", False),
        "clinical": availability.get("has_clinical", False),
    }
    selected = [a for a in selected if a in allowed_agents and available_map.get(a, False)]

    # Fallback deterministic plan if LLM returns nothing usable
    if not selected:
        if availability.get("has_vitals"):
            selected.append("vitals")
        if availability.get("has_treatments"):
            selected.append("treatment")
        if availability.get("has_clinical"):
            selected.append("clinical")

    return {
        "selected_agents": selected,
        "reason": parsed.get("reason", "Fallback data-driven plan") if isinstance(parsed, dict) else "Fallback data-driven plan",
        "priority": parsed.get("priority", "medium") if isinstance(parsed, dict) else "medium",
    }

# ----------------------
# AGENTS
# ----------------------

# 🟪 Commander Agent
def CommanderNode(state: State):
    pid = state["patient_id"]
    availability = get_data_availability(pid)

    llm_plan = plan_agents_with_llm(pid, availability)
    selected_agents = llm_plan["selected_agents"]

    # Safety rule: if clinical notes exist, always run clinical extraction.
    if availability.get("has_clinical") and "clinical" not in selected_agents:
        selected_agents.append("clinical")
        llm_plan["reason"] = (
            f"{llm_plan.get('reason', '')} | Clinical notes available, so clinical agent was enforced."
        ).strip(" |")

    msg = {
        "role": "system",
        "content": (
            f"Commander selected agents for {pid}: {selected_agents if selected_agents else ['none']} "
            f"based on data availability {availability}."
        ),
    }

    return {
        "plan": {
            "selected_agents": selected_agents,
            "availability": availability,
            "reason": llm_plan.get("reason", "Data-aware orchestration"),
            "priority": llm_plan.get("priority", "medium"),
            "planner": "llm_commander",
        },
        "messages": state["messages"] + [msg],
    }


def route_from_commander(state: State):
    selected_agents = state.get("plan", {}).get("selected_agents", [])
    if not selected_agents:
        return ["correlation"]
    return selected_agents

# 🟩 Vitals Agent (NO LLM)
def VitalsNode(state: State):
    data = get_vitals(state["patient_id"])
    if not data:
        return {"vitals": {}}

    oxygen = data["oxygen"][-1]
    hr = data["heart_rate"][-1]

    anomaly = None
    if oxygen < 90 or hr > 110:
        anomaly = f"Oxygen drop to {oxygen}% and HR spike to {hr}"

    return {
        "vitals": {
            "anomaly": anomaly,
            "severity": "critical" if anomaly else "normal"
        }
    }

# 🟩 Treatment Agent (NO LLM)
def TreatmentNode(state: State):
    treatments = get_treatments(state["patient_id"])
    if not treatments:
        return {"treatment": {}}

    recent = treatments[-1]
    return {
        "treatment": {
            "recent_drug": recent["drug"],
            "time": recent["time"]
        }
    }

# 🟩 Clinical Agent (LLM)
def ClinicalNode(state: State):
    notes = get_clinical_notes(state["patient_id"])
    if not notes:
        return {"clinical": {}}

    prompt = f"""
Extract key medical symptoms from the following notes:

{chr(10).join(notes)}

Return JSON:
{{
 "symptoms": "...",
 "insight": "..."
}}
"""

    response = llm.invoke([{"role": "user", "content": prompt}])
    parsed = parse_llm_json(response.content)
    if not parsed:
        parsed = {"symptoms": "", "insight": clean_json_block(response.content)}

    return {"clinical": parsed}

# 🟥 Correlation Engine
def CorrelationNode(state: State):
    vitals = state.get("vitals", {})
    clinical = state.get("clinical", {})
    treatment = state.get("treatment", {})

    drug = str(treatment.get("recent_drug", "")).lower()
    insight = str(clinical.get("insight", "")).lower()

    kb = KNOWLEDGE_BASE_DF[
        KNOWLEDGE_BASE_DF.apply(
            lambda row: str(row["drug_context"]).lower() in drug
            or str(row["condition_trigger"]).lower() in insight,
            axis=1
        )
    ]

    kb_text = "\n".join(kb["recommended_action"].tolist()) if not kb.empty else "General monitoring"

    return {
        "correlation": {
            "vitals": vitals,
            "clinical": clinical,
            "treatment": treatment
        },
        "kb_context": kb_text
    }

# 🟦 Decision + Action (LLM)
def SolutionNode(state: State):
    prompt = f"""
You are a clinical AI system.

Patient Data:
{json.dumps(state["correlation"], indent=2)}

Guidelines:
{state["kb_context"]}

Give:
- Root cause
- Recommended action
"""

    res = llm.invoke([{"role": "user", "content": prompt}])
    return {"solution": res.content}

# 🟦 Report
def ReportNode(state: State):
    plan = state.get("plan", {})
    return {
        "report": {
            "patient_id": state["patient_id"],
            "analysis": state["correlation"],
            "decision": state["solution"],
            "called_agents": plan.get("selected_agents", []),
            "commander_plan": plan,
            "timestamp": datetime.now().isoformat()
        }
    }

# ----------------------
# GRAPH (PARALLEL AGENTS)
# ----------------------
builder = StateGraph(State)

builder.add_node("commander", CommanderNode)
builder.add_node("vitals", VitalsNode)
builder.add_node("treatment", TreatmentNode)
builder.add_node("clinical", ClinicalNode)
builder.add_node("correlation", CorrelationNode)
builder.add_node("solution", SolutionNode)
builder.add_node("report", ReportNode)

# FLOW
builder.add_edge(START, "commander")

# DYNAMIC ROUTING FROM COMMANDER
builder.add_conditional_edges(
    "commander",
    route_from_commander,
    {
        "vitals": "vitals",
        "treatment": "treatment",
        "clinical": "clinical",
        "correlation": "correlation",
    },
)

# MERGE
builder.add_edge("vitals", "correlation")
builder.add_edge("treatment", "correlation")
builder.add_edge("clinical", "correlation")

builder.add_edge("correlation", "solution")
builder.add_edge("solution", "report")
builder.add_edge("report", END)

graph = builder.compile()

# ----------------------
# RUN
# ----------------------
def run_investigation(patient_id: str):
    state = {
        "patient_id": patient_id,
        "messages": [{"role": "user", "content": f"Investigate {patient_id}"}]
    }
    result = graph.invoke(state)
    return result["report"]

if __name__ == "__main__":
    output = run_investigation("P002")
    print(json.dumps(output, indent=2))