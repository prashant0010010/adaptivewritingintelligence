@echo off
REM One-time setup. Run from the project folder: scripts\setup_windows.bat
cd /d "%~dp0\.."
where python >nul 2>nul || (echo Python was not found. Install Python 3.11 or 3.12 from python.org and tick "Add python.exe to PATH". & exit /b 1)
if not exist .venv ( python -m venv .venv || exit /b 1 )
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt || exit /b 1
if not exist .env ( copy .env.example .env >nul & echo Created .env. Add GEMINI_API_KEY there only if you want Gemini features. )
call .venv\Scripts\python.exe -c "from config.settings import get_settings; from database.db import init_db; s=get_settings(); s.ensure_dirs(); print('Database ready at', s.db_path, 'schema', init_db(s.db_path))"
echo Setup complete. Start the app with scripts\run_windows.bat
