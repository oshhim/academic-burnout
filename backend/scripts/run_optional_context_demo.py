"""Live API demonstration of optional C4 context; no C1–C3 records are created."""
import argparse
from itertools import product
import json
from pathlib import Path
from uuid import uuid4
import httpx


def run(client):
    pid = 'C4-' + uuid4().hex[:12]
    base = {'participant_id': pid, 'data_source': 'synthetic_demo', 'consent': True}
    def post(path, body):
        response = client.post('/api/v1' + path, json=body)
        response.raise_for_status()
        return response.json()
    post('/participants', base)
    rows = []
    for i, mask in enumerate(product([False, True], repeat=3)):
        components = [k for k, on in zip(['facial', 'voice', 'risk'], mask) if on]
        fixture = post('/interventions/demo-contexts', {**base, 'client_update_id': f'fixture-{i}', 'components': components})
        offer = post('/interventions/recommendations', {**base, 'client_request_id': f'offer-{i}', 'strategy': 'multimodal_weighted', 'goal': 'refocus', 'available_seconds': 300, 'demo_context_id': fixture['demo_context_id']})
        assert offer['integration']['fallback'] == (not any(mask))
        assert abs(sum(offer['integration']['normalized_weights'].values()) - (1 if any(mask) else 0)) < 1e-9
        rows.append({'components': components, 'integration': offer['integration'], 'options': offer['options']})
    started = post('/interventions/sessions', {**base, 'client_session_id': 'start', 'recommendation_id': offer['recommendation_id'], 'activity_id': offer['options'][0]['activity']['activity_id']})
    post('/interventions/events', {**base, 'client_event_id': 'complete', 'session_id': started['session_id'], 'outcome': 'completed'})
    post('/interventions/feedback', {**base, 'client_feedback_id': 'rating', 'session_id': started['session_id'], 'helpfulness': 4, 'would_repeat': True})
    return {'participant_id': pid, 'synthetic_only': True, 'availability_cases': rows, 'completed_session_id': started['session_id']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--api-key', default='local-demo-key-change-me')
    parser.add_argument('--output', type=Path, default=Path('data/optional_context_demo_results.json'))
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, headers={'X-API-Key': args.api_key}, timeout=30, trust_env=False) as client:
        report = run(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"Verified all 8 combinations and activity completion/feedback for {report['participant_id']}. Results: {args.output}")
