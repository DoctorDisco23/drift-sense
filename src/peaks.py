"""
Peak Detection, Periodicity Handling, Sub-Pixel Refinement & Center-Distance Tie-Breaking
Module for Drift-Sense (Member B Deliverable).

Handles candidate peak extraction from cross-correlation maps using NMS,
detects periodic grid structures, breaks ties in repeating patterns using physical
stage drift prior (center distance penalty), and performs sub-pixel quadratic fitting.
"""

import numpy as np
import cv2


def find_peaks(corr_map, min_distance=10, threshold_rel=0.7, top_k=10):
    """
    Extracts candidate local peak coordinates from a correlation response matrix
    using Non-Maximum Suppression (NMS).

    Args:
        corr_map: 2D numpy array representing template matching response map.
        min_distance: Minimum pixel distance between adjacent peak candidates.
        threshold_rel: Relative threshold factor (fraction of global maximum score).
        top_k: Maximum number of peak candidates to return.

    Returns:
        List of dicts: [{'top_left_x': x, 'top_left_y': y, 'score': score}, ...]
    """
    if corr_map is None or corr_map.size == 0:
        return []

    min_val, max_val, _, _ = cv2.minMaxLoc(corr_map)
    if max_val <= 0:
        return [{'top_left_x': 0, 'top_left_y': 0, 'score': 0.0}]

    abs_threshold = max_val * threshold_rel

    # Local dilation (NMS filter)
    kernel_size = 2 * min_distance + 1
    kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
    dilated = cv2.dilate(corr_map, kernel)

    # Find locations matching local maximum and exceeding relative threshold
    local_max_mask = (corr_map == dilated) & (corr_map >= abs_threshold)
    y_coords, x_coords = np.where(local_max_mask)

    candidates = []
    for y, x in zip(y_coords, x_coords):
        candidates.append({
            'top_left_x': int(x),
            'top_left_y': int(y),
            'score': float(corr_map[y, x])
        })

    # Sort candidates by score descending
    candidates.sort(key=lambda item: item['score'], reverse=True)

    if not candidates:
        _, max_val, _, max_loc = cv2.minMaxLoc(corr_map)
        candidates = [{
            'top_left_x': int(max_loc[0]),
            'top_left_y': int(max_loc[1]),
            'score': float(max_val)
        }]

    return candidates[:top_k]


def detect_periodicity(corr_map, candidate_peaks, score_margin=0.05):
    """
    Detects whether the correlation response exhibits spatial periodicity (repeating patterns),
    where multiple peaks have nearly identical high correlation scores.

    Args:
        corr_map: 2D correlation map.
        candidate_peaks: List of peak dicts from find_peaks.
        score_margin: Relative margin within highest score to consider competing peaks.

    Returns:
        Dict containing periodicity metrics:
        {'is_periodic': bool, 'competing_count': int, 'max_score': float}
    """
    if not candidate_peaks:
        return {'is_periodic': False, 'competing_count': 1, 'max_score': 0.0}

    max_score = candidate_peaks[0]['score']
    threshold = max_score * (1.0 - score_margin)

    competing = [p for p in candidate_peaks if p['score'] >= threshold]
    competing_count = len(competing)

    is_periodic = competing_count >= 2

    return {
        'is_periodic': is_periodic,
        'competing_count': competing_count,
        'max_score': max_score
    }


def break_ties_by_center_distance(candidates, search_shape, template_shape,
                                   score_weight=0.7, dist_weight=0.3,
                                   max_rel_diff=0.05):
    """
    Selects the optimal candidate coordinate among competing high-scoring peaks.

    In semiconductor wafer inspection, physical stage drift is typically centered
    around the nominal ROI. When periodic structures produce multiple peaks of near-equal
    correlation, this tie-breaking mechanism penalizes candidates further away from
    the search frame center.

    Args:
        candidates: List of peak candidate dicts.
        search_shape: (height, width) tuple of search image.
        template_shape: (height, width) tuple of resized template.
        score_weight: Weight given to correlation score (0.0 to 1.0).
        dist_weight: Weight given to distance proximity to image center.
        max_rel_diff: Maximum score tolerance from global peak to consider candidate for tie-breaking.

    Returns:
        Selected candidate dict with augmented keys:
        'center_x', 'center_y', 'dist_from_center', 'fitness_score'
    """
    if not candidates:
        h, w = search_shape[:2]
        return {
            'top_left_x': 0, 'top_left_y': 0,
            'center_x': w / 2.0, 'center_y': h / 2.0,
            'score': 0.0, 'dist_from_center': 0.0,
            'fitness_score': 0.0
        }

    search_h, search_w = search_shape[:2]
    tmpl_h, tmpl_w = template_shape[:2]

    frame_center_x = search_w / 2.0
    frame_center_y = search_h / 2.0

    max_dist = np.sqrt(frame_center_x**2 + frame_center_y**2) + 1e-5
    top_score = candidates[0]['score']
    cutoff_score = top_score * (1.0 - max_rel_diff)

    eligible = [c for c in candidates if c['score'] >= cutoff_score]
    if not eligible:
        eligible = candidates[:1]

    processed = []
    for cand in eligible:
        tl_x = cand['top_left_x']
        tl_y = cand['top_left_y']
        c_x = tl_x + tmpl_w / 2.0
        c_y = tl_y + tmpl_h / 2.0

        dist = np.sqrt((c_x - frame_center_x)**2 + (c_y - frame_center_y)**2)

        norm_score = cand['score'] / (top_score + 1e-8)
        norm_dist_penalty = dist / max_dist

        fitness = score_weight * norm_score + dist_weight * (1.0 - norm_dist_penalty)

        item = dict(cand)
        item['center_x'] = float(c_x)
        item['center_y'] = float(c_y)
        item['dist_from_center'] = float(dist)
        item['fitness_score'] = float(fitness)
        processed.append(item)

    # Sort by combined fitness score
    processed.sort(key=lambda item: item['fitness_score'], reverse=True)
    return processed[0]


def refine_subpixel(corr_map, top_left_x, top_left_y):
    """
    Performs 2D sub-pixel quadratic surface interpolation around the integer peak location
    to achieve sub-pixel position resolution.

    Args:
        corr_map: 2D correlation map numpy array.
        top_left_x: Integer x position of peak top-left corner.
        top_left_y: Integer y position of peak top-left corner.

    Returns:
        (dx, dy) sub-pixel offset floats in range [-0.5, +0.5].
    """
    h, w = corr_map.shape[:2]
    x, y = int(top_left_x), int(top_left_y)

    # Check boundaries for 3x3 neighborhood
    if x <= 0 or x >= w - 1 or y <= 0 or y >= h - 1:
        return 0.0, 0.0

    # 1D parabolic fit along X axis
    c = corr_map[y, x]
    left = corr_map[y, x - 1]
    right = corr_map[y, x + 1]

    denom_x = left - 2.0 * c + right
    if abs(denom_x) > 1e-6:
        dx = (left - right) / (2.0 * denom_x)
    else:
        dx = 0.0

    # 1D parabolic fit along Y axis
    up = corr_map[y - 1, x]
    down = corr_map[y + 1, x]

    denom_y = up - 2.0 * c + down
    if abs(denom_y) > 1e-6:
        dy = (up - down) / (2.0 * denom_y)
    else:
        dy = 0.0

    # Clip offsets to valid sub-pixel shift bounds [-0.5, 0.5]
    dx = float(np.clip(dx, -0.5, 0.5))
    dy = float(np.clip(dy, -0.5, 0.5))

    return dx, dy
