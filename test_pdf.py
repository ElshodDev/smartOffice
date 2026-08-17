import io
from services.pdf_report import generate_pdf
data = {
    'full_name': 'Eshmatov Ali Toshmatovich',
    'birth_date': '1965-yil',
    'birth_place': 'Toshkent sh., Yunusobod t.',
    'nationality': 'Ozbek',
    'party': 'yoq',
    'education': 'Oliy',
    'graduated': 'Toshkent sh., Yunusobod t.',
    'specialty': 'Pensioner'
}
try:
    pdf_bytes = generate_pdf(data)
    print("Success, len:", len(pdf_bytes))
except Exception as e:
    import traceback
    traceback.print_exc()
