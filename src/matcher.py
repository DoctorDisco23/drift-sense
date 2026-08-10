"""
Core Template Matching & Multi-Scale AI Matcher Engine
Module for Drift-Sense (Member B Deliverable).

Combines preprocessing, multi-scale correlation, NMS peak detection,
periodicity tie-breaking, sub-pixel accuracy, and AI feature matching fallback.
"""

import cv2
import numpy as np
from src.preprocess import preprocess_image, load_gray
from src.peaks import (
    find_peaks,
    detect_periodicity,
    break_ties_by_center_distance,
    refine_subpixel
)


def resize_reference(reference, scale):
    """
    Resizes reference image by given scale factor.
    If scale = 0.1, image width and height become 10x smaller.
    """
    h, w = reference.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    small_reference = cv2.resize(reference, (new_w, new_h), interpolation=interp)
    return small_reference


def ai_feature_matching_fallback(search, reference, scale):
    """
    AI Feature-Matching Fallback (ORB + RANSAC).
    Used as an advanced enhancement when template matching correlation confidence is low
    or under heavy non-linear distortion.

    Args:
        search: Preprocessed search image array.
        reference: Preprocessed reference image array.
        scale: Base scale factor.

    Returns:
        (center_x, center_y, confidence)
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

    inlier_count = int(np.sum(inliers))
    confidence = float(inlier_count) / float(len(good_matches))

    ref_h, ref_w = small_ref.shape[:2]
    ref_center = np.float32([[[ref_w / 2.0, ref_h / 2.0]]])
    transformed_center = cv2.perspectiveTransform(ref_center, M)

    center_x = float(transformed_center[0][0][0])
    center_y = float(transformed_center[0][0][1])

    return center_x, center_y, confidence


def locate_reference(search_path, reference_path, scale=0.1,
                     multi_scale=True, use_preprocessing=True,
                     refine_subpixel_flag=True, return_details=False):
    """
    Main algorithmic entry point to locate reference image inside search image.

    Args:
        search_path: File path or numpy array of search image.
        reference_path: File path or numpy array of reference image.
        scale: Estimated scale factor (e.g. 0.1 for 10x smaller reference patch).
        multi_scale: Enable multi-scale correlation search.
        use_preprocessing: Enable adaptive preprocessing.
        refine_subpixel_flag: Enable sub-pixel quadratic surface interpolation.
        return_details: If True, return (x, y, score, details_dict).

    Returns:
        (center_x, center_y, confidence_score) or extended 4-tuple if return_details=True.
    """
    search_raw = load_gray(search_path)
    reference_raw = load_gray(reference_path)

    search_h, search_w = search_raw.shape[:2]
    ref_orig_h, ref_orig_w = reference_raw.shape[:2]

    # Preprocessing pipeline
    if use_preprocessing:
        search = preprocess_image(search_raw, use_clahe=True, use_denoise=True)
        reference = preprocess_image(reference_raw, use_clahe=True, use_denoise=True)
    else:
        search, reference = search_raw, reference_raw

    # Multi-scale scale factors
    if multi_scale:
        scale_factors = [scale * factor for factor in [0.95, 1.0, 1.05]]
    else:
        scale_factors = [scale]

    all_candidates = []

    for s in scale_factors:
        small_ref = resize_reference(reference, s)
        tmpl_h, tmpl_w = small_ref.shape[:2]

        if tmpl_h > search_h or tmpl_w > search_w or tmpl_h == 0 or tmpl_w == 0:
            continue

        corr_map = cv2.matchTemplate(search, small_ref, cv2.TM_CCOEFF_NORMED)
        peaks = find_peaks(corr_map, min_distance=max(5, tmpl_w // 4), threshold_rel=0.5, top_k=20)

        for p in peaks:
            p['scale'] = s
            p['tmpl_w'] = tmpl_w
            p['tmpl_h'] = tmpl_h
            p['corr_map'] = corr_map
            all_candidates.append(p)

    if not all_candidates:
        if return_details:
            return search_w // 2, search_h // 2, 0.0, {}
        return search_w // 2, search_h // 2, 0.0

    # Sort candidates by correlation score
    all_candidates.sort(key=lambda item: item['score'], reverse=True)

    # Detect periodicity
    best_map = all_candidates[0]['corr_map']
    best_peaks = find_peaks(best_map, min_distance=10, threshold_rel=0.5, top_k=20)
    periodicity_info = detect_periodicity(best_map, best_peaks, score_margin=0.05)

    # Filter candidates belonging to top scale
    top_scale = all_candidates[0]['scale']
    scale_candidates = [c for c in all_candidates if abs(c['scale'] - top_scale) < 1e-4]

    # Re-verify top candidates at high resolution against reference_raw
    if len(scale_candidates) > 1 and periodicity_info['is_periodic']:
        ref_float = reference_raw.astype(np.float32)
        for cand in scale_candidates[:15]:
            x, y = cand['top_left_x'], cand['top_left_y']
            tmpl_h, tmpl_w = cand['tmpl_h'], cand['tmpl_w']
            if y + tmpl_h <= search_h and x + tmpl_w <= search_w:
                search_crop = search_raw[y:y+tmpl_h, x:x+tmpl_w]
                # Scale search crop up to original reference dimension
                crop_upscaled = cv2.resize(search_crop, (ref_orig_w, ref_orig_h), interpolation=cv2.INTER_CUBIC).astype(np.float32)
                diff = np.mean(np.abs(crop_upscaled - ref_float))
                cand['highres_diff'] = float(diff)
            else:
                cand['highres_diff'] = 1e6

        # Sort candidate peaks by high-res difference (lowest difference first)
        scale_candidates.sort(key=lambda item: item.get('highres_diff', 1e6))

    selected = break_ties_by_center_distance(
        scale_candidates,
        search_shape=(search_h, search_w),
        template_shape=(all_candidates[0]['tmpl_h'], all_candidates[0]['tmpl_w']),
        score_weight=0.8,
        dist_weight=0.2,
        max_rel_diff=0.05
    )

    pred_x = selected['center_x']
    pred_y = selected['center_y']
    score = selected['score']

    # Sub-pixel refinement
    dx, dy = 0.0, 0.0
    if refine_subpixel_flag and 'corr_map' in selected:
        dx, dy = refine_subpixel(
            selected['corr_map'],
            selected['top_left_x'],
            selected['top_left_y']
        )
        pred_x += dx
        pred_y += dy

    # AI Feature Matching Fallback
    used_ai_fallback = False
    if score < 0.4:
        ai_x, ai_y, ai_conf = ai_feature_matching_fallback(search_raw, reference_raw, scale)
        if ai_conf > 0.2:
            pred_x, pred_y, score = ai_x, ai_y, ai_conf
            used_ai_fallback = True

    details = {
        'selected_scale': selected.get('scale', scale),
        'subpixel_dx': dx,
        'subpixel_dy': dy,
        'periodicity': periodicity_info,
        'fitness_score': selected.get('fitness_score', score),
        'used_ai_fallback': used_ai_fallback
    }

    if return_details:
        return pred_x, pred_y, float(score), details

    return pred_x, pred_y, float(score)