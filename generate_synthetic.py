"""
Synthetic SEM-style dataset generator (DRAM-like periodic + unique textures).
AM-compliant: 1000x1000 pairs, 9:1-11:1 scale, +/-2 deg rotation,
noise/gamma degradation, full per-pair metadata, fixed seed.
"""
import os
import cv2
import numpy as np
import pandas as pd

SEARCH_SIZE = 1000
REF_SIZE = 1000
OUT_DIR = os.path.join("data", "synthetic")
SCALE_RATIOS = [9.0, 9.5, 10.0, 10.5, 11.0]          # ← NEW (was: fixed 10)

os.makedirs(OUT_DIR, exist_ok=True)
np.random.seed(42)


def make_random_search(size):
    img = np.random.randint(0, 256, (size, size), dtype=np.uint8)
    return cv2.GaussianBlur(img, (5, 5), 0)


def make_periodic_search(size, cell):
    img = np.full((size, size), 25, dtype=np.uint8)
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            xe = min(x + cell - 5, size - 1)
            ye = min(y + cell - 5, size - 1)
            cv2.rectangle(img, (x + 5, y + 5), (xe, ye), 205, -1)
            cv2.circle(img, (x + cell // 2, y + cell // 2), 4, 80, -1)
    noise = np.random.normal(0, 5, img.shape).astype(np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def degrade(img, noise_sigma, gamma):                 # ← NEW function
    out = np.power(img.astype(np.float32) / 255.0, gamma) * 255.0
    if noise_sigma > 0:
        out = out + np.random.normal(0, noise_sigma, out.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def generate_one(idx, difficulty):
    ratio = float(np.random.choice(SCALE_RATIOS))     # ← NEW: scale varies 9-11
    patch = int(round(REF_SIZE / ratio))              # ← NEW: patch size follows ratio
    angle = float(np.random.uniform(-2, 2)) if np.random.rand() < 0.6 else 0.0   # ← NEW
    noise_sigma = float(np.random.uniform(0, 12))     # ← NEW
    gamma = float(np.random.uniform(0.85, 1.15))      # ← NEW

    if difficulty == "easy":
        search_clean = make_random_search(SEARCH_SIZE)
        x = int(np.random.randint(60, SEARCH_SIZE - patch - 60))
        y = int(np.random.randint(60, SEARCH_SIZE - patch - 60))
        cell_img = np.random.randint(0, 256, (patch, patch), dtype=np.uint8)
        cell_img = cv2.GaussianBlur(cell_img, (3, 3), 0)
        search_clean[y:y + patch, x:x + patch] = cell_img
    else:
        cell = patch
        search_clean = make_periodic_search(SEARCH_SIZE, cell)
        cells = SEARCH_SIZE // cell
        x = (cells // 2) * cell + int(np.random.randint(-4, 5))
        y = (cells // 2) * cell + int(np.random.randint(-4, 5))
        cell_img = search_clean[y:y + patch, x:x + patch].copy()
        noise = np.random.normal(0, 25, cell_img.shape).astype(np.int16)
        cell_img = np.clip(cell_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        search_clean[y:y + patch, x:x + patch] = cell_img

    patch_base = search_clean[y:y + patch, x:x + patch].copy()
    reference = cv2.resize(patch_base, (REF_SIZE, REF_SIZE), interpolation=cv2.INTER_CUBIC)

    true_x = x + patch / 2.0
    true_y = y + patch / 2.0

    search = search_clean
    if angle != 0.0:                                  # ← NEW: rotate whole search image
        M = cv2.getRotationMatrix2D((SEARCH_SIZE / 2, SEARCH_SIZE / 2), angle, 1.0)
        search = cv2.warpAffine(search_clean, M, (SEARCH_SIZE, SEARCH_SIZE),
                                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        true_x = float(M[0][0] * true_x + M[0][1] * true_y + M[0][2])
        true_y = float(M[1][0] * true_x + M[1][1] * true_y + M[1][2])

    search = degrade(search, noise_sigma, gamma)      # ← NEW: noise + gamma

    s_name = f"search_{idx:03d}.png"
    r_name = f"reference_{idx:03d}.png"
    cv2.imwrite(os.path.join(OUT_DIR, s_name), search)
    cv2.imwrite(os.path.join(OUT_DIR, r_name), reference)

    return {
        "id": idx,
        "search_image": s_name,
        "reference_image": r_name,
        "true_x": round(true_x, 3),
        "true_y": round(true_y, 3),
        "patch_size": patch,
        "scale": ratio,                               # ← NEW metadata
        "rotation_deg": round(angle, 3),              # ← NEW metadata
        "noise_sigma": round(noise_sigma, 3),         # ← NEW metadata
        "gamma": round(gamma, 3),                     # ← NEW metadata
        "difficulty": difficulty,
    }


rows = []
idx = 0
for _ in range(30):
    rows.append(generate_one(idx, "easy")); idx += 1
for _ in range(10):
    rows.append(generate_one(idx, "hard")); idx += 1

pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "ground_truth.csv"), index=False)
print(f"Done. Generated {len(rows)} synthetic test cases (1000x1000).")
print(f"Saved inside: {OUT_DIR}")