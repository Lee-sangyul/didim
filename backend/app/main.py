import json
import sys
import uuid
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .demo import DemoAssessment, assess, demo_reply
from .models import Assessment, Attachment, Case, Message, now_iso
from .privacy import mask_pii
from .risk import assess_with_claude, bucket, split_countermeasures

from sqlmodel import Session, SQLModel, select

from .config import ROOT, settings
from .database import engine, get_session
from .routers import auth_router

if getattr(sys, "frozen", False):
    app_root = Path(sys.executable).resolve().parent
else:
    app_root = ROOT

FRONTEND_DIST = app_root / "frontend" / "dist"
UPLOAD_DIR = settings.upload_dir

app = FastAPI(title="디딤 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)

SYSTEM = """당신은 교권 침해 상담 도우미 '디딤'입니다. 한국어로 차분하고 지지적으로 답하세요. 법률 자문이나 확정 판단을 하지 마세요. 제공되지 않은 법령 조항을 지어내지 마세요. 개인정보 최소화, 증거 원본 보존, 관리자 보고, 교원단체·법률 전문가 검토 같은 절차를 안내하세요. 학생에게 해가 되는 조언, 은폐, 보복, 불법행위를 돕지 마세요. 즉각적인 신체 위험이 있으면 안전 확보와 긴급기관 연락을 먼저 권고하세요."""

MAX_UPLOAD_BYTES = settings.max_upload_bytes


class CreateCase(BaseModel):
    title: str = "새 상담"


class ChatInput(BaseModel):
    content: str = Field(min_length=2, max_length=8000)


class CasePublic(BaseModel):
    id: int
    title: str
    category: str
    risk_level: str
    risk_score: int
    based_law: list[str]
    created_at: str
    updated_at: str


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    role: str
    content: str
    created_at: str


class AssessmentPublic(BaseModel):
    id: int
    case_id: int
    message_id: Optional[int]
    risk_level: str
    risk_score: int
    category: str
    rationale: str
    based_law: list[str]
    actions: list[str]
    created_at: str


class AttachmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    filename: str
    content_type: str
    size: int
    created_at: str


def case_public(case: Case) -> CasePublic:
    try:
        based_law = json.loads(case.based_law or "[]")
    except json.JSONDecodeError:
        based_law = []
    return CasePublic(
        id=case.id or 0,
        title=case.title,
        category=case.category,
        risk_level=case.risk_level,
        risk_score=case.risk_score,
        based_law=based_law,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def assessment_public(item: Assessment) -> AssessmentPublic:
    try:
        based_law = json.loads(item.based_law or "[]")
    except json.JSONDecodeError:
        based_law = []
    try:
        actions = json.loads(item.actions or "[]")
    except json.JSONDecodeError:
        actions = []
    return AssessmentPublic(
        id=item.id or 0,
        case_id=item.case_id,
        message_id=item.message_id,
        risk_level=item.risk_level,
        risk_score=item.risk_score,
        category=item.category,
        rationale=item.rationale,
        based_law=based_law,
        actions=actions,
        created_at=item.created_at,
    )

@app.on_event("startup")
def startup() -> None:
    if settings.is_sqlite:
        SQLModel.metadata.create_all(engine)

        with engine.connect() as conn:
            cols = {
                row[1]
                for row in conn.exec_driver_sql(
                    'PRAGMA table_info("case")'
                ).fetchall()
            }

            if "based_law" not in cols:
                conn.exec_driver_sql(
                    'ALTER TABLE "case" '
                    "ADD COLUMN based_law VARCHAR DEFAULT '[]'"
                )
                conn.commit()

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

@app.get("/api/health")
def health() -> dict:
    demo = settings.demo_mode or not settings.anthropic_api_key

    return {
        "ok": True,
        "mode": "demo" if demo else "claude",
        "environment": settings.app_env,
    }


@app.get("/api/cases", response_model=list[CasePublic])
def list_cases(session: Session = Depends(get_session)) -> list[CasePublic]:
    return [case_public(item) for item in session.exec(select(Case).order_by(Case.updated_at.desc()))]


@app.post("/api/cases", response_model=CasePublic)
def create_case(body: CreateCase, session: Session = Depends(get_session)) -> CasePublic:
    case = Case(title=body.title.strip() or "새 상담")
    session.add(case); session.commit(); session.refresh(case)
    greeting = Message(case_id=case.id or 0, role="assistant", content="안녕하세요. 겪고 계신 상황을 시간 순서대로 적어 주세요. 실명·전화번호 등 개인정보는 입력하지 않는 것이 좋습니다.")
    session.add(greeting); session.commit()
    return case_public(case)


@app.get("/api/cases/{case_id}/messages", response_model=list[MessagePublic])
def messages(case_id: int, session: Session = Depends(get_session)) -> list[MessagePublic]:
    return [MessagePublic.model_validate(item) for item in session.exec(select(Message).where(Message.case_id == case_id).order_by(Message.id))]


@app.get("/api/cases/{case_id}/assessments", response_model=list[AssessmentPublic])
def assessments(case_id: int, session: Session = Depends(get_session)) -> list[AssessmentPublic]:
    return [assessment_public(item) for item in session.exec(select(Assessment).where(Assessment.case_id == case_id).order_by(Assessment.id))]


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: int, session: Session = Depends(get_session)) -> None:
    case = session.get(Case, case_id)
    if not case: raise HTTPException(404, "상담을 찾을 수 없습니다.")
    for msg in session.exec(select(Message).where(Message.case_id == case_id)):
        session.delete(msg)
    for item in session.exec(select(Assessment).where(Assessment.case_id == case_id)):
        session.delete(item)
    for att in session.exec(select(Attachment).where(Attachment.case_id == case_id)):
        path = UPLOAD_DIR / str(case_id) / att.stored_name
        path.unlink(missing_ok=True)
        session.delete(att)
    session.delete(case); session.commit()


@app.post("/api/cases/{case_id}/attachments", response_model=AttachmentPublic)
async def upload_attachment(case_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)) -> AttachmentPublic:
    case = session.get(Case, case_id)
    if not case: raise HTTPException(404, "상담을 찾을 수 없습니다.")
    original_name = Path(file.filename or "attachment").name
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    case_dir = UPLOAD_DIR / str(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    dest = case_dir / stored_name
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "파일 크기는 20MB를 초과할 수 없습니다.")
            out.write(chunk)
    attachment = Attachment(case_id=case_id, filename=original_name, stored_name=stored_name, content_type=file.content_type or "application/octet-stream", size=size)
    session.add(attachment); session.commit(); session.refresh(attachment)
    return AttachmentPublic.model_validate(attachment)


@app.get("/api/cases/{case_id}/attachments", response_model=list[AttachmentPublic])
def list_attachments(case_id: int, session: Session = Depends(get_session)) -> list[AttachmentPublic]:
    return [AttachmentPublic.model_validate(item) for item in session.exec(select(Attachment).where(Attachment.case_id == case_id).order_by(Attachment.id))]


@app.get("/api/cases/{case_id}/attachments/{attachment_id}/download")
def download_attachment(case_id: int, attachment_id: int, session: Session = Depends(get_session)) -> FileResponse:
    attachment = session.get(Attachment, attachment_id)
    if not attachment or attachment.case_id != case_id: raise HTTPException(404, "파일을 찾을 수 없습니다.")
    path = UPLOAD_DIR / str(case_id) / attachment.stored_name
    if not path.exists(): raise HTTPException(404, "파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=attachment.filename, media_type=attachment.content_type)


@app.delete("/api/cases/{case_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(case_id: int, attachment_id: int, session: Session = Depends(get_session)) -> None:
    attachment = session.get(Attachment, attachment_id)
    if not attachment or attachment.case_id != case_id: raise HTTPException(404, "파일을 찾을 수 없습니다.")
    path = UPLOAD_DIR / str(case_id) / attachment.stored_name
    path.unlink(missing_ok=True)
    session.delete(attachment); session.commit()


@app.post("/api/cases/{case_id}/chat")
def chat(case_id: int, body: ChatInput, session: Session = Depends(get_session)) -> StreamingResponse:
    case = session.get(Case, case_id)
    if not case: raise HTTPException(404, "상담을 찾을 수 없습니다.")
    original = body.content.strip()
    masked = mask_pii(original)
    demo_assessment = assess(masked)
    session.add(Message(case_id=case_id, role="user", content=original))
    case.category, case.risk_level, case.risk_score, case.updated_at = demo_assessment.category, demo_assessment.level, demo_assessment.score, now_iso()
    if case.title == "새 상담": case.title = masked[:28] + ("…" if len(masked) > 28 else "")
    session.add(case); session.commit()
    prior = list(session.exec(select(Message).where(Message.case_id == case_id).order_by(Message.id)))
    demo = settings.demo_mode or not settings.anthropic_api_key
    model_name = settings.anthropic_model

    def events():
        chunks: list[str] = []
        assessment: DemoAssessment = demo_assessment
        based_law: list[str] = []
        try:
            if demo:
                answer = demo_reply(masked, demo_assessment)
                for part in answer.split(" "):
                    token = part + " "; chunks.append(token)
                    yield f"data: {json.dumps({'type':'delta','text':token}, ensure_ascii=False)}\n\n"
            else:
                client = Anthropic(api_key=settings.anthropic_api_key)
                history = [{"role": m.role, "content": mask_pii(m.content)} for m in prior[-12:]]
                with client.messages.stream(model=model_name, max_tokens=1400, system=SYSTEM, messages=history) as stream:
                    for text in stream.text_stream:
                        chunks.append(text)
                        yield f"data: {json.dumps({'type':'delta','text':text}, ensure_ascii=False)}\n\n"
                try:
                    first_user = next((m.content for m in prior if m.role == "user"), original)
                    result = assess_with_claude(client, model_name, mask_pii(first_user), masked)
                    based_law = result["based_law"]
                    actions = split_countermeasures(result["countermeasures"]) or demo_assessment.actions
                    assessment = DemoAssessment(bucket(result["risk_level"]), result["risk_level"], demo_assessment.category, result["countermeasures"] or demo_assessment.rationale, actions)
                except Exception as exc:
                    print(f"risk assessment fallback ({case_id}): {exc}")
            final = "".join(chunks).strip()
            with Session(engine) as save:
                saved_case = save.get(Case, case_id)
                saved_case.risk_level, saved_case.risk_score, saved_case.category = assessment.level, assessment.score, assessment.category
                saved_case.based_law = json.dumps(based_law, ensure_ascii=False)
                reply_message = Message(case_id=case_id, role="assistant", content=final)
                save.add(saved_case); save.add(reply_message); save.commit(); save.refresh(reply_message)
                save.add(Assessment(
                    case_id=case_id,
                    message_id=reply_message.id,
                    risk_level=assessment.level,
                    risk_score=assessment.score,
                    category=assessment.category,
                    rationale=assessment.rationale,
                    based_law=json.dumps(based_law, ensure_ascii=False),
                    actions=json.dumps(assessment.actions, ensure_ascii=False),
                ))
                save.commit()
            yield f"data: {json.dumps({'type':'done','assessment':{**assessment.__dict__, 'based_law': based_law}}, ensure_ascii=False)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type':'error','message':'AI 응답 중 오류가 발생했습니다. 설정과 API 키를 확인하세요.'}, ensure_ascii=False)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
