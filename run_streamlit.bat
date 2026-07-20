@echo off
call "%~dp0.venv\Scripts\activate.bat"
python -m streamlit run "%~dp0streamlit_app.py"
