import re

LATIN_TO_CYRILLIC = {
    'sh': 'ш', 'Sh': 'Ш', 'SH': 'Ш',
    'ch': 'ч', 'Ch': 'Ч', 'CH': 'Ч',
    'ya': 'я', 'Ya': 'Я', 'YA': 'Я',
    'yu': 'ю', 'Yu': 'Ю', 'YU': 'Ю',
    'yo': 'ё', 'Yo': 'Ё', 'YO': 'Ё',
    "o'": 'ў', "O'": 'Ў', "o‘": 'ў', "O‘": 'Ў',
    "g'": 'ғ', "G'": 'Ғ', "g‘": 'ғ', "G‘": 'Ғ',
    'ts': 'ц', 'Ts': 'Ц', 'TS': 'Ц',
    'a': 'а', 'A': 'А',
    'b': 'б', 'B': 'Б',
    'd': 'д', 'D': 'Д',
    'e': 'е', 'E': 'Е',
    'f': 'ф', 'F': 'Ф',
    'g': 'г', 'G': 'Г',
    'h': 'ҳ', 'H': 'Ҳ',
    'i': 'и', 'I': 'И',
    'j': 'ж', 'J': 'Ж',
    'k': 'к', 'K': 'К',
    'l': 'л', 'L': 'Л',
    'm': 'м', 'M': 'М',
    'n': 'н', 'N': 'Н',
    'o': 'о', 'O': 'О',
    'p': 'п', 'P': 'П',
    'q': 'қ', 'Q': 'Қ',
    'r': 'р', 'R': 'Р',
    's': 'с', 'S': 'С',
    't': 'т', 'T': 'Т',
    'u': 'у', 'U': 'У',
    'v': 'в', 'V': 'В',
    'x': 'х', 'X': 'Х',
    'y': 'й', 'Y': 'Й',
    'z': 'з', 'Z': 'З'
}

CYRILLIC_TO_LATIN = {
    'Ш': 'Sh', 'ш': 'sh',
    'Ч': 'Ch', 'ч': 'ch',
    'Я': 'Ya', 'я': 'ya',
    'Ю': 'Yu', 'ю': 'yu',
    'Ё': 'Yo', 'ё': 'yo',
    'Ў': "O'", 'ў': "o'",
    'Ғ': "G'", 'ғ': "g'",
    'Ц': 'Ts', 'ц': 'ts',
    'А': 'A', 'а': 'a',
    'Б': 'B', 'б': 'b',
    'Д': 'D', 'д': 'd',
    'Е': 'E', 'е': 'e',
    'Э': 'E', 'э': 'e',
    'Ф': 'F', 'ф': 'f',
    'Г': 'G', 'г': 'g',
    'Ҳ': 'H', 'ҳ': 'h',
    'И': 'I', 'и': 'i',
    'Ж': 'J', 'ж': 'j',
    'К': 'K', 'к': 'k',
    'Л': 'L', 'л': 'l',
    'М': 'M', 'м': 'm',
    'Н': 'N', 'н': 'n',
    'О': 'O', 'о': 'o',
    'П': 'P', 'п': 'p',
    'Қ': 'Q', 'қ': 'q',
    'Р': 'R', 'р': 'r',
    'С': 'S', 'с': 's',
    'Т': 'T', 'т': 't',
    'У': 'U', 'у': 'u',
    'В': 'V', 'в': 'v',
    'Х': 'X', 'х': 'x',
    'Й': 'Y', 'й': 'y',
    'З': 'Z', 'з': 'z',
    'Ъ': "'", 'ъ': "'"
}

def to_cyrillic(text: str) -> str:
    for k, v in LATIN_TO_CYRILLIC.items():
        text = text.replace(k, v)
    return text

def to_latin(text: str) -> str:
    for k, v in CYRILLIC_TO_LATIN.items():
        text = text.replace(k, v)
    return text


# ── Yangi lotin alifbosi (2021-yil loyihasi) ─────────────────────────────
# o' → ó, g' → ǵ, sh → ş, ch → ç, ng → ñ (faqat [ŋ] tovushi)

# O'zbek tilida o'/g' harflari turli tutuq belgilari bilan yoziladi: ' ‘ ’ ʻ ʼ `
_APOSTROPHES = "'‘’ʻʼ`"
_NEW_LATIN_RULES = [
    (re.compile(rf"([oO])[{_APOSTROPHES}]"), {"o": "ó", "O": "Ó"}),
    (re.compile(rf"([gG])[{_APOSTROPHES}]"), {"g": "ǵ", "G": "Ǵ"}),
    (re.compile(r"([sS])[hH]"), {"s": "ş", "S": "Ş"}),
    (re.compile(r"([cC])[hH]"), {"c": "ç", "C": "Ç"}),
]

# ng → ñ faqat bitta tovush [ŋ] bo'lganda: yangi, teng, rang, ming, -ning, -ngiz.
# Qo'shimcha chegarasidagi n + g ikki alohida tovush va o'zgarmaydi:
#   admin+ga, men+ga, qil-in+gan, yukla-n+gach  →  "ng" dan keyin unli a/o/u/e kelsa;
#   keyin+gi, bugun+gi, oldin+gi, ingliz        →  alohida ro'yxat.
_NG = re.compile(r"([nN])[gG](?![aeouAEOUóÓ])")
# [ŋ] dan keyin unli keladigan o'zaklar: kengash, kengaytirish
_NG_ROOT = re.compile(r"(?i)\b(ke)(n)g(a[şsy])")
_NG_SEPARATE = re.compile(r"(?i)\b(keyin|bugun|oldin|kun|tun|ichkarin)(gi)|\b(i)(ngliz)")


def _ng(text: str) -> str:
    protected: list[str] = []

    def keep(m: re.Match) -> str:
        protected.append(m.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = _NG_SEPARATE.sub(keep, text)
    text = _NG_ROOT.sub(lambda m: m.group(1) + ("ñ" if m.group(2) == "n" else "Ñ") + m.group(3), text)
    text = _NG.sub(lambda m: "ñ" if m.group(1) == "n" else "Ñ", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)


def to_new_latin(text: str) -> str:
    """Hozirgi lotin yozuvidagi matnni yangi lotin alifbosiga o'giradi."""
    for pattern, mapping in _NEW_LATIN_RULES:
        text = pattern.sub(lambda m: mapping[m.group(1)], text)
    return _ng(text)


def _iter_paragraphs(container):
    """Hujjat, jadval katakchalari ichidagi barcha paragraflarni qaytaradi."""
    for paragraph in container.paragraphs:
        yield paragraph
    for table in getattr(container, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_paragraphs(cell)


def transliterate_docx(src_path: str, dst_path: str, convert) -> int:
    """
    Word hujjatdagi matnni `convert` funksiyasi bilan o'giradi.
    Shrift, qalinlik, rang kabi formatlash saqlanadi (har bir "run" alohida o'giriladi).
    O'girilgan belgilar sonini qaytaradi.
    """
    from docx import Document

    document = Document(src_path)
    containers = [document]
    for section in document.sections:
        containers += [section.header, section.footer]

    changed = 0
    for container in containers:
        for paragraph in _iter_paragraphs(container):
            for run in paragraph.runs:
                if run.text:
                    new_text = convert(run.text)
                    if new_text != run.text:
                        run.text = new_text
                        changed += 1
    document.save(dst_path)
    return changed


def docx_has_text(path: str) -> bool:
    from docx import Document

    document = Document(path)
    return any(p.text.strip() for p in _iter_paragraphs(document))
