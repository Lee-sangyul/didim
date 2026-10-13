"""브라우저 E2E: 실제 Chrome/Edge로 빌드된 화면을 조작한다 (Playwright).

worker 프로세스에서 실행한다: python -m scripts.checks.worker browser <base_url> <username> <password>
서버는 오케스트레이터가 띄워 둔다(DEMO_MODE, 임시 DB). 외부 호출 없음.
"""
from __future__ import annotations

import re
from typing import Callable

from .core import FAIL, PASS, WARN, Result

CHANNELS = ("chrome", "msedge", None)  # None = Playwright가 내려받은 chromium(설치돼 있을 때만)
TIMEOUT_MS = 15_000


def _launch(pw):
    errors = []
    for channel in CHANNELS:
        try:
            kwargs = {"channel": channel} if channel else {}
            return pw.chromium.launch(headless=True, **kwargs), channel or "chromium"
        except Exception as exc:  # 채널이 없으면 다음 후보
            errors.append(f"{channel or 'chromium'}: {str(exc).splitlines()[0][:100]}")
    raise RuntimeError("실행할 브라우저가 없습니다. Chrome 또는 Edge를 설치하거나 `playwright install chromium`을 실행하세요.\n" + "\n".join(errors))


def run_flow(base: str, username: str, password: str) -> list[Result]:
    from playwright.sync_api import expect, sync_playwright

    results: list[Result] = []
    problems: list[str] = []  # 콘솔 오류·페이지 예외·5xx 응답

    def step(name: str, fn: Callable[[], None]) -> bool:
        try:
            fn()
        except Exception as exc:
            msg = str(exc).strip().splitlines()
            results.append(Result(f"[브라우저] {name}", FAIL, (msg[0] if msg else repr(exc))[:300]))
            return False
        results.append(Result(f"[브라우저] {name}", PASS))
        return True

    with sync_playwright() as pw:
        try:
            browser, channel = _launch(pw)
        except RuntimeError as exc:
            return [Result("[브라우저] 브라우저 실행", FAIL, str(exc))]
        results.append(Result("[브라우저] 브라우저 실행", PASS, channel))

        context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="ko-KR")
        context.set_default_timeout(TIMEOUT_MS)
        page = context.new_page()
        # 로그인 전 세션 확인(/api/auth/me)과 잘못된 비밀번호는 401이 정상이다.
        # 브라우저는 모든 4xx를 콘솔 오류로 찍으므로, 네트워크 오류는 응답 이벤트로만 판단한다.
        expected_401 = ("/api/auth/me", "/api/auth/login")

        def on_response(r):
            if r.status >= 500 or (r.status >= 400 and not (r.status == 401 and any(p in r.url for p in expected_401))):
                problems.append(f"HTTP {r.status} {r.request.method} {r.url[:100]}")

        page.on("console", lambda m: problems.append(f"console.error: {m.text[:160]}")
                if m.type == "error" and "Failed to load resource" not in m.text else None)
        page.on("pageerror", lambda e: problems.append(f"pageerror: {str(e)[:160]}"))
        page.on("response", on_response)
        page.on("dialog", lambda d: d.accept())  # 삭제 확인(confirm)

        textarea = page.locator(".input textarea")
        bubble_assistants = page.locator("article.message.assistant")

        # ---- 로그인
        def open_login():
            page.goto(base + "/")
            expect(page.locator("form.login-form")).to_be_visible()

        if not step("화면 로딩(로그인 폼)", open_login):
            browser.close()
            return results

        def bad_login():
            page.locator("input[autocomplete=username]").fill(username)
            page.locator("input[autocomplete=current-password]").fill("wrong-password-123")
            page.locator("button.login-submit").click()
            expect(page.locator(".login-error")).to_be_visible()

        step("잘못된 비밀번호는 오류 표시", bad_login)

        def good_login():
            page.locator("input[autocomplete=current-password]").fill(password)
            page.locator("button.login-submit").click()
            expect(page.locator("button.new")).to_be_visible()

        if not step("로그인", good_login):
            browser.close()
            return results

        # ---- 입력창 가변 길이 (R007)
        def composer_grows():
            page.locator("button.new").click()
            h1 = textarea.evaluate("e => e.getBoundingClientRect().height")
            textarea.click()
            page.keyboard.type("첫째 줄")
            for line in ("둘째 줄", "셋째 줄"):
                page.keyboard.press("Shift+Enter")
                page.keyboard.type(line)
            h3 = textarea.evaluate("e => e.getBoundingClientRect().height")
            assert h3 > h1 * 2, f"3줄 입력 후 높이 {h1}px -> {h3}px (늘어나지 않음)"
            expect(page.locator(".input.multiline")).to_be_visible()
            for _ in range(8):
                page.keyboard.press("Shift+Enter")
                page.keyboard.type("x")
            hmax = textarea.evaluate("e => e.getBoundingClientRect().height")
            assert hmax <= 130, f"최대 5줄 이후에도 계속 늘어남({hmax}px)"
            textarea.fill("")
            page.wait_for_function("() => document.querySelector('.input textarea').getBoundingClientRect().height < 40")

        step("입력창이 줄 수에 맞춰 늘어나고 5줄에서 멈춤", composer_grows)

        # ---- 채팅
        def chat():
            textarea.fill("학부모가 매일 밤 전화로 욕설과 협박을 합니다. 통화는 녹음해 두었습니다.")
            page.keyboard.press("Enter")
            expect(page.locator("article.message.user")).to_have_count(1)
            expect(bubble_assistants.last.locator(".message-actions")).to_be_visible()
            assert bubble_assistants.last.inner_text().strip(), "답변이 비어 있음"

        if not step("메시지 전송 → 답변 스트리밍 완료", chat):
            browser.close()
            return results

        def risk_panel():
            expect(page.locator(".risk-card")).to_contain_text("/ 100")

        step("위험도 패널 표시", risk_panel)

        # ---- 답변 버튼 레이아웃 (R006)
        def buttons_layout():
            actions = bubble_assistants.last.locator(".message-actions")
            boxes = [b.bounding_box() for b in actions.locator("button").all()]
            assert len(boxes) >= 3, f"버튼 {len(boxes)}개(복사·북마크·재생성 기대)"
            ys = {round(b["y"]) for b in boxes}
            assert max(ys) - min(ys) <= 6, f"버튼이 한 줄에 있지 않음(y={sorted(ys)})"
            xs = sorted((b["x"], b["width"]) for b in boxes)
            for (x1, w1), (x2, _) in zip(xs, xs[1:]):
                assert x1 + w1 <= x2 + 1, "버튼이 서로 겹침"
            assert all(b["width"] <= 48 for b in boxes), "버튼이 비정상적으로 큼(아이콘 버튼 기대)"

        step("복사·북마크·재생성 버튼이 한 줄에 겹치지 않고 배치", buttons_layout)

        def bookmark():
            btn = bubble_assistants.last.locator("button.bookmark-btn")
            btn.click()
            expect(btn).to_have_attribute("aria-pressed", "true")

        step("북마크 토글", bookmark)

        # ---- 재생성 (R010)
        def regenerate():
            bubble_assistants.last.locator("button.regenerate-btn").click()
            expect(page.locator(".version-nav")).to_contain_text("2/2")
            expect(page.locator("article.message.user")).to_have_count(1)

        step("답변 다시 생성 → 버전 2/2, 질문 중복 없음", regenerate)

        def regenerate_persists():
            page.reload()
            expect(page.locator(".version-nav")).to_contain_text("2/2")
            expect(page.locator("article.message.user")).to_have_count(1)

        step("새로고침 후에도 버전 유지", regenerate_persists)

        def version_nav():
            nav = page.locator(".version-nav")
            nav.get_by_role("button").first.click()
            expect(nav).to_contain_text("1/2")

        step("이전 버전으로 이동", version_nav)

        # ---- 첨부
        def attachment():
            page.locator("input.file-hidden").set_input_files(
                {"name": "증거-메모.txt", "mimeType": "text/plain", "buffer": "점검용 첨부 파일".encode()}
            )
            expect(page.locator(".aside")).to_contain_text("증거-메모.txt")

        step("첨부 업로드 후 목록에 표시", attachment)

        # ---- 상담 삭제
        def delete_case():
            before = page.locator(".case-list button.case").count()
            page.get_by_role("button", name="삭제", exact=True).first.click()
            expect(page.locator(".case-list button.case")).to_have_count(before - 1)

        step("상담 삭제", delete_case)

        # ---- 로그아웃
        def logout():
            page.get_by_role("button", name=re.compile("로그아웃")).first.click()
            expect(page.locator("form.login-form")).to_be_visible()

        step("로그아웃", logout)

        # ---- 클라이언트 라우트(SPA 폴백)
        def register_route():
            page.goto(base + "/register")
            expect(page.locator("form")).to_be_visible()

        step("/register 화면(SPA 폴백)", register_route)
        context.close()

        # ---- 모바일 폭
        def mobile():
            ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True, locale="ko-KR")
            ctx.set_default_timeout(TIMEOUT_MS)
            m = ctx.new_page()
            m.on("dialog", lambda d: d.accept())
            m.goto(base + "/")
            m.locator("input[autocomplete=username]").fill(username)
            m.locator("input[autocomplete=current-password]").fill(password)
            m.locator("button.login-submit").click()
            expect(m.locator(".input textarea")).to_be_visible()
            overflow = m.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            ctx.close()
            assert overflow <= 1, f"가로 스크롤 발생({overflow}px)"

        step("모바일 폭(375px)에서 가로 넘침 없이 입력창 표시", mobile)

        def no_problems():
            assert not problems, "; ".join(problems[:4])

        step("콘솔 오류·5xx 응답 없음", no_problems)
        browser.close()

    return results
