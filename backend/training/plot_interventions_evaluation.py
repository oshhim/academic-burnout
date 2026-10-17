"""Scientific artifact for the synthetic comparison; no human effects implied."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

if __name__ == "__main__":
    root = Path("models/interventions")
    result = json.loads((root / "evaluation.json").read_text())
    rows = result["strategy_comparison"]
    labels = [r["strategy"].capitalize() for r in rows]
    values = [r["mean_observed_helpfulness"] for r in rows]
    fig, ax = plt.subplots(figsize=(9, 5.4), layout="constrained")
    bars = ax.bar(labels, values, color=["#99b8a9", "#23745c", "#548e7a"], width=.6)
    ax.set_ylim(0, 5)
    ax.set_ylabel("Mean observed helpfulness (simulated 1–5 rating)")
    ax.set_title("SYNTHETIC DATA ONLY · Component 4 policies", loc="left", fontsize=15, pad=18, weight="bold")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, value + .09, f"{value:.3f}", ha="center")
    ax.spines[["top","right"]].set_visible(False)
    ax.yaxis.grid(True, alpha=.2)
    ax.set_axisbelow(True)
    fig.supxlabel("120 simulated people × 28 contexts · fixed weights · seed 418\nOne engineered environment; no human outcomes or evidence of health benefit.", fontsize=10)
    fig.savefig(root / "policy_comparison.png", dpi=180)
    fig.savefig(root / "policy_comparison.pdf")
