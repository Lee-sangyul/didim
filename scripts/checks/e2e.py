"""API 시나리오: 로그인 -> 상담 -> 채팅 -> 첨부 -> 타인 접근 차단 -> 삭제 -> 로그아웃.

DB 종류(SQLite/Postgres)는 환경변수 DATABASE_URL이 정한다.
SQLite에서는 외래키 강제를 켠다(Postgres와 같은 조건). 외부 AI·법령 API는 호출하지 않는다(DEMO_MODE).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .core import FAIL, PASS, Result

PASSWORD = "check-only-pw-1234"


def _sse(text: str) -> list[dict]:
    return [json.loads(b[6:]) for b in text.split("\n\n") if b.startswith("data: ")]


def run_scenario(label: str) -> list[Result]:
    from fastapi.testclient import TestClient
    from sqlalchemy import event, text
    from sqlmodel import Session, select

    from app.config import settings
    from app.database import engine
    from app.main import UPLOAD_DIR, app
    from app.models import Assessment, Attachment, Case, Message, User
    from app.security.password import hash_password

    results: list[Result] = []

    def step(name: str, ok: bool, detail: str = "") -> bool:
        results.append(Result(f"[{label}] {name}", PASS if ok else FAIL, "" if ok else detail))
        return ok

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _fk_on(conn, _record):  # noqa: ANN001
            conn.execute("PRAGMA foreign_keys=ON")

    tag = uuid.uuid4().hex[:6]
    owner, other = f"chk_a_{tag}", f"chk_b_{tag}"

    with TestClient(app) as anon:  # startup(스키마 보충·업로드 폴더) 실행
        if not step("서버 기동(startup)", anon.get("/api/health").status_code == 200, "health != 200"):
            return results

        with Session(engine) as s:
            for username in (owner, other):
                s.add(User(username=username, password_hash=hash_password(PASSWORD), name=username))
            s.commit()

        health = anon.get("/api/health").json()
        step("외부 호출 없는 데모 모드", health.get("mode") == "demo", f"mode={health.get('mode')}")
        step("미로그인 요청은 401", anon.get("/api/cases").status_code == 401, "401이 아님")
        step(
            "잘못된 비밀번호는 거부",
            anon.post("/api/auth/login", json={"username": owner, "password": "wrong-password"}).status_code == 401,
            "401이 아님",
        )

        with TestClient(app) as a, TestClient(app) as b:
            if not step(
                "로그인",
                a.post("/api/auth/login", json={"username": owner, "password": PASSWORD}).status_code == 200,
                "로그인 실패",
            ):
                return results
            b.post("/api/auth/login", json={"username": other, "password": PASSWORD})

            created = a.post("/api/cases", json={"title": "점검"})
            if not step("상담 생성", created.status_code == 200, f"{created.status_code} {created.text[:120]}"):
                return results
            case_id = created.json()["id"]
            step("상담 목록에 포함", case_id in [c["id"] for c in a.get("/api/cases").json()], "목록에 없음")

            chat = a.post(f"/api/cases/{case_id}/chat", json={"content": "학부모가 매일 전화로 욕설을 합니다."})
            events = _sse(chat.text)
            kinds = [e["type"] for e in events]
            done = next((e for e in events if e["type"] == "done"), None)
            step("채팅 스트리밍(delta -> done)", "delta" in kinds and done is not None and "error" not in kinds, f"이벤트: {kinds[:5]}...")
            if done:
                keys = {"level", "score", "category", "rationale", "actions", "based_law", "citations"}
                step("응답에 평가 필드 포함", keys <= set(done["assessment"]), f"누락: {keys - set(done['assessment'])}")

            msgs = a.get(f"/api/cases/{case_id}/messages").json()
            roles = [m["role"] for m in msgs]
            step("메시지 저장(안내·질문·답변)", roles == ["assistant", "user", "assistant"], f"roles={roles}")
            step("평가 이력 저장", len(a.get(f"/api/cases/{case_id}/assessments").json()) == 1, "평가가 1건이 아님")

            # 답변 다시 생성: 사용자 메시지가 늘지 않고 같은 답변에 버전이 쌓여야 한다 (R010)
            answer_id, greeting_id = msgs[-1]["id"], msgs[0]["id"]
            regen = a.post(f"/api/cases/{case_id}/messages/{answer_id}/regenerate")
            regen_events = _sse(regen.text)
            step(
                "답변 다시 생성(delta -> done)",
                regen.status_code == 200 and any(e["type"] == "done" for e in regen_events)
                and not any(e["type"] == "error" for e in regen_events),
                f"{regen.status_code} {[e['type'] for e in regen_events][:4]}",
            )
            after = a.get(f"/api/cases/{case_id}/messages").json()
            step(
                "재생성 후 메시지 수 불변(사용자 질문 중복 없음)",
                [m["role"] for m in after] == roles, f"roles={[m['role'] for m in after]}",
            )
            step(
                "재생성 버전이 같은 답변에 저장",
                len(after[-1]["versions"]) == 2 and after[-1]["content"] == after[-1]["versions"][-1],
                f"versions={len(after[-1]['versions'])}",
            )
            step(
                "안내 메시지·타인 요청은 재생성 거부",
                a.post(f"/api/cases/{case_id}/messages/{greeting_id}/regenerate").status_code in (400, 409)
                and b.post(f"/api/cases/{case_id}/messages/{answer_id}/regenerate").status_code == 404,
                "거부되지 않음",
            )

            payload = b"%PDF-1.4 check"
            up = a.post(f"/api/cases/{case_id}/attachments", files={"file": ("증거.pdf", payload, "application/pdf")})
            if step("첨부 업로드", up.status_code == 200, f"{up.status_code} {up.text[:120]}"):
                att_id = up.json()["id"]
                dl = a.get(f"/api/cases/{case_id}/attachments/{att_id}/download")
                step("첨부 다운로드(내용 일치)", dl.status_code == 200 and dl.content == payload, f"{dl.status_code}")
                step("첨부 목록", len(a.get(f"/api/cases/{case_id}/attachments").json()) == 1, "1건이 아님")

            step(
                "타인 상담 접근 차단(404)",
                all(
                    r.status_code == 404
                    for r in (
                        b.get(f"/api/cases/{case_id}/messages"),
                        b.post(f"/api/cases/{case_id}/chat", json={"content": "침입 시도입니다"}),
                        b.delete(f"/api/cases/{case_id}"),
                    )
                ),
                "다른 사용자가 접근 가능",
            )

            stored = list((UPLOAD_DIR / str(case_id)).glob("*"))
            deleted = a.delete(f"/api/cases/{case_id}")
            step("상담 삭제(204, 외래키 순서)", deleted.status_code == 204, f"{deleted.status_code} {deleted.text[:160]}")

            with Session(engine) as s:
                left = (
                    len(s.exec(select(Message).where(Message.case_id == case_id)).all())
                    + len(s.exec(select(Assessment).where(Assessment.case_id == case_id)).all())
                    + len(s.exec(select(Attachment).where(Attachment.case_id == case_id)).all())
                    + (1 if s.get(Case, case_id) else 0)
                )
            step("삭제 후 연관 데이터 없음", left == 0, f"{left}건 남음")
            step("삭제 후 업로드 파일 제거", not any(p.exists() for p in stored), "파일이 남음")

            a.post("/api/auth/logout")
            step("로그아웃 후 접근 차단", a.get("/api/cases").status_code == 401, "여전히 접근 가능")

        # 점검 계정 정리 (Postgres 임시 DB여도 흔적을 남기지 않는다)
        with Session(engine) as s:
            s.execute(text("DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE username IN (:a,:b))"), {"a": owner, "b": other})
            s.execute(text("DELETE FROM users WHERE username IN (:a,:b)"), {"a": owner, "b": other})
            s.commit()

    return results
