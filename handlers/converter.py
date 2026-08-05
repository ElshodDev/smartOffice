from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from services.transliterator import to_cyrillic, to_latin
from deep_translator import GoogleTranslator
import logging

router = Router()

class ConverterStates(StatesGroup):
    waiting_for_text = State()

def get_direction_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🇺🇿 Lotin ➡️ Kirill", callback_data="conv_lat_cyr"),
            InlineKeyboardButton(text="🇺🇿 Kirill ➡️ Lotin", callback_data="conv_cyr_lat")
        ],
        [
            InlineKeyboardButton(text="🇬🇧 EN ➡️ 🇺🇿 UZ", callback_data="trans_en_uz"),
            InlineKeyboardButton(text="🇺🇿 UZ ➡️ 🇬🇧 EN", callback_data="trans_uz_en")
        ],
        [
            InlineKeyboardButton(text="🇷🇺 RU ➡️ 🇺🇿 UZ", callback_data="trans_ru_uz"),
            InlineKeyboardButton(text="🇺🇿 UZ ➡️ 🇷🇺 RU", callback_data="trans_uz_ru")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Tugma matni yangilandi
@router.message(F.text == "🔄 Tarjimon / Alifbo")
async def start_converter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Qaysi yo'nalishda tarjima qilishni xohlaysiz?",
        reply_markup=get_direction_menu()
    )

# Eski tugmani bosib qo'yganlar uchun ham ishlayverishi uchun
@router.message(F.text == "🔄 Lotin <-> Kirill")
async def start_converter_legacy(message: Message, state: FSMContext):
    await start_converter(message, state)

@router.callback_query(F.data.startswith("conv_") | F.data.startswith("trans_"))
async def process_direction(callback: CallbackQuery, state: FSMContext):
    direction = callback.data
    await state.update_data(direction=direction)
    
    # Text mapping
    directions_text = {
        "conv_lat_cyr": "Lotin ➡️ Kirill",
        "conv_cyr_lat": "Kirill ➡️ Lotin",
        "trans_en_uz": "Inglizcha ➡️ O'zbekcha",
        "trans_uz_en": "O'zbekcha ➡️ Inglizcha",
        "trans_ru_uz": "Ruscha ➡️ O'zbekcha",
        "trans_uz_ru": "O'zbekcha ➡️ Ruscha",
    }
    
    dir_text = directions_text.get(direction, "Noma'lum")
    await callback.message.edit_text(
        f"Siz **{dir_text}** yo'nalishini tanladingiz.\n\nEndi tarjima qilish uchun matnni yuboring:",
        parse_mode="Markdown"
    )
    
    await state.set_state(ConverterStates.waiting_for_text)

@router.message(ConverterStates.waiting_for_text, F.text)
async def convert_text(message: Message, state: FSMContext):
    data = await state.get_data()
    direction = data.get('direction')
    
    if not direction:
        await message.answer("Iltimos, avval yo'nalishni tanlang!")
        await state.clear()
        return
        
    text = message.text
    msg = await message.answer("Kuting... ⏳")
    
    try:
        if direction.startswith("conv_"):
            if direction == "conv_lat_cyr":
                result = to_cyrillic(text)
            else:
                result = to_latin(text)
        elif direction.startswith("trans_"):
            # trans_en_uz
            _, src, dest = direction.split('_')
            translator = GoogleTranslator(source=src, target=dest)
            result = translator.translate(text)
            
        await msg.edit_text(
            f"**Natija:**\n\n{result}\n\n_Yana matn yuborishingiz yoki bosh menyudan boshqa bo'limni tanlashingiz mumkin._", 
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Tarjimada xatolik: {e}")
        await msg.edit_text("Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring yoki boshqa matn yuboring.")
