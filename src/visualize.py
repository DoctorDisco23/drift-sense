"""
Visualization module for Drift-Sense.

Generates side-by-side overlay images (Reference | Search) showing:
- Ground truth center (green ring)
- Predicted center (red dot)
- Matched bounding box
- Error and confidence metrics

Usage:
    python src\visualize.py
"""
import os
import sys

# Make sure the project root is on sys.path no matter how this is run
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2
import numpy as np
import pandas as pd

from src.matcher import locate_reference

DATA_DIR = os.path.join(ROOT, "data", "synthetic")
OUT_DIR = os.path.join(ROOT, "results", "visualizations")


def visualize_sample(sample_id, data_dir=DATA_DIR, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)

    gt_path = os.path.join(data_dir, "ground_truth.csv")
    df = pd.read_csv(gt_path)
    row = df[df["id"] == sample_id].iloc[0]

    search_path = os.path.join(data_dir, row["search_image"])
    ref_path = os.path.join(data_dir, row["reference_image"])

    search_img = cv2.imread(search_path)
    ref_img = cv2.imread(ref_path)

    if search_img is None or ref_img is None:
        print(f"Could not load images for sample {sample_id}")
        return

    # Convert grayscale to 3-channel BGR so we can draw colored markers
    if len(search_img.shape) == 2:
        search_img = cv2.cvtColor(search_img, cv2.COLOR_GRAY2BGR)
    if len(ref_img.shape) == 2:
        ref_img = cv2.cvtColor(ref_img, cv2.COLOR_GRAY2BGR)

    # Run the matcher with diagnostics
    pred_x, pred_y, score, details = locate_reference(
        search_path=search_path,
        reference_path=ref_path,
        scale=0.1,
        return_details=True,
    )

    true_x, true_y = float(row["true_x"]), float(row["true_y"])
    error = float(np.hypot(pred_x - true_x, pred_y - true_y))

    # --- Draw on the search image ---
    # Ground truth: larger green ring (stays visible under the red marker)
    cv2.circle(search_img, (int(round(true_x)), int(round(true_y))), 10, (0, 255, 0), 2)
    cv2.putText(search_img, "GT", (int(true_x) + 12, int(true_y) - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Prediction: red dot + bounding box
    cv2.circle(search_img, (int(round(pred_x)), int(round(pred_y))), 4, (0, 0, 255), -1)
    cv2.putText(search_img, "Pred", (int(pred_x) + 12, int(pred_y) + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Bounding box of the matched region (reference 320 px -> ~32 px in search)
    box = 32
    tl = (int(round(pred_x - box / 2)), int(round(pred_y - box / 2)))
    br = (int(round(pred_x + box / 2)), int(round(pred_y + box / 2)))
    cv2.rectangle(search_img, tl, br, (0, 0, 255), 2)

    # Metrics overlay
    cv2.putText(search_img, f"Sample {sample_id} ({row['difficulty'].upper()})",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(search_img, f"Error: {error:.3f} px",
                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(search_img, f"Score: {score:.3f}",
                (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # --- Side-by-side: Reference | Search ---
    ref_resized = cv2.resize(ref_img, (search_img.shape[1], search_img.shape[0]))
    combined = np.hstack((ref_resized, search_img))

    out_path = os.path.join(out_dir, f"overlay_{sample_id:03d}.png")
    cv2.imwrite(out_path, combined)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    # One easy (unique texture) and one hard (periodic) case
    visualize_sample(0)
    visualize_sample(36)
    print("Done! Check results/visualizations/")