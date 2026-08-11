import os
import numpy as np
import pandas as pd

from src.matcher import locate_reference

DATA_DIR = os.path.join("data", "synthetic")
RESULTS_DIR = "results"

CONFIGS = {
    "full":          dict(multi_scale=True,  use_preprocessing=True,  refine_subpixel_flag=True),
    "no_preproc":    dict(multi_scale=True,  use_preprocessing=False, refine_subpixel_flag=True),
    "no_multiscale": dict(multi_scale=False, use_preprocessing=True,  refine_subpixel_flag=True),
    "no_subpixel":   dict(multi_scale=True,  use_preprocessing=True,  refine_subpixel_flag=False),
}

def main():
    gt = pd.read_csv(os.path.join(DATA_DIR, "ground_truth.csv"))

    rows = []
    for row in gt.itertuples():
        s = os.path.join(DATA_DIR, row.search_image)
        r = os.path.join(DATA_DIR, row.reference_image)

        for name, cfg in CONFIGS.items():
            px, py, score, det = locate_reference(
                s, r, scale=0.1, return_details=True, **cfg
            )
            err = float(np.hypot(px - row.true_x, py - row.true_y))
            rows.append({
                "id": row.id,
                "difficulty": row.difficulty,
                "config": name,
                "error_px": round(err, 3),
                "score": round(score, 3),
                "ai_fallback": det.get("used_ai_fallback", False),
                "periodic_detected": det.get("periodicity", {}).get("is_periodic", None),
            })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "ablation.csv"), index=False)

    print("\n=== MEAN ERROR BY CONFIG ===")
    print(df.groupby("config")["error_px"].mean().round(3).to_string())

    print("\n=== FAILURES ON FULL PIPELINE (error > 10 px) ===")
    full_fail = df[(df.config == "full") & (df.error_px > 10)]
    print(full_fail.to_string(index=False))

    print("\n=== FAILURE AUTOPSY ===")
    for i in full_fail["id"]:
        e_full = df.loc[(df.id == i) & (df.config == "full"), "error_px"].iloc[0]
        e_nopre = df.loc[(df.id == i) & (df.config == "no_preproc"), "error_px"].iloc[0]
        e_noms = df.loc[(df.id == i) & (df.config == "no_multiscale"), "error_px"].iloc[0]
        fb = df.loc[(df.id == i) & (df.config == "full"), "ai_fallback"].iloc[0]
        per = df.loc[(df.id == i) & (df.config == "full"), "periodic_detected"].iloc[0]
        print(
            f"id {i:>2}: full={e_full:8.2f} | no_preproc={e_nopre:8.2f} | "
            f"no_multiscale={e_noms:8.2f} | ai_fallback={fb} | periodic_detected={per}"
        )

if __name__ == "__main__":
    main()