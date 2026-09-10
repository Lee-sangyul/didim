# 디딤 — 교권 침해 상담 도우미

로컬 전용 `React + FastAPI + SQLite` 상담 프로그램입니다. 기본값은 API 비용 없이 작동하는 데모 분석 모드이며, Anthropic API 키를 설정하면 Claude 스트리밍 응답을 사용합니다.

> 이 프로그램은 일반적인 안내 도구입니다. 법률 자문이나 학교·수사기관의 판단을 대신하지 않습니다. 실제 개인정보는 가능한 한 입력하지 마세요.

## 가장 쉬운 실행법 (Windows)

1. [Python 3.11 이상](https://www.python.org/downloads/)을 설치합니다. 설치 화면에서 **Add Python to PATH**를 선택합니다.
2. [Node.js LTS](https://nodejs.org/)를 설치합니다.
3. 프로젝트 폴더의 `start.bat`을 더블클릭합니다.
4. 설치가 끝나면 `http://localhost:5173`이 자동으로 열립니다.

첫 실행은 패키지를 설치하므로 시간이 조금 걸립니다. 이후에는 바로 시작됩니다. API 문서는 `http://localhost:8000/docs`에서 볼 수 있습니다.

## Claude API 연결

1. 루트의 `.env.example`을 복사하여 `.env`로 이름을 바꿉니다. `start.bat`을 한 번 실행했다면 자동 생성돼 있습니다.
2. 아래처럼 수정합니다.

```env
ANTHROPIC_API_KEY=발급받은_API_키
ANTHROPIC_MODEL=claude-sonnet-5
DEMO_MODE=false
DATABASE_URL=sqlite:///./data/didim.db
```

3. 실행 중인 `디딤 API` 창과 `디딤 화면` 창을 닫고 `start.bat`을 다시 실행합니다.

API 키는 절대 GitHub, 화면 코드, 채팅 내용에 넣지 마세요. 사용자 입력은 전화번호·주민등록번호·이메일 패턴을 서버에서 마스킹한 뒤 Claude에 전송합니다. 사람 이름과 주소는 문맥에 따라 구분하기 어려우므로 사용자가 처음부터 가명으로 입력해야 합니다.

## 직접 실행

```bash
# 터미널 1
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000

# 터미널 2
cd frontend
npm install
npm run dev
```

## 테스트와 빌드

```bash
# 백엔드
cd backend
../.venv/bin/python -m pytest

# 프런트엔드
cd frontend
npm run build
```

Windows에서는 테스트 Python 경로를 `..\.venv\Scripts\python.exe -m pytest`로 사용합니다.

## 데이터 초기화

프로그램을 완전히 종료한 뒤 `data/didim.db`를 삭제하면 모든 상담 기록이 초기화됩니다. 데이터베이스는 로컬 컴퓨터에만 저장되지만, 디스크 암호화까지 자동 제공하지는 않습니다. 실제 민감정보를 저장하려면 Windows 장치 암호화/BitLocker와 사용자 계정 잠금을 함께 사용하세요.

## 현재 범위

- 상담 생성·조회·삭제
- SQLite 로컬 저장
- SSE 실시간 응답
- API 키가 없을 때 데모 분석
- 위험도와 단계별 대응 권고
- 연락처·주민등록번호·이메일 마스킹
- 인쇄 대화상자를 이용한 PDF 저장
- 반응형 화면

법령 RAG 지식베이스는 포함하지 않았습니다. 따라서 Claude 모드에서도 구체적인 법조문을 확정적으로 제시하는 용도가 아니며, 법적 근거는 최신 공식 자료와 전문가를 통해 별도로 확인해야 합니다.

