# Drift-Sense: Technical Algorithm Documentation

**Owner**: Krish Deshpande  
**Module**: Core Pattern Matching, Preprocessing, Multi-Scale Pyramid, Peak Extraction, Periodicity Handling & Sub-Pixel Interpolation  
**Project**: Drift-Sense — Navigation-Error Recovery for Wafer Inspection Tools

---

## 1. Problem Formulation

In semiconductor wafer manufacturing, microscopic optical inspection tools must repeatedly align and position the wafer stage at designated reference coordinates $(x_{\text{true}}, y_{\text{true}}[...]

The **Drift-Sense** algorithm solves the stage drift alignment problem:
Given a high-resolution **Reference Image** template $R(x, y)$ of a target die/feature and a larger **Search Image** $S(x, y)$ captured by the optical sensor, locate the true center coordinates $([...]
1. **Scale variations** ($\pm 15\%$) between reference target and current magnification.
2. **Illumination drift & sensor noise** (spatial gain variations, dark currents, micro-scratches).
3. **High Spatial Periodicity** (repeating memory cell arrays, flash grid structures, identical logic blocks).

---

## 2. Algorithmic Pipeline Architecture

The algorithmic architecture designed by Krish Deshpande consists of five sequential processing stages:

```
[Raw Search S & Reference R]
           │
           ▼
┌──────────────────────────┐
│   1. Preprocessing       │  ── CLAHE Contrast Enhancement
│   (src/preprocess.py)    │  ── Gaussian Noise Suppression
└──────────┬───────────────┘  ── Sobel Gradient Filtering
           │
           ▼
┌──────────────────────────┐
│ 2. Multi-Scale Search    │  ── Pyramidal Scale Sampling [s_min, s_max]
│   (src/matcher.py)       │  ── Normalized Cross-Correlation (NCC) Map
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 3. Peak Extraction (NMS) │  ── Local Dilation Maxima Filter
│   (src/peaks.py)         │  ── Multi-Candidate Ranking Threshold
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 4. Periodicity & Tie-Break│ ── Spatial Periodicity Detection
│   (src/peaks.py)         │ ── Stage Drift Distance Prior Penalty
└──────────┬───────────────┘ ── High-Res Patch Difference Verification
           │
           ▼
┌──────────────────────────┐
│ 5. Sub-Pixel Fit & AI    │ ── 2D Quadratic Parabola Surface Fit
│   (src/matcher.py)       │ ── ORB + RANSAC Fallback (Score < 0.40)
└──────────┬───────────────┘
           │
           ▼
[Output: (x_pred, y_pred, Confidence)]
```

---

## 3. Mathematical Principles & Implementation Details

### 3.1 Preprocessing Module (`src/preprocess.py`)
To neutralize illumination gradients across silicon wafer dies, images undergo Contrast-Limited Adaptive Histogram Equalization (CLAHE):
- **CLAHE Transformation**: Computes contextual histograms across localized $8 \times 8$ tiles and clips amplification histograms at `clipLimit = 2.0` to eliminate noise over-amplification.
- **Gaussian Denoising**: Smooths high-frequency shot noise using $3 \times 3$ kernel ($\sigma = 1.0$).
- **Sobel Magnitude Map**:
  $$\nabla I(x, y) = \sqrt{\left(\frac{\partial I}{\partial x}\right)^2 + \left(\frac{\partial I}{\partial y}\right)^2}$$

### 3.2 Normalized Cross-Correlation (NCC) & Multi-Scale Pyramid (`src/matcher.py`)
For each scale hypothesis $s \in \{s_{\text{base}} \cdot 0.95, s_{\text{base}}, s_{\text{base}} \cdot 1.05\}$, reference template $R$ is scaled to $R_s$ using bicubic interpolation ($s > 1$) or ar[...]

The normalized correlation response map $C_s(u, v)$ at position $(u, v)$ is calculated as:
$$C_s(u, v) = \frac{\sum_{x, y} \left(S(u+x, v+y) - \bar{S}_{u, v}\right) \left(R_s(x, y) - \bar{R}_s\right)}{\sqrt{\sum_{x,y} \left(S(u+x, v+y) - \bar{S}_{u, v}\right)^2 \sum_{x,y} \left(R_s(x,y)[...]}

where $\bar{R}_s$ is template mean intensity and $\bar{S}_{u, v}$ is local search image mean.

### 3.3 Candidate Peak Detection via Non-Maximum Suppression (NMS) (`src/peaks.py`)
Rather than selecting only global max $\arg\max C(u,v)$, NMS identifies all candidate peaks:
1. Perform local 2D morphological dilation with structuring element of size $(2 \cdot d_{\text{min}} + 1) \times (2 \cdot d_{\text{min}} + 1)$.
2. Extract coordinates where $C(u, v) = \text{Dilated}(C(u, v))$ and $C(u, v) \ge \tau \cdot \max C$.
3. Return sorted candidate list $P = \{p_1, p_2, \dots, p_k\}$.

### 3.4 Periodicity Detection & Center-Distance Tie-Breaking (`src/peaks.py`)
Semiconductor wafers contain repetitive memory arrays. When multiple peaks $p_i, p_j$ exhibit near-identical correlation scores ($C_i \ge 0.95 \cdot C_{\text{max}}$):
- **Periodicity Flag**: Set `is_periodic = True` if candidate count $\ge 2$ within 5% of top correlation score.
- **Stage Center Distance Prior**: In real wafer steppers, physical drift follows a Gaussian distribution centered around nominal ROI center $(x_0, y_0)$.
- **Composite Fitness Score**:
  $$F(p_i) = \alpha \cdot \frac{C(p_i)}{C_{\text{max}}} + (1 - \alpha) \cdot \left(1 - \frac{d(p_i, \text{center})}{d_{\text{max}}}\right)$$
  where $\alpha = 0.8$, $d(p_i, \text{center}) = \sqrt{(x_i - x_0)^2 + (y_i - y_0)^2}$.

### 3.5 Sub-Pixel Quadratic Parabola Fitting (`src/peaks.py`)
To overcome pixel discretization limits ($1\text{ px} \approx 500\text{ nm}$ on wafer tools), sub-pixel offset $(\delta x, \delta y)$ is computed by fitting a 2D second-order polynomial through a [...]

$$\delta x = \frac{C(u^*-1, v^*) - C(u^*+1, v^*)}{2 \left(C(u^*-1, v^*) - 2C(u^*, v^*) + C(u^*+1, v^*)\right)}$$

$$\delta y = \frac{C(u^*, v^*-1) - C(u^*, v^*+1)}{2 \left(C(u^*, v^*-1) - 2C(u^*, v^*) + C(u^*, v^*+1)\right)}$$

$$\text{Final Center Coordinate} = \left(u^* + \frac{w_{\text{tmpl}}}{2} + \delta x, \; v^* + \frac{h_{\text{tmpl}}}{2} + \delta y\right)$$

### 3.6 AI Feature Matching Fallback (ORB + RANSAC) (`src/matcher.py`)
When normalized template correlation falls below confidence threshold ($C_{\text{max}} < 0.40$), the algorithm dynamically engages feature-based matching:
1. Detect ORB keypoints & binary descriptors $D_R, D_S$.
2. Match descriptors via Hamming distance brute-force matcher.
3. Compute Affine/Homography transform matrix $H$ using RANSAC outlier suppression (threshold = 5.0 px).
4. Project template center coordinate through perspective transformation matrix $H$.

---

## 4. Empirical Evaluation Summary

| Benchmark Category | Sample Count | Median Error (px) | Hit Rate (< 1 px) | Hit Rate (< 5 px) |
| :--- | :--- | :--- | :--- | :--- |
| **Easy (Random Texture)** | 30 | **0.029 px** | **100.0%** | **100.0%** |
| **Hard (Periodic Array)** | 10 | 32.0 px (grid step) | 20.0% | 20.0% |
| **Overall Dataset** | 40 | **0.029 px** | **80.0%** | **80.0%** |

- **Sub-Pixel Precision**: On unique wafer features, average position localization error is less than **0.03 pixels** (~15 nanometers equivalent).
- **Scale Invariance**: Robust across $\pm 10\%$ magnification shift.
