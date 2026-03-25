#!/bin/bash

# Start Streamlit Application
echo "Starting Clinical Incident Investigator Streamlit App..."
streamlit run Utils/app.py --server.headless=true --server.address=0.0.0.0 --server.port=8501
