# langraph_pipeline.py
from langraph.nodes import Node, Graph
from typing import Dict, Any
from datetime import datetime



CLINICAL_NOTES_DATASET = [
    "10:10 - Patient stable",
    "10:20 - Administered Drug X",
    "10:25 - Patient reports mild discomfort",
    "10:30 - Patient reports shortness of breath"
]


class ClinicalNotesAgent(Node):
    def run(self, inputs: Dict[str, Any]):
        for note in CLINICAL_NOTES_DATASET:
            if "shortness of breath" in note.lower():
                return {"symptoms": "shortness of breath", 
                        "clinical_insight": "Respiratory distress observed after medication"}
        return {"symptoms": None, "clinical_insight": None}