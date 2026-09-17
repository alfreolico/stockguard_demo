@echo off
cd /d %~dp0
if not exist .venv (
  echo Creating virtual environment...
  py -m venv .venv
)
echo Installing/updating dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo Starting StockGuard...
.venv\Scripts\python.exe -m streamlit run app.py
pause
