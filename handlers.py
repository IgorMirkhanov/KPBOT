import asyncio
import logging

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from document_generator import SERVICE_CATALOG, generate_pdf, sanitize_price_digits

router = Router()
logger = logging.getLogger(__name__)

DEADLINE_PROMPT = (
    "📅 Укажите срок действия КП или дату запуска проекта "
    "(например: 11.07.2026 или «30 дней с даты подписания»):"
)


class FormStates(StatesGroup):
    waiting_for_services = State()
    waiting_for_company_name = State()
    waiting_for_price_mode = State()
    waiting_for_custom_price = State()
    waiting_for_project_deadline = State()


def _services_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service_id, meta in SERVICE_CATALOG.items():
        prefix = "✅ " if service_id in selected else ""
        builder.button(
            text=f"{prefix}{meta['label']}",
            callback_data=f"svc:{service_id}",
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="📥 Сформировать КП",
            callback_data="cart:generate",
        )
    )
    return builder.as_markup()


def _price_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 Оставить стандартные",
            callback_data="price:standard",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💰 Изменить цену",
            callback_data="price:custom",
        )
    )
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(selected_services=[])
    await state.set_state(FormStates.waiting_for_services)
    await message.answer(
        "👋 <b>Конструктор КП MediaPeace</b>\n\n"
        "Выберите одну или несколько услуг (нажмите для выбора/снятия).\n"
        "Когда закончите — нажмите «📥 Сформировать КП».",
        reply_markup=_services_keyboard([]),
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Заполнение отменено. Нажмите /start для нового КП.")


@router.callback_query(
    StateFilter(FormStates.waiting_for_services),
    F.data.startswith("svc:"),
)
async def toggle_service(callback: types.CallbackQuery, state: FSMContext) -> None:
    service_id = callback.data.split(":", 1)[1]
    if service_id not in SERVICE_CATALOG:
        await callback.answer("Неизвестная услуга", show_alert=True)
        return

    data = await state.get_data()
    selected: list[str] = list(data.get("selected_services", []))

    if service_id in selected:
        selected.remove(service_id)
    else:
        selected.append(service_id)

    await state.update_data(selected_services=selected)
    await callback.message.edit_reply_markup(reply_markup=_services_keyboard(selected))
    await callback.answer()


@router.callback_query(
    StateFilter(FormStates.waiting_for_services),
    F.data == "cart:generate",
)
async def proceed_from_cart(callback: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected: list[str] = data.get("selected_services", [])

    if not selected:
        await callback.answer("Выберите хотя бы одну услугу", show_alert=True)
        return

    await state.set_state(FormStates.waiting_for_company_name)
    await callback.message.edit_text(
        f"✅ Выбрано услуг: <b>{len(selected)}</b>\n\n"
        "Введите название компании-получателя:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(
    StateFilter(FormStates.waiting_for_company_name),
    F.text,
    ~F.text.startswith("/"),
)
async def process_company_name(message: types.Message, state: FSMContext) -> None:
    company_name = message.text.strip()
    if len(company_name) < 2:
        await message.answer("⚠️ Название компании слишком короткое. Введите ещё раз:")
        return

    await state.update_data(company_name=company_name)
    await state.set_state(FormStates.waiting_for_price_mode)
    await message.answer(
        "💼 Как сформировать стоимость в таблице бюджета?",
        reply_markup=_price_mode_keyboard(),
    )


@router.message(StateFilter(FormStates.waiting_for_company_name))
async def process_company_name_invalid(message: types.Message) -> None:
    await message.answer("⚠️ Отправьте название компании текстом.")


@router.callback_query(
    StateFilter(FormStates.waiting_for_price_mode),
    F.data == "price:standard",
)
async def choose_standard_prices(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.update_data(use_base_prices=True, custom_price=None)
    await state.set_state(FormStates.waiting_for_project_deadline)
    await callback.message.edit_text(
        "✅ Будут использованы <b>стандартные цены</b> из прайс-листа.\n\n" + DEADLINE_PROMPT,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(
    StateFilter(FormStates.waiting_for_price_mode),
    F.data == "price:custom",
)
async def choose_custom_price(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.update_data(use_base_prices=False)
    await state.set_state(FormStates.waiting_for_custom_price)
    await callback.message.edit_text(
        "💰 Введите вашу кастомную стоимость за 1 месяц (только число, например: 850000):"
    )
    await callback.answer()


@router.callback_query(StateFilter(FormStates.waiting_for_price_mode))
async def choose_price_mode_invalid(callback: types.CallbackQuery) -> None:
    await callback.answer("Выберите один из вариантов цены", show_alert=True)


@router.message(
    StateFilter(FormStates.waiting_for_custom_price),
    F.text,
    ~F.text.startswith("/"),
)
async def process_custom_price(message: types.Message, state: FSMContext) -> None:
    raw_price = message.text.strip()
    try:
        custom_price = sanitize_price_digits(raw_price)
    except ValueError:
        await message.answer(
            "⚠️ Некорректная цена. Введите положительное число, например: 850000"
        )
        return

    await state.update_data(use_base_prices=False, custom_price=custom_price)
    await state.set_state(FormStates.waiting_for_project_deadline)
    await message.answer(DEADLINE_PROMPT)


@router.message(StateFilter(FormStates.waiting_for_custom_price))
async def process_custom_price_invalid(message: types.Message) -> None:
    await message.answer("⚠️ Отправьте стоимость числом.")


@router.message(
    StateFilter(FormStates.waiting_for_project_deadline),
    F.text,
    ~F.text.startswith("/"),
)
async def process_project_deadline(message: types.Message, state: FSMContext) -> None:
    project_deadline = message.text.strip()
    if len(project_deadline) < 2:
        await message.answer("⚠️ Введите срок или дату запуска проекта:")
        return

    await state.update_data(project_deadline=project_deadline)
    data = await state.get_data()

    await message.answer("⏳ Генерирую PDF-презентацию, подождите...")

    doc_data = {
        "company_name": data["company_name"],
        "project_deadline": project_deadline,
        "selected_services": data["selected_services"],
        "use_base_prices": data.get("use_base_prices", True),
        "custom_price": data.get("custom_price"),
    }

    try:
        pdf_path = await asyncio.to_thread(generate_pdf, doc_data)
        await message.answer_document(
            types.FSInputFile(pdf_path, filename="Коммерческое_Предложение.pdf"),
            caption="✅ Коммерческое предложение успешно сформировано!",
        )
    except Exception as exc:
        logger.exception("PDF generation failed")
        await message.answer(f"❌ Ошибка генерации: {exc}")
    finally:
        await state.clear()


@router.message(StateFilter(FormStates.waiting_for_project_deadline))
async def process_project_deadline_invalid(message: types.Message) -> None:
    await message.answer("⚠️ Отправьте срок или дату текстом.")
