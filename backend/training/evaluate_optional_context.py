"""Reproducible C4 sensitivity and missingness audit, without human outcomes."""
import argparse
from datetime import datetime, timezone
from itertools import product
import json
from pathlib import Path
from app.interventions.context import mapped, normalize, unavailable, BASE_WEIGHTS, MAPPING_VERSION
from app.interventions.policy import rank
from app.interventions.schemas import default_preferences
from app.interventions.catalog import POLICY_VERSION, CATALOG_VERSION


def evaluate():
    clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
    keys = {'facial': 'persistent_visual_change', 'voice': 'sad_style_fixture', 'risk': 'higher_exhaustion_proxy'}
    prefs = default_preferences()
    prefs['category_ratings'].update(pause=3, planning=4, reflection=2)
    context = {'goal': 'refocus', 'available_seconds': 300}
    rows = []
    violations = 0
    for mask in product([False, True], repeat=3):
        modalities = {k: mapped(k, 'synthetic-fixture', clock.isoformat(), keys[k], 'synthetic_fixture') if on else unavailable(k) for k, on in zip(BASE_WEIGHTS, mask)}
        integration = normalize(modalities, clock, 'explicit_fixture')
        strategies = {}
        for strategy in ('generic', 'preference', 'adaptive', 'multimodal_weighted'):
            options, _ = rank(prefs, context, strategy, {}, set(), integration)
            strategies[strategy] = [{'activity_id': o['activity']['activity_id'], 'score': o['score'], 'explanation': o['explanation']} for o in options]
            for o in options:
                a = o['activity']
                violations += int(a['duration_seconds'] > 300 or a['activity_id'] in prefs['excluded_activity_ids'])
        a = strategies['adaptive']; w = strategies['multimodal_weighted']
        ascores = {o['activity_id']: o['score'] for o in a}
        rows.append({'available_components': [k for k, on in zip(BASE_WEIGHTS, mask) if on], 'normalized_weights': integration['normalized_weights'],
                     'fallback': integration['fallback'], 'exact_independent_fallback': a == w if not any(mask) else None,
                     'score_changes': sum(o['score'] != ascores[o['activity_id']] for o in w), 'strategies': strategies})
    return {'synthetic_only': True, 'human_participants': 0, 'clinical_validation': False, 'trained_model': False,
            'policy_version': POLICY_VERSION, 'catalog_version': CATALOG_VERSION, 'mapping_version': MAPPING_VERSION,
            'availability_combinations': len(rows), 'hard_constraint_violations': violations,
            'all_missing_fallback_matches_adaptive': rows[0]['exact_independent_fallback'], 'cases': rows,
            'interpretation': 'Software sensitivity and missingness audit. No helpfulness ratings, model accuracy or health improvements were measured.',
            'next_study': 'Compare four policies with real consented feedback, participant grouping, prespecified mappings, missingness and modality ablations.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('models/interventions/optional_context_evaluation.json'))
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))
