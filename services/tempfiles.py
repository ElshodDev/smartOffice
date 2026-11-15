"""
Har bir so'rov uchun alohida vaqtinchalik papka.

Avval natija fayllari hamma uchun bir xil nom bilan yozilardi (masalan temp/merged_result.pdf),
shuning uchun bir vaqtda ishlagan ikki foydalanuvchining fayllari aralashib ketardi.
Endi har bir ish o'zining noyob papkasida bajariladi va oxirida butunlay o'chiriladi.
"""
import os
import re
import shutil
import time
import uuid

TEMP_ROOT = "temp"
STALE_AFTER_SECONDS = 2 * 60 * 60   # foydalanuvchi yarim yo'lda tashlab ketgan ishlar
_JOB_DIR_RE = re.compile(r"^[a-z0-9]+_[0-9a-f]{12}$")
_last_cleanup = 0.0


def cleanup_stale_jobs(now: float | None = None) -> int:
    """2 soatdan eski ish papkalarini o'chiradi (bot o'chib qolgan yoki ish tashlab ketilgan)."""
    now = now or time.time()
    removed = 0
    try:
        entries = os.listdir(TEMP_ROOT)
    except FileNotFoundError:
        return 0
    for name in entries:
        path = os.path.join(TEMP_ROOT, name)
        if _JOB_DIR_RE.match(name) and os.path.isdir(path):
            try:
                if now - os.path.getmtime(path) > STALE_AFTER_SECONDS:
                    shutil.rmtree(path, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
    return removed


def new_job_dir(prefix: str = "job") -> str:
    global _last_cleanup
    if time.time() - _last_cleanup > 600:  # ko'pi bilan 10 daqiqada bir marta
        _last_cleanup = time.time()
        cleanup_stale_jobs()
    path = os.path.join(TEMP_ROOT, f"{prefix}_{uuid.uuid4().hex[:12]}")
    os.makedirs(path, exist_ok=True)
    return path


def remove(*paths: str | None) -> None:
    for path in paths:
        if not path:
            continue
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def safe_filename(name: str, default: str = "fayl", max_len: int = 60) -> str:
    """Fayl nomidan / \\ : * ? " < > | kabi belgilarni olib tashlaydi."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", str(name)).strip(" .-")
    return (name[:max_len].strip(" .-") or default)
