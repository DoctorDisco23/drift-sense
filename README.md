<div align="center">

# 🎯 Drift-Sense

**AI-Powered Navigation-Error Recovery & Sub-Pixel Alignment for Wafer Inspection Tools**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-1.26%2B-01324D?logo=numpy&logoColor=white)
![Mean Error](https://img.shields.io/badge/Mean%20Error-0.031%20px-brightgreen)
![Hit Rate](https://img.shields.io/badge/Hit%20Rate%20%401px-100%25-brightgreen)
![Training](https://img.shields.io/badge/Training%20Latency-0%20ms-orange)

*A deterministic, zero-shot computer-vision engine that re-locates microscopic wafer sites with sub-pixel precision — even inside highly periodic semiconductor layouts.*

</div>

---

## 📌 The Problem

Modern wafer inspection tools must return to **the exact same microscopic site** on a die thousands of times per day. In practice, thermal expansion, vibration, and mechanical slack cause **navigation drift**, and the tool may land several pixels off-target.

Because semiconductor layouts (DRAM arrays, FinFET gates) are **highly periodic**, a wrong location looks nearly identical to the right one — classical template matching breaks down exactly where precision matters most.

> **Task:** Given a *Reference Image* and a larger *Search Image* in which the reference pattern appears (shrunk ~10×), return the center coordinates `(x, y)` of the matching region. If multiple matching regions are found, return the one closest to the center of the Search Image.

---

## 💡 The Solution

**Drift-Sense** is a coarse-to-fine, fully deterministic pipeline combining classical signal processing with advanced computer vision — **no training data, no GPU, 0 ms training latency**.

```text
 Search S (512×512)          Reference R (320×320)
        │                            │
        └──────────┬─────────────────┘
                   ▼
      ┌─────────────────────────────┐
      │ 1 · ADAPTIVE PREPROCESSING  │  CLAHE · Gaussian denoise · Z-score
      └─────────────────────────────┘
                   ▼
      ┌─────────────────────────────┐
      │ 2 · MULTI-SCALE NCC SEARCH  │  s ∈ {0.95, 1.00, 1.05} · s_base
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
      │     + AI FALLBACK           │  ORB keypoints + RANSAC homography
      └─────────────────────────────┘
                   ▼
        Output: (x, y) + confidence
```

---

## 📊 Benchmark Results

Evaluated on a **seeded, reproducible synthetic benchmark** (`np.random.seed(42)`) — 40 test cases: 30 unique-texture (*easy*) + 10 highly periodic grids (*hard*) with realistic sub-cell stage drift.

| Metric | Result |
|---|---|
| **Mean localization error** | **0.031 px** |
| Median error | 0.030 px |
| Max error | 0.073 px |
| **Hit rate @ 1 px** | **100 %** |
| Catastrophic failures (> 10 px) | **0 / 40** |
| Mean match confidence | 0.852 |
| Training latency | 0 ms |

### 🔬 Ablation Study

| Configuration | Mean error (px) |
|---|---|
| **Full pipeline** | **0.031** |
| − Multi-scale search | 0.031 |
| − Preprocessing * | 0.010 |
| − Sub-pixel refinement * | 0.000 |

\* On mathematically perfect synthetic grids, raw integer matching is exact. The preprocessing and sub-pixel modules are engineered for **real-world optical noise, illumination shifts, and analog blur**, which destroy raw template matching.

---

## 🚀 Quickstart

```bash
# 1 · Clone & install
git clone https://github.com/DoctorDisco23/drift-sense.git
cd drift-sense
pip install -r requirements.txt
pip install python-pptx        # optional — regenerates the presentation deck

# 2 · Generate the reproducible benchmark (40 cases + ground truth)
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

### Sample diagnostic output

```text
==========================================
 TESTING DRIFT-SENSE MATCHER (Sample #36)
 Difficulty: HARD  (periodic grid)
==========================================
 True Center Coordinate : (432.00, 112.00)
 Pred Center Coordinate : (431.9930, 111.9910)
 Sub-Pixel Offsets (dx,dy): (-0.0070, -0.0090)
 Position Error         : 0.0115 pixels
 Match Confidence Score : 0.8548
 Periodicity Detected   : True
==========================================
```

---

## 🗂️ Repository Structure

```text
drift-sense/
├── generate_synthetic.py      # seeded benchmark generator (easy + hard periodic)
├── run_baseline.py            # full evaluation harness
├── run_ablation.py            # module-level ablation study
├── test_demo.py               # interactive diagnostic demo
├── create_presentation.py     # regenerates the .pptx deck
├── src/
│   ├── preprocess.py          # CLAHE · denoise · Sobel · Z-score
│   ├── matcher.py             # multi-scale NCC engine + AI fallback
│   ├── peaks.py               # NMS peaks · periodicity · tie-break · sub-pixel
│   ├── evaluate.py            # metrics reporter
│   └── visualize.py           # GT-vs-prediction overlay generator
├── docs/                      # algorithm notes · architecture · demo script · HTML deck
├── data/synthetic/            # images + ground_truth.csv
└── results/                   # metrics · predictions · ablation · visualizations
```

---

## 🧠 Key Design Decisions

| Decision | Why |
|---|---|
| **NCC over raw matching** | Normalized cross-correlation is invariant to linear intensity shifts (`I → aI + b`), preserving accuracy under illumination changes. |
| **Physics-informed tie-break** | Stage drift is small, so the true site lies near the ROI center. When multiple matches are found, candidates score `0.8·score + 0.2·(1 − dist)` and the center-closest wins — exactly per the spec. |
| **Periodicity-aware re-verification** | Repeating grids trigger a high-resolution re-score of candidates before tie-breaking. |
| **Zero-shot AI fallback** | ORB + RANSAC homography engages only when NCC confidence < 0.40 — no training, no weights. |
| **Seeded benchmark** | `seed(42)` makes every result in this repo bit-for-bit reproducible. |

---

## 🤝 Team

| | |
|---|---|
| **Krish Deshpande** — *Algorithm Lead* | Preprocessing, multi-scale matcher, NMS peaks, periodicity tie-breaking, sub-pixel fit, ORB+RANSAC fallback, technical documentation |
| **Shubh Garg** — *Data & Evaluation Lead* | Synthetic ground-truth pipeline, metrics & ablation harness, visualization overlays, repository & presentation |

---

## 📚 References

- Bradski, G. (2000). *The OpenCV Library*. Dr. Dobb's Journal of Software Tools.
- Problem statement: **Applied Materials** — Navigation-Error Recovery for Wafer Inspection Tools (hackathon brief).

---

<div align="center">

**Drift-Sense · Semiconductor Tooling Hackathon 2026**

</div>