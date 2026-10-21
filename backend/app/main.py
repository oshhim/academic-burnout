from contextlib import asynccontextmanager
import logging
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.config import Settings
from app.database import make_engine, session_factory
from app.dependencies import authenticate
from app.facial.calculations import FEATURES, SCALE_FLOORS, MODEL_VERSION
from app.facial.router import router as facial_router
from app.participants import router as participants_router
from app.voice.router import router as voice_router
from app.voice.model import VoiceModel
from app.risk.router import router as risk_router
from app.risk.model import RiskModel
from app.interventions.router import router as interventions_router
from app.interventions.policy import status as intervention_status


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        # Alembic is deliberately responsible for schema creation/versioning.
        with engine.connect() as db:
            try:
                revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                if revision != "0005":
                    raise RuntimeError("Database revision mismatch. Run: python -m alembic upgrade head")
            except Exception as exc:
                raise RuntimeError("Initialize/update the database with: python -m alembic upgrade head") from exc
        app.state.voice_model = VoiceModel(settings.voice_model_dir).load()
        app.state.risk_model = RiskModel(settings.risk_model_dir).load()
        yield
        engine.dispose()

    app = FastAPI(title="EMPath+ Model Backend", version="0.5.0", lifespan=lifespan, description="C1 facial reference, C2 public voice baseline, C3 longitudinal exhaustion-proxy and C4 independent preference/feedback ranking with optional synthetic multimodal context.")
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessions = session_factory(engine)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-API-Key"], expose_headers=["X-Request-ID", "X-Process-Time-Ms"])

    @app.middleware("http")
    async def bounded_body_and_tracking(request: Request, call_next):
        rid = str(uuid4())
        request.state.request_id = rid
        start = perf_counter()
        # Read a bounded body even when Content-Length is absent/chunked.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            limit = settings.max_audio_request_bytes if request.url.path in {"/api/v1/voice/features", "/api/v1/voice/checkins"} else settings.max_request_bytes
            if size > limit:
                return JSONResponse(status_code=413, content={"error": {"code": "request_too_large", "message": "Request exceeds configured byte limit."}, "request_id": rid}, headers={"X-Request-ID": rid})
            chunks.append(chunk)
        request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time-Ms"] = f"{(perf_counter() - start) * 1000:.2f}"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": detail, "request_id": request.state.request_id})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        issues = [{"loc": list(e["loc"]), "type": e["type"], "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "issues": issues}, "request_id": request.state.request_id})

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        rid = getattr(request.state, "request_id", "unavailable")
        # Never log SQL statement parameters or submitted numerical windows here.
        logging.getLogger("empath").error("Unhandled %s request_id=%s", type(exc).__name__, rid)
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "The request could not be completed."}, "request_id": rid}, headers={"X-Request-ID": rid})

    @app.get("/health", tags=["Shared - health"])
    def health():
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable", "api_version": "0.5.0", "voice_model": app.state.voice_model.status()["status"], "risk_model": app.state.risk_model.status()}

    @app.get("/", include_in_schema=False)
    @app.get("/facial-demo", include_in_schema=False)
    def facial_demo_page():
        return FileResponse(Path(__file__).parent / "static" / "facial.html")

    @app.get("/voice-demo", include_in_schema=False)
    def voice_demo_page():
        return FileResponse(Path(__file__).parent / "static" / "voice.html")

    @app.get("/risk-demo", include_in_schema=False)
    def risk_demo_page():
        return FileResponse(Path(__file__).parent / "static" / "risk.html")

    @app.get("/interventions-demo", include_in_schema=False)
    def interventions_demo_page():
        return FileResponse(Path(__file__).parent / "static" / "interventions.html")

    @app.get("/voice-demo/samples", include_in_schema=False)
    def voice_samples():
        import json
        return json.loads((Path(__file__).parent / "static" / "voice_samples" / "manifest.json").read_text())

    @app.get("/voice-demo/audio/{filename}", include_in_schema=False)
    def voice_sample(filename: str):
        import json
        folder = Path(__file__).parent / "static" / "voice_samples"
        allowed = {r["filename"] for r in json.loads((folder / "manifest.json").read_text())["samples"]}
        if filename not in allowed:
            raise HTTPException(status_code=404, detail="Unknown bundled public sample")
        return FileResponse(folder / filename, media_type="audio/wav")

    api = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])

    @api.get("/models", tags=["Shared - model registry"])
    def models():
        return {
            "facial": {"status": "implemented", "method": "robust statistical calculation", "version": MODEL_VERSION, "trained_wellbeing_model": False, "clinical_validation": False},
            "voice": app.state.voice_model.status(),
            "risk": {**app.state.risk_model.status(), "component_status": "longitudinal_exhaustion_proxy_implemented", "burnout_prediction_validated": False},
            "interventions": intervention_status(),
        }

    @api.get("/facial/config", tags=["Component 1 - facial behaviour"])
    def config():
        return {"feature_schema_version": "facial-window-v1", "features": list(FEATURES), "scale_floors": SCALE_FLOORS, "minimum_calibration_sessions": 3,
                "minimum_usable_seconds": 8, "minimum_usable_fraction": 0.8,
                "minimum_usable_phase_seconds": 5, "deviation_levels": {"within_reference_range": "score < 1", "moderate_visual_change": "1 <= score < 2", "large_visual_change": "score >= 2"},
                "quality_gate": {"face_count": 1, "tracking_score_min": 0.6, "brightness_min": 0.15, "brightness_max": 0.95, "sharpness_min": 0.35, "max_abs_yaw_deg": 35, "max_abs_pitch_deg": 30},
                "threshold_status": "provisional_engineering_settings", "requires_local_validation": True}

    api.include_router(participants_router)
    api.include_router(facial_router)
    api.include_router(voice_router)
    api.include_router(risk_router)
    api.include_router(interventions_router)
    app.include_router(api)
    return app


app = create_app()
