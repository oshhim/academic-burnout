"""Isolated live-HTTP verification: temporary DB + server + synthetic demo.
Does not change your normal database. Run from backend/ with Python 3.12.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import httpx
from scripts.run_optional_context_demo import run


def verify():
    with tempfile.TemporaryDirectory(prefix='empath-c4-') as temp:
        env = {**os.environ, 'DATABASE_URL': f'sqlite:///{Path(temp) / "test.db"}', 'API_KEY': 'isolated-c4-test-key', 'ENABLE_RESEARCH_MODE': 'false'}
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env, check=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        log_path = Path(temp) / 'server.log'
        with log_path.open('w') as logs:
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--log-level', 'warning'], env=env, stdout=logs, stderr=logs)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'X-API-Key': env['API_KEY']}, timeout=30, trust_env=False) as client:
                    deadline = time.monotonic() + 45
                    while True:
                        try:
                            health = client.get('/health'); health.raise_for_status(); break
                        except httpx.HTTPError:
                            if server.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError(log_path.read_text())
                            time.sleep(.2)
                    assert health.json()['voice_model'] == 'ready'
                    assert health.json()['risk_model']['status'] == 'ready'
                    report = run(client)
                    audit = client.get('/api/v1/interventions/evaluation/optional-context')
                    audit.raise_for_status()
                    assert audit.json()['all_missing_fallback_matches_adaptive']
                    report['health'] = health.json()
                    report['openapi_new_strategy'] = 'multimodal_weighted' in json.dumps(client.get('/openapi.json').json())
                    return report
            finally:
                server.terminate()
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired: server.kill(); server.wait()


if __name__ == '__main__':
    report = verify()
    path = Path('data/optional_context_live_verification.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'PASS: models ready, 8 availability masks, lifecycle, feedback, OpenAPI and context audit. {path}')
