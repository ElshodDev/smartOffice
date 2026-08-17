from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from keyboards.reply import get_main_menu, get_documents_menu, get_formats_menu, get_profile_menu

router = Router()

@router.message(F.text == "📁 Hujjatlar bilan ishlash")
async def nav_documents(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📁 <b>Hujjatlar bilan ishlash</b> bo'limi.\n\nKerakli amalni tanlang:",
        parse_mode="HTML",
        reply_markup=get_documents_menu()
    )

@router.message(F.text == "🔄 Formatlar va Tarjima")
async def nav_formats(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔄 <b>Formatlar va Tarjima</b> bo'limi.\n\nKerakli amalni tanlang:",
        parse_mode="HTML",
        reply_markup=get_formats_menu()
    )

@router.message(F.text == "👤 Profil va Sozlamalar")
async def nav_profile(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👤 <b>Profil va Sozlamalar</b> bo'limi.\n\nKerakli amalni tanlang:",
        parse_mode="HTML",
        reply_markup=get_profile_menu()
    )

@router.message(F.text == "🔙 Asosiy menyu")
async def nav_back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔙 Bosh menyuga qaytdingiz.",
        reply_markup=get_main_menu()
    )
