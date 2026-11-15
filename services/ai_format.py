"""
AI javobini Telegram'ga moslash:
  - Markdown (**qalin**, *kursiv*, `kod`, ```blok```, # sarlavha, - ro'yxat) → Telegram HTML;
  - uzun javobni 4000 belgidan oshmaydigan qismlarga bo'lish (teglar buzilmaydi);
  - AI qo'shgan [[bo'lim:KEY]] belgilarini ajratib olish (bot ularni tugmaga aylantiradi).
"""
import html
import re

TELEGRAM_LIMIT = 4000
SECTION_TAG = re.compile(r"\[\[\s*bo['‘’ʻ]?lim\s*:\s*([a-z_]+)\s*\]\]", re.IGNORECASE)


def extract_sections(text: str, allowed: set[str], limit: int = 2) -> tuple[str, list[str]]:
    keys = []
    for key in SECTION_TAG.findall(text):
        key = key.lower()
        if key in allowed and key not in keys:
            keys.append(key)
    cleaned = SECTION_TAG.sub("", text)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, keys[:limit]


def _inline(text: str) -> str:
    """Bitta qatordagi Markdown → HTML (matn avval escape qilinadi)."""
    parts = re.split(r"(`[^`\n]+`)", text)
    out = []
    for part in parts:
        if len(part) > 1 and part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{html.escape(part[1:-1], quote=False)}</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"<b>\1</b>", s)
        # *kursiv* — faqat so'z chegarasida (2*3*4 kabi ifodalar kursivga aylanmaydi)
        s = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"<i>\1</i>", s)
        out.append(s)
    return "".join(out)


def markdown_to_blocks(text: str) -> list[str]:
    """Javobni HTML bloklarga ajratadi; har bir blok o'z teglarini o'zi yopadi."""
    blocks, buffer = [], []
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0

    def flush():
        if buffer:
            blocks.append("\n".join(buffer))
            buffer.clear()

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(f"<pre>{html.escape(chr(10).join(code), quote=False)}</pre>")
            i += 1
            continue
        stripped = line.strip()
        if not stripped:
            flush()
        elif heading := re.match(r"^#{1,6}\s+(.*)", stripped):
            flush()
            buffer.append(f"<b>{_inline(heading.group(1).strip('# '))}</b>")
        elif bullet := re.match(r"^\s*[*\-+•]\s+(.*)", line):
            indent = "   " if len(line) - len(line.lstrip()) >= 2 else ""
            buffer.append(f"{indent}• {_inline(bullet.group(1))}")
        elif re.fullmatch(r"[-*_]{3,}", stripped):
            flush()
        else:
            buffer.append(_inline(line.rstrip()))
        i += 1
    flush()
    return [b for b in blocks if b.strip()]


def split_for_telegram(blocks: list[str], limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Bloklarni xabarlarga yig'adi. Juda uzun blok qatorlar bo'yicha bo'linadi."""
    messages, current = [], ""
    for block in blocks:
        pieces = [block]
        if len(block) > limit:
            if block.startswith("<pre>"):
                inner = html.unescape(block[5:-6])
                pieces = [f"<pre>{html.escape(inner[j:j + limit - 20], quote=False)}</pre>" for j in range(0, len(inner), limit - 20)]
            else:
                pieces, chunk = [], ""
                for line in block.split("\n"):
                    while len(line) > limit:     # bitta juda uzun qator
                        pieces.append(line[:limit])
                        line = line[limit:]
                    if len(chunk) + len(line) + 1 > limit:
                        pieces.append(chunk)
                        chunk = ""
                    chunk = f"{chunk}\n{line}" if chunk else line
                if chunk:
                    pieces.append(chunk)
        for piece in pieces:
            if current and len(current) + len(piece) + 2 > limit:
                messages.append(current)
                current = ""
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        messages.append(current)
    return messages or [""]


def to_telegram(text: str) -> list[str]:
    return split_for_telegram(markdown_to_blocks(text))


def strip_html(text: str) -> str:
    """HTML yuborib bo'lmasa (Telegram rad etsa) — oddiy matn varianti."""
    return html.unescape(re.sub(r"</?(b|i|code|pre)>", "", text))
