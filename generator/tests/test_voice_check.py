import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from drova_voice.casting import Casting
from drova_voice.cli import main
from drova_voice.fish_voices import load_catalog
from drova_voice.voice_check import SKIPPED, query_voices, substitute, summarize, used_voices

WORKERS = Path(__file__).resolve().parents[1] / "workers"
KEY = "sk-test-geheim-123"
LENA = "a" * 32
LEON = "b" * 32


def load_catalog_from(body, tmp_path):
    path = tmp_path / "fish_voices_check.yaml"
    path.write_text(body, encoding="utf-8")
    return load_catalog(path)


def test_summarize_covers_a_missing_voice_only_when_the_fallback_is_usable(tmp_path):
    catalog = load_catalog_from(
        f"voices:\n  lena: {{id: '{LENA}', label: Lena, gender: f}}\n"
        f"  leon: {{id: '{LEON}', label: Leon, gender: m}}\n"
        "fallbacks:\n  lena: leon\n", tmp_path)
    casting = Casting("leon", {"mira": "lena"})
    uses = used_voices(catalog, casting)
    lines, code = summarize(uses, {LENA: {"status": "missing"}, LEON: {"status": "ok"}}, catalog)
    assert code == 0 and any(line.startswith("ERSATZ lena") for line in lines)
    lines, code = summarize(uses, {LENA: {"status": "missing"}, LEON: {"status": "missing"}}, catalog)
    assert code == 1 and any(line.startswith("FEHLT lena") for line in lines)
    assert substitute(catalog, "lena", {LENA}) == "leon"
    assert substitute(catalog, "lena", {LENA, LEON}) is None


def test_retiring_voice_is_reported_and_does_not_fail_the_check(tmp_path):
    catalog = load_catalog_from(
        f"voices:\n  lena: {{id: '{LENA}', label: Lena, gender: f}}\n", tmp_path)
    lines, code = summarize(
        used_voices(catalog, Casting("lena", {})),
        {LENA: {"status": "retiring", "retire_at": "2026-12-01T00:00:00Z"}}, catalog)
    assert code == 0 and "LÄUFT AB lena" in lines[1] and "2026-12-01" in lines[1]


def test_check_voices_skips_without_a_key(pipeline_repo, monkeypatch, capsys):
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check-voices"]) == 0
    assert SKIPPED in capsys.readouterr().out


def test_check_voices_reports_a_fake_result_and_does_not_open_a_socket(pipeline_repo, monkeypatch, capsys):
    monkeypatch.setenv("FISH_API_KEY", KEY)
    called = {}

    def fake_query(workers_dir, ids, env=None):
        called["ids"] = list(ids)
        return [{"id": item, "status": "ok"} for item in ids]

    monkeypatch.setattr("drova_voice.pipeline.query_voices", fake_query)
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check-voices"]) == 0
    out = capsys.readouterr().out
    assert "in Ordnung" in out and called["ids"]
    assert KEY not in out


class _GetServer:
    def __init__(self, routes):
        self.routes = routes
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append(self.path)
                status, payload = outer.routes.get(self.path, (404, {"message": "missing"}))
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}/model"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def test_query_voices_talks_to_the_worker_against_a_local_server_only():
    found = {f"/model/{LENA}": (200, {"_id": LENA, "state": "trained", "pvc_release_state": "retiring",
                                      "pvc_retire_effective_at": "2026-12-01T00:00:00Z", "dmca_taken_down": False})}
    with _GetServer(found) as server:
        env = dict(os.environ)
        env.update({
            "FISH_API_KEY": KEY,
            "FISH_MODEL_API_URL": server.base,
            "FISH_MODEL": "s2.1-pro-free",
            "FISH_TEMPERATURE": "0.7",
            "FISH_TOP_P": "0.7",
            "FISH_LATENCY": "normal",
            "FISH_MAX_ATTEMPTS": "2",
        })
        rows = query_voices(WORKERS, [LENA, LEON], env)
    by_id = {row["id"]: row for row in rows}
    assert by_id[LENA]["status"] == "retiring" and by_id[LENA]["retire_at"].startswith("2026-12-01")
    assert by_id[LEON]["status"] == "missing"
    assert server.requests == [f"/model/{LENA}", f"/model/{LEON}"]
    assert KEY not in json.dumps(rows)
