import os
import numpy as np
import pandas as pd

from src.matcher import locate_reference


DATA_DIR = os.path.join("data", "synthetic")
RESULTS_DIR = "results"


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    ground_truth_path = os.path.join(DATA_DIR, "ground_truth.csv")

    if not os.path.exists(ground_truth_path):
        raise FileNotFoundError(
            f"Ground truth file not found: {ground_truth_path}"
        )

    ground_truth = pd.read_csv(ground_truth_path)

    records = []

    for row in ground_truth.itertuples():
        search_path = os.path.join(DATA_DIR, row.search_image)
        reference_path = os.path.join(DATA_DIR, row.reference_image)

        # If scale column exists, use it.
        # The synthetic generator uses scale = 10, meaning reference is 10x bigger.
        # Therefore matcher scale should be 1 / 10 = 0.1.
        scale_value = getattr(row, "scale", 10.0)

        if scale_value and float(scale_value) > 0:
            matcher_scale = 1.0 / float(scale_value)
        else:
            matcher_scale = 0.1

        pred_x, pred_y, score = locate_reference(
            search_path=search_path,
            reference_path=reference_path,
            scale=matcher_scale
        )

        true_x = row.true_x
        true_y = row.true_y

        error_px = float(
            np.sqrt(
                (pred_x - true_x) ** 2 +
                (pred_y - true_y) ** 2
            )
        )

        records.append(
            {
                "id": row.id,
                "search_image": row.search_image,
                "reference_image": row.reference_image,
                "true_x": true_x,
                "true_y": true_y,
                "pred_x": pred_x,
                "pred_y": pred_y,
                "error_px": error_px,
                "score": score,
                "difficulty": getattr(row, "difficulty", "unknown"),
            }
        )

    predictions = pd.DataFrame(records)

    predictions_path = os.path.join(RESULTS_DIR, "predictions.csv")
    predictions.to_csv(predictions_path, index=False)

    errors = predictions["error_px"]

    metrics = {
        "num_samples": len(predictions),
        "mean_error_px": float(errors.mean()),
        "median_error_px": float(errors.median()),
        "max_error_px": float(errors.max()),
        "hit_rate_1px": float((errors <= 1).mean()),
        "hit_rate_3px": float((errors <= 3).mean()),
        "hit_rate_5px": float((errors <= 5).mean()),
        "hit_rate_10px": float((errors <= 10).mean()),
        "avg_match_score": float(predictions["score"].mean()),
    }

    metrics_df = pd.DataFrame([metrics])

    metrics_path = os.path.join(RESULTS_DIR, "metrics.csv")
    metrics_df.to_csv(metrics_path, index=False)

    print("\nPredictions saved to:")
    print(predictions_path)

    print("\nMetrics saved to:")
    print(metrics_path)

    print("\nEvaluation Metrics:")
    print(metrics_df.to_string(index=False))


if __name__ == "__main__":
    main()