# EMPath+

Research prototype for student wellbeing support, with a shared backend and a mobile app.

| Folder | Contents | Status |
|---|---|---|
| [backend/](backend/) | FastAPI + SQLite REST API with four components: C1 facial reference, C2 voice, C3 longitudinal risk, C4 interventions | Implemented (0.4.0) — see [backend/README.md](backend/README.md) |
| [mobile/](mobile/) | Expo (React Native) app that calls the backend API | Test app for all four components with demo data or real camera/microphone capture — see [mobile/README.md](mobile/README.md) |

## Quick start (backend)

Requires 64-bit Python 3.12.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate.bat
python -m pip install -r requirements-tested.txt
cp .env.example .env               # Windows: copy .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Then open <http://127.0.0.1:8000/docs>. Full setup, demos, tests and troubleshooting are in [backend/README.md](backend/README.md).

No component is a validated burnout, stress or clinical model, and the repository contains no real student data.
