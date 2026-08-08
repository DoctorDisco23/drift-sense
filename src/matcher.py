import cv2


def load_gray(path):
    """
    Load image in grayscale.
    """
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")

    return img


def resize_reference(reference, scale):
    """
    Resize reference image by given scale.
    If scale = 0.1, image becomes 10x smaller.
    """
    h, w = reference.shape[:2]

    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    small_reference = cv2.resize(
        reference,
        (new_w, new_h),
        interpolation=cv2.INTER_AREA
    )

    return small_reference


def locate_reference(search_path, reference_path, scale=0.1):
    """
    Finds the location of the reference image inside the search image.

    Returns:
        center_x, center_y, confidence_score
    """
    search = load_gray(search_path)
    reference = load_gray(reference_path)

    small_reference = resize_reference(reference, scale)

    # Safety check: template must be smaller than search image
    if (
        small_reference.shape[0] > search.shape[0]
        or small_reference.shape[1] > search.shape[1]
    ):
        h, w = search.shape[:2]
        return w // 2, h // 2, 0.0

    # Template matching
    result = cv2.matchTemplate(
        search,
        small_reference,
        cv2.TM_CCOEFF_NORMED
    )

    _, score, _, max_loc = cv2.minMaxLoc(result)

    template_h, template_w = small_reference.shape[:2]

    # max_loc is top-left corner, so convert to center
    center_x = max_loc[0] + template_w // 2
    center_y = max_loc[1] + template_h // 2

    return int(center_x), int(center_y), float(score)