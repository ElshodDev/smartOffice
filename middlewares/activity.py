"""Faollikni yozish, admin bloklagan foydalanuvchilarni to'xtatish va bo'limlar hisobi."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID
from services import activity


def _is_admin(user_id: int) -> bool:
    return bool(ADMIN_ID) and str(user_id) == str(ADMIN_ID).lstrip("@")


class ActivityMiddleware(BaseMiddleware):
    """Outer middleware (message va callback_query): har bir foydalanuvchini bazada saqlaydi."""

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None or user.is_bot:
            return await handler(event, data)
        if activity.is_banned(user.id) and not _is_admin(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("⛔️ Siz botdan foydalanishdan cheklangansiz.", show_alert=True)
            elif isinstance(event, Message) and event.chat.type == "private":
                await event.answer("⛔️ Siz botdan foydalanishdan cheklangansiz. "
                                   "Xato deb hisoblasangiz, adminga murojaat qiling.")
            return None
        activity.record_user(user.id, user.full_name)
        return await handler(event, data)


class SectionMiddleware(BaseMiddleware):
    """Inner middleware: shu routerning handleri ishlaganda bo'lim ishlatilgan deb hisoblanadi."""

    def __init__(self, section: str, by_callback: dict[str, str] | None = None):
        self.section = section
        self.by_callback = by_callback or {}

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is not None and not user.is_bot:
            section = self.section
            if isinstance(event, CallbackQuery) and event.data:
                for prefix, sec in self.by_callback.items():
                    if event.data.startswith(prefix):
                        section = event.data.split(":", 1)[1] if sec == "*" else sec
                        break
            activity.record_section(user.id, section)
        return await handler(event, data)


# Router (modul nomi) → bo'lim
ROUTER_SECTIONS = {
    "excel_hub": "excel", "excel_tools": "excel", "excel_utils": "excel",
    "smart_splitter": "excel", "category_splitter": "excel",
    "search_data": "search",
    "pdf_tools": "pdf",
    "word_hub": "word", "word_tools": "word",
    "doc_generator": "docgen",
    "report_generator": "obyektivka",
    "form_filler": "blanka",
    "converter": "translate", "converter_hub": "format",
    "format_converter": "format",
    "ocr_tools": "ocr",
    "utility_tools": "qr",
    "reminders": "reminders",
    "ai_assistant": "ai",
}
# Bitta routerda bir nechta bo'lim bo'lsa — callback_data prefiksi bo'yicha aniqlanadi
CALLBACK_SECTIONS = {
    "format_converter": {"format_scan": "scan"},
    "converter_hub": {"conv_hub_translate": "translate"},
    "ai_assistant": {"go:": "*"},        # AI tavsiya qilgan bo'limni ochish — o'sha bo'lim hisoblanadi
}


def attach_section_tracking(module) -> None:
    name = module.__name__.rsplit(".", 1)[-1]
    section = ROUTER_SECTIONS.get(name)
    if not section:
        return
    mw = SectionMiddleware(section, CALLBACK_SECTIONS.get(name))
    module.router.message.middleware(mw)
    module.router.callback_query.middleware(mw)
