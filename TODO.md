# TODO / 메모

작업하면서 "나중에 사람이 결정·확인해야 하는 것"을 모아 두는 문서입니다.
결함 목록과 자동 점검은 `scripts/regressions.json`, 점검 실행은 `python scripts/check.py`입니다.
항목을 끝내면 지우고, 결정이 나면 날짜와 함께 남겨 주세요.

## 운영 반영 때 (사람이 해야 함)

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

- [ ] **배포 순서 강제 (R016)** — "마이그레이션 → 코드" 순서를 사람이 기억하는 방식이라 어기기 쉽습니다. 후보:
  1. 서버 시작 시 DB 리비전이 코드의 head와 다르면 경고/기동 거부
  2. `check.py`에 운영 DB를 읽기 전용으로 확인하는 단계 추가 (운영 접속 정보가 필요해 민감)
  3. 배포 스크립트/CI에 마이그레이션 단계를 고정
  → 운영 환경(어디에 어떻게 배포하는지)이 정해져야 선택할 수 있습니다.

## 구조적 부채

- [ ] `frontend/src/App.tsx` 분리 (1,100줄+, 상태 20여 개, JSX 400줄) — 훅(`useVoiceInput`, `useTextareaFit`, `useBookmarks`)과
  컴포넌트(`MessageItem`, `Composer`, `AssessmentPanel`, `ReportView`)로. 팀원 작업과 충돌하므로 **작업 시점을 합의한 뒤** 진행.
  브라우저 E2E(`--only browser`)가 있어서 이전보다 안전합니다.
- [ ] 루트 `test_didim.py`를 `backend/tests/`의 pytest로 병합 (지금은 수정하지 않고 `check.py`가 호출만 함)
- [ ] `SESSION_SECRET`은 설정만 있고 코드에서 쓰이지 않음 — 제거하거나 용도를 정할 것

## 아직 검증하지 못한 것

- [ ] Windows 실행 (`check.py`의 Postgres 경로, `npx.cmd`, `start.bat`/`start.ps1`)
- [ ] 다크 모드 화면 (자동 검증 없음)
- [ ] 음성 입력, 인쇄(PDF) — 브라우저 기능이라 자동화하지 않음
- [ ] 실제 Claude 응답으로 화면 확인 (E2E는 데모 모드)
- [ ] PyInstaller exe 패키징 — `launcher.py` + `frontend/dist` + `data/legal/articles.json`이 묶이는지, exe에서 `legal.db` 자동 생성이 되는지
- [ ] 이전 비밀번호가 git 이력에 남아 있음 — 계정 비밀번호는 변경 완료. 저장소가 외부에 공개된 적이 있다면 이력 정리 검토
