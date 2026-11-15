# Python 3.11 qulay va yengil bazaviy rasm (image)
FROM python:3.11-slim

# Tesseract OCR va PDF vositalari ishlashi uchun kerakli tizim paketlarini o'rnatish
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-rus \
    tesseract-ocr-uzb \
    poppler-utils \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Ishchi katalogni yaratish
WORKDIR /app

# Talab qilinadigan kutubxonalar ro'yxatini ko'chirish
COPY requirements.txt .

# Kutubxonalarni o'rnatish
RUN pip install --no-cache-dir -r requirements.txt

# pdf2docx opencv-python (GUI) ni talab qiladi, u esa libGL kutubxonasisiz ishlamaydi.
# Serverda grafik interfeys yo'q, shuning uchun uni headless versiyasiga almashtiramiz.
RUN pip uninstall -y opencv-python \
    && pip install --no-cache-dir opencv-python-headless==5.0.0.93

# Barcha kod va fayllarni konteynerga nusxalash
COPY . .

# Botni ishga tushirish komandasi
CMD ["python", "main.py"]
