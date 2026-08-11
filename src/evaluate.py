"""
Standalone evaluation reporter for Drift-Sense.
Reads existing predictions and prints metrics without re-running the matcher.

Usage:
    python src/evaluate.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

PREDICTIONS_PATH = os.path.join(ROOT, "results", "predictions.csv")


def main():
    pred = pd.read_csv(PREDICTIONS_PATH)
    errors = pred["error_px"]

    metrics = {
        "num_samples": len(pred),
        "mean_error_px": round(float(errors.mean()), 4),
        "median_error_px": round(float(errors.median()), 4),
        "max_error_px": round(float(errors.max()), 4),
        "hit_rate_1px": round(float((errors <= 1).mean()), 3),
        "hit_rate_5px": round(float((errors <= 5).mean()), 3),
        "hit_rate_10px": round(float((errors <= 10).mean()), 3),
    }

    print("\n=== EVALUATION SUMMARY (from results/predictions.csv) ===")
    for k, v in metrics.items():
        print(f"{k:>16}: {v}")

    print("\n=== PER-DIFFICULTY MEAN ERROR ===")
    print(pred.groupby("difficulty")["error_px"].mean().round(4).to_string())


if __name__ == "__main__":
    main()