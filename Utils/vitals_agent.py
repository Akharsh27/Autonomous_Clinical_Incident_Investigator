# langraph_pipeline.py
from langraph.nodes import Node, Graph
from typing import Dict, Any
from datetime import datetime


VITALS_DATASET = {
    "patient_id": "P123",
    "timestamp": ["10:00", "10:15", "10:30", "10:32"],
    "oxygen": [98, 97, 96, 85],
    "heart_rate": [72, 75, 80, 120],
}





class VitalsAgent(Node):
    def run(self, inputs: Dict[str, Any]):
        oxygen = VITALS_DATASET["oxygen"][-1]
        hr = VITALS_DATASET["heart_rate"][-1]
        anomaly = None
        if oxygen < 90 or hr > 110:
            anomaly = f"Sudden oxygen drop to {oxygen}% and HR spike to {hr}"
        return {"vitals_anomaly": anomaly, "severity": "critical" if anomaly else "normal"}
