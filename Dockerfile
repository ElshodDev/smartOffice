# Python 3.11 qulay va yengil bazaviy rasm (image)
FROM python:3.11-slim

# Tesseract OCR va PDF vositalari ishlashi uchun kerakli tizim paketlarini o'rnatish
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-rus \
    tesseract-ocr-uzb \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Ishchi katalogni yaratish
WORKDIR /app

# Talab qilinadigan kutubxonalar ro'yxatini ko'chirish
COPY requirements.txt .

# Kutubxonalarni o'rnatish
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kod va fayllarni konteynerga nusxalash
COPY . .

# Botni ishga tushirish komandasi
CMD ["python", "main.py"]
