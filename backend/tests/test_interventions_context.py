"""Optional-context contract, actual adapter integration, isolation and replay."""
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path
import io
import json
import numpy as np
import pytest
import soundfile as sf
from sqlalchemy import func, select
from app.models import FacialSession, VoiceSession, RiskPrediction, InterventionDemoContext, Participant
from scripts.facial_demo_data import calibration_sessions, session
from scripts.risk_demo_data import demo_observations
from test_interventions_api import register, rec, prefs, start, finish, rate, base

KINDS = ['facial', 'voice', 'risk']


def fixture(client, components=KINDS, pid='I1', key='fixture', **changes):
    response = client.post('/api/v1/interventions/demo-contexts', json={**base(pid), 'client_update_id': key, 'components': components, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def weighted(client, key='weighted', **changes):
    response = rec(client, request_id=key, strategy='multimodal_weighted', limit=8, **changes)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize('mask', list(product([False, True], repeat=3)))
def test_every_availability_combination_and_exact_fallback(client, mask):
    register(client)
    components = [k for k, on in zip(KINDS, mask) if on]
    f = fixture(client, components)
    r = weighted(client, demo_context_id=f['demo_context_id'])
    integration = r['integration']
    weights = integration['normalized_weights']
    assert integration['fallback'] == (not any(mask))
    total = sum({'facial': .3, 'voice': .2, 'risk': .5}[k] for k in components)
    for k in KINDS:
        assert weights[k] == pytest.approx({'facial': .3, 'voice': .2, 'risk': .5}[k] / total if k in components else 0)
    if components:
        assert sum(weights.values()) == pytest.approx(1)
        assert integration['context_share'] == .25
        for o in r['options']:
            e = o['explanation']
            assert set(e['component_contributions']) == set(components)
            assert o['score'] == pytest.approx(.75 * e['independent_score_before_penalty'] + .25 * e['context_score'] - e['recent_repeat_penalty'], abs=1e-8)
    else:
        a = rec(client, request_id='adaptive', limit=8).json()
        assert [(o['activity']['activity_id'], o['score']) for o in r['options']] == [(o['activity']['activity_id'], o['score']) for o in a['options']]


def test_fixtures_are_isolated_opt_in_immutable_and_deleted(client):
    register(client)
    f = fixture(client)
    assert fixture(client) == f
    assert client.post('/api/v1/interventions/demo-contexts', json={**base(), 'client_update_id': 'fixture', 'components': []}).status_code == 409
    with client.app.state.sessions() as db:
        for table in (FacialSession, VoiceSession, RiskPrediction):
            assert db.scalar(select(func.count()).select_from(table)) == 0
    assert weighted(client)['integration']['fallback']  # Fixtures are never auto-selected.
    first = weighted(client, 'with-fixture', demo_context_id=f['demo_context_id'])
    with client.app.state.sessions() as db:
        row = db.get(InterventionDemoContext, f['demo_context_id'])
        row.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.commit()
    assert weighted(client, 'with-fixture', demo_context_id=f['demo_context_id']) == first
    expired = weighted(client, 'expired', demo_context_id=f['demo_context_id'])
    assert expired['integration']['fallback']
    export = client.get('/api/v1/participants/I1/export').json()
    assert export['intervention_demo_contexts'][0]['synthetic_only']
    assert client.delete('/api/v1/participants/I1').status_code == 204
    with client.app.state.sessions() as db:
        assert db.get(InterventionDemoContext, f['demo_context_id']) is None


def test_context_changes_scores_but_constraints_and_repeat_penalty_survive(client):
    register(client)
    f = fixture(client, ['facial', 'risk'])
    a = rec(client, request_id='a', limit=8).json()
    r = weighted(client, demo_context_id=f['demo_context_id'])
    assert r['integration']['normalized_weights'] == pytest.approx({'facial': .375, 'voice': 0, 'risk': .625})
    a_scores = {o['activity']['activity_id']: o['score'] for o in a['options']}
    assert any(o['score'] != a_scores[o['activity']['activity_id']] for o in r['options'])
    sid = start(client, r).json()['session_id']
    finish(client, sid)
    rate(client, sid)
    again = weighted(client, 'again', demo_context_id=f['demo_context_id'])
    chosen = next(o for o in again['options'] if o['activity']['activity_id'] == r['options'][0]['activity']['activity_id'])
    assert chosen['explanation']['recent_repeat_penalty'] == .05  # Applied once.
    assert chosen['explanation']['feedback_count'] == 1
    prefs(client, allow_audio=False, allow_movement=False, excluded_activity_ids=['quiet_pause'], max_duration_seconds=120)
    limited = weighted(client, 'limited', demo_context_id=f['demo_context_id'])
    for o in limited['options']:
        assert not o['activity']['audio'] and not o['activity']['movement']
        assert o['activity']['duration_seconds'] <= 120
        assert o['activity']['activity_id'] != 'quiet_pause'


def test_quality_missing_history_context_disabled_and_cross_owner(client):
    register(client)
    register(client, 'I2')
    f = fixture(client, facial_scenario='poor_quality', voice_scenario='poor_quality', risk_scenario='insufficient_history')
    assert weighted(client, demo_context_id=f['demo_context_id'])['integration']['fallback']
    assert rec(client, pid='I2', request_id='foreign', strategy='multimodal_weighted', demo_context_id=f['demo_context_id']).status_code == 404
    f = fixture(client, key='good')
    disabled = weighted(client, 'disabled', context_mode='none')
    assert disabled['integration']['fallback'] and all(m['reason'] == 'context_disabled' for m in disabled['integration']['modalities'].values())
    assert rec(client, request_id='invalid', strategy='multimodal_weighted', context_mode='none', demo_context_id=f['demo_context_id']).status_code == 422
    assert rec(client, request_id='invalid2', strategy='multimodal_weighted', demo_context_id=f['demo_context_id'], facial_session_id='other').status_code == 422
    local = {**base('LOCAL', 'local_research'), 'client_request_id': 'local', 'strategy': 'multimodal_weighted', 'goal': 'rest', 'available_seconds': 300}
    client.app.state.settings.enable_research_mode = True
    assert client.post('/api/v1/participants', json=base('LOCAL', 'local_research')).status_code == 201
    result = client.post('/api/v1/interventions/recommendations', json=local)
    assert result.status_code == 201 and result.json()['integration']['fallback']
    assert client.post('/api/v1/interventions/demo-contexts', json={**base('LOCAL', 'local_research'), 'client_update_id': 'bad', 'components': KINDS}).status_code == 422


def actual_face(client):
    ids = []
    for p in calibration_sessions('I1'):
        r = client.post('/api/v1/facial/calibrations', json=p)
        assert r.status_code == 201, r.text
        ids.append(r.json()['session_id'])
    r = client.post('/api/v1/facial/baselines', json={'participant_id': 'I1', 'session_ids': ids})
    assert r.status_code == 201, r.text
    p = session('I1', 'persistent', scenario='persistent', at=datetime.now(timezone.utc) - timedelta(seconds=100))
    r = client.post('/api/v1/facial/checkins', json=p)
    assert r.status_code == 201, r.text
    return r.json()


def test_actual_c1_c3_outputs_are_read_without_changing_them(client):
    register(client)
    face = actual_face(client)
    daily, weekly = demo_observations('I1', 'rising')
    assert client.post('/api/v1/risk/daily/batch', json={'records': daily}).status_code == 201
    for row in weekly:
        assert client.post('/api/v1/risk/weekly', json=row).status_code == 201
    prediction = client.post('/api/v1/risk/predictions', json={'participant_id': 'I1', 'client_prediction_id': 'risk'}).json()
    assert prediction['status'] == 'demo_only_prediction'
    r = weighted(client)
    assert r['integration']['normalized_weights'] == pytest.approx({'facial': .375, 'voice': 0, 'risk': .625})
    assert r['integration']['modalities']['facial']['mapping_key'] == 'persistent_visual_change'
    explicit = weighted(client, 'explicit', context_mode='explicit_refs', facial_session_id=face['session_id'])
    assert explicit['references'][0]['used_for_ranking']
    assert explicit['integration']['normalized_weights'] == {'facial': 1, 'voice': 0, 'risk': 0}
    with client.app.state.sessions() as db:
        assert db.get(FacialSession, face['session_id']).result == face
        assert db.get(RiskPrediction, prediction['prediction_id']).result == prediction
        row = db.get(FacialSession, face['session_id']); row.recorded_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(); db.commit()
    stale = weighted(client, 'stale', context_mode='explicit_refs', facial_session_id=face['session_id'])
    assert stale['integration']['fallback'] and stale['integration']['modalities']['facial']['reason'] == 'stale_result'


def test_actual_synthetic_audio_pipeline_can_supply_optional_voice_context(client):
    register(client)
    # A generated harmonic signal exercises the pipeline; it is not natural speech.
    sr = 16000
    t = np.arange(sr * 3) / sr
    values = (.1 * np.sin(2 * np.pi * 150 * t) + .025 * np.sin(2 * np.pi * 300 * t)) * (.7 + .3 * np.sin(2 * np.pi * 3 * t))
    stream = io.BytesIO(); sf.write(stream, values, sr, format='WAV', subtype='PCM_16')
    metadata = {**base(), 'client_session_id': 'tone', 'recorded_at': (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()}
    response = client.post('/api/v1/voice/checkins', data={'metadata': json.dumps(metadata)}, files={'audio': ('synthetic.wav', stream.getvalue(), 'audio/wav')})
    assert response.status_code == 201, response.text
    assert response.json()['status'] == 'accepted'
    r = weighted(client)
    assert r['integration']['normalized_weights'] == {'facial': 0, 'voice': 1, 'risk': 0}
    assert r['integration']['modalities']['voice']['origin'] == 'assessment_record'


def test_state_restoration_unrated_feedback_and_guide_contract(client):
    register(client)
    catalog = client.get('/api/v1/interventions/catalog').json()['activities']
    assert len(catalog) == 8
    for a in catalog:
        assert sum(s['duration_seconds'] for s in a['guide_steps']) == a['duration_seconds']
    r = weighted(client)
    sid = start(client, r).json()['session_id']
    state = client.get('/api/v1/interventions/state/I1').json()
    assert state['unfinished'][0]['session_id'] == sid
    finish(client, sid)
    state = client.get('/api/v1/interventions/state/I1').json()
    assert state['unfinished'] == [] and state['unrated'][0]['session_id'] == sid
    rate(client, sid)
    assert client.get('/api/v1/interventions/state/I1').json()['unrated'] == []


@pytest.mark.parametrize('case,reason', [('future', 'future_result'), ('quality', 'insufficient_quality'), ('version', 'unsupported_model_version'), ('baseline', 'baseline_unavailable'), ('temporal', 'invalid_temporal_result')])
def test_ineligible_actual_assessment_cannot_influence_rank(client, case, reason):
    register(client)
    face = actual_face(client)
    with client.app.state.sessions() as db:
        row = db.get(FacialSession, face['session_id'])
        if case == 'future': row.recorded_at = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
        if case == 'quality': row.status = 'insufficient_quality'
        if case == 'baseline': row.baseline_id = 'missing'
        if case == 'version': row.result = {**row.result, 'evidence': {**row.result['evidence'], 'model_version': 'unknown'}}
        if case == 'temporal': row.result = {**row.result, 'temporal': {**row.result['temporal'], 'return_fraction': None}}
        db.commit()
    r = weighted(client, context_mode='explicit_refs', facial_session_id=face['session_id'])
    assert r['integration']['fallback']
    assert r['integration']['modalities']['facial']['reason'] == reason
    assert all(o['explanation']['component_contributions'] == {} for o in r['options'])


def test_live_synthetic_script_and_new_evaluation_route(client):
    from scripts.run_optional_context_demo import run
    report = run(client)
    assert len(report['availability_cases']) == 8
    assert client.get('/api/v1/interventions/state/' + report['participant_id']).json()['unrated'] == []
    audit = client.get('/api/v1/interventions/evaluation/optional-context')
    assert audit.status_code == 200 and audit.json()['all_missing_fallback_matches_adaptive']
