# Township Water Guardian

A water-operations prototype with a light blue and warm-neutral Next.js dashboard,
real recorded sensor replay, and a LangGraph investigation and approval workflow.
**ML training is separate. No Monitor model is trained by this application.**

## Run locally on Windows

Dependencies are already installed on this machine. From this project folder:

```powershell
.\scripts\start-dev.ps1 -WithLocalLLM
```

Open <http://127.0.0.1:3000>. The backend API is at
<http://127.0.0.1:9000/docs>. First startup loads recorded observations; allow a
few seconds for the services to become ready. Logs are written under `work/`.

For a new machine, install Python 3.12+, Node.js 20.9+ and pnpm, then run:

```powershell
.\scripts\setup.ps1
.\scripts\start-dev.ps1
```

Stop only the services started by this project with:

```powershell
.\scripts\stop-dev.ps1
```

Scripts also recognise the bundled Codex runtimes on this machine. If Windows
blocks local scripts, invoke the script with `powershell -ExecutionPolicy Bypass
-File .\scripts\start-dev.ps1 -WithLocalLLM` for that launch.

## Provider configuration

The root `.env` exists with blank `GROQ_API_KEY` and `GEMINI_API_KEY` fields.
Fill those in and restart the backend. Credentials stay in the backend; the
frontend `.env.local` contains only its API URL. Environment files are ignored
by Git, while `.env.example` documents the settings.

Each structured agent request tries **Groq → Gemini → Ollama**. Missing cloud
keys are skipped. Failed requests or invalid responses advance to the next
provider. If all providers fail, an explicitly labelled evidence-only response
keeps the approval workflow usable. Provider use appears in Agent activity.

The supplied local folder is an Ollama model store, configured as:

- Model: `qwen3.5:2b-q4_K_M`
- Store: `D:/SCHOLARSHIPS/My Items/Degree Project/Qwen3.5_2B`
- Server: <http://127.0.0.1:11434>

`-WithLocalLLM` starts the installed Ollama server with that store when no local
server is running. It reuses a running server and does not download another model.
Keep `OLLAMA_MODEL` consistent with the tags in your running Ollama server.

The backend uses port 9000 because Windows has reserved port 8000 on this machine.
To change it, update `BACKEND_PORT` in the root `.env` and the matching
`NEXT_PUBLIC_API_URL` in `frontend/.env.local`, then restart the services.

## What is implemented

- Three illustrative deployment zones: industrial facilities, parks/irrigation,
  and malls. Each has its own virtual device, recording assignment and replay
  session.
- Nine WDSEventDB recordings read from the existing dataset folder. Original
  spreadsheets are preserved. The dashboard plots recorded samples and original
  sensor values, with configurable channels and replay speed.
- A software ESP32-style publisher sends actual recorded measurements as JSON
  over HTTP to FastAPI. This is a software device simulation, not an electrical
  ESP32 simulator. The API can later receive the same packet format from hardware.
- SQLite stores telemetry, immutable incident evidence, investigations, a
  configured demonstration crew roster, work orders and the activity log.
- **Orchestrator:** LangGraph controls the investigation and persists its approval
  checkpoint in a separate SQLite file.
- **Diagnosis agent:** receives sensor-window statistics and, when available,
  the Monitor prediction; produces a validated assessment and inspection advice.
- **Dispatch agent:** checks available crews by skill and zone; produces a draft
  task. Crew IDs are checked against the eligible roster.
- **Human approval:** approve or reject, then start and complete an authorised
  task. A crew is reserved only at approval and released on completion. Approval
  can resume after a backend restart.
- **Monitor adapter:** loads an independently exported joblib model; automatic
  investigations become available when it predicts a leak or sensor fault.
- Settings and Evaluation screens. Evaluation stays empty until actual measured
  results are exported. No RAG is included in this version.

## Demo before ML training

1. On Overview, start replay and select a zone and sensor channel.
2. Choose **Investigate readings**. Until training, the classification remains
   **Needs review**; the agents prepare an inspection based on the observations.
3. Follow **Investigations** and **Agent activity** to see the assessment and task.
4. Review the draft in **Work orders**. Approve or reject with an optional note.
5. An approved task can move to **In progress**, then **Completed**. These are
   recorded demonstration actions; no external crew messages are sent.
6. Pause replay before changing a recording or starting sample in Settings.

The initial workspace preloads the first 120 measured samples per zone so there
is evidence to explore immediately. Playback continues from there. Reset creates
new replay sessions and preserves previous investigations and their evidence.

## Connect the model later

Train and evaluate separately, then save the bundle to `models/monitor.joblib`.
The bundle contains `model`, ordered `features`, `class_map`, and an optional
`version`. The model receives a pandas DataFrame, so include preprocessing inside
the saved pipeline. Use **Settings → Reload model**, or restart the backend.
See [models/README.md](models/README.md) for the export contract.

Before connecting a model, the API returns no ML prediction. A manual LLM review
is not presented as a trained leak detector. Ground-truth columns, filenames and
scenario metadata are excluded from the operational input. Hold out complete
recordings when evaluating, and establish the training target from the event
documentation rather than assuming a three-class label column.

This initial adapter accepts named sensor channels per sample. If the trained
model needs rolling-window features, add that feature builder to the Monitor
adapter at integration time. Load joblib files exported by your team; pickle-based
model files execute Python during loading.

## Data and evidence

WDSEventDB is a public physical water-distribution laboratory dataset. These
recordings are not SDP telemetry or measurements from industrial facilities,
parks or malls. Zone assignments and the crew roster are demonstration context.
Replay speed and arrival timestamps are not the original measurement interval.
The dashboard uses original sensor units until calibration metadata is verified,
so it does not invent litres saved, monetary savings or field accuracy.

Dataset source, licence and attribution: [DATA_SOURCES.md](DATA_SOURCES.md).

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
pnpm typecheck
pnpm build
```

The backend tests use isolated temporary databases and mocked provider responses.
They check source measurements, prohibited labels, duplicate and stale packets,
model loading, provider fallback, persistent approval, crew rechecks, and task
transitions. They do not train an ML model or call paid cloud APIs.

Next.js uses its supported Webpack mode because the Turbopack CSS worker failed
in this Windows runtime. Both development and production scripts use that mode.
