"""Publication/export-friendly plots from actual saved metrics, no fake values."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    folder = Path("models/voice")
    report = json.loads((folder / "evaluation.json").read_text())
    names = list(report["comparisons"])
    cv = [report["comparisons"][name]["cv_macro_f1_mean"] for name in names]
    test = [report["comparisons"][name]["heldout_test"]["macro_f1"] for name in names]
    short = ["Dummy", "Logistic regression", "Linear SVM", "RBF SVM C=1", "RBF SVM C=10"]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(8.8, 4.8), layout="constrained")
    positions = np.arange(len(names))
    ax.bar(positions - .18, cv, width=.35, label="Train-speaker CV", color="#186b55")
    ax.bar(positions + .18, test, width=.35, label="Held-out speakers", color="#8eaec3")
    ax.set(xticks=positions, xticklabels=short, ylim=(0, .65), ylabel="Macro F1", title="RAVDESS baseline comparison — quality-accepted recordings")
    ax.tick_params(axis="x", labelsize=9)
    ax.legend(frameon=False, loc="upper left")
    ax.text(0.99, .96, "Selection uses CV only\n18 train / 6 test actors", transform=ax.transAxes, ha="right", va="top", fontsize=9)
    fig.savefig(folder / "model_comparison.png", dpi=180)
    fig.savefig(folder / "model_comparison.pdf")
    plt.close(fig)
    matrix = np.asarray(report["comparisons"][report["selected_model"]]["heldout_test"]["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(7.3, 6.3), layout="constrained")
    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax, label="Recording count", shrink=.7)
    selected_name = short[names.index(report["selected_model"])]
    ax.set(xticks=np.arange(8), yticks=np.arange(8), xticklabels=report["label_order"], yticklabels=report["label_order"], xlabel="Predicted acted style", ylabel="Dataset acted label", title=f"{selected_name}: held-out actor confusion matrix")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    for i in range(8):
        for j in range(8):
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center", color="white" if matrix[i, j] > matrix.max() / 2 else "#193b50", fontsize=9)
    fig.savefig(folder / "confusion_matrix.png", dpi=180)
    fig.savefig(folder / "confusion_matrix.pdf")
    plt.close(fig)
    print("Saved comparison and confusion-matrix PNG/PDF plots from actual metrics.")


if __name__ == "__main__":
    main()
