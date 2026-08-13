<div align="center">

# 🎯 Drift-Sense

**AI-Powered Navigation-Error Recovery & Sub-Pixel Alignment for Wafer Inspection Tools**

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)
![Mean Error](https://img.shields.io/badge/Mean%20Error-0.077%20px-brightgreen)
![Hit Rate](https://img.shields.io/badge/Hit%20Rate%20%401px-100%25-brightgreen)
![Training](https://img.shields.io/badge/Training%20Latency-0%20ms-orange)

*A deterministic, zero-shot computer-vision engine that re-locates microscopic wafer sites with sub-pixel precision — even inside highly periodic semiconductor layouts.*

</div>

---

## 📌 The Problem

Modern wafer inspection tools must return to **the exact same microscopic site** on a die thousands of times per day. In practice, thermal expansion, vibration and mechanical slack cause **navigation drift**, and the tool may land several pixels off-target.

Because semiconductor layouts (DRAM arrays, FinFET gates) are **highly periodic**, a wrong location looks nearly identical to the right one — classical template matching breaks down exactly where precision matters most.

> **Task:** Given a 1000×1000 Reference Image (100× view) and a 1000×1000 Search Image (10× view) in which the reference pattern appears at ~10× reduced scale, return the center coordinates `(x, y)` of the matching region. If multiple matching regions are found, return the one closest to the center of the Search Image.

---

## 💡 The Solution

**Drift-Sense** is a coarse-to-fine, fully deterministic pipeline combining classical signal processing with advanced computer vision — **no training data, no GPU, 0 ms training latency**.

```text
 Search S (1000×1000)        Reference R (1000×1000)
        │                            │
        └──────────┬─────────────────┘
                   ▼
      ┌─────────────────────────────┐
      │ 1 · ADAPTIVE PREPROCESSING  │  CLAHE · Gaussian denoise · Z-score
      └─────────────────────────────┘
                   ▼
      ┌─────────────────────────────┐
      │ 2 · MULTI-SCALE NCC SEARCH  │  9:1–11:1 scale window + ±2° rotation refine
      └─────────────────────────────┘
                   ▼
      ┌─────────────────────────────┐
      │ 3 · NMS PEAK EXTRACTION     │  2D dilation morphology, top-K peaks
      └─────────────────────────────┘
                   ▼
      ┌─────────────────────────────┐
      │ 4 · PERIODICITY AWARENESS   │  grid-ambiguity detection
      │     + HIGH-RES RE-VERIFY    │  + physical stage-drift prior
      └─────────────────────────────┘
                   ▼
      ┌─────────────────────────────┐
      │ 5 · SUB-PIXEL REFINEMENT    │  2D quadratic surface fit
      │     + GEOMETRIC FALLBACK    │  ORB keypoints + RANSAC homography
      └─────────────────────────────┘
                   ▼
        Output: (x, y) + confidence
```

---

## 📊 Benchmark Results

Evaluated on a **seeded, reproducible synthetic benchmark** (`np.random.seed(42)`) — 40 test cases (30 unique-texture *easy* + 10 highly periodic *hard*), 1000×1000 pairs, scale ratios 9:1–11:1, rotations up to ±2°, Gaussian noise and gamma degradation.

| Metric | Result |
|---|---|
| **Mean localization error** | **0.077 px** |
| Median error | 0.063 px |
| Max error | 0.247 px |
| **Pass rate @ 5 / 4 / 2 / 1 px** | **100 %** |
| Sub-pixel rate (< 0.5 px) | 100 % |
| Catastrophic failures (> 10 px) | **0 / 40** |
| Mean match confidence | 0.853 |
| **Mean inference time** | **245 ms** (P95: 386 ms) |
| Training latency | 0 ms |

**Runtime environment:** Intel 18 logical CPUs · Windows 11 · Python 3.13.1 · OpenCV 4.x · CPU-only · timed with `time.perf_counter()` wall-clock per image pair.

### Robustness breakdown

| Scale ratio | 9:1 | 9.5:1 | 10:1 | 10.5:1 | 11:1 |
|---|---|---|---|---|---|
| Mean error (px) | 0.111 | 0.069 | 0.059 | 0.039 | 0.085 |

| Rotation | None | Rotated (±2°) |
|---|---|---|
| Mean error (px) | 0.022 | 0.106 |

| Difficulty | Easy | Hard (periodic) |
|---|---|---|
| Mean error (px) | 0.060 | 0.127 |

### 🔬 Ablation Study

| Configuration | Mean error (px) |
|---|---|
| **Full pipeline** | **0.084** |
| − Multi-scale search | 85.579 |
| − Preprocessing | 22.870 |
| − Sub-pixel refinement | 0.369 |

On the AM-compliant benchmark, removing multi-scale search collapses accuracy to ~86 px (9:1–11:1 scale cases fail), and removing preprocessing to ~23 px (noise/gamma cases fail) — confirming every stage is necessary.

---

## 🚀 Quickstart

```bash
# 1 · Clone & install
git clone https://github.com/DoctorDisco23/drift-sense.git
cd drift-sense
pip install -r requirements.txt

# 2 · Generate the reproducible benchmark (40 cases + ground truth + metadata)
python generate_synthetic.py

# 3 · Run full evaluation
python run_baseline.py          # → results/metrics.csv, results/predictions.csv
python run_ablation.py          # → results/ablation.csv (module-level study)

# 4 · Interactive diagnostic demo
python test_demo.py

# 5 · Visual overlays & metrics summary
python src/visualize.py         # → results/visualizations/overlay_*.png
python src/evaluate.py          # console metrics summary
```

### Sample evaluation output

```text
 num_samples  mean_error_px  median_error_px  max_error_px  pass_rate_5px  pass_rate_1px  subpixel_rate_0.5px  mean_runtime_ms
          40       0.076946         0.063359      0.247015            1.0            1.0                  1.0         244.80
```

---

## 📐 Conventions & Assumptions

- **Coordinate convention:** origin `(0, 0)` at top-left; `x` increases right, `y` increases downward. Output is the target centre in search-image pixels.
- **Multiple matches:** resolved by the spec rule — the candidate closest to the search-image centre wins (implemented as a physics-informed prior: stage drift is small).
- **Scale:** nominal 10:1; robustness window 9:1–11:1 handled by multi-scale search.
- **Rotation:** ±2° handled by conditional rotation refinement.
- **Images:** 1000×1000 grayscale for both reference (100× view) and search (10× view).
- **Data:** synthetic only, seeded (`seed 42`), no proprietary fab data; per-pair metadata (scale, rotation, noise, gamma) stored in `data/synthetic/ground_truth.csv`.

---

## 🗂️ Repository Structure

```text
drift-sense/
├── generate_synthetic.py      # seeded benchmark generator (easy + hard periodic)
├── run_baseline.py            # full evaluation harness (metrics + runtime)
├── run_ablation.py            # module-level ablation study
├── test_demo.py               # interactive diagnostic demo
├── create_presentation.py     # regenerates the .pptx deck
├── references.md              # literature justification (SEM noise, DRAM structures, stage drift)
├── src/
│   ├── preprocess.py          # CLAHE · denoise · Sobel · Z-score
│   ├── matcher.py             # multi-scale NCC engine + rotation refine + fallback
│   ├── peaks.py               # NMS peaks · periodicity · tie-break · sub-pixel
│   ├── evaluate.py            # metrics reporter
│   └── visualize.py           # GT-vs-prediction overlay generator
├── docs/                      # algorithm notes · architecture · demo script · HTML deck
├── data/synthetic/            # 1000×1000 images + ground_truth.csv (manifest)
└── results/                   # metrics · predictions · ablation · visualizations
```

---

## 🧠 Key Design Decisions

| Decision | Why |
|---|---|
| **NCC over raw matching** | Normalized cross-correlation is invariant to linear intensity shifts (`I → aI + b`), preserving accuracy under illumination changes. |
| **Physics-informed tie-break** | Drift is small, so the true site lies near the ROI center. When multiple matches are found, the center-closest wins — exactly per the spec. |
| **Periodicity-aware re-verification** | Repeating grids trigger high-resolution re-score of candidates before tie-breaking. |
| **Zero-shot geometric fallback** | ORB + RANSAC homography engages only when NCC confidence < 0.40 — no weights, no training. |
| **Seeded benchmark** | `seed(42)` makes every result in this repo bit-for-bit reproducible. |

---

## 🤝 Team

| | |
|---|---|
| **Krish Deshpande** — *Algorithm Lead* | Preprocessing, multi-scale matcher, NMS peaks, periodicity tie-breaking, sub-pixel fit, ORB+RANSAC fallback, technical documentation |
| **Shubh Garg** — *Data & Evaluation Lead* | Synthetic ground-truth pipeline, metrics & ablation harness, visualization overlays, repository & presentation |

---

## 📚 References

- Bushnell, M. L. *Semiconductor Physical Design* — justifies the periodic DRAM-style lattice model.
- Goldstein, J. I. et al. *Scanning Electron Microscopy and X-Ray Microanalysis* — justifies shot noise, charging and degradation models.
- Slocum, A. H. *Precision Machine Design* — justifies the bounded stage-drift prior behind the tie-breaking rule.

---

<div align="center">

**Drift-Sense · SEMICON India Hackathon 2026 · Applied Materials Problem Statement**

</div>