"""
Core Template Matching & Multi-Scale Matcher Engine (Drift-Sense).
AM-Hackathon compliant: handles 9:1-11:1 scale, +/-2 deg rotation,
periodic ambiguity, sub-pixel refinement, geometric (ORB+RANSAC) fallback.
"""
import cv2
import numpy as np

from src.preprocess import preprocess_image, load_gray
from src.peaks import (
    find_peaks,
    detect_periodicity,
    break_ties_by_center_distance,
    refine_subpixel,
)

# Nominal 10:1; robustness window 9:1-11:1 -> scale in [0.09, 0.11]
SCALE_MULTIPLIERS = [0.90, 0.95, 1.00, 1.05, 1.10]
ROTATION_REFINE_ANGLES = [-2.0, -1.0, 1.0, 2.0]
ROTATION_TRIGGER_SCORE = 0.70


def resize_reference(reference, scale):
    """Resize reference by scale factor (0.1 => 10x smaller)."""
    h, w = reference.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(reference, (new_w, new_h), interpolation=interp)


def rotate_image(img, angle_deg):
    """Rotate template by angle_deg (0 => unchanged)."""
    if angle_deg == 0.0:
        return img
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def geometric_feature_fallback(search, reference, scale):
    """
    Zero-shot geometric fallback (ORB keypoints + RANSAC homography).
    Classical CV safety net for extreme distortion; no learned weights.
    Returns (center_x, center_y, confidence).
    """
    small_ref = resize_reference(reference, scale)
    orb = cv2.ORB_create(nfeatures=1000)
    kp1, des1 = orb.detectAndCompute(small_ref, None)
    kp2, des2 = orb.detectAndCompute(search, None)
    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        h, w = search.shape[:2]
        return w // 2, h // 2, 0.0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    if len(matches) < 4:
        h, w = search.shape[:2]
        return w // 2, h // 2, 0.0
    matches = sorted(matches, key=lambda x: x.distance)
    good_matches = matches[:min(50, len(matches))]
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    M, inliers = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if M is None or inliers is None:
        h, w = search.shape[:2]
        return w // 2, h // 2, 0.0
    confidence = float(np.sum(inliers)) / float(len(good_matches))
    ref_h, ref_w = small_ref.shape[:2]
    ref_center = np.float32([[[ref_w / 2.0, ref_h / 2.0]]])
    transformed = cv2.perspectiveTransform(ref_center, M)
    return float(transformed[0][0][0]), float(transformed[0][0][1]), confidence


def _collect_peaks(all_candidates, corr_map, s, ang, tmpl_h, tmpl_w):
    peaks = find_peaks(corr_map, min_distance=max(5, tmpl_w // 4),
                       threshold_rel=0.5, top_k=20)
    for p in peaks:
        p['scale'] = s
        p['angle'] = ang
        p['tmpl_w'] = tmpl_w
        p['tmpl_h'] = tmpl_h
        p['corr_map'] = corr_map
        all_candidates.append(p)
    return peaks


def locate_reference(search_path, reference_path, scale=0.1,
                     multi_scale=True, use_preprocessing=True,
                     refine_subpixel_flag=True, return_details=False):
    """
    Locate the reference pattern inside the search image.
    Returns (x, y, score) or (x, y, score, details) if return_details=True.
    """
    search_raw = load_gray(search_path)
    reference_raw = load_gray(reference_path)
    search_h, search_w = search_raw.shape[:2]
    ref_orig_h, ref_orig_w = reference_raw.shape[:2]

    if use_preprocessing:
        search = preprocess_image(search_raw, use_clahe=True, use_denoise=True)
        reference = preprocess_image(reference_raw, use_clahe=True, use_denoise=True)
    else:
        search, reference = search_raw, reference_raw

    if multi_scale:
        scale_factors = [scale * m for m in SCALE_MULTIPLIERS]
    else:
        scale_factors = [scale]

    all_candidates = []
    best_score = -1.0
    best_scale = scale_factors[len(scale_factors) // 2]

    # ---- Stage 1: multi-scale NCC at angle 0 ----
    for s in scale_factors:
        small_ref = resize_reference(reference, s)
        tmpl_h, tmpl_w = small_ref.shape[:2]
        if tmpl_h > search_h or tmpl_w > search_w or tmpl_h == 0 or tmpl_w == 0:
            continue
        corr_map = cv2.matchTemplate(search, small_ref, cv2.TM_CCOEFF_NORMED)
        peaks = _collect_peaks(all_candidates, corr_map, s, 0.0, tmpl_h, tmpl_w)
        if peaks and peaks[0]['score'] > best_score:
            best_score = peaks[0]['score']
            best_scale = s

    # ---- Stage 2: rotation refinement (1-2 deg) when confidence is low ----
    if multi_scale and best_score < ROTATION_TRIGGER_SCORE:
        for ang in ROTATION_REFINE_ANGLES:
            small_ref = rotate_image(resize_reference(reference, best_scale), ang)
            tmpl_h, tmpl_w = small_ref.shape[:2]
            if tmpl_h > search_h or tmpl_w > search_w:
                continue
            corr_map = cv2.matchTemplate(search, small_ref, cv2.TM_CCOEFF_NORMED)
            _collect_peaks(all_candidates, corr_map, best_scale, ang, tmpl_h, tmpl_w)

    if not all_candidates:
        if return_details:
            return search_w // 2, search_h // 2, 0.0, {}
        return search_w // 2, search_h // 2, 0.0

    all_candidates.sort(key=lambda item: item['score'], reverse=True)

    best_map = all_candidates[0]['corr_map']
    best_peaks = find_peaks(best_map, min_distance=10, threshold_rel=0.5, top_k=20)
    periodicity_info = detect_periodicity(best_map, best_peaks, score_margin=0.05)

    top_scale = all_candidates[0]['scale']
    top_angle = all_candidates[0].get('angle', 0.0)
    scale_candidates = [c for c in all_candidates
                        if abs(c['scale'] - top_scale) < 1e-4
                        and abs(c.get('angle', 0.0) - top_angle) < 1e-4]

    # ---- High-res re-verification for periodic ambiguity ----
    if len(scale_candidates) > 1 and periodicity_info['is_periodic']:
        ref_float = reference_raw.astype(np.float32)
        for cand in scale_candidates[:15]:
            x, y = cand['top_left_x'], cand['top_left_y']
            tmpl_h, tmpl_w = cand['tmpl_h'], cand['tmpl_w']
            if y + tmpl_h <= search_h and x + tmpl_w <= search_w:
                crop = search_raw[y:y + tmpl_h, x:x + tmpl_w]
                crop_up = cv2.resize(crop, (ref_orig_w, ref_orig_h),
                                     interpolation=cv2.INTER_CUBIC).astype(np.float32)
                cand['highres_diff'] = float(np.mean(np.abs(crop_up - ref_float)))
            else:
                cand['highres_diff'] = 1e6
        scale_candidates.sort(key=lambda item: item.get('highres_diff', 1e6))

    selected = break_ties_by_center_distance(
        scale_candidates,
        search_shape=(search_h, search_w),
        template_shape=(all_candidates[0]['tmpl_h'], all_candidates[0]['tmpl_w']),
        score_weight=0.8,
        dist_weight=0.2,
        max_rel_diff=0.05,
    )

    pred_x = selected['center_x']
    pred_y = selected['center_y']
    score = selected['score']

    dx, dy = 0.0, 0.0
    if refine_subpixel_flag and 'corr_map' in selected:
        dx, dy = refine_subpixel(selected['corr_map'],
                                 selected['top_left_x'], selected['top_left_y'])
        pred_x += dx
        pred_y += dy

    used_fallback = False
    if score < 0.4:
        ai_x, ai_y, ai_conf = geometric_feature_fallback(search_raw, reference_raw, scale)
        if ai_conf > 0.2:
            pred_x, pred_y, score = ai_x, ai_y, ai_conf
            used_fallback = True

    details = {
        'selected_scale': selected.get('scale', scale),
        'selected_angle': selected.get('angle', 0.0),
        'subpixel_dx': dx,
        'subpixel_dy': dy,
        'periodicity': periodicity_info,
        'fitness_score': selected.get('fitness_score', score),
        'used_ai_fallback': used_fallback,
    }
    if return_details:
        return pred_x, pred_y, float(score), details
    return pred_x, pred_y, float(score)