import os
import time
import platform
import numpy as np
import pandas as pd

from src.matcher import locate_reference

DATA_DIR = os.path.join("data", "synthetic")
RESULTS_DIR = "results"


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ground_truth_path = os.path.join(DATA_DIR, "ground_truth.csv")
    if not os.path.exists(ground_truth_path):
        raise FileNotFoundError(f"Ground truth file not found: {ground_truth_path}")

    ground_truth = pd.read_csv(ground_truth_path)

    records = []
    runtimes_ms = []

    for row in ground_truth.itertuples():
        search_path = os.path.join(DATA_DIR, row.search_image)
        reference_path = os.path.join(DATA_DIR, row.reference_image)

        scale_value = getattr(row, "scale", 10.0)
        matcher_scale = 1.0 / float(scale_value) if scale_value else 0.1

        t0 = time.perf_counter()
        pred_x, pred_y, score = locate_reference(
            search_path=search_path,
            reference_path=reference_path,
            scale=matcher_scale,
        )
        runtime_ms = (time.perf_counter() - t0) * 1000.0
        runtimes_ms.append(runtime_ms)

        true_x, true_y = row.true_x, row.true_y
        error_px = float(np.sqrt((pred_x - true_x) ** 2 + (pred_y - true_y) ** 2))

        records.append({
            "id": row.id,
            "search_image": row.search_image,
            "reference_image": row.reference_image,
            "true_x": true_x,
            "true_y": true_y,
            "pred_x": pred_x,
            "pred_y": pred_y,
            "error_px": error_px,
            "score": score,
            "runtime_ms": runtime_ms,
            "difficulty": getattr(row, "difficulty", "unknown"),
            "scale": getattr(row, "scale", 10.0),
            "rotation_deg": getattr(row, "rotation_deg", 0.0),
        })

    predictions = pd.DataFrame(records)
    predictions.to_csv(os.path.join(RESULTS_DIR, "predictions.csv"), index=False)

    errors = predictions["error_px"]
    rt = np.array(runtimes_ms)

    metrics = {
        "num_samples": len(predictions),
        "mean_error_px": float(errors.mean()),
        "median_error_px": float(errors.median()),
        "max_error_px": float(errors.max()),
        "pass_rate_5px": float((errors <= 5).mean()),
        "pass_rate_4px": float((errors <= 4).mean()),
        "pass_rate_2px": float((errors <= 2).mean()),
        "pass_rate_1px": float((errors <= 1).mean()),
        "subpixel_rate_0.5px": float((errors <= 0.5).mean()),
        "avg_match_score": float(predictions["score"].mean()),
        "mean_runtime_ms": float(rt.mean()),
        "p95_runtime_ms": float(np.percentile(rt, 95)),
    }
    pd.DataFrame([metrics]).to_csv(os.path.join(RESULTS_DIR, "metrics.csv"), index=False)

    print("\n=== EVALUATION METRICS ===")
    print(pd.DataFrame([metrics]).to_string(index=False))

    print("\n=== RUNTIME / ENVIRONMENT ===")
    print(f"Hardware       : {platform.processor() or platform.machine()} | "
          f"{platform.system()} {platform.release()} | {os.cpu_count()} logical CPUs")
    print(f"Python version : {platform.python_version()}")
    print("Timing method  : time.perf_counter() wall-clock per image pair (CPU-only)")

    print("\n=== PER-DIFFICULTY ===")
    print(predictions.groupby("difficulty")["error_px"]
          .agg(["mean", "median", "max"]).round(4).to_string())

    if "scale" in predictions.columns:
        print("\n=== PER-SCALE (mean error px) ===")
        print(predictions.groupby("scale")["error_px"].mean().round(4).to_string())

    if "rotation_deg" in predictions.columns:
        rot_bucket = np.where(predictions["rotation_deg"].abs() < 0.01, "none", "rotated")
        print("\n=== PER-ROTATION (mean error px) ===")
        print(predictions.groupby(rot_bucket)["error_px"].mean().round(4).to_string())

    print("\nPredictions saved to:", os.path.join(RESULTS_DIR, "predictions.csv"))
    print("Metrics saved to  :", os.path.join(RESULTS_DIR, "metrics.csv"))


if __name__ == "__main__":
    main()