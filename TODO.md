# TODO / 메모

작업하면서 "나중에 사람이 결정·확인해야 하는 것"을 모아 두는 문서입니다.
결함 목록과 자동 점검은 `scripts/regressions.json`, 점검 실행은 `python scripts/check.py`입니다.
항목을 끝내면 지우고, 결정이 나면 날짜와 함께 남겨 주세요.

## 운영 반영 때 (사람이 해야 함)

- [ ] **로그인 시도 제한을 다시 켜기 (R018)** — 데모 시연을 위해 2026-10에 꺼 뒀습니다(기본값 꺼짐). **운영 공개 전에 반드시 켜세요.**
  서버: `.env`에 `LOGIN_RATE_LIMIT_ENABLED=true` / 화면: `VITE_LOGIN_GUARD=true npm run build` 후 `frontend/dist` 커밋.
  켜면 아이디 5회·IP 20회 실패 시 15분 잠금입니다(프록시 뒤라면 아래 항목도 함께).

- [ ] **마이그레이션 적용** — `cd backend && alembic upgrade head`
  - 이번 변경분: `d5e6f7a8b9c0`(로그인 시도 기록 테이블), `e6f7a8b9c0d1`(기존 가입 증빙의 삭제 기한을 5년 기준으로 재계산)
  - **코드 배포보다 먼저** 적용합니다. 순서가 어긋나면 로그인 자체가 실패합니다 (R003·R016과 같은 유형).
- [ ] **증빙 문서 삭제 작업 정기 실행 설정** — 보관 기간 5년이 지난 문서를 지우는 명령은 만들어 두었지만, 서버가 스스로 부르지는 않습니다.
  - 명령: `cd backend && python -m scripts.purge_registration_documents` (`--dry-run`으로 대상 먼저 확인)
  - 운영 서버의 cron / Windows 작업 스케줄러에 하루 1회로 등록해야 실제로 삭제됩니다. (R017)
- [ ] **리버스 프록시 뒤에서 운영한다면** — 로그인 IP 제한이 프록시 주소를 보게 됩니다. uvicorn을 `--proxy-headers`로 실행하고 신뢰할 프록시를 지정하세요. (`backend/app/services/login_guard.py`)
- [ ] 운영 `.env`: `COOKIE_SECURE=true`(완료), `DEMO_MODE=false`, `APP_ENV=production` 확인
- [ ] 릴리스 전 `cd frontend && npm run build` 후 `frontend/dist`를 커밋 (배포 화면이 이 폴더입니다. `check.py`가 소스와 다르면 WARN)
- [ ] 학생 PC(Windows)에서 `python scripts/check.py`, `start.bat`을 한 번씩 실행해 보기

## 법령 근거 조문 (사용자 검토 대기)

- [ ] **`expected_articles` 사람 검토** — `backend/tests/legal/eval_cases.json`의 값은 AI가 초안으로 넣은 것(`reviewed: false`)입니다.
  명세상 기대 조문은 사람이 지정해야 하므로, 검토 전의 recall 수치는 참고만 하세요.
- [ ] 현재 검색 recall@8 = 32/35 (실패: case-008, case-009, case-025). 검토 후 다시 측정
- [ ] selector 실호출 평가(`pytest -m live -s`)는 한 번도 돌리지 않았음 (사례 35건 × LLM 2회 호출 비용)
- [ ] 임베딩 도입 여부는 위 수치를 본 뒤 결정 (명세 13-3)
- 결정(2026-10): 법령 DB는 SQLite 파일 방식을 유지합니다. `articles.json`만 배포하면 서버 시작 시 `legal.db`를 자동 생성합니다. 상태는 `/api/health/legal`.

## 같이 고민할 것

- [x] ~~배포 순서 강제 (R016)~~ — 결정(2026-10): **뒤처진 DB에서도 기동은 허용**. 요청은 설명 있는 503으로 실패하고 마이그레이션 후 재시작 없이 복구됨. 절차는 README "배포 순서"
- [ ] (R016 후속) 배포 환경이 정해지면 배포 스크립트/CI에 `python -m scripts.migrate`(확인) → `--upgrade` 단계를 고정할 것. 지금은 사람이 순서를 지킨다
- [ ] Supabase **트랜잭션 풀러(포트 6543)** 에서 psycopg3의 서버 측 prepared statement가 문제를 일으킬 수 있다는 보고가 있음.
  지금까지 증상은 확인하지 못했지만, 간헐적 오류가 보이면 `create_engine(..., connect_args={"prepare_threshold": None})` 적용을 검토 (검증 없이 바꾸지 않았음)

## 구조적 부채

- [x] ~~`App.tsx` 분리~~ — 완료(2026-10). `workspace/` 폴더 구조는 AGENTS.md "프런트엔드 구조" 참고
- [ ] `frontend/src/workspace/hooks/useWorkspace.ts`가 가장 큼(약 380줄). 늘어나면 상담 목록/메시지 전송/첨부로 나눌 것

## 아직 검증하지 못한 것

- [ ] Windows 실행 (`check.py`의 Postgres 경로, `npx.cmd`, `start.bat`/`start.ps1`)
- [ ] 다크 모드 화면 (자동 검증 없음)
- [ ] 음성 입력, 인쇄(PDF) — 브라우저 기능이라 자동화하지 않음
- [ ] 실제 Claude 응답으로 화면 확인 (E2E는 데모 모드)
- [ ] PyInstaller exe 패키징 — `launcher.py` + `frontend/dist` + `data/legal/articles.json`이 묶이는지, exe에서 `legal.db` 자동 생성이 되는지
- [x] 이전 비밀번호가 git 이력에 남아 있음 — 계정 비밀번호는 변경 완료. 저장소가 외부에 공개된 적이 있다면 이력 정리 검토
