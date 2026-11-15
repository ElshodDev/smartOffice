"""
Word (.docx) shablonlaridagi {{o'zgaruvchi}} larni topish va almashtirish.

Word matnni ko'pincha bir nechta "run"ga bo'lib saqlaydi (masalan "{{", "ism", "}}"),
shuning uchun almashtirish paragraf darajasida bajariladi: mos kelgan qism birinchi
run'ga yoziladi va formatlash (shrift, qalinlik) o'sha run'dan olinadi.
"""
import re

from docx import Document

# {{ ism }}, {{o'qituvchi}}, {{Tug'ilgan sana}}, {{F.I.Sh}} — qavslar ichidagi har qanday matn
PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def normalize_key(key: str) -> str:
    """Kalitlarni solishtirish uchun: kichik harf, ortiqcha bo'shliqsiz, apostroflar bir xil."""
    key = re.sub(r"\s+", " ", str(key)).strip().lower()
    return re.sub(r"[‘’ʻʼ`]", "'", key)


def _iter_paragraphs(container):
    for paragraph in container.paragraphs:
        yield paragraph
    for table in getattr(container, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_paragraphs(cell)


def iter_all_paragraphs(document):
    """Hujjat tanasi, jadvallar, sarlavha va pastki kolontitullardagi barcha paragraflar."""
    yield from _iter_paragraphs(document)
    for section in document.sections:
        for part in (section.header, section.footer, section.first_page_header, section.first_page_footer):
            yield from _iter_paragraphs(part)


def find_placeholders(document) -> list[str]:
    """Hujjatdagi o'zgaruvchilar nomlari (birinchi uchragan tartibda, takrorlarsiz)."""
    seen, result = set(), []
    for paragraph in iter_all_paragraphs(document):
        for match in PLACEHOLDER_RE.finditer(paragraph.text):
            name = match.group(1)
            key = normalize_key(name)
            if key not in seen:
                seen.add(key)
                result.append(name)
    return result


def _replace_in_paragraph(paragraph, values: dict[str, str]) -> int:
    runs = paragraph.runs
    if not runs:
        return 0
    texts = [run.text for run in runs]
    full = "".join(texts)
    matches = [m for m in PLACEHOLDER_RE.finditer(full) if normalize_key(m.group(1)) in values]
    if not matches:
        return 0

    # Har bir belgining qaysi run'ga tegishli ekanini aniqlaymiz
    owner = []
    for index, text in enumerate(texts):
        owner.extend([index] * len(text))

    new_texts = list(texts)
    # Oxiridan boshlab almashtiramiz, shunda oldingi pozitsiyalar o'zgarmaydi
    for match in reversed(matches):
        start, end = match.span()
        first, last = owner[start], owner[end - 1]
        run_start = sum(len(t) for t in texts[:first])
        run_end_start = sum(len(t) for t in texts[:last])
        value = values[normalize_key(match.group(1))]
        if first == last:
            text = new_texts[first]
            local_start = start - run_start
            new_texts[first] = text[:local_start] + value + text[local_start + (end - start):]
        else:
            new_texts[first] = new_texts[first][: start - run_start] + value
            for middle in range(first + 1, last):
                new_texts[middle] = ""
            new_texts[last] = new_texts[last][end - run_end_start:]

    for run, text in zip(runs, new_texts):
        if run.text != text:
            run.text = text
    return len(matches)


def fill_document(document, values: dict[str, str]) -> int:
    """{{kalit}} larni qiymatlar bilan almashtiradi. Almashtirishlar sonini qaytaradi."""
    normalized = {normalize_key(k): ("" if v is None else str(v)) for k, v in values.items()}
    return sum(_replace_in_paragraph(p, normalized) for p in iter_all_paragraphs(document))


def fill_template(src_path: str, dst_path: str, values: dict[str, str]) -> int:
    document = Document(src_path)
    count = fill_document(document, values)
    document.save(dst_path)
    return count


def template_placeholders(path: str) -> list[str]:
    return find_placeholders(Document(path))
