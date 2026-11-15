"""
📸 Hujjat skaneri: telefonda olingan suratdan "skan" qilingan ko'rinishdagi sahifa yasaydi.

1. Suratdagi qog'ozning 4 burchagini topadi (kontur bo'yicha).
2. Qog'ozni to'g'ri to'rtburchak qilib tekislaydi (perspektivani to'g'rilash).
3. Rejimga qarab: oq-qora (matn hujjatlari uchun) yoki rangli (yorug'lik tekislangan) qiladi.
Qog'oz topilmasa — butun surat ishlatiladi (faqat tozalanadi).
"""
import cv2
import numpy as np
from PIL import Image, ImageOps

DETECT_SIZE = 1000          # burchaklarni qidirish uchun kichraytirilgan o'lcham
MAX_OUTPUT_SIDE = 2200      # natija sahifaning eng uzun tomoni (~A4 200 dpi)
MIN_PAGE_AREA = 0.2         # qog'oz suratning kamida 20% ini egallashi kerak


def _load(path: str) -> np.ndarray:
    """EXIF bo'yicha buradi (telefon suratlari), HEIC ham o'qiladi (pillow-heif)."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Burchaklarni tartiblaydi: chap-yuqori, o'ng-yuqori, o'ng-past, chap-past."""
    pts = pts.reshape(4, 2).astype("float32")
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def find_page(image: np.ndarray) -> np.ndarray | None:
    """Qog'ozning 4 burchagini (asl o'lchamda) qaytaradi; topilmasa None."""
    h, w = image.shape[:2]
    scale = DETECT_SIZE / max(h, w)
    small = cv2.resize(image, (int(w * scale), int(h * scale))) if scale < 1 else image.copy()
    scale = min(scale, 1.0)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    # Matn harflari kontur bo'lib qolmasligi uchun yopish (morphological close)
    closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    edges = cv2.Canny(closed, 30, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = MIN_PAGE_AREA * small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(contour) < min_area:
            break
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return _order_corners(approx) / scale
    return None


def _warp(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = corners
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(corners, target)
    return cv2.warpPerspective(image, matrix, (width, height))


def _limit_size(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    scale = MAX_OUTPUT_SIDE / max(h, w)
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else image


def _enhance_bw(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Soya va notekis yorug'likni olib tashlash: fonni bo'lib tashlaymiz
    background = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), 31)
    normalized = cv2.divide(gray, background, scale=255)
    normalized = cv2.GaussianBlur(normalized, (3, 3), 0)
    block = max(15, (min(gray.shape) // 40) | 1)
    return cv2.adaptiveThreshold(normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 15)


def _enhance_color(image: np.ndarray) -> np.ndarray:
    result = np.empty_like(image)
    for channel in range(3):
        plane = image[:, :, channel]
        background = cv2.medianBlur(cv2.dilate(plane, np.ones((7, 7), np.uint8)), 31)
        result[:, :, channel] = cv2.divide(plane, background, scale=255)
    return result


def scan_image(src_path: str, dst_path: str, mode: str = "bw") -> bool:
    """
    Suratni skanerlaydi va JPG/PNG qilib saqlaydi.
    Qog'oz burchaklari topilgan bo'lsa True, topilmagan bo'lsa (butun surat ishlatildi) False.
    """
    image = _load(src_path)
    corners = find_page(image)
    page = _warp(image, corners) if corners is not None else image
    if corners is not None:  # qog'oz chetidagi stol foni qoldiqlarini qirqamiz
        h, w = page.shape[:2]
        mh, mw = max(2, h // 100), max(2, w // 100)
        page = page[mh:h - mh, mw:w - mw]
    page = _limit_size(page)
    result = _enhance_bw(page) if mode == "bw" else _enhance_color(page)
    if result.ndim == 2:
        Image.fromarray(result).save(dst_path, optimize=True)
    else:
        Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB)).save(dst_path, quality=85, optimize=True)
    return corners is not None
