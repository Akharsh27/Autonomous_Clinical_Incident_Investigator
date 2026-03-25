# langraph_pipeline.py
from langraph.nodes import Node, Graph
from typing import Dict, Any
from datetime import datetime


TREATMENT_HISTORY_DATASET = [
    {"drug": "Drug A", "time": "09:00"},
    {"drug": "Drug X", "time": "10:15"}
]




class TreatmentAgent(Node):
    def run(self, inputs: Dict[str, Any]):
        recent = TREATMENT_HISTORY_DATASET[-1]
        return {"recent_treatment": recent["drug"], 
                "time": recent["time"], 
                "insight": "New drug administered shortly before incident"}