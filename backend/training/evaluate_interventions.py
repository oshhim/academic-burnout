"""Compare fixed policies in an explicitly synthetic environment, never clinical efficacy."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
from app.interventions.catalog import ACTIVITIES, CATALOG_VERSION, CATEGORIES, GOALS, POLICY_VERSION
from app.interventions.policy import feedback_summary, rank
from app.interventions.schemas import default_preferences

# This historical preference simulator has no component observations. Keep its
# three baseline comparisons separate from the optional-context sensitivity audit.
STRATEGIES = ("generic", "preference", "adaptive")


def simulate(people=120, rounds=28, seed=418):
    rng = np.random.default_rng(seed)
    per_person = {s: [] for s in STRATEGIES}
    counts = {s: {"offers": 0, "empty": 0, "starts": 0, "completed": 0, "ratings": [], "constraint_violations": 0, "chosen": set()} for s in STRATEGIES}
    logs = []
    for person in range(people):
        hidden = dict(zip(CATEGORIES, rng.uniform(0, 1, len(CATEGORIES))))
        prefs = default_preferences()
        # Partly noisy/missing declared likes: not exact hidden reward labels.
        prefs["category_ratings"] = {c: 3 if rng.random() < 0.35 else int(np.clip(np.rint(1 + 4 * hidden[c] + rng.normal(0, 1.1)), 1, 5)) for c in CATEGORIES}
        prefs["allow_movement"] = bool(rng.random() > 0.2)
        prefs["allow_audio"] = bool(rng.random() > 0.25)
        if rng.random() < 0.15:
            prefs["excluded_activity_ids"] = [str(rng.choice([a["activity_id"] for a in ACTIVITIES]))]
        goal_sequence = rng.choice(GOALS, rounds)
        available_sequence = rng.choice([60, 120, 180, 300, 600], rounds)
        histories = {s: [] for s in STRATEGIES}
        starts = {s: [] for s in STRATEGIES}
        rewards = {s: [] for s in STRATEGIES}
        for day in range(rounds):
            clock = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
            context = {"goal": str(goal_sequence[day]), "available_seconds": int(available_sequence[day])}
            # Common potential responses across policies for this simulated person/day.
            # This hidden reward generator is not the engineering ranking formula.
            potentials = {}
            for activity in ACTIVITIES:
                utility = np.clip(0.15 + 0.55 * hidden[activity["category"]] + 0.15 * (context["goal"] in activity["goals"]) + rng.normal(0, 0.12), 0, 1)
                rating = int(np.clip(np.rint(1 + 4 * utility + rng.normal(0, 0.6)), 1, 5))
                potentials[activity["activity_id"]] = {"rating": rating, "complete": bool(rng.random() < 0.75 + 0.20 * utility), "respond": bool(rng.random() < 0.80)}
            for strategy in STRATEGIES:
                stats = feedback_summary(histories[strategy], clock)
                recent = {aid for when, aid in starts[strategy] if clock - timedelta(days=7) <= when <= clock}
                options, excluded = rank(prefs, context, strategy, stats, recent)
                group = counts[strategy]
                group["offers"] += 1
                if not options:
                    group["empty"] += 1
                    continue
                chosen = options[0]["activity"]  # Simulator assumes user starts the first eligible offer.
                aid = chosen["activity_id"]
                violation = aid in prefs["excluded_activity_ids"] or chosen["duration_seconds"] > min(prefs["max_duration_seconds"], context["available_seconds"]) or (chosen["movement"] and not prefs["allow_movement"]) or (chosen["audio"] and not prefs["allow_audio"])
                group["constraint_violations"] += int(violation)
                group["starts"] += 1
                group["chosen"].add(aid)
                starts[strategy].append((clock, aid))
                potential = potentials[aid]
                if potential["complete"]:
                    group["completed"] += 1
                    # Potential rating known only in simulation; not inferred from missing real feedback.
                    rewards[strategy].append((potential["rating"] - 1) / 4)
                observed = potential["complete"] and potential["respond"]
                if observed:
                    group["ratings"].append(potential["rating"])
                    histories[strategy].append({"activity_id": aid, "created_at": clock.isoformat(), "helpfulness": potential["rating"], "feedback_id": f"SIM-{person}-{day}-{strategy}"})
                logs.append({"participant_id": f"SIM-C4-{person:03d}", "data_source": "synthetic_demo", "round": day, "created_at": clock.isoformat(),
                             "strategy": strategy, "context": context, "activity_id": aid, "completed": potential["complete"],
                             "helpfulness": potential["rating"] if observed else None, "clinical_outcome": False})
        for strategy in STRATEGIES:
            per_person[strategy].append(float(np.mean(rewards[strategy])) if rewards[strategy] else None)
    results = []
    for strategy in STRATEGIES:
        group = counts[strategy]
        values = [v for v in per_person[strategy] if v is not None]
        results.append({"strategy": strategy, "decision_contexts": group["offers"], "no_eligible_contexts": group["empty"], "started": group["starts"],
                        "completed": group["completed"], "observed_feedback": len(group["ratings"]), "hard_constraint_violations": group["constraint_violations"],
                        "distinct_activities_chosen": len(group["chosen"]), "completion_rate_among_started": group["completed"] / group["starts"] if group["starts"] else None,
                        "mean_observed_helpfulness": float(np.mean(group["ratings"])) if group["ratings"] else None,
                        "mean_simulator_utility_per_person_among_completed": float(np.mean(values)) if values else None})
    return {"policy_version": POLICY_VERSION, "catalog_version": CATALOG_VERSION, "data_source": "synthetic_demo", "synthetic_only": True,
            "human_participants": 0, "seed": seed, "simulated_people": people, "rounds_per_person": rounds, "strategy_comparison": results,
            "clinical_validation": False, "weight_optimization_performed": False, "real_world_off_policy_evaluation": False,
            "optional_component_context_evaluated": False, "optional_context_audit": "models/interventions/optional_context_evaluation.json",
            "protocol": "Fixed policy weights, common synthetic person/context/potential responses across strategies. Each strategy receives only its own observed earlier feedback. First option always started; missing ratings stay missing.",
            "reward_generator": "Hidden random category likes + goal term + independent noise; noisy/partly neutral declared preferences. Completion and feedback sampling separate. This environment rewards category fit by construction.",
            "limitations": ["No human dataset or health outcomes. Results describe one engineered simulator only.", "Selection always chooses first offer; human choices, adherence and preferences can differ.", "Weights are not learned or clinically calibrated; simulator utility is not wellbeing improvement.", "Deterministic real logs have no full action support or valid propensity estimates for unbiased counterfactual comparisons."]}, logs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--people", type=int, default=120)
    parser.add_argument("--rounds", type=int, default=28)
    parser.add_argument("--seed", type=int, default=418)
    parser.add_argument("--output", type=Path, default=Path("models/interventions/evaluation.json"))
    parser.add_argument("--interactions", type=Path, default=Path("data/synthetic/intervention_interactions.json"))
    args = parser.parse_args()
    if not 1 <= args.people <= 2000 or not 1 <= args.rounds <= 365:
        parser.error("Use 1–2000 simulated people and 1–365 rounds")
    result, logs = simulate(args.people, args.rounds, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    args.interactions.parent.mkdir(parents=True, exist_ok=True)
    args.interactions.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
