"""
📷 Obyektivka uchun 3×4 sm fotosurat: istalgan rasmdan yuzni topib, standart kadrga keltiradi.

Kadr: 30×40 mm (3:4), 300 dpi → 354×472 piksel.
Yuz gorizontal markazda; bosh (tepadan iyakkacha) kadr balandligining ~58% ini egallaydi;
boshning tepasida ~9% bo'sh joy qoladi (hujjat suratlaridagi odatiy joylashuv).
Yuz topilmasa — rasm markazidan (yuqoriroq qismidan) 3:4 nisbatda qirqiladi.
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageOps

PHOTO_MM = (30, 40)
OUTPUT_PX = (354, 472)          # 30×40 mm, 300 dpi
HEAD_SHARE = 0.58               # bosh balandligi / kadr balandligi
TOP_MARGIN = 0.09               # bosh tepasidagi bo'sh joy / kadr balandligi
DETECT_MAX_SIDE = 1200

_cascade = None


def _detector():
    global _cascade
    if _cascade is None:
        path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        _cascade = cv2.CascadeClassifier(path)
    return _cascade


def _detect(rgb: np.ndarray, max_side: int, min_share: float):
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else rgb
    # Mahalliy kontrast (CLAHE): katta bir xil fon yuz qismining yorqinligini buzmaydi
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY))
    min_side = max(24, int(min(small.shape[:2]) * min_share))
    faces = _detector().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(min_side, min_side))
    if len(faces) == 0:
        return None
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    return int(x / scale), int(y / scale), int(fw / scale), int(fh / scale)


def find_face(rgb: np.ndarray) -> tuple[int, int, int, int] | None:
    """Eng katta yuz (x, y, w, h) asl o'lchamda; topilmasa None.
    Avval tez (kichraytirilgan) qidiradi; topilmasa — kattaroq o'lchamda, kichik yuzlar uchun."""
    return _detect(rgb, DETECT_MAX_SIDE, 0.06) or _detect(rgb, DETECT_MAX_SIDE * 2, 0.02)


def crop_box(image_w: int, image_h: int, face: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
    """3:4 kadr (left, top, right, bottom). Yuz chetda bo'lsa, kadr rasmdan tashqariga chiqishi mumkin."""
    if face is None:
        crop_w = min(image_w, image_h * 3 / 4)
        crop_h = crop_w * 4 / 3
        left = (image_w - crop_w) / 2
        top = max(0.0, (image_h - crop_h) * 0.25)   # odatda yuz rasmning yuqori qismida
    else:
        fx, fy, fw, fh = face
        head_h = fh * 1.6                           # detektor oralig'i: qosh–iyak; soch/bosh tepasigacha qo'shamiz
        crop_h = head_h / HEAD_SHARE
        crop_w = crop_h * 3 / 4
        crown_y = fy - fh * 0.45
        top = crown_y - crop_h * TOP_MARGIN
        left = fx + fw / 2 - crop_w / 2
    return int(round(left)), int(round(top)), int(round(left + crop_w)), int(round(top + crop_h))


def make_photo(src_path: str, dst_path: str) -> bool:
    """3×4 rasm yasaydi (JPEG). Yuz topilgan bo'lsa True."""
    with Image.open(src_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        face = find_face(np.array(im))
        left, top, right, bottom = crop_box(im.width, im.height, face)
        # Kadr rasmdan tashqariga chiqsa — oq fon bilan to'ldiramiz
        canvas = Image.new("RGB", (right - left, bottom - top), "white")
        canvas.paste(im, (-left, -top))
        canvas = canvas.resize(OUTPUT_PX, Image.LANCZOS)
        canvas.save(dst_path, "JPEG", quality=92, dpi=(300, 300))
    return face is not None
