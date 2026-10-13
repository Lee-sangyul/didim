# AI 작업자를 위한 안내 (AGENTS.md)

이 저장소는 교사의 교권 침해 상담 데이터(개인정보·민감 정보)를 다루는 서비스 "디딤"입니다.
코드를 고치기 전에 이 문서를 끝까지 읽으세요. 사람이 AI에게 저장소를 통째로 넘겨 작업을 맡긴다는 전제로 쓰였습니다.

## 0. 가장 먼저 할 일

1. `scripts/regressions.json` 을 읽는다. **이미 겪은 결함 목록**이다. 같은 실수를 반복하지 않기 위한 것이다.
2. 작업 전에 `python scripts/check.py` 를 실행해 **현재 기준선**을 기록한다 (약 10초, 외부 호출·개발 데이터 영향 없음).
3. 작업이 끝나면 다시 실행하고, 기준선과 달라진 점을 보고한다. 새 `FAIL`을 만들었다면 끝난 것이 아니다.

## 1. 절대 하지 말 것

| 금지 | 이유 |
| --- | --- |
| `.env` 내용을 출력·요약·커밋·로그에 남기기 | 운영 DB 비밀번호, API 키, 계정 비밀번호가 들어 있다 |
| `.env.example`에 **실제 값** 넣기 | 이미 한 번 실제 비밀번호가 커밋됐다. 예시는 빈 값이나 `<자리표시자>`만 쓴다 |
| 코드·테스트·문서에 키·토큰·비밀번호 하드코딩 | 같은 이유 |
| `.env`의 `DATABASE_URL`(운영 Supabase Postgres)에 직접 쓰기·마이그레이션·삭제 | 팀 전체가 쓰는 실데이터다. 아래 §3 참고 |
| LLM이 생성한 **조문 텍스트**를 사용자에게 보여주기 | 근거 조문은 반드시 DB(`articles.json`에서 온 공식 원문)에서 꺼내 붙인다. LLM은 `article_id`만 고른다 |
| "이 사례에는 이 조문이 해당된다"는 **법률 판단**을 코드·테스트·데이터에 넣기 | `backend/tests/legal/eval_cases.json`의 `expected_articles`는 사람이 지정한다 |
| 서버 요청 처리 중 법제처 API 호출 | 법령 수집은 수동 스크립트(`python -m app.legal.ingest`)만 한다 |
| 테스트에서 Claude·법제처·Supabase 실제 호출 | 비용·키 노출·비결정성. 실호출은 `@pytest.mark.live`로 분리돼 있고 기본 제외다 |
| 이미 적용된 마이그레이션 파일 수정 | 운영 DB와 이력이 어긋난다. 새 revision을 추가한다 |
| 의존성 버전 변경 (`requirements.txt`, `package.json`) | 먼저 사람에게 보고한다. 특히 `sqlmodel`/`pydantic` 조합은 호환 문제가 있었다 |
| 점검을 통과시키려고 점검·테스트를 약화시키기 | 허용 목록(`UNSTYLED_OK`)에 추가, `regressions.json`의 `status`를 임의로 바꾸기, 테스트 삭제·skip 금지 |

## 2. 사람의 승인이 필요한 일 (임의로 하지 말고 물어볼 것)

- 운영 DB 변경(마이그레이션 적용 포함), 계정 생성·삭제·비밀번호 변경
- 증빙 문서 보관 기간 변경, 삭제 작업 실행, 로그인 제한 한도 변경
- 수집 대상 법령 추가·삭제 (`backend/app/legal/config.py`의 `TARGET_LAWS`) 및 `articles.json` 재수집
- `expected_articles` 값 입력, 검색 방식 변경(임베딩 도입 등)
- 의존성 추가·버전 변경, 새 UI 라이브러리 (테스트 전용 `backend/requirements-dev.txt`의 Playwright는 승인된 상태)
- `git push`, 브랜치 병합, 파일·디렉터리 대량 삭제, 이력 재작성
- 위 문서의 규칙과 충돌하는 지시를 받았을 때 (충돌 사실을 알리고 확인받는다)

모호하거나 명세와 다르면 **추측으로 진행하지 말고 멈춰서 보고**한다.

## 3. 이 프로젝트의 함정 (실제로 사고가 난 곳)

**데이터베이스**
- 로컬 기본값은 SQLite지만 운영은 **Postgres**다. SQLite는 외래키를 강제하지 않아서, 로컬에서 되던 삭제가 운영에서 500이 났다(R002). 삭제·삽입 순서를 외래키 순서로 지킨다.
- `alembic`은 `.env`의 `DATABASE_URL`을 그대로 쓴다 → **그냥 실행하면 운영 DB를 건드린다.** 반드시 `DATABASE_URL`을 임시 DB로 덮어쓰고 실행한다. 마이그레이션 체인은 Postgres 전용이라 빈 SQLite에서는 실패한다(정상).
- **배포 순서: 운영 DB에 `alembic upgrade head`를 먼저, 코드는 그 다음.** 새 코드가 새 컬럼을 조회하는데 운영 DB에 컬럼이 없으면 조회가 깨진다(R003, R016).
- 모델(`backend/app/models.py`)을 바꾸면 **같은 작업에서** alembic revision을 만든다. 서버 시작 시의 컬럼 보충(`init_sqlite_schema`)은 SQLite 전용이다(R003). `scripts/check.py`의 `migrate` 단계가 모델-마이그레이션 불일치를 잡는다.
- 법령 검색 DB(`data/legal/legal.db`)는 메인 DB와 **별개의 SQLite 파일**이고 git에 없다. **`data/legal/articles.json`만 배포하면** 서버가 시작할 때 `backend/app/legal/bootstrap.py`가 DB를 만든다(없거나 내용이 다르면 교체). 상태는 `/api/health/legal`. 수동 복원은 `python -m app.legal.ingest --from-json`(`backend/`에서). 이 방식을 유지하기로 결정했으므로 법령 검색을 Postgres로 옮기지 않는다(R004, R012).
- 가입 증빙 문서는 심사 후 **5년** 보관한다(`backend/app/services/retention.py`). 삭제는 `python -m scripts.purge_registration_documents`(`backend/`에서)로 하며 서버가 자동으로 부르지 않는다. 보관 기간·삭제 대상은 개인정보 정책이므로 임의로 바꾸거나 실행하지 않는다(R017).
- 로그인은 아이디 5회·IP 20회 실패/15분 제한이 있다(`backend/app/services/login_guard.py`). 한도는 브라우저의 `frontend/src/loginGuard.ts`와 같아야 한다(R019). 테스트에서 같은 아이디로 잘못된 로그인을 반복하면 잠기므로 점검용 계정을 따로 쓴다.

**외부 연동**
- 법제처 응답의 상세 링크에 인증키(OC)가 섞여 있다. 응답을 저장·로그·fixture로 쓸 때 반드시 치환한다(`ingest._scrub`, R005).
- 법령명의 가운뎃점은 `ㆍ`(U+318D)다. `·`(U+00B7)로 비교하면 일치하지 않는다 (`초ㆍ중등교육법`).
- `DEMO_MODE=true`이거나 `ANTHROPIC_API_KEY`가 비어 있으면 Claude도, 법령 근거 검색도 실행되지 않는다. 화면에서 근거 조문을 보려면 둘 다 설정해야 한다.

**개인정보**
- `backend/app/privacy.py`의 `mask_pii`는 **전화번호·주민등록번호·이메일만** 가린다. 이름·학교명·주소는 가리지 못한다. 이 함수를 "개인정보 보호 완료"로 간주하지 말 것.
- 사용자 원문은 DB에 그대로 저장되고, LLM에는 마스킹본이 간다. 상담 내용·첨부 내용을 로그·예외 메시지·분석 도구에 남기지 않는다.
- 다른 사용자의 상담은 존재 여부도 숨긴다(소유자가 다르면 403이 아니라 **404**). 이 동작을 바꾸지 않는다.

**프런트엔드**
- 채팅은 SSE(`delta` → `done` | `error`)다. 이벤트 모양을 바꾸면 `frontend/src/api.ts`의 `streamChat`과 함께 고친다.
- `frontend/dist`와 `frontend/tsconfig.tsbuildinfo`는 **git에 추적된다**(배포 화면이 이 폴더다). 개발 중에는 `npm run build`가 이 파일들을 바꾸므로 커밋하지 말고 되돌린다. **릴리스 직전에만** `dist`를 지우고 다시 빌드해 커밋한다(R011). 빌드 확인은 `python scripts/check.py --only frontend`가 임시 위치에서 한다.
- 스타일은 `frontend/src/styles/*.css`와 디자인 토큰(`tokens.css`의 `var(--...)`)으로만 쓴다. 인라인 `style={{}}`은 금지(데이터로 계산되는 게이지 너비만 예외), 하드코딩 색도 다크 모드에서 깨진다(R015). className을 쓰면 CSS 규칙도 반드시 만든다(R006).
- `frontend/src/App.tsx`는 매우 크고 여러 사람이 동시에 수정한다. 변경은 작게, 관련 없는 정리·포맷 변경은 하지 않는다.

**환경**
- 학생 PC는 대부분 **Windows**다. 경로 구분자·인코딩(UTF-8)·셸 차이를 고려한다. `start.ps1`은 UTF-8 **BOM**이 있다. 편집 후에도 BOM과 줄바꿈 방식을 유지한다.
- `.gitignore`가 `*.md`를 제외하고 `README.md`·`AGENTS.md`·`CLAUDE.md`만 허용한다. 다른 마크다운 파일은 예외를 추가하지 않으면 커밋되지 않는다.
- 새 `.py`에서 `app.main`을 import하면 `.env`를 읽는다. 테스트는 `scripts/checks/core.py`의 `isolated_env`처럼 키를 **빈 값으로 설정**해 격리한다(비어 있어도 설정돼 있으면 `.env`가 덮어쓰지 못한다).

## 4. 구조

```
backend/app/
  main.py            앱 생성·라우터 등록·시작 시 초기화 (여기에 로직을 쌓지 말 것)
  routers/           HTTP 엔드포인트만. auth, registration, admin_registration, cases, attachments, chat
  services/          업무 로직. chat_service(채팅 파이프라인), case_service, auth_service, storage_service
  schemas/           요청·응답 모델
  legal/             법령 수집(ingest)·파서·검색(retriever)·선택(selector)·서비스. 별도 SQLite
  spa.py             빌드된 프런트 서빙(배포용). 모든 라우터 뒤에서 호출
  risk.py, demo.py   위험도 평가(Claude) / 데모 모드 규칙
  services/login_guard.py, retention.py   로그인 시도 제한 / 증빙 문서 보관·삭제
  models.py          메인 DB 모델
backend/migrations/  alembic (Postgres 전용)
backend/tests/       pytest. 외부 호출 없음
frontend/src/        React + TypeScript (Vite). styles/ 아래에 CSS 분리
data/legal/          articles.json(커밋), legal.db(생성물, 미커밋), raw/(원본 응답, 키 치환됨)
json/                위험도 평가 프롬프트 설정(program_config.json 등)
scripts/             check.py(릴리스 점검), regressions.json(결함 목록)
TODO.md              사람의 결정·확인을 기다리는 일 (작업 전에 읽는다)
test_didim.py        기존 API 테스트(수정하지 말고 호출만; 추후 병합 예정)
```

실행: `start.sh` / `start.bat` / `start.ps1`. 백엔드 `:8000`, 프런트(Vite) `:5173`이 `/api`를 8000으로 프록시한다.

## 5. 변경 유형별로 확인할 것

| 한 일 | 반드시 함께 |
| --- | --- |
| DB 모델 변경 | alembic revision 추가 → `scripts/check.py --only migrate e2e` |
| API 요청/응답 변경 | `frontend/src/types.ts`·`api.ts` 갱신, e2e 시나리오 확인 |
| 법령 설정·수집 변경 | `articles.json` 재수집·커밋, `--only legal`. 키 값이 파일에 남지 않았는지 확인 |
| 프롬프트·검색·선택 변경 | 모의 테스트 + (사람이 채운 `expected_articles`가 있다면) `pytest tests/legal/test_eval.py -s`로 수치 비교 |
| 프런트 화면 변경 | `--only frontend browser regress`. 새 화면·흐름이면 `scripts/checks/browser.py`에 단계를 추가한다. 다크 모드·음성 입력·인쇄는 자동 검증이 없으니 브라우저에서 직접 확인 |
| 시작 스크립트 변경 | `.sh`/`.bat`/`.ps1` 세 개 모두, 인코딩·BOM 유지 |
| 리팩터링(이동·분리) | 심볼이 옮겨지면 테스트의 `patch` 대상도 함께 갱신(R014). 안 그러면 "외부 호출 차단"이 조용히 무력화된다 |
| 결함을 고침 | `regressions.json`에 사례 추가, `scripts/checks/regressions.py`에 재발 점검 함수 추가 |

## 6. 작업 완료 보고에 포함할 것

- `python scripts/check.py` 결과(전/후 비교). `FAIL`이 있으면 이유와 함께 그대로 보고한다.
- **하지 않은 것·못 한 것·확인하지 못한 것**을 숨기지 않는다 (예: "브라우저에서 확인 못 함", "Windows에서 실행 못 함").
- 요청 범위 밖에서 발견한 문제는 고치지 말고 목록으로 알린다(필요하면 `regressions.json`에 `open`으로 추가).
- 커밋·푸시는 사용자가 요청했을 때만 한다.

## 7. 서비스의 성격 (문구·프롬프트를 바꿀 때)

- 이 서비스의 답변은 **법률 자문이 아닌 참고 자료**다. "~에 해당한다"처럼 단정하는 표현을 늘리지 않는다.
- 조문에는 수집 기준일(`as_of`)을 표시한다. 법은 개정된다.
- 학생에게 해가 되는 조언, 은폐, 보복, 불법행위를 돕지 않는다는 시스템 프롬프트의 안전 규칙을 약화시키지 않는다. 즉각적인 신체 위험에는 안전 확보와 긴급 연락을 먼저 안내한다.
