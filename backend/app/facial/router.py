from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.facial.service import create_baseline, fail, now, participant, submit_session
from app.models import FacialBaseline, FacialSession, SelfReport
from app.schemas import BaselineCreate, BaselineOutput, CheckinInput, HistoryOutput, Ratings, SessionInput, SessionOutput

router = APIRouter(prefix="/facial", tags=["Component 1 - facial behaviour"])


@router.post("/calibrations", response_model=SessionOutput, status_code=201)
def calibrate(payload: SessionInput, request: Request, db: Session = Depends(get_db)):
    return submit_session(db, payload, "calibration", request.app.state.settings.enable_research_mode)


@router.post("/baselines", response_model=BaselineOutput, status_code=201)
def baseline(payload: BaselineCreate, request: Request, db: Session = Depends(get_db)):
    return create_baseline(db, payload, request.app.state.settings.enable_research_mode)


@router.get("/baselines/{participant_id}", response_model=list[BaselineOutput])
def baselines(participant_id: str, db: Session = Depends(get_db)):
    participant(db, participant_id)
    rows = db.scalars(select(FacialBaseline).where(FacialBaseline.participant_id == participant_id).order_by(FacialBaseline.version.desc())).all()
    return [r.summary for r in rows]


@router.post("/checkins", response_model=SessionOutput, status_code=201)
def checkin(payload: CheckinInput, request: Request, db: Session = Depends(get_db)):
    return submit_session(db, payload, "checkin", request.app.state.settings.enable_research_mode)


@router.get("/history/{participant_id}", response_model=HistoryOutput)
def history(participant_id: str, limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0), kind: str = Query(default="checkin", pattern="^(calibration|checkin|all)$"), db: Session = Depends(get_db)):
    participant(db, participant_id)
    where = [FacialSession.participant_id == participant_id]
    if kind != "all":
        where.append(FacialSession.kind == kind)
    total = db.scalar(select(func.count()).select_from(FacialSession).where(*where))
    rows = db.scalars(select(FacialSession).where(*where).order_by(FacialSession.recorded_at.desc(), FacialSession.id).offset(offset).limit(limit)).all()
    return HistoryOutput(participant_id=participant_id, total=total, offset=offset, limit=limit, sessions=[r.result for r in rows])


@router.post("/self-reports/{session_id}", response_model=Ratings, status_code=201)
def self_report(session_id: str, ratings: Ratings, request: Request, db: Session = Depends(get_db)):
    row = db.get(FacialSession, session_id)
    if row is None:
        fail(404, "session_not_found", "Unknown session ID.")
    if row.data_source == "local_research" and not request.app.state.settings.enable_research_mode:
        fail(403, "research_mode_disabled", "Research self-report collection is disabled.")
    old = db.get(SelfReport, session_id)
    if old:
        if old.ratings != ratings.model_dump():
            fail(409, "self_report_conflict", "This session already has a different self-report; responses are immutable.")
        return old.ratings
    db.add(SelfReport(session_id=session_id, participant_id=row.participant_id, created_at=now(), ratings=ratings.model_dump()))
    result = dict(row.result)
    result["request_self_report"] = False
    row.result = result
    db.commit()
    return ratings


@router.get("/self-reports/{session_id}", response_model=Ratings)
def read_self_report(session_id: str, db: Session = Depends(get_db)):
    report = db.get(SelfReport, session_id)
    if report is None:
        fail(404, "self_report_not_found", "No self-report exists for this session.")
    return report.ratings
