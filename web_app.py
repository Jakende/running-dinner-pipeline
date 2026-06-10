import html
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
UPLOAD_DIR = INPUT_DIR / "uploads"
OUTPUT_ROOT = DATA_DIR / "output"
RUNS_DIR = OUTPUT_ROOT / "runs"

app = FastAPI(title="Running Dinner Pipeline")


def _read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6f5;
      --panel: #ffffff;
      --panel-soft: #f8faf9;
      --text: #111817;
      --muted: #66706e;
      --line: #d9e0dd;
      --line-strong: #b8c4c0;
      --accent: #0f5b52;
      --accent-strong: #0a3f39;
      --accent-soft: #e5f2ef;
      --warn: #a66a00;
      --warn-soft: #fff4dc;
      --danger: #9f1d20;
      --danger-soft: #fde8e8;
      --ok: #20704f;
      --ok-soft: #e7f4ec;
      --shadow: 0 18px 45px rgba(16, 24, 22, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ overflow-x: hidden; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      background: rgba(255, 255, 255, 0.92);
      border-bottom: 1px solid var(--line);
      padding: 16px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      position: sticky;
      top: 0;
      z-index: 10;
      backdrop-filter: blur(14px);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--text);
      text-decoration: none;
      font-weight: 800;
      letter-spacing: 0;
    }}
    .brand-mark {{
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      background: var(--accent);
      color: #fff;
      box-shadow: 0 8px 20px rgba(15, 91, 82, 0.22);
    }}
    .header-status {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }}
    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--ok);
    }}
    main {{ width: 100%; max-width: 1180px; margin: 0 auto; padding: 30px 28px 42px; }}
    h1 {{ font-size: 30px; line-height: 1.15; margin: 0; letter-spacing: 0; }}
    h2 {{ font-size: 17px; line-height: 1.2; margin: 0 0 14px; letter-spacing: 0; }}
    h3 {{ font-size: 14px; margin: 0 0 8px; color: var(--muted); }}
    p {{ line-height: 1.5; }}
    form, .panel, .run-table-wrap {{
      max-width: 100%;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 18px;
      box-shadow: var(--shadow);
    }}
    .top-grid {{
      display: grid;
      grid-template-columns: minmax(320px, 0.86fr) minmax(360px, 1.14fr);
      gap: 18px;
      align-items: start;
    }}
    .top-grid > *, .grid > *, .metric-grid > * {{ min-width: 0; }}
    .page-title {{
      margin-bottom: 18px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
    }}
    .page-title p {{ margin: 8px 0 0; color: var(--muted); max-width: 680px; }}
    label {{ display: block; font-weight: 750; margin-bottom: 6px; font-size: 13px; }}
    input[type="file"], input[type="number"], input[type="text"], input[type="date"], input[type="time"], textarea {{
      width: 100%;
      min-height: 42px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      margin-bottom: 14px;
      font: inherit;
      color: var(--text);
    }}
    textarea {{
      min-height: 92px;
      resize: vertical;
    }}
    input[type="file"]::file-selector-button {{
      min-height: 34px;
      padding: 0 12px;
      margin-right: 10px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: #fff;
      color: var(--accent);
      font: inherit;
      font-weight: 760;
      cursor: pointer;
    }}
    input[type="file"]::file-selector-button:hover {{ background: var(--accent-soft); }}
    input:focus {{
      outline: 3px solid rgba(15, 91, 82, 0.14);
      border-color: var(--accent);
    }}
    .dropzone {{
      border: 1px dashed var(--line-strong);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 14px;
      background: var(--panel-soft);
      overflow: hidden;
    }}
    .dropzone input {{ margin-bottom: 0; background: transparent; border: 0; padding-left: 0; }}
    .help {{ margin: -6px 0 14px; color: var(--muted); font-size: 13px; }}
    .form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .button-row {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .icon {{
      width: 16px;
      height: 16px;
      flex: 0 0 16px;
    }}
    button svg, .button svg {{ margin-right: 8px; }}
    button.full {{ width: 100%; }}
    button, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 14px;
      border-radius: 6px;
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      text-decoration: none;
      font-weight: 760;
      font-size: 14px;
      cursor: pointer;
      line-height: 1;
      white-space: nowrap;
    }}
    button:hover, .button:hover {{ background: var(--accent-strong); border-color: var(--accent-strong); }}
    .button.secondary {{
      background: #fff;
      color: var(--accent);
    }}
    .button.secondary:hover {{ background: var(--accent-soft); }}
    .button.warn {{
      border-color: #d99724;
      background: var(--warn-soft);
      color: #704900;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      background: var(--panel-soft);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 88px;
    }}
    .metric strong {{ display: block; font-size: 24px; line-height: 1.1; margin-top: 6px; }}
    .metric span {{ color: var(--muted); font-size: 12px; font-weight: 750; }}
    .notice {{
      border-radius: 8px;
      border: 1px solid var(--line);
      padding: 12px;
      margin: 12px 0 0;
      background: var(--panel-soft);
      color: var(--text);
    }}
    .notice.warning {{ background: var(--warn-soft); border-color: #ecc36d; color: #59400c; }}
    .notice.error {{ background: var(--danger-soft); border-color: #efb8b8; color: var(--danger); }}
    .progress-card {{
      display: flex;
      align-items: flex-start;
      gap: 12px;
      border-color: #c6d8d3;
      background: #eef7f4;
    }}
    .spinner {{
      width: 18px;
      height: 18px;
      margin-top: 2px;
      border-radius: 999px;
      border: 3px solid rgba(15, 91, 82, 0.18);
      border-top-color: var(--accent);
      animation: spin 0.85s linear infinite;
      flex: 0 0 18px;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .status {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      background: var(--panel-soft);
      color: var(--muted);
    }}
    .status.ok {{ background: var(--ok-soft); color: var(--ok); }}
    .status.warn {{ background: var(--warn-soft); color: var(--warn); }}
    .status.failed {{ background: var(--danger-soft); color: var(--danger); }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 22px 0 10px;
    }}
    .section-head h2 {{ margin: 0; }}
    .run-table-wrap {{ padding: 0; overflow: hidden; }}
    .table-scroll {{ overflow-x: auto; }}
    .run-id {{
      display: inline-block;
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
      vertical-align: bottom;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
    }}
    th, td {{
      text-align: left;
      padding: 13px 14px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
      background: var(--panel-soft);
      white-space: nowrap;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    td {{ font-size: 14px; }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    pre {{
      white-space: pre-wrap;
      background: #101214;
      color: #f4f4f4;
      border-radius: 8px;
      padding: 14px;
      overflow: auto;
      max-height: 440px;
    }}
    .log-tail {{
      max-height: 260px;
      margin: 12px 0 0;
    }}
    .muted {{ color: var(--muted); }}
    a {{ overflow-wrap: anywhere; }}
    .status-failed {{ color: var(--danger); font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .artifact-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      max-height: 340px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .artifact-list li {{ border-bottom: 1px solid var(--line); }}
    .artifact-list li:last-child {{ border-bottom: 0; }}
    .artifact-list a {{
      display: block;
      padding: 10px 12px;
      color: var(--accent);
      text-decoration: none;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .artifact-list a:hover {{ background: var(--accent-soft); }}
    .summary-line {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin: 10px 0 0;
    }}
    ul {{ margin: 0; padding-left: 18px; }}
    @media (max-width: 900px) {{
      header {{ align-items: flex-start; flex-direction: column; }}
      main {{ padding: 18px; }}
      .page-title {{ display: block; }}
      .top-grid, .metric-grid {{ grid-template-columns: 1fr; }}
      .form-row {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 28px; }}
      input[type="file"] {{ font-size: 14px; white-space: normal; }}
      input[type="file"]::file-selector-button {{ display: block; margin: 0 0 10px; width: fit-content; }}
      .run-id {{ max-width: 100%; white-space: normal; }}
      td {{ overflow-wrap: anywhere; }}
      .grid {{ grid-template-columns: 1fr; }}
      table, thead, tbody, th, td, tr {{ display: block; }}
      th {{ display: none; }}
      td {{ border-bottom: 0; padding-bottom: 4px; }}
      tr {{ border-bottom: 1px solid var(--line); padding: 8px 0; }}
    }}
  </style>
</head>
<body>
  <header>
    <a class="brand" href="/">
      <span class="brand-mark">
        <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14M12 5v14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </span>
      <span>Running Dinner Pipeline</span>
    </a>
    <span class="header-status"><span class="dot"></span>Lokale Web-App</span>
  </header>
  <main>{body}</main>
</body>
</html>"""
    )


def _runs_index() -> list[dict]:
    index = _read_json(RUNS_DIR / "index.json", {"runs": []})
    return index.get("runs", [])


def _status_badge(status: str, valid: bool | None = None) -> str:
    escaped = html.escape(status or "unknown")
    if "failed" in (status or ""):
        cls = "failed"
    elif status == "completed" and valid:
        cls = "ok"
    elif status:
        cls = "warn"
    else:
        cls = ""
    return f'<span class="status {cls}">{escaped}</span>'


def _format_datetime(value: str) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def _run_dir(run_id: str) -> Path:
    candidate = (RUNS_DIR / run_id).resolve()
    runs_root = RUNS_DIR.resolve()
    if runs_root not in candidate.parents and candidate != runs_root:
        raise HTTPException(status_code=400, detail="Invalid run id")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return candidate


def _run_file(run_id: str, file_path: str) -> Path:
    run_dir = _run_dir(run_id)
    candidate = (run_dir / file_path).resolve()
    if run_dir.resolve() not in candidate.parents and candidate != run_dir.resolve():
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


def _slug(text: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in text).strip("-").lower()
    return "-".join(part for part in safe.split("-") if part)[:48] or "run"


def _write_initial_manifest(run_dir: Path, run_id: str, input_path: Path, trials: int, event: dict):
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "running",
        "input": {"path": str(input_path), "sha256": None},
        "parameters": {
            "trials": trials,
            "db": str(DATA_DIR / "intermediate" / "dinner.db"),
        },
        "event": event,
        "artifacts": {"run_dir": f"runs/{run_id}"},
        "pipeline_log": "pipeline.log",
    }
    _write_json(run_dir / "manifest.json", manifest)


def _mark_run_process_failed(run_dir: Path, run_id: str, returncode: int):
    manifest_path = run_dir / "manifest.json"
    manifest = _read_json(manifest_path, {})
    manifest.update(
        {
            "run_id": run_id,
            "status": "failed",
            "error": f"Pipeline exited with code {returncode}",
            "pipeline_log": "pipeline.log",
        }
    )
    _write_json(manifest_path, manifest)


def _run_pipeline_in_background(cmd: list[str], run_dir: Path, run_id: str):
    log_path = run_dir / "pipeline.log"

    def target():
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        with log_path.open("a", encoding="utf-8", buffering=1) as log:
            log.write(f"[{datetime.now().isoformat(timespec='seconds')}] Pipeline process started.\n")
            process = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            returncode = process.wait()
            log.write(f"[{datetime.now().isoformat(timespec='seconds')}] Pipeline process exited with code {returncode}.\n")
        if returncode != 0:
            _mark_run_process_failed(run_dir, run_id, returncode)

    threading.Thread(target=target, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
def home():
    runs = _runs_index()
    rows = []
    for run in runs:
        stats = run.get("stats", {})
        validation = run.get("validation", {})
        status = run.get("status", "unknown")
        inactive = stats.get("inactive_teams", 0) or 0
        actions = f"""
        <div class="button-row">
          <a class="button secondary" href="/runs/{html.escape(run['run_id'])}">
            <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Öffnen
          </a>
        </div>
        """
        rows.append(
            f"""<tr>
  <td><a href="/runs/{html.escape(run['run_id'])}"><code class="run-id">{html.escape(run['run_id'])}</code></a></td>
  <td>{html.escape(_format_datetime(run.get('created_at', '')))}</td>
  <td>{_status_badge(status, validation.get('valid'))}</td>
  <td>{stats.get('active_teams', '-')} aktiv <span class="muted">/ {stats.get('imported_teams', '-')} importiert</span>{f'<br><span class="status warn">{inactive} inaktiv</span>' if inactive else ''}</td>
  <td>{stats.get('total_distance', '-')} km</td>
  <td>{'<span class="status ok">OK</span>' if validation.get('valid') else '<span class="status warn">Prüfen</span>'}</td>
  <td>{actions}</td>
</tr>"""
        )

    latest = runs[0] if runs else {}
    latest_stats = latest.get("stats", {})
    latest_validation = latest.get("validation", {})
    latest_event = latest.get("event", {})
    latest_summary = "Noch kein Run vorhanden."
    if latest:
        event_bits = [latest_event.get("title") or "Running Dinner"]
        if latest_event.get("date"):
            event_bits.append(latest_event["date"])
        latest_summary = f"{html.escape(' | '.join(event_bits))}<br><span class='muted'>Run: {html.escape(latest.get('run_id', ''))}</span>"

    table_body = "\n".join(rows) or "<tr><td colspan='7' class='muted'>Noch keine Runs vorhanden.</td></tr>"
    body = f"""
<div class="page-title">
  <div>
    <h1>Runs steuern und prüfen</h1>
    <p>Daten importieren, Optimierung starten, Validierung prüfen und alle Karten sowie E-Mail-Entwürfe pro Run wiederfinden.</p>
  </div>
  <span class="status ok">bereit</span>
</div>
<div class="top-grid">
  <form action="/runs" method="post" enctype="multipart/form-data">
    <h2>Neuen Run starten</h2>
    <div class="dropzone">
      <label for="input_file">Teilnahmedaten hochladen</label>
      <input id="input_file" name="input_file" type="file" accept=".json,.csv,.xlsx,application/json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required>
    </div>
    <p class="help">Unterstützt JSON, CSV und XLSX. LimeSurvey-Fragecodes werden automatisch erkannt.</p>
    <div class="form-row">
      <div>
        <label for="trials">Optimierungsversuche</label>
        <input id="trials" name="trials" type="number" min="1" max="50000" value="5000">
      </div>
      <div>
        <label for="label">Run-Label</label>
        <input id="label" name="label" type="text" placeholder="summer-2026-final">
      </div>
    </div>
    <h3>Rahmeninformationen für die E-Mail</h3>
    <label for="event_title">Titel</label>
    <input id="event_title" name="event_title" type="text" value="Running Dinner">
    <div class="form-row">
      <div>
        <label for="event_date">Datum</label>
        <input id="event_date" name="event_date" type="date">
      </div>
      <div>
        <label for="event_time">Startzeit</label>
        <input id="event_time" name="event_time" type="time">
      </div>
    </div>
    <label for="event_meeting_point">Treffpunkt / Abschlussort (optional)</label>
    <input id="event_meeting_point" name="event_meeting_point" type="text" placeholder="z.B. Abschluss ab 21:30 im ...">
    <label for="event_meeting_point_en">Meeting / final location (English, optional)</label>
    <input id="event_meeting_point_en" name="event_meeting_point_en" type="text" placeholder="e.g. final meetup from 21:30 at ...">
    <label for="event_info">Weitere Informationen (Deutsch)</label>
    <textarea id="event_info" name="event_info" placeholder="Zeitplan, Mitbringen, Kontakt zur Orga, Hinweise zum Versand ..."></textarea>
    <label for="event_info_en">Additional information (English)</label>
    <textarea id="event_info_en" name="event_info_en" placeholder="Timing, what to bring, organizing team contact, sending notes ..."></textarea>
    <button class="full" type="submit">
      <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      Run starten
    </button>
  </form>
  <section class="panel">
    <h2>Letzter Stand</h2>
    <p class="muted">{latest_summary}</p>
    <div class="metric-grid">
      <div class="metric"><span>Aktive Teams</span><strong>{latest_stats.get('active_teams', '-')}</strong></div>
      <div class="metric"><span>Importiert</span><strong>{latest_stats.get('imported_teams', '-')}</strong></div>
      <div class="metric"><span>Inaktiv</span><strong>{latest_stats.get('inactive_teams', '-')}</strong></div>
      <div class="metric"><span>Distanz</span><strong>{latest_stats.get('total_distance', '-')}</strong></div>
    </div>
    <div class="summary-line">
      {_status_badge(latest.get('status', 'kein Run'), latest_validation.get('valid')) if latest else '<span class="status warn">kein Run</span>'}
      {'<span class="status ok">Validierung OK</span>' if latest_validation.get('valid') else '<span class="status warn">Validierung offen</span>'}
      {f'<span class="status warn">{latest_stats.get("same_address_conflicts", 0)} Adresskonflikte erkannt</span>' if latest else ''}
    </div>
  </section>
</div>
<div class="section-head">
  <h2>Run-Historie</h2>
  <span class="muted">{len(runs)} gespeicherte Runs</span>
</div>
<div class="run-table-wrap">
  <div class="table-scroll">
    <table>
      <thead>
        <tr><th>Run</th><th>Zeit</th><th>Status</th><th>Teams</th><th>Distanz</th><th>Validierung</th><th>Aktionen</th></tr>
      </thead>
      <tbody>{table_body}</tbody>
    </table>
  </div>
</div>
"""
    return _page("Running Dinner Pipeline", body)


@app.post("/runs")
async def create_run(
    input_file: UploadFile = File(...),
    trials: int = Form(5000),
    label: str = Form(""),
    event_title: str = Form("Running Dinner"),
    event_date: str = Form(""),
    event_time: str = Form(""),
    event_meeting_point: str = Form(""),
    event_meeting_point_en: str = Form(""),
    event_info: str = Form(""),
    event_info_en: str = Form(""),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_path = Path(input_file.filename or "upload.json")
    suffix = original_path.suffix.lower()
    if suffix not in {".json", ".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use JSON, CSV, or XLSX.")
    base_name = _slug(label or original_path.stem)
    run_id = f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}-{base_name}"
    input_path = UPLOAD_DIR / f"{run_id}{suffix}"
    with input_path.open("wb") as f:
        shutil.copyfileobj(input_file.file, f)

    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "title": event_title or "Running Dinner",
        "date": event_date or "",
        "time": event_time or "",
        "meeting_point": event_meeting_point or "",
        "meeting_point_en": event_meeting_point_en or "",
        "additional_info": event_info or "",
        "additional_info_en": event_info_en or "",
    }
    _write_initial_manifest(run_dir, run_id, input_path, trials, event)
    (run_dir / "pipeline.log").write_text(
        f"[{datetime.now().isoformat(timespec='seconds')}] Run queued from Web App.\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "main.py",
        "--input",
        str(input_path),
        "--output",
        str(OUTPUT_ROOT),
        "--db",
        str(DATA_DIR / "intermediate" / "dinner.db"),
        "--trials",
        str(trials),
        "--run-id",
        run_id,
        "--event-title",
        event_title,
        "--event-date",
        event_date,
        "--event-time",
        event_time,
        "--event-meeting-point",
        event_meeting_point,
        "--event-meeting-point-en",
        event_meeting_point_en,
        "--event-info",
        event_info,
        "--event-info-en",
        event_info_en,
    ]
    _run_pipeline_in_background(cmd, run_dir, run_id)

    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(run_id: str):
    run_dir = _run_dir(run_id)
    manifest = _read_json(run_dir / "manifest.json", {})
    status = manifest.get("status") or "running"
    is_running = status in {"running", "started"}
    stats = manifest.get("stats", {})
    validation = manifest.get("validation", {})
    artifacts = manifest.get("artifacts", {})
    event = manifest.get("event", {})

    email_files = sorted((run_dir / "emails").glob("*.txt")) if (run_dir / "emails").exists() else []
    map_files = sorted((run_dir / "maps").glob("*.html")) if (run_dir / "maps").exists() else []
    error_html = ""
    if manifest.get("error"):
        error_html = f"<p class='status-failed'>{html.escape(manifest['error'])}</p>"

    validation_errors = "".join(f"<li>{html.escape(e)}</li>" for e in validation.get("errors", []))
    if not validation_errors:
        validation_errors = "<li class='muted'>Keine Validierungsfehler gespeichert.</li>"
    inactive_names = stats.get("inactive_team_names", []) or []
    inactive_html = "".join(f"<li>{html.escape(name)}</li>" for name in inactive_names)
    inactive_notice = ""
    if inactive_names:
        inactive_notice = f"""
        <div class="notice warning">
          <strong>{len(inactive_names)} inaktive Teams</strong>
          <ul>{inactive_html}</ul>
        </div>
        """

    email_links = "".join(
        f"<li><a href='/runs/{html.escape(run_id)}/files/emails/{html.escape(path.name)}'>{html.escape(path.name)}</a></li>"
        for path in email_files
    ) or "<li class='muted'>Keine E-Mail-Dateien vorhanden.</li>"
    map_links = "".join(
        f"<li><a href='/runs/{html.escape(run_id)}/files/maps/{html.escape(path.name)}'>{html.escape(path.name)}</a></li>"
        for path in map_files
    ) or "<li class='muted'>Keine Karten vorhanden.</li>"

    aggregate_link = ""
    if (run_dir / "aggregated_map.html").exists():
        aggregate_link = f"<a class='button' href='/runs/{html.escape(run_id)}/files/aggregated_map.html'>Gesamtkarte öffnen</a>"

    log_link = ""
    if (run_dir / "pipeline.log").exists():
        log_link = f"<a class='button secondary' href='/runs/{html.escape(run_id)}/files/pipeline.log'>Log öffnen</a>"

    log_tail_html = ""
    log_path = run_dir / "pipeline.log"
    if log_path.exists():
        log_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        log_tail = "\n".join(log_lines[-80:]) or "Noch keine Log-Ausgabe vorhanden."
        log_tail_html = f"""
<section class="panel">
  <h2>{'Live-Log' if is_running else 'Pipeline-Log'}</h2>
  <pre class="log-tail">{html.escape(log_tail)}</pre>
</section>
"""

    progress_html = ""
    auto_refresh = ""
    if is_running:
        progress_html = """
<div class="notice progress-card">
  <span class="spinner" aria-hidden="true"></span>
  <div>
    <strong>Run läuft</strong>
    <p class="muted" style="margin: 4px 0 0;">Die Seite aktualisiert sich automatisch. Das Log unten zeigt die letzten Pipeline-Schritte.</p>
  </div>
</div>
"""
        auto_refresh = "<script>setTimeout(() => window.location.reload(), 3000);</script>"

    body = f"""
<div class="page-title">
  <div>
    <h1>Run <code>{html.escape(run_id)}</code></h1>
    <p>Status, Validierung und Artefakte dieses Laufs.</p>
  </div>
  {_status_badge(status, validation.get('valid'))}
</div>
{error_html}
{progress_html}
<div class="links" style="margin-bottom: 18px;">
  <a class="button secondary" href="/">
    <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    Zur Run-Liste
  </a>
  {aggregate_link}
  <a class="button secondary" href="/runs/{html.escape(run_id)}/download.zip">
    <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3v12m0 0l4-4m-4 4l-4-4M5 21h14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    Run als ZIP
  </a>
  {log_link}
</div>
<div class="metric-grid">
  <div class="metric"><span>Importiert</span><strong>{stats.get('imported_teams', '-')}</strong></div>
  <div class="metric"><span>Aktiv</span><strong>{stats.get('active_teams', '-')}</strong></div>
  <div class="metric"><span>Inaktiv</span><strong>{stats.get('inactive_teams', '-')}</strong></div>
  <div class="metric"><span>Distanz</span><strong>{stats.get('total_distance', '-')}</strong></div>
</div>
{inactive_notice}
<section class="panel">
  <h2>Rahmeninformationen</h2>
  <p><strong>{html.escape(event.get('title') or 'Running Dinner')}</strong></p>
  <p>Datum: {html.escape(event.get('date') or '-')} · Startzeit: {html.escape(event.get('time') or '-')}</p>
  <p>Treffpunkt / Abschlussort: {html.escape(event.get('meeting_point') or '-')}</p>
  <p>Meeting / final location: {html.escape(event.get('meeting_point_en') or '-')}</p>
  <p class="muted">{html.escape(event.get('additional_info') or 'Keine weiteren Informationen hinterlegt.')}</p>
  <p class="muted">{html.escape(event.get('additional_info_en') or 'No additional English information stored.')}</p>
</section>
<div class="grid" style="margin-top: 18px;">
  <section class="panel">
    <h2>Status</h2>
    <p><strong>{html.escape(status)}</strong></p>
    <p class="muted">Erstellt: {html.escape(_format_datetime(manifest.get('created_at', '')))}</p>
    <p>Teams: {stats.get('imported_teams', '-')} importiert, {stats.get('active_teams', '-')} aktiv</p>
    <p>Gesamtdistanz: {stats.get('total_distance', '-')} km</p>
    <p>Adresskonflikte: {stats.get('same_address_conflicts', 0)}</p>
    <p>Artefaktpfad: <code>{html.escape(artifacts.get('run_dir', ''))}</code></p>
  </section>
  <section class="panel">
    <h2>Validierung</h2>
    <p>{'<span class="status ok">OK</span>' if validation.get('valid') else '<span class="status warn">Nicht OK oder noch nicht gelaufen</span>'}</p>
    <ul>{validation_errors}</ul>
  </section>
</div>
<div class="grid">
  <section class="panel">
    <h2>E-Mail-Entwürfe</h2>
    <ul class="artifact-list">{email_links}</ul>
  </section>
  <section class="panel">
    <h2>Team-Karten</h2>
    <ul class="artifact-list">{map_links}</ul>
  </section>
</div>
{log_tail_html}
<section class="panel">
  <h2>Manifest</h2>
  <pre>{html.escape(json.dumps(manifest, ensure_ascii=False, indent=2))}</pre>
</section>
{auto_refresh}
"""
    return _page(f"Run {run_id}", body)


@app.get("/runs/{run_id}/files/{file_path:path}")
def run_artifact(run_id: str, file_path: str):
    path = _run_file(run_id, file_path)
    if path.suffix == ".log" or path.suffix == ".txt" or path.suffix == ".json":
        return PlainTextResponse(path.read_text(encoding="utf-8"))
    return FileResponse(path)


@app.get("/runs/{run_id}/download.zip")
def run_zip(run_id: str):
    run_dir = _run_dir(run_id)
    zip_base = RUNS_DIR / run_id
    zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=run_dir)
    return FileResponse(zip_path, media_type="application/zip", filename=f"{run_id}.zip")
