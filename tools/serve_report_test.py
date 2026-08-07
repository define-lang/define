import http.client
import json
import threading
from http import HTTPStatus
from http.server import HTTPServer
from pathlib import Path

from tools import serve_report


def _request(
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    response_body = response.read()
    response_headers = dict(response.getheaders())
    connection.close()
    return response.status, response_headers, response_body


def _post_without_content_length(port: int, origin: str) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.putrequest("POST", "/secret-token/submit")
    connection.putheader("Content-Type", "application/json")
    connection.putheader("Origin", origin)
    connection.endheaders()
    response = connection.getresponse()
    _ = response.read()
    connection.close()
    return response.status


def test_server_restricts_access_and_stops_after_valid_submission(tmp_path: Path):
    report_path = tmp_path / "report.html"
    selection_path = tmp_path / "selection.json"
    _ = report_path.write_text("<h1>Coverage</h1>")

    serve_report.ReportHandler.report_path = report_path
    serve_report.ReportHandler.selection_path = selection_path
    serve_report.ReportHandler.submission_received = False
    serve_report.ReportHandler.access_path = "/secret-token/"

    with HTTPServer(("127.0.0.1", 0), serve_report.ReportHandler) as server:
        authority = f"127.0.0.1:{server.server_port}"
        origin = f"http://{authority}"
        serve_report.ReportHandler.expected_authority = authority
        serve_report.ReportHandler.expected_origin = origin

        server_thread = threading.Thread(
            target=serve_report.serve_until_submission, args=(server,)
        )
        server_thread.start()

        status, _, _ = _request(
            server.server_port,
            "GET",
            "/secret-token/",
            headers={"Host": "attacker.example"},
        )
        assert status == HTTPStatus.NOT_FOUND

        status, _, _ = _request(server.server_port, "GET", "/wrong-token/")
        assert status == HTTPStatus.NOT_FOUND

        status, headers, body = _request(server.server_port, "GET", "/secret-token/")
        assert status == HTTPStatus.OK
        assert body == b"<h1>Coverage</h1>"
        assert headers["Cache-Control"] == "no-store"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]

        valid_payload = json.dumps({"items": []})
        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://attacker.example",
            },
            body=valid_payload,
        )
        assert status == HTTPStatus.FORBIDDEN
        assert not selection_path.exists()

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/submit",
            headers={"Content-Type": "application/json", "Origin": origin},
            body=valid_payload,
        )
        assert status == HTTPStatus.NOT_FOUND

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={"Content-Type": "text/plain", "Origin": origin},
            body=valid_payload,
        )
        assert status == HTTPStatus.UNSUPPORTED_MEDIA_TYPE

        assert (
            _post_without_content_length(server.server_port, origin)
            == HTTPStatus.LENGTH_REQUIRED
        )

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={
                "Content-Length": "1048577",
                "Content-Type": "application/json",
                "Origin": origin,
            },
        )
        assert status == HTTPStatus.CONTENT_TOO_LARGE

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={
                "Content-Length": "-1",
                "Content-Type": "application/json",
                "Origin": origin,
            },
        )
        assert status == HTTPStatus.BAD_REQUEST

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={"Content-Type": "application/json", "Origin": origin},
            body="not JSON",
        )
        assert status == HTTPStatus.BAD_REQUEST

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={"Content-Type": "application/json", "Origin": origin},
            body="[]",
        )
        assert status == HTTPStatus.BAD_REQUEST

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={"Content-Type": "application/json", "Origin": origin},
            body="{}",
        )
        assert status == HTTPStatus.BAD_REQUEST

        status, _, _ = _request(
            server.server_port,
            "POST",
            "/secret-token/submit",
            headers={"Content-Type": "application/json", "Origin": origin},
            body=valid_payload,
        )
        assert status == HTTPStatus.NO_CONTENT

        server_thread.join(timeout=1)
        assert not server_thread.is_alive()

    assert selection_path.read_text() == '{\n  "items": []\n}\n'
