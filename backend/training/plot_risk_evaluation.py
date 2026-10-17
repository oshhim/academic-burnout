import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


if __name__ == "__main__":
    folder = Path("models/risk")
    report = json.loads((folder / "evaluation.json").read_text())
    names = list(report["comparisons"])
    labels = ["Dummy prior", "Weekly persistence", "Behaviour-only logistic", "Combined logistic", "Combined random forest", "Combined gradient boosting"]
    test = [report["comparisons"][n]["heldout_test"]["roc_auc"] for n in names]
    brier = [report["comparisons"][n]["heldout_test"]["brier_score"] for n in names]
    cv = [report["comparisons"][n]["cv_roc_auc_mean"] for n in names]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), layout="constrained", gridspec_kw={"width_ratios": [1.7, 1]})
    y = np.arange(len(names))
    if all(v is not None for v in cv):
        axes[0].barh(y - .18, cv, height=.34, color="#206d58", label="Purged CV")
        axes[0].barh(y + .18, test, height=.34, color="#93adbf", label="Held-out people / later dates")
    else:
        axes[0].barh(y, test, height=.55, color="#93adbf", label="Held-out people / later dates")
    axes[0].set(yticks=y, yticklabels=labels, xlabel="ROC AUC (higher is better)", xlim=(0, 1))
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, fontsize=8, frameon=False)
    axes[1].barh(y, brier, height=.55, color=["#206d58" if n == report["selected_model"] else "#93adbf" for n in names])
    axes[1].set(yticks=y, yticklabels=[], xlabel="Test Brier score (lower is better)", xlim=(0, .32))
    axes[1].invert_yaxis()
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    title = "SYNTHETIC DATA ONLY — technical pipeline evaluation" if report["synthetic_only"] else "Exploratory local exhaustion proxy — no clinical validation"
    fig.suptitle(title, fontweight="bold", fontsize=13)
    fig.savefig(folder / "risk_model_comparison.png", dpi=170)
    fig.savefig(folder / "risk_model_comparison.pdf")
    plt.close(fig)
    print("Saved correctly labelled risk-model comparison PNG/PDF.")
