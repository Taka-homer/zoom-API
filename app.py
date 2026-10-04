"""会議作成ボタン用のローカル画面を http://127.0.0.1:8765 で開く。"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from create_meeting import ZoomError, create_zoom_meeting

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != "/":
            self.send_error(404)
            return
        body = (ROOT / "index.html").read_bytes()
        self._send(200, "text/html; charset=utf-8", body)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/meetings":
            self.send_error(404)
            return
        try:
            meeting = create_zoom_meeting()
        except ZoomError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception as exc:
            self._send_json(500, {"error": f"予期しないエラーが発生しました。\n{exc}"})
            return
        self._send_json(201, meeting)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", body)

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ブラウザで http://{HOST}:{PORT} を開いてください。")
    print("止めるときは Ctrl+C を押します。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止しました。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
