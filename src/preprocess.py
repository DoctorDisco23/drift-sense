"""
Preprocessing Module for Drift-Sense (Member B Deliverable)
Provides grayscale normalization, CLAHE contrast enhancement,
noise reduction, and edge extraction to handle illumination drift
and sensor noise on wafer inspection tools.
"""

import cv2
import numpy as np


def load_gray(image_input):
    """
    Loads an image in grayscale format.
    Accepts either a file path string or an existing numpy array.
    """
    if isinstance(image_input, str):
        img = cv2.imread(image_input, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(f"Could not read image from path: {image_input}")
        return img
    elif isinstance(image_input, np.ndarray):
        if len(image_input.shape) == 3 and image_input.shape[2] in (3, 4):
            return cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
        return image_input.copy()
    else:
        raise ValueError("image_input must be a file path string or numpy array.")


def normalize_minmax(img):
    """
    Normalizes image pixel values to [0, 255] uint8 range.
    """
    img_float = img.astype(np.float32)
    min_val, max_val = np.min(img_float), np.max(img_float)
    if max_val > min_val:
        norm = (img_float - min_val) / (max_val - min_val) * 255.0
    else:
        norm = np.zeros_like(img_float)
    return norm.astype(np.uint8)


def normalize_zscore(img):
    """
    Performs Z-score normalization (zero mean, unit standard deviation),
    returning float32 image.
    """
    img_float = img.astype(np.float32)
    mean, std = np.mean(img_float), np.std(img_float)
    if std > 1e-5:
        norm = (img_float - mean) / std
    else:
        norm = img_float - mean
    return norm


def apply_clahe(img, clip_limit=2.0, tile_grid_size=(8, 8)):
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE)
    to enhance local contrast on silicon wafer surface features.
    """
    if img.dtype != np.uint8:
        img = normalize_minmax(img)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(img)


def apply_denoising(img, method="gaussian", ksize=3, sigma=1.0):
    """
    Applies Gaussian or Median filtering to suppress high-frequency sensor noise.
    """
    if ksize % 2 == 0:
        ksize += 1
    if method == "gaussian":
        return cv2.GaussianBlur(img, (ksize, ksize), sigmaX=sigma)
    elif method == "median":
        return cv2.medianBlur(img, ksize)
    elif method == "bilateral":
        return cv2.bilateralFilter(img, d=ksize, sigmaColor=75, sigmaSpace=75)
    return img


def extract_edges(img, method="sobel"):
    """
    Extracts gradient/edge magnitude representation using Sobel or Laplacian filters.
    High contrast edge representations improve pattern matching in noisy or low-contrast conditions.
    """
    if img.dtype != np.uint8:
        img = normalize_minmax(img)

    if method == "sobel":
        grad_x = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)
        return normalize_minmax(magnitude)
    elif method == "laplacian":
        lap = cv2.Laplacian(img, cv2.CV_32F, ksize=3)
        return normalize_minmax(np.abs(lap))
    elif method == "canny":
        return cv2.Canny(img, threshold1=50, threshold2=150)
    return img


def preprocess_image(img, use_clahe=True, use_denoise=True, use_edges=False):
    """
    Complete flexible preprocessing pipeline for wafer inspection images.

    Args:
        img: Input image (path or numpy array)
        use_clahe: Enable CLAHE contrast equalization
        use_denoise: Enable Gaussian noise reduction
        use_edges: Convert image to edge magnitude representation

    Returns:
        Preprocessed uint8 numpy array
    """
    processed = load_gray(img)

    if use_denoise:
        processed = apply_denoising(processed, method="gaussian", ksize=3, sigma=1.0)

    if use_clahe:
        processed = apply_clahe(processed, clip_limit=2.0, tile_grid_size=(8, 8))

    if use_edges:
        processed = extract_edges(processed, method="sobel")

    return processed
