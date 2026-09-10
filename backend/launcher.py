import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000


def port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((HOST, PORT)) == 0


def open_browser() -> None:
    time.sleep(1.2)
    webbrowser.open(f"http://{HOST}:{PORT}")


def main() -> None:
    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).resolve().parent)

    if port_in_use():
        webbrowser.open(f"http://{HOST}:{PORT}")
        return

    import uvicorn
    from app.main import app

    threading.Thread(target=open_browser, daemon=True).start()
    print("디딤을 시작합니다. 이 창을 닫으면 프로그램이 종료됩니다.")
    print(f"브라우저가 자동으로 열리지 않으면 http://{HOST}:{PORT} 로 접속하세요.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
