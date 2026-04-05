#!/bin/bash
# Move to the project folder
cd "$(dirname "$0")"

# Activate the environment and run Streamlit
source venv/bin/activate
streamlit run dashboard.py --server.headless true & 

# Wait a few seconds for it to start, then open the browser
sleep 3
open "http://localhost:8501"