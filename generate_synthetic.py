import os
import cv2
import numpy as np
import pandas as pd

# -----------------------------
# CONFIG
# -----------------------------
SEARCH_SIZE = 512
PATCH_SIZE = 32
SCALE = 10
OUT_DIR = "data/synthetic"

os.makedirs(OUT_DIR, exist_ok=True)


# -----------------------------
# IMAGE GENERATORS
# -----------------------------
def make_random_search_image():
    """
    Creates a random texture image.
    This is the easy case: the pattern is usually unique.
    """
    img = np.random.randint(0, 256, (SEARCH_SIZE, SEARCH_SIZE), dtype=np.uint8)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    return img


def make_periodic_search_image():
    """
    Creates a repetitive grid-like image.
    This is harder because many regions look similar.
    """
    img = np.full((SEARCH_SIZE, SEARCH_SIZE), 25, dtype=np.uint8)

    step = PATCH_SIZE

    for y in range(0, SEARCH_SIZE, step):
        for x in range(0, SEARCH_SIZE, step):
            cv2.rectangle(
                img,
                (x + 5, y + 5),
                (x + step - 5, y + step - 5),
                205,
                -1
            )
            cv2.circle(
                img,
                (x + step // 2, y + step // 2),
                4,
                80,
                -1
            )

    # Add slight noise so it is not perfectly identical everywhere
    noise = np.random.normal(0, 5, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return img


# -----------------------------
# TARGET INSERTION
# -----------------------------
def add_unique_patch(img):
    """
    Adds a unique random patch into the search image.
    This gives us a clear ground truth.
    """
    h, w = img.shape[:2]

    x = np.random.randint(20, w - PATCH_SIZE - 20)
    y = np.random.randint(20, h - PATCH_SIZE - 20)

    patch = np.random.randint(0, 256, (PATCH_SIZE, PATCH_SIZE), dtype=np.uint8)
    patch = cv2.GaussianBlur(patch, (3, 3), 0)

    img[y:y + PATCH_SIZE, x:x + PATCH_SIZE] = patch

    return img, x, y


def modify_periodic_cell(img):
    """
    Chooses one cell in the periodic grid and slightly modifies it.
    This creates a hard case where many cells look similar,
    but one is still the intended target.
    """
    step = PATCH_SIZE
    cells = SEARCH_SIZE // step

    gx = np.random.randint(2, cells - 2)
    gy = np.random.randint(2, cells - 2)

    x = gx * step
    y = gy * step

    cell = img[y:y + step, x:x + step].copy()

    # Slightly disturb the target cell
    noise = np.random.normal(0, 25, cell.shape).astype(np.int16)
    cell = np.clip(cell.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    img[y:y + step, x:x + step] = cell

    return img, x, y


# -----------------------------
# CREATE ONE TEST CASE
# -----------------------------
def generate_one(idx, difficulty="easy"):
    if difficulty == "easy":
        search = make_random_search_image()
        search, x, y = add_unique_patch(search)
    else:
        search = make_periodic_search_image()
        search, x, y = modify_periodic_cell(search)

    # The true matching region inside the search image
    patch = search[y:y + PATCH_SIZE, x:x + PATCH_SIZE].copy()

    # Reference image is the same patch, but 10x larger
    reference = cv2.resize(
        patch,
        (PATCH_SIZE * SCALE, PATCH_SIZE * SCALE),
        interpolation=cv2.INTER_CUBIC
    )

    search_filename = f"search_{idx:03d}.png"
    reference_filename = f"reference_{idx:03d}.png"

    search_path = os.path.join(OUT_DIR, search_filename)
    reference_path = os.path.join(OUT_DIR, reference_filename)

    cv2.imwrite(search_path, search)
    cv2.imwrite(reference_path, reference)

    true_x = x + PATCH_SIZE // 2
    true_y = y + PATCH_SIZE // 2

    return {
        "id": idx,
        "search_image": search_filename,
        "reference_image": reference_filename,
        "true_x": true_x,
        "true_y": true_y,
        "patch_size": PATCH_SIZE,
        "scale": SCALE,
        "difficulty": difficulty
    }


# -----------------------------
# GENERATE DATASET
# -----------------------------
rows = []
idx = 0

# 30 easy examples
for _ in range(30):
    rows.append(generate_one(idx, difficulty="easy"))
    idx += 1

# 10 hard periodic examples
for _ in range(10):
    rows.append(generate_one(idx, difficulty="hard"))
    idx += 1

df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT_DIR, "ground_truth.csv"), index=False)

print(f"Done. Generated {len(df)} synthetic test cases.")
print(f"Saved inside: {OUT_DIR}")