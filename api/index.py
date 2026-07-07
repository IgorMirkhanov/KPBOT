"""
Primary Vercel Serverless entrypoint.
Served at /api/index (default) and rewritten to /webhook via vercel.json.
"""

from __future__ import annotations

import logging
import os
import sys
from http.server import BaseHTTPRequestHandler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from webhook_app import handle_webhook_post_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    def _respond(self, code: int, body: bytes = b"", content_type: str = "text/plain") -> None:
        self.send_response(code)
        if body:
            self.send_header("Content-Type", content_type)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _headers_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.headers.items()}

    def do_GET(self) -> None:
        self._respond(200, b"KPBOT webhook is running. POST Telegram updates here.")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        code, response_body = handle_webhook_post_sync(body, self._headers_dict())
        self._respond(code, response_body)
