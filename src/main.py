from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

import requests
import asyncio
import logging

from config import BOT_TOKEN, USER_ID
from converter import docx_to_pdf, pdf_to_docx
from ai_handler import ask_openrouter

logging.basicConfig(level=logging.INFO)

# FSM
class AIStates(StatesGroup):
    waiting_for_prompt = State()

class WeatherStates(StatesGroup):
    waiting_for_city_text = State()
    waiting_for_location = State()

# Глобальные настройки
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Модели ИИ
AI_MODELS = {
    "DeepSeek R1": "deepseek/deepseek-r1-0528:free",
    "Mistral": "mistralai/mistral-small-3.2-24b-instruct:free",
    "Qwen3 Coder": "qwen/qwen3-coder:free"
}
# Модель по умолчанию 
DEFAULT_MODEL = "mistralai/mistral-small-3.2-24b-instruct:free"

PROMPTS = {
    "weather": (
        "Ты — дружелюбный метеоспециалист. Расскажи, какая сегодня погода в регионе '{city}'. "
        "Укажи примерную температуру, состояние неба, ветер, влажность. "
        "Если точные данные неизвестны — дай обоснованную оценку на основе типичной погоды для этого региона и времени года. "
        "Ответь кратко в 1–2 предложения, на русском. Не пиши 'Я не знаю'. "
        "Не используй '*' или эмодзи."
    ),
    "general": (
        "Отвечай на русском языке. Будь кратким и полезным. "
        "Если вопрос сложный — объясни просто. "
        "Не используй markdown, звёздочки или эмодзи, если не просят."
    )
}

# Главное меню
def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="Погода"),
        types.KeyboardButton(text="Конвертор")
    )
    builder.row(
        types.KeyboardButton(text="Модели ИИ")
    )
    return builder.as_markup(resize_keyboard=True)

# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Рад вас видеть, {message.from_user.first_name}!\n"
        "Чем могу вам помочь?",
        reply_markup=get_main_menu()
    )

# Обработчик Погоды
@dp.message(F.text == "Погода")
async def weather_start(message: types.Message, state: FSMContext):
    if message.from_user.id != USER_ID:
        return
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="Ввести город"),
        KeyboardButton(text="Определить по месту")
    )
    builder.row(
        KeyboardButton(text="Назад")
    )
    await message.answer(
        "Как узнать погоду?",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Обработчик ручного ввода
@dp.message(F.text == "Ввести город")
async def manual_city_input(message: types.Message, state: FSMContext):
    await message.answer("Напиши город или регион:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(WeatherStates.waiting_for_city_text)

@dp.message(WeatherStates.waiting_for_city_text)
async def get_ai_weather_by_city(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_menu())
        return

    if not message.text:
        await message.answer("Не удалось прочитать текст.")
        return

    city = message.text.strip()
    if len(city) < 2:
        await message.answer("Название слишком короткое.")
        return

    await get_weather_response(message, city)
    await state.clear()

@dp.message(F.text == "Определить по месту")
async def ask_location(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="Отправить моё местоположение", request_location=True)
    )
    builder.row(
        KeyboardButton(text="Отмена")
    )
    await message.answer(
        "Пришли своё местоположение:",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )
    await state.set_state(WeatherStates.waiting_for_location)

# Обработчик геолокации
@dp.message(WeatherStates.waiting_for_location)
@dp.message(F.location)
async def handle_location(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != WeatherStates.waiting_for_location:
        return

    lat = message.location.latitude
    lon = message.location.longitude
    thinking_msg = await message.answer("Определяем город по координатам...")

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&lang=ru"
        headers = {"User-Agent": "TelegramWeatherBot/1.0"}
        response = requests.get(url, headers=headers).json()
        address = response.get("address", {})

        city = (
            address.get("city") or
            address.get("town") or
            address.get("village") or
            address.get("hamlet") or
            "ближайший населённый пункт"
        )
        region = address.get("state", "")
        city_display = f"{city}, {region}" if region else city

        await get_weather_response(message, city_display)

    except Exception as e:
        await get_weather_response(message, "этой области")

    finally:
        await bot.delete_message(message.chat.id, thinking_msg.message_id)

    await state.clear()

# --- Запрос к ИИ для погоды ---
async def get_weather_response(message: types.Message, city: str):
    thinking_msg = await message.answer(f"Запрашиваю погоду в {city}...")

    prompt = PROMPTS["weather"].format(city=city)
    response = await ask_openrouter(model=DEFAULT_MODEL, prompt=prompt)

    await bot.delete_message(message.chat.id, thinking_msg.message_id)
    await message.answer(response, reply_markup=get_main_menu())

# Обработчик Конвертора
@dp.message(F.text == "Конвертер")
async def converter_info(message: types.Message, state: FSMContext):
    if message.from_user.id != USER_ID:
        return
    await state.clear()  # Очистим, если был в другом режиме
    await message.answer(
        "Отправь файл:\n"
        "• DOCX → PDF: отправь .docx\n"
        "• PDF → DOCX: отправь .pdf",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(F.document)
async def handle_document(message: types.Message):
    if message.from_user.id != USER_ID:
        return

    file = message.document
    file_name = file.file_name
    file_path = f"downloads/{file_name}"
    output_path = ""

    await bot.download(file, file_path)

    try:
        if file_name.lower().endswith(".docx"):
            output_path = file_path.replace(".docx", ".pdf")
            success = docx_to_pdf(file_path, output_path)
            result_msg = "DOCX → PDF готов!"
        elif file_name.lower().endswith(".pdf"):
            output_path = file_path.replace(".pdf", ".docx")
            success = pdf_to_docx(file_path, output_path)
            result_msg = "PDF → DOCX готов!"
        else:
            await message.answer("Неподдерживаемый формат. Только .docx или .pdf")
            return

        if success:
            await message.answer(result_msg)
            await message.answer_document(types.FSInputFile(output_path))
        else:
            await message.answer("Ошибка при конвертации.")

    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        import os
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(output_path) and success:
            os.remove(output_path)

# Обработчик моделей
@dp.message(F.text == "Модели ИИ")
async def choose_model(message: types.Message):
    if message.from_user.id != USER_ID:
        return
    builder = ReplyKeyboardBuilder()
    for btn_text in AI_MODELS.keys():
        builder.add(KeyboardButton(text=btn_text))
    builder.row(KeyboardButton(text="Назад"))
    await message.answer("Выбери модель ИИ:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text.in_(AI_MODELS.keys()))
async def model_chosen(message: types.Message, state: FSMContext):
    model_name = message.text
    model_id = AI_MODELS[model_name]
    await state.update_data(model=model_id)
    await state.set_state(AIStates.waiting_for_prompt)
    await message.answer(
        f"Выбрана модель: {model_name}\n"
        "Что хотите узнать?",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(AIStates.waiting_for_prompt)
async def get_ai_response(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_menu())
        return
    if message.text in AI_MODELS.keys():
        await model_chosen(message, state)
        return

    data = await state.get_data()
    model = data.get("model")
    prompt = f"{PROMPTS['general']}\n\nВопрос: {message.text}"

    thinking_msg = await message.answer("Думаю...")
    response = await ask_openrouter(model, prompt)
    await bot.delete_message(message.chat.id, thinking_msg.message_id)
    await message.answer(response, reply_markup=types.ReplyKeyboardRemove())

# Обработчик кнопок Назад, Отмена
@dp.message(F.text == "Назад")
@dp.message(F.text == "Отмена")
async def go_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_menu())

# Обработчик текста
@dp.message(F.text & ~F.text.startswith("/"))
async def universal_ai_response(message: types.Message):
    if message.from_user.id != USER_ID:
        return


    if message.text in ["Погода", "Конвертер", "Модели ИИ"]:
        return

    thinking_msg = await message.answer("Думаю...")
    prompt = f"{PROMPTS['general']}\n\nВопрос: {message.text}"
    response = await ask_openrouter(model=DEFAULT_MODEL, prompt=prompt)
    await bot.delete_message(message.chat.id, thinking_msg.message_id)
    await message.answer(response, reply_markup=get_main_menu())

async def main():
    import os
    os.makedirs("downloads", exist_ok=True)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())