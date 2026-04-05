import subprocess
import sys
import os

project_dir = os.path.dirname(os.path.abspath(__file__))
python = sys.executable

print("🚀 Starting Scanner Service...")
patrol = subprocess.Popen([python, "scanner_service.py"], cwd=project_dir)

print("🌐 Starting Dashboard...")
dashboard = subprocess.Popen([python, "-m", "streamlit", "run", "dashboard.py"], cwd=project_dir)

print("✅ Both running. Press Ctrl+C to stop everything.")

try:
    patrol.wait()
    dashboard.wait()
except KeyboardInterrupt:
    print("\n🛑 Shutting down...")
    patrol.terminate()
    dashboard.terminate()