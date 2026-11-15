"""
✍️ Rasmiy hujjat yaratuvchi: ariza, tushuntirish xati, dalolatnoma, tavsifnoma, buyruq.

Har bir hujjat turi:
  - fields: foydalanuvchidan so'raladigan savollar (tartib bilan);
  - fallback_body(values): AI ishlamasa ishlatiladigan tayyor matn;
  - ai_task(values): Gemini'ga asosiy matnni yozish uchun topshiriq.
Rekvizitlar (kimga, kimdan, sana, imzo) har doim shablondan olinadi — AI faqat asosiy matnni yozadi.
"""
from dataclasses import dataclass, field
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from services.transliterator import to_cyrillic


@dataclass
class Field:
    key: str
    question: str
    example: str = ""
    optional: bool = False


@dataclass
class DocType:
    key: str
    title: str          # menyudagi nom
    heading: str        # hujjat sarlavhasi (ARIZA, BUYRUQ ...)
    fields: list[Field]
    layout: str = "letter"   # letter | act | order | reference
    fallback_body: callable = None
    ai_task: callable = None
    extra: dict = field(default_factory=dict)


def _v(values: dict, key: str, default: str = "") -> str:
    value = (values.get(key) or "").strip()
    return value if value and value.lower() not in ("-", "yo'q", "yoq") else default


def sentence(text: str) -> str:
    """Bosh harf bilan boshlab, nuqta bilan tugatadi."""
    text = (text or "").strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


# ── Umumiy maydonlar ────────────────────────────────────────────────────────
TO = Field("to", "Kimga? (tashkilot, rahbar lavozimi va F.I.Sh.)", "«Ziyo» MChJ direktori A. Aliyevga")
FROM = Field("from", "Kimdan? (lavozimingiz va F.I.Sh.)", "buxgalter Karimova Dilnoza Rustamovnadan")
SIGNER = Field("signer", "Imzo qo'yadigan shaxsning qisqa ismi", "D. Karimova")


DOC_TYPES: dict[str, DocType] = {}


def _register(doc: DocType):
    DOC_TYPES[doc.key] = doc


_register(DocType(
    key="ariza_ish", title="📄 Ariza — ishga qabul qilish", heading="ARIZA",
    fields=[TO, Field("from", "Kimdan? (F.I.Sh., yashash manzili)", "Toshkent sh., Yunusobod t. 4-mavze, 12-uy\nyashovchi Karimova Dilnoza Rustamovnadan"),
            Field("position", "Qaysi lavozimga?", "buxgalter"),
            Field("start", "Qaysi sanadan?", "01.12.2026"),
            Field("details", "Qo'shimcha ma'lumot (ma'lumoti, tajribasi)", "oliy ma'lumotli, 5 yillik tajriba", optional=True),
            SIGNER],
    fallback_body=lambda v: [
        f"Meni {_v(v, 'start', 'tegishli sanadan')} dan boshlab {_v(v, 'position', 'bo‘sh lavozim')} lavozimiga ishga qabul qilishingizni so'rayman."
        + (f" Ma'lumot uchun: {_v(v, 'details').rstrip('.')}." if _v(v, 'details') else ""),
    ],
    ai_task=lambda v: f"Ishga qabul qilish haqidagi ariza matni. Lavozim: {_v(v, 'position')}. Sana: {_v(v, 'start')}. "
                      f"Qo'shimcha: {_v(v, 'details', 'yo‘q')}.",
))

_register(DocType(
    key="ariza_tatil", title="🏖 Ariza — mehnat ta'tili", heading="ARIZA",
    fields=[TO, FROM,
            Field("period", "Ta'til muddati (qachondan qachongacha yoki necha kun)", "15.12.2026 dan 21 kalendar kun"),
            Field("kind", "Ta'til turi", "yillik asosiy mehnat ta'tili", optional=True),
            Field("reason", "Sabab yoki qo'shimcha (agar bo'lsa)", "oilaviy sharoitga ko'ra", optional=True),
            SIGNER],
    fallback_body=lambda v: [
        f"Menga {_v(v, 'period')} muddatga {_v(v, 'kind', 'navbatdagi yillik mehnat ta‘tili')} berishingizni so'rayman."
        + (f" Sabab: {_v(v, 'reason').rstrip('.')}." if _v(v, 'reason') else ""),
    ],
    ai_task=lambda v: f"Mehnat ta'tili berish haqidagi ariza matni. Muddat: {_v(v, 'period')}. "
                      f"Ta'til turi: {_v(v, 'kind', 'yillik asosiy mehnat ta‘tili')}. Sabab: {_v(v, 'reason', 'ko‘rsatilmagan')}.",
))

_register(DocType(
    key="ariza_boshash", title="🚪 Ariza — ishdan bo'shash", heading="ARIZA",
    fields=[TO, FROM,
            Field("date", "Qaysi sanadan bo'shamoqchisiz?", "31.12.2026"),
            Field("reason", "Sabab", "o'z xohishimga ko'ra", optional=True),
            SIGNER],
    fallback_body=lambda v: [
        f"Meni {_v(v, 'date', 'tegishli sanadan')} dan boshlab {_v(v, 'reason', 'o‘z xohishimga ko‘ra')} egallab turgan "
        "lavozimimdan ozod qilishingizni so'rayman.",
    ],
    ai_task=lambda v: f"Ishdan bo'shash haqidagi ariza matni. Sana: {_v(v, 'date')}. Sabab: {_v(v, 'reason', 'o‘z xohishiga ko‘ra')}.",
))

_register(DocType(
    key="ariza_boshqa", title="✏️ Ariza — boshqa mavzuda", heading="ARIZA",
    fields=[TO, FROM,
            Field("request", "Nimani so'rayapsiz? (qisqacha, o'z so'zingiz bilan)", "farzandim kasal bo'lgani uchun 3 kunga ish haqi saqlanmagan ta'til so'rayman"),
            SIGNER],
    fallback_body=lambda v: [sentence(_v(v, 'request')) + " Arizamni ko'rib chiqishingizni so'rayman."],
    ai_task=lambda v: f"Ariza matni. Arizachining so'rovi (o'z so'zlari bilan): {_v(v, 'request')}.",
))

_register(DocType(
    key="tushuntirish", title="📝 Tushuntirish xati", heading="TUSHUNTIRISH XATI",
    fields=[TO, FROM,
            Field("event", "Nima bo'ldi? (holat va sana)", "12.11.2026 kuni ishga 1 soat kechikib keldim"),
            Field("reason", "Sababi nima?", "jamoat transporti tirbandlik sababli kechikdi"),
            Field("promise", "Va'da / xulosa (ixtiyoriy)", "bunday holat takrorlanmasligiga harakat qilaman", optional=True),
            SIGNER],
    fallback_body=lambda v: [
        f"Shuni ma'lum qilamanki, {_v(v, 'event').rstrip('.')}. Buning sababi: {_v(v, 'reason').rstrip('.')}.",
        sentence(_v(v, 'promise', "Kelgusida bunday holat takrorlanmasligiga harakat qilaman")),
    ],
    ai_task=lambda v: f"Tushuntirish xati matni. Holat: {_v(v, 'event')}. Sabab: {_v(v, 'reason')}. "
                      f"Xulosa/va'da: {_v(v, 'promise', 'bunday holat takrorlanmasligi')}.",
))

_register(DocType(
    key="dalolatnoma", title="📋 Dalolatnoma", heading="DALOLATNOMA", layout="act",
    fields=[Field("org", "Tashkilot nomi", "«Ziyo» MChJ"),
            Field("place", "Tuzilgan joy (shahar)", "Toshkent sh."),
            Field("topic", "Dalolatnoma nima haqida?", "ish joyida bo'lmaganlik haqida"),
            Field("members", "Komissiya a'zolari (lavozimi va F.I.Sh., har biri yangi qatorda)", "Kadrlar bo'limi boshlig'i A. Aliyev\nBuxgalter D. Karimova"),
            Field("facts", "Nima aniqlandi? (qisqacha)", "operator S. Toirov 14.11.2026 kuni 09:00 dan 13:00 gacha sababsiz ish joyida bo'lmadi"),
            Field("conclusion", "Xulosa (ixtiyoriy)", "ushbu holat yuzasidan tushuntirish xati talab qilinsin", optional=True)],
    fallback_body=lambda v: [
        f"Biz, quyida imzo chekuvchilar, ushbu dalolatnomani shu haqda tuzdik: {_v(v, 'facts')}.",
        (f"Xulosa: {_v(v, 'conclusion')}." if _v(v, 'conclusion') else "Ushbu dalolatnoma ikki nusxada tuzildi."),
    ],
    ai_task=lambda v: f"Dalolatnoma matni ('Biz, quyida imzo chekuvchilar...' bilan boshlansin). Mavzu: {_v(v, 'topic')}. "
                      f"Aniqlangan holat: {_v(v, 'facts')}. Xulosa: {_v(v, 'conclusion', 'yo‘q')}.",
))

_register(DocType(
    key="tavsifnoma", title="🧾 Tavsifnoma (xarakteristika)", heading="TAVSIFNOMA", layout="reference",
    fields=[Field("person", "Kim haqida? (F.I.Sh., tug'ilgan yili)", "Karimova Dilnoza Rustamovna, 1995-yilda tug'ilgan"),
            Field("job", "Tashkilot va lavozimi, qachondan ishlaydi", "«Ziyo» MChJda 2020-yildan buxgalter"),
            Field("qualities", "Ish faoliyati va fazilatlari (qisqacha)", "mas'uliyatli, hisobotlarni o'z vaqtida topshiradi, jamoada hurmatga ega"),
            Field("purpose", "Qayerga taqdim etish uchun?", "bank kredit bo'limiga", optional=True),
            Field("signer_title", "Imzolovchi rahbar lavozimi", "Direktor"),
            SIGNER],
    fallback_body=lambda v: [
        sentence(_v(v, 'person')) + f" Hozirda {_v(v, 'job').rstrip('.')} lavozimida faoliyat yuritib kelmoqda.",
        f"Ish faoliyati davomida o'zini quyidagicha namoyon qildi: {_v(v, 'qualities').rstrip('.')}.",
        (f"Tavsifnoma {_v(v, 'purpose')} taqdim etish uchun berildi." if _v(v, 'purpose') else "Tavsifnoma talab qilingan joyga taqdim etish uchun berildi."),
    ],
    ai_task=lambda v: f"Xodimga tavsifnoma (xarakteristika) matni, 2-3 xatboshi, uchinchi shaxsda. Shaxs: {_v(v, 'person')}. "
                      f"Ish joyi va lavozimi: {_v(v, 'job')}. Fazilatlari: {_v(v, 'qualities')}. "
                      f"Oxirgi gap: tavsifnoma {_v(v, 'purpose', 'talab qilingan joyga')} taqdim etish uchun berildi.",
))

_register(DocType(
    key="buyruq", title="📑 Buyruq", heading="BUYRUQ", layout="order",
    fields=[Field("org", "Tashkilot nomi", "«Ziyo» MChJ"),
            Field("number", "Buyruq raqami", "45-K"),
            Field("place", "Shahar", "Toshkent sh."),
            Field("topic", "Buyruq mavzusi (... haqida)", "D. Karimovani ishga qabul qilish haqida"),
            Field("basis", "Asos (ixtiyoriy)", "D. Karimovaning 25.11.2026 dagi arizasi", optional=True),
            Field("items", "Nimalar buyuriladi? (har bir band yangi qatorda)", "Karimova Dilnoza 01.12.2026 dan buxgalter lavozimiga qabul qilinsin\nBuyruq ijrosi kadrlar bo'limiga yuklansin"),
            Field("signer_title", "Rahbar lavozimi", "Direktor"),
            Field("signer", "Rahbarning qisqa ismi", "A. Aliyev")],
    fallback_body=lambda v: [line.strip().rstrip(".;") for line in _v(v, "items").splitlines() if line.strip()],
    ai_task=lambda v: f"Buyruqning 'BUYURAMAN:' qismidagi bandlar. Mavzu: {_v(v, 'topic')}. Asos: {_v(v, 'basis', 'yo‘q')}. "
                      f"Foydalanuvchi yozgan bandlar: {_v(v, 'items')}. Har bir bandni alohida qatorda, raqamsiz, rasmiy buyruq "
                      "uslubida ('... qilinsin', '... yuklansin') yoz. Yangi band qo'shma.",
))


AI_RULES = (
    "Sen O'zbekiston davlat va tashkilot ish yuritish standartlarini yaxshi biladigan kotibsan. "
    "Quyidagi ma'lumotlar asosida hujjatning FAQAT asosiy matnini o'zbek tilida (lotin yozuvida), rasmiy uslubda yoz. "
    "Sarlavha, kimga/kimdan, sana va imzo YOZMA — ular alohida qo'yiladi. "
    "Berilgan faktlardan tashqari yangi ism, sana, raqam yoki fakt O'YLAB TOPMA; to'ldiriladigan joy ([...], ___) qoldirma. "
    "Qisqa va aniq bo'lsin (ko'pi bilan 120 so'z), markdown ishlatma, faqat oddiy matn.\n\n"
)


def ai_prompt(doc: DocType, values: dict) -> str:
    return AI_RULES + doc.ai_task(values)


def body_paragraphs(doc: DocType, values: dict, ai_text: str | None) -> list[str]:
    if ai_text:
        paragraphs = [p.strip() for p in ai_text.split("\n") if p.strip()]
    else:
        paragraphs = [p for p in doc.fallback_body(values) if p]
    return [p.replace("‘", "'") for p in paragraphs]


# ── Word hujjatni yasash ─────────────────────────────────────────────────────
def _para(document, text="", align=None, bold=False, size=14, indent=False, space_after=6, italic=False):
    p = document.add_paragraph()
    if align is not None:
        p.alignment = align
    fmt = p.paragraph_format
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = 1.15
    if indent:
        fmt.first_line_indent = Cm(1.25)
    run = p.add_run(text)
    run.bold, run.italic = bold, italic
    run.font.size = Pt(size)
    run.font.name = "Times New Roman"
    return p


def _signature_line(document, left: str, right: str):
    table = document.add_table(rows=1, cols=2)
    for cell, text, align in ((table.cell(0, 0), left, WD_ALIGN_PARAGRAPH.LEFT), (table.cell(0, 1), right, WD_ALIGN_PARAGRAPH.RIGHT)):
        p = cell.paragraphs[0]
        p.alignment = align
        run = p.add_run(text)
        run.font.size = Pt(14)
        run.font.name = "Times New Roman"


def build_docx(doc: DocType, values: dict, body: list[str], path: str, cyrillic: bool = False, today: date | None = None):
    t = to_cyrillic if cyrillic else (lambda s: s)
    today_str = (today or date.today()).strftime("%d.%m.%Y")
    document = Document()
    for section in document.sections:
        section.top_margin, section.bottom_margin = Cm(2), Cm(2)
        section.left_margin, section.right_margin = Cm(3), Cm(1.5)
    style = document.styles["Normal"]
    style.font.name, style.font.size = "Times New Roman", Pt(14)

    J, C, R, L = WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.RIGHT, WD_ALIGN_PARAGRAPH.LEFT

    if doc.layout == "letter":
        for line in [_v(values, "to")] + _v(values, "from").splitlines():
            if line.strip():
                p = _para(document, t(line.strip()), space_after=0)
                p.paragraph_format.left_indent = Cm(8.5)
        _para(document, space_after=18)
        _para(document, t(doc.heading), align=C, bold=True, space_after=12)
        for text in body:
            _para(document, t(text), align=J, indent=True)
        _para(document, space_after=18)
        _signature_line(document, today_str, t(f"__________ {_v(values, 'signer')}"))

    elif doc.layout == "act":
        _para(document, t(_v(values, "org")), align=C, bold=True, space_after=12)
        _para(document, t(doc.heading), align=C, bold=True, space_after=0)
        _para(document, t(_v(values, "topic")), align=C, space_after=12)
        _signature_line(document, today_str, t(_v(values, "place")))
        _para(document, space_after=6)
        members = [m.strip() for m in _v(values, "members").splitlines() if m.strip()]
        if members:
            _para(document, t("Komissiya a'zolari:"), bold=True, space_after=2)
            for i, member in enumerate(members, start=1):
                _para(document, t(f"{i}. {member}"), space_after=2)
            _para(document, space_after=6)
        for text in body:
            _para(document, t(text), align=J, indent=True)
        _para(document, space_after=18)
        for member in members:
            _signature_line(document, t(member), "__________")

    elif doc.layout == "reference":
        _para(document, t(doc.heading), align=C, bold=True, space_after=18)
        for text in body:
            _para(document, t(text), align=J, indent=True)
        _para(document, space_after=24)
        _signature_line(document, t(_v(values, "signer_title", "Rahbar")), t(f"__________ {_v(values, 'signer')}"))
        _para(document, today_str, align=L, space_after=0, size=12)
        _para(document, t("M.O'."), align=L, size=12)

    elif doc.layout == "order":
        _para(document, t(_v(values, "org")), align=C, bold=True, space_after=12)
        _para(document, t(doc.heading), align=C, bold=True, space_after=12)
        _signature_line(document, today_str, t(f"№ {_v(values, 'number')}"))
        _para(document, t(_v(values, "place")), align=C, space_after=12, size=12)
        _para(document, t(_v(values, "topic")), align=C, bold=True, space_after=12)
        if _v(values, "basis"):
            _para(document, t(f"Asos: {_v(values, 'basis')}."), align=J, indent=True)
        _para(document, t("BUYURAMAN:"), bold=True, space_after=6)
        for i, text in enumerate(body, start=1):
            text = text.lstrip("0123456789.) ").rstrip(";.")
            _para(document, t(f"{i}. {text}."), align=J, indent=True)
        _para(document, space_after=24)
        _signature_line(document, t(_v(values, "signer_title", "Rahbar")), t(f"__________ {_v(values, 'signer')}"))

    document.save(path)
