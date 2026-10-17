"""Self-contained real TCP/server smoke test, with a disposable database."""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from scripts.run_facial_demo import run_facial_demo
from scripts.run_voice_demo import run_voice_demo
from scripts.run_risk_demo import run_risk_demo
from scripts.run_interventions_demo import run_interventions_demo


def main():
    parser = argparse.ArgumentParser(description="Start a temporary server, verify all four HTTP pipelines and stop it.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="empath-http-") as folder:
        env = dict(os.environ, DATABASE_URL=f"sqlite:///{Path(folder) / "verify.db"}", API_KEY="http-verification-demo-key", ENABLE_RESEARCH_MODE="false")
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, check=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with (Path(folder) / "server.log").open("w+") as log:
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"X-API-Key": env["API_KEY"]}, trust_env=False, timeout=10) as client:
                    for _ in range(60):
                        if server.poll() is not None:
                            log.seek(0)
                            raise RuntimeError(f"Server exited during startup: {log.read()}")
                        try:
                            if client.get("/health").status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("Temporary server did not become healthy")
                    assert client.get("/").status_code == 200
                    assert client.get("/facial-demo").status_code == 200
                    assert client.get("/docs").status_code == 200
                    schema = client.get("/openapi.json").json()
                    assert "/api/v1/facial/checkins" in schema["paths"]
                    report = run_facial_demo(client, "DEMO-HTTP-VERIFIED")
                    results = report["scenarios"]
                    assert results["return"]["temporal"]["return_fraction"] > 0
                    assert results["persistent"]["temporal"]["return_fraction"] < 0
                    assert results["poor_quality"]["deviation"] is None
                    history = client.get("/api/v1/facial/history/DEMO-HTTP-VERIFIED").json()
                    assert history["total"] == 4
                    assert len(client.get("/api/v1/participants/DEMO-HTTP-VERIFIED/export").json()["facial_sessions"]) == 7
                    report["verification"] = {"transport": "real_http_tcp", "history_count": history["total"], "temporary_database": True}
                    assert client.get("/voice-demo").status_code == 200
                    voice = run_voice_demo(client, "RAVDEMO-HTTP-VERIFIED")
                    assert voice["history_total"] == 3
                    assert all(row["response"]["prediction"] is not None for row in voice["results"])
                    assert client.get("/api/v1/models").json()["voice"]["status"] == "ready"
                    report["voice_public_audio_verification"] = voice
                    assert client.get("/risk-demo").status_code == 200
                    risk = run_risk_demo(client)
                    assert risk["scenarios"]["steady"]["status"] == "demo_only_prediction"
                    assert risk["scenarios"]["sparse"]["risk"] is None
                    report["risk_synthetic_verification"] = risk
                    assert client.get("/interventions-demo").status_code == 200
                    interventions = run_interventions_demo(client)
                    assert interventions["current_session"]["status"] == "completed"
                    assert client.get("/api/v1/models").json()["interventions"]["status"] == "implemented"
                    report["interventions_synthetic_verification"] = interventions
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for scenario, result in report["scenarios"].items():
        print(f"{scenario}: {result["status"]}; deviation={result["deviation"]}; temporal={result["temporal"]}")
    print("PASS: real HTTP startup, all pages/docs, C1 facial workflow, C2 public WAV uploads and C3 four synthetic longitudinal scenarios and C4 recommendation/feedback workflow.")


if __name__ == "__main__":
    main()
