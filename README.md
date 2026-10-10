# Adaptive Writing Intelligence

A local Windows-friendly app that analyses your own writing, helps you revise drafts, and learns your preferences from your accept, edit and reject decisions. It runs in your browser through Streamlit, stores everything in a local SQLite file, and works **without any API key**.

What it is not: it does not train or fine-tune any model. "Learning" here means counting your feedback and keeping a versioned, editable preference profile. See `docs/LIMITATIONS.md`.

## 1. Install (Windows, VS Code)

1. Install **Python 3.11 or 3.12** from python.org. Tick **Add python.exe to PATH**. (Developed and tested on Python 3.12.)
2. Right-click the ZIP, choose **Extract All**.
3. In VS Code: **File > Open Folder** and choose the extracted `adaptive-writing-intelligence` folder.
4. Open the terminal: **Terminal > New Terminal** (PowerShell).
5. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell says scripts are disabled, allow it for this terminal window only (no permanent change):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Or skip activation and call `.\.venv\Scripts\python.exe` directly in the commands below.

6. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

7. (Optional) Gemini key. Copy `.env.example` to `.env` and add your key:

```powershell
copy .env.example .env
notepad .env
```

Get a key from Google AI Studio. Model names, quotas and free-tier limits change, so check Google's current documentation. Change `GEMINI_MODEL` in `.env` if you see "model not found".

8. Initialise the database (the app also does this automatically at start):

```powershell
python -c "from config.settings import get_settings; from database.db import init_db; s=get_settings(); s.ensure_dirs(); print(init_db(s.db_path))"
```

9. Start the app:

```powershell
streamlit run app.py
```

Your browser opens at http://localhost:8501. On the very first run Streamlit may ask for an email: press Enter to skip. Usage statistics are switched off in `.streamlit/config.toml`.

Shortcut: `scripts\setup_windows.bat` does steps 5 to 8 and `scripts\run_windows.bat` starts the app.

10. Run the tests:

```powershell
python -m pytest
```

No API key or internet is needed for the tests.

## 2. First use

1. **Profiles**: create a profile. Optionally answer the **Onboarding** questions (all skippable, nothing is inferred).
2. **Writing samples**: paste text or upload TXT, DOCX or PDF. Check the preview, fix extraction errors, then save. Try the files in `examples/`.
3. **Profile laboratory**: view measurements per genre, with an evidence label and warnings for small samples.
4. **Reasoning and revision**: analyse an argument locally, or pick a revision mode and generate a revision. To generate, choose a language model mode in the sidebar:
   - *Local only*: analysis works, generation is disabled.
   - *Gemini*: needs a key. You must tick a consent box for every request.
   - *Demo provider*: offline and rule-based (removes a few filler phrases). It only shows the workflow and is not a real model.
5. Accept, edit or reject. Rejecting never turns text into a style example. Feedback is stored and, after at least 3 consistent informative decisions, a preference becomes active (see Profiles > Preferences). You can set, reset or restore preferences.
6. **History**: compare any two versions and restore one into the workspace.
7. **Reports and evaluation**: download Markdown, TXT or DOCX reports; run the evaluation on synthetic or your own cases.

## 3. Privacy: what is stored and what leaves the computer

- **Stored locally** in `%LOCALAPPDATA%\AdaptiveWritingIntelligence\` (override with `AWI_DATA_DIR`): `awi.db` (profiles, samples, drafts, revisions, feedback, preferences), `exports\`, `backups\`, `logs\app.log`. Logs never contain your text or API key.
- **Leaves your computer only** when you choose Gemini mode, tick the consent box and click a button. Then the selected draft or passage, up to 3 approved example passages and your stated preferences go to Google. Stored samples are never sent automatically. The app shows what will be sent and how many characters.
- The app makes no analytics or background network requests.
- Profiles separate data inside the app. They are **not** security boundaries: anyone who can open your Windows account can read `awi.db`.
- Delete a sample, draft or whole profile in the app and it is removed from the database.

## 4. Back up and reset

- **Back up**: Reports and evaluation > Data and backup > "Create a database backup now", or copy `awi.db` while the app is closed.
- **Restore**: close the app, then copy a backup over `awi.db` (or run `python -c "from database.db import restore_db; from config.settings import get_settings as g; s=g(); restore_db(r'PATH\TO\backup.db', s.db_path)"`). A `.before_restore` copy of the old file is kept.
- **Reset everything**: close the app and delete `awi.db`. It is recreated empty at the next start.
- **Move to another computer**: copy `awi.db` into the new data folder.

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| `python` not recognised | Reinstall Python and tick "Add to PATH", or use the `py` launcher: `py -3.12 -m venv .venv` |
| Activation blocked | Use the process-scope command in step 5 |
| `streamlit` not recognised | Activate the venv, or run `python -m streamlit run app.py` |
| Port in use | `streamlit run app.py --server.port 8502` |
| "No Gemini API key" | Create `.env` from `.env.example`, add the key, restart the app |
| Rate limit / quota message | Wait, or check your plan. The app retries transient errors a couple of times |
| "Model not found" | Update `GEMINI_MODEL` in `.env` from Google's current model list |
| PDF has no text | It is probably scanned. OCR is not supported: paste the text instead |
| Garbled DOCX/PDF text | Fix it in the preview box before saving |
| Database error at start | Check the data folder is writable, or set `AWI_DATA_DIR` to another folder |

## 6. Project layout

`app.py` entry point; `core/` analysis, revision, quality checks, learning, retrieval, evaluation; `providers/` Gemini and mock providers behind one interface; `database/` schema, migrations and repository; `ui/` Streamlit pages; `utils/` parsing, export, text helpers; `tests/`; `docs/ARCHITECTURE.md`, `docs/LIMITATIONS.md`, `docs/VERIFICATION.md`.
