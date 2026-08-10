"""
Interactive Demo & Testing Script for Drift-Sense Matcher
Run this script to evaluate the matcher on a sample image and view details.
"""

import os
import pandas as pd
from src.matcher import locate_reference

DATA_DIR = os.path.join("data", "synthetic")
GROUND_TRUTH_PATH = os.path.join(DATA_DIR, "ground_truth.csv")


def run_demo(sample_id=0):
    if not os.path.exists(GROUND_TRUTH_PATH):
        print("Ground truth dataset not found. Generating data...")
        os.system("python generate_synthetic.py")

    df = pd.read_csv(GROUND_TRUTH_PATH)
    sample = df[df["id"] == sample_id].iloc[0]

    search_path = os.path.join(DATA_DIR, sample["search_image"])
    ref_path = os.path.join(DATA_DIR, sample["reference_image"])
    true_x, true_y = sample["true_x"], sample["true_y"]

    print(f"\n==========================================")
    print(f" TESTING DRIFT-SENSE MATCHER (Sample #{sample_id})")
    print(f" Difficulty: {sample['difficulty'].upper()}")
    print(f" Search Image: {sample['search_image']}")
    print(f" Reference Image: {sample['reference_image']}")
    print(f"==========================================")

    # Run matcher with extended diagnostic details
    pred_x, pred_y, score, details = locate_reference(
        search_path=search_path,
        reference_path=ref_path,
        scale=0.1,
        return_details=True
    )

    error = ((pred_x - true_x)**2 + (pred_y - true_y)**2)**0.5

    print(f"\n[RESULTS]")
    print(f" True Center Coordinate : ({true_x:.2f}, {true_y:.2f})")
    print(f" Pred Center Coordinate : ({pred_x:.4f}, {pred_y:.4f})")
    print(f" Sub-Pixel Offsets (dx,dy): ({details['subpixel_dx']:.4f}, {details['subpixel_dy']:.4f})")
    print(f" Position Error         : {error:.4f} pixels")
    print(f" Match Confidence Score : {score:.4f}")
    print(f" Selected Scale Factor  : {details['selected_scale']:.3f}")
    print(f" Periodicity Detected   : {details['periodicity']['is_periodic']}")
    print(f"==========================================\n")


if __name__ == "__main__":
    # Test on an easy unique pattern sample
    run_demo(sample_id=0)
    # Test on a periodic pattern sample
    run_demo(sample_id=36)
