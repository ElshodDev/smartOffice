"""
To'lov tizimi: Click va Payme (TEST rejimi).

TEST rejimida haqiqiy pul olinmaydi.
Haqiqiy rejimga o'tish uchun .env faylidagi kalitlarni almashtiring.
"""
import logging
import hashlib
import json
import os
import base64

from aiohttp import web
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext

from services.subscription import (
    PLANS, activate_premium, is_premium,
    get_expiry, save_payment, confirm_payment
)

router = Router()

# ── Config ──
CLICK_SERVICE_ID  = os.getenv("CLICK_SERVICE_ID",  "0")       # test
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "0")       # test
CLICK_SECRET_KEY  = os.getenv("CLICK_SECRET_KEY",  "test")    # test
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "TEST_MERCHANT_ID")  # test
PAYME_KEY         = os.getenv("PAYME_KEY",         "test")    # test

# Render'dagi bot URL (webhook uchun)
BOT_BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://smartoffice-moms.onrender.com")

# Test rejimida ekanligini aniqlash
IS_TEST = CLICK_SERVICE_ID == "0" or PAYME_MERCHANT_ID == "TEST_MERCHANT_ID"


# ── Payme to'lov havolasi ──
def payme_url(user_id: int, amount_tiyin: int, plan: str) -> str:
    """Payme checkout havolasi (tiyin — 1 so'm = 100 tiyin)."""
    payload = f"m={PAYME_MERCHANT_ID};ac.user_id={user_id};ac.plan={plan};a={amount_tiyin}"
    encoded = base64.b64encode(payload.encode()).decode()
    if IS_TEST:
        return f"https://test.paycom.uz/{encoded}"
    return f"https://checkout.paycom.uz/{encoded}"


# ── Click to'lov havolasi ──
def click_url(user_id: int, amount_sum: int, plan: str) -> str:
    """Click to'lov havolasi."""
    merchant_trans = f"{user_id}_{plan}"
    if IS_TEST:
        # TEST: Click'da real test endpoint yo'q, shuning uchun matn ko'rsatamiz
        return f"https://my.click.uz/services/pay?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={amount_sum}&transaction_param={merchant_trans}"
    return f"https://my.click.uz/services/pay?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={amount_sum}&transaction_param={merchant_trans}"


# ── Paket tanlash klaviaturasi ──
def plans_kb() -> InlineKeyboardMarkup:
    buttons = []
    for key, plan in PLANS.items():
        price_som = plan["price"] // 100
        buttons.append([
            InlineKeyboardButton(
                text=f"{plan['name']} — {price_som:,} so'm".replace(",", " "),
                callback_data=f"buy_{key}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="pay_cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── go_premium callback (boshqa handlerlardan yo'naltirish) ──
@router.callback_query(F.data == "go_premium")
async def go_premium(callback: CallbackQuery):
    await callback.answer()
    test_note = "\n⚠️ <i>Hozir TEST rejimi — haqiqiy pul olinmaydi.</i>" if IS_TEST else ""
    await callback.message.edit_text(
        "💳 <b>Premium Paketlar</b>\n\n"
        "🤖 <b>AI Yordamchi</b> — cheksiz savol\n"
        "📋 <b>Hisobot Generator</b> — PDF + Excel\n"
        "💎 <b>Full Premium</b> — hamma narsa\n"
        f"{test_note}",
        parse_mode="HTML",
        reply_markup=plans_kb()
    )



# ── To'lov usuli tanlash ──
def provider_kb(plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Click orqali to'lash", callback_data=f"pay_click_{plan}"),
        ],
        [
            InlineKeyboardButton(text="🔵 Payme orqali to'lash", callback_data=f"pay_payme_{plan}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="premium_back"),
        ]
    ])


# ── "💳 Premium" tugmasi ──
@router.message(F.text == "💳 Premium")
async def show_premium(message: Message):
    expiry = await get_expiry(message.from_user.id)

    header = ""
    if expiry:
        header = f"✅ <b>Sizning premium obunangiz faol</b>\n📅 Tugash sanasi: <b>{expiry}</b>\n\n"
    else:
        header = "⭐ <b>Premium obuna</b>\n\nPremium xizmatlar orqali botdan to'liq foydalaning!\n\n"

    test_note = "\n⚠️ <i>Hozir TEST rejimi — haqiqiy pul olinmaydi.</i>" if IS_TEST else ""

    await message.answer(
        f"{header}"
        f"📦 <b>Paketlar:</b>\n\n"
        f"🤖 <b>AI Yordamchi</b> — 99 so'm/oy (cheksiz savol)\n"
        f"📋 <b>Hisobot Generator</b> — 49 so'm/oy\n"
        f"💎 <b>Full Premium</b> — 199 so'm/oy (hamma narsa)\n"
        f"{test_note}",
        parse_mode="HTML",
        reply_markup=plans_kb()
    )


# ── Paket tanlandi ──
@router.callback_query(F.data.startswith("buy_"))
async def choose_provider(callback: CallbackQuery):
    plan_key = callback.data.split("_", 1)[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Noma'lum paket!", show_alert=True)
        return

    price_som = plan["price"] // 100
    await callback.message.edit_text(
        f"✅ Tanlagan paket: <b>{plan['name']}</b>\n"
        f"💰 Narxi: <b>{price_som:,} so'm</b>\n\n"
        f"To'lov usulini tanlang:".replace(",", " "),
        parse_mode="HTML",
        reply_markup=provider_kb(plan_key)
    )
    await callback.answer()


# ── Click orqali to'lash ──
@router.callback_query(F.data.startswith("pay_click_"))
async def pay_click(callback: CallbackQuery):
    plan_key = callback.data.split("pay_click_")[1]
    plan = PLANS.get(plan_key)
    user_id = callback.from_user.id
    amount_som = plan["price"] // 100

    url = click_url(user_id, amount_som, plan_key)
    await save_payment(user_id, plan["price"], plan_key, "click", f"click_{user_id}_{plan_key}")

    test_note = "\n\n⚠️ <i>TEST rejimi: haqiqiy pul olinmaydi. Haqiqiy kalitlar kiritilganda ishlaydi.</i>" if IS_TEST else ""

    await callback.message.edit_text(
        f"🟢 <b>Click orqali to'lash</b>\n\n"
        f"Paket: <b>{plan['name']}</b>\n"
        f"Summa: <b>{amount_som:,} so'm</b>\n\n"
        f"👇 Quyidagi havolani bosing va to'lovni amalga oshiring:{test_note}".replace(",", " "),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Click orqali to'lash", url=url)],
            [InlineKeyboardButton(text="✅ To'lovni tasdiqlash (TEST)", callback_data=f"test_confirm_{plan_key}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="pay_cancel")],
        ])
    )
    await callback.answer()


# ── Payme orqali to'lash ──
@router.callback_query(F.data.startswith("pay_payme_"))
async def pay_payme(callback: CallbackQuery):
    plan_key = callback.data.split("pay_payme_")[1]
    plan = PLANS.get(plan_key)
    user_id = callback.from_user.id
    amount_tiyin = plan["price"]

    url = payme_url(user_id, amount_tiyin, plan_key)
    await save_payment(user_id, plan["price"], plan_key, "payme", f"payme_{user_id}_{plan_key}")

    test_note = "\n\n⚠️ <i>TEST rejimi: haqiqiy pul olinmaydi. Haqiqiy kalitlar kiritilganda ishlaydi.</i>" if IS_TEST else ""

    await callback.message.edit_text(
        f"🔵 <b>Payme orqali to'lash</b>\n\n"
        f"Paket: <b>{plan['name']}</b>\n"
        f"Summa: <b>{amount_tiyin // 100:,} so'm</b>\n\n"
        f"👇 Quyidagi havolani bosing va to'lovni amalga oshiring:{test_note}".replace(",", " "),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Payme orqali to'lash", url=url)],
            [InlineKeyboardButton(text="✅ To'lovni tasdiqlash (TEST)", callback_data=f"test_confirm_{plan_key}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="pay_cancel")],
        ])
    )
    await callback.answer()


# ── TEST: To'lovni qo'lda tasdiqlash (faqat test rejimda) ──
@router.callback_query(F.data.startswith("test_confirm_"))
async def test_confirm(callback: CallbackQuery, bot: Bot):
    if not IS_TEST:
        await callback.answer("Bu funksiya faqat test rejimida ishlaydi!", show_alert=True)
        return

    plan_key = callback.data.split("test_confirm_")[1]
    plan = PLANS.get(plan_key)
    user_id = callback.from_user.id

    await activate_premium(user_id, plan_key, plan["days"])
    expiry = await get_expiry(user_id)

    await callback.message.edit_text(
        f"🎉 <b>Premium faollashtirildi! (TEST rejimi)</b>\n\n"
        f"✅ Paket: <b>{plan['name']}</b>\n"
        f"📅 Tugash sanasi: <b>{expiry}</b>\n\n"
        f"<i>Haqiqiy to'lov tizimi ulanganida bu avtomatik bo'ladi.</i>",
        parse_mode="HTML"
    )
    await callback.answer("✅ Premium faollashtirildi!", show_alert=True)


# ── Orqaga ──
@router.callback_query(F.data == "premium_back")
async def premium_back(callback: CallbackQuery):
    await callback.answer()
    await show_premium.__wrapped__(callback.message) if hasattr(show_premium, '__wrapped__') else None
    await callback.message.edit_reply_markup(reply_markup=plans_kb())


# ── Bekor qilish ──
@router.callback_query(F.data == "pay_cancel")
async def pay_cancel(callback: CallbackQuery):
    await callback.answer("Bekor qilindi.")
    await callback.message.delete()


# ── Webhook handlers (aiohttp uchun) ──
async def click_webhook(request: web.Request) -> web.Response:
    """Click webhook endpointi."""
    try:
        data = await request.json()
        logging.info(f"Click webhook: {data}")
        # Haqiqiy Click HMAC tekshiruvi bu yerga qo'shiladi
        return web.json_response({"error": 0, "error_note": "Success"})
    except Exception as e:
        logging.error(f"Click webhook xato: {e}")
        return web.json_response({"error": -1, "error_note": str(e)})


async def payme_webhook(request: web.Request) -> web.Response:
    """Payme webhook endpointi (JSON-RPC)."""
    try:
        data = await request.json()
        logging.info(f"Payme webhook: {data}")
        method = data.get("method", "")
        # Haqiqiy Payme autentifikatsiyasi bu yerga qo'shiladi
        if method == "CheckPerformTransaction":
            return web.json_response({"result": {"allow": True}})
        elif method == "CreateTransaction":
            return web.json_response({"result": {"create_time": 0, "transaction": "1", "state": 1}})
        elif method == "PerformTransaction":
            return web.json_response({"result": {"perform_time": 0, "transaction": "1", "state": 2}})
        return web.json_response({"result": {}})
    except Exception as e:
        logging.error(f"Payme webhook xato: {e}")
        return web.json_response({"error": {"code": -32400, "message": str(e)}})
