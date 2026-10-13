from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.spa import mount_frontend


def make_app(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>INDEX</html>")
    (dist / "assets" / "a.js").write_text("console.log(1)")
    (dist / "sw.js").write_text("// sw")
    (tmp_path / "secret.txt").write_text("TOP-SECRET")

    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    assert mount_frontend(app, dist) is True
    return TestClient(app)


def test_serves_index_assets_and_client_routes(tmp_path):
    c = make_app(tmp_path)
    assert "INDEX" in c.get("/").text
    assert "INDEX" in c.get("/register").text  # 클라이언트 라우팅
    assert c.get("/assets/a.js").text == "console.log(1)"
    assert c.get("/sw.js").text == "// sw"  # dist 루트의 정적 파일


def test_api_routes_win_and_unknown_api_is_404_not_html(tmp_path):
    c = make_app(tmp_path)
    assert c.get("/api/ping").json() == {"ok": True}
    assert c.get("/api/nope").status_code == 404
    assert "INDEX" not in c.get("/api/nope").text


def test_cannot_escape_dist(tmp_path):
    c = make_app(tmp_path)
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"):
        assert "TOP-SECRET" not in c.get(path).text


def test_no_dist_means_no_mount(tmp_path):
    assert mount_frontend(FastAPI(), tmp_path / "missing") is False
