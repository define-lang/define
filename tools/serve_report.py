"""Serve an interactive coverage report and save its submitted selections."""

import json
import os
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar, cast, override

import click

_MAX_SUBMISSION_BYTES = 1_048_576


class ReportHandler(BaseHTTPRequestHandler):
    """Serve one report and accept its selection submission."""

    report_path: ClassVar[Path]
    selection_path: ClassVar[Path]
    submission_received: ClassVar[bool] = False
    access_path: ClassVar[str]
    expected_authority: ClassVar[str]
    expected_origin: ClassVar[str]

    def _has_valid_authority(self) -> bool:
        return self.headers.get("Host") == self.expected_authority

    def _send_security_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            + "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
            + "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; "
            + "form-action 'self'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")

    def do_GET(self):
        """Serve the report at the server's only page."""
        if not self._has_valid_authority() or self.path != self.access_path:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = self.report_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self._send_security_headers()
        self.end_headers()
        _ = self.wfile.write(content)

    def do_POST(self):
        """Save a submission from the report."""
        if not self._has_valid_authority() or self.path != self.access_path + "submit":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if self.headers.get("Origin") != self.expected_origin:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.headers.get("Content-Type") != "application/json":
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        content_length_text = self.headers.get("Content-Length")
        if content_length_text is None:
            self.send_error(HTTPStatus.LENGTH_REQUIRED)
            return
        try:
            content_length = int(content_length_text)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        if content_length < 0:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        if content_length > _MAX_SUBMISSION_BYTES:
            self.send_error(HTTPStatus.CONTENT_TOO_LARGE)
            return
        try:
            payload = cast("object", json.loads(self.rfile.read(content_length)))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        payload_mapping = cast("dict[str, object]", payload)
        if not isinstance(payload_mapping.get("items"), list):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        _ = self.selection_path.write_text(json.dumps(payload, indent=2) + "\n")
        self.send_response(204)
        self._send_security_headers()
        self.end_headers()
        ReportHandler.submission_received = True

    @override
    def log_message(self, format: str, *args: object):
        """Keep the long-running skill server quiet between submissions."""


@click.command()
@click.argument(
    "report",
    type=click.Path(path_type=Path),
    default=Path("htmlcov/coverage_report.html"),
)
@click.argument(
    "selection",
    type=click.Path(path_type=Path),
    default=Path("htmlcov/coverage_report_selection.json"),
)
@click.option("--port", type=int, default=0, show_default="automatic")
def main(report: Path, selection: Path, port: int):
    """Serve the requested report until it receives a submission."""
    working_directory = Path(os.environ.get("BUILD_WORKING_DIRECTORY", Path.cwd()))
    ReportHandler.report_path = (working_directory / report).resolve()
    ReportHandler.selection_path = (working_directory / selection).resolve()
    ReportHandler.submission_received = False
    with HTTPServer(("127.0.0.1", port), ReportHandler) as server:
        access_token = secrets.token_urlsafe(32)
        ReportHandler.access_path = f"/{access_token}/"
        ReportHandler.expected_authority = f"127.0.0.1:{server.server_port}"
        ReportHandler.expected_origin = f"http://{ReportHandler.expected_authority}"
        click.echo(ReportHandler.expected_origin + ReportHandler.access_path)
        serve_until_submission(server)


def serve_until_submission(server: HTTPServer):
    """Handle requests until the report receives a valid submission."""
    while not ReportHandler.submission_received:
        server.handle_request()


if __name__ == "__main__":
    main()
