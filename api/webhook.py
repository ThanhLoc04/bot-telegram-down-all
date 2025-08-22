import requests
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from io import BytesIO
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Lấy từ biến môi trường Vercel
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Domain Vercel của bạn

app = FastAPI()

# Cache link video
video_cache = {}

# ================== DOWNR API ==================
def get_download_data(url: str):
    api_url = "https://downr.org/.netlify/functions/download"
    headers = {"Content-Type": "application/json"}
    resp = requests.post(api_url, headers=headers, json={"url": url}, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Lỗi API: {resp.status_code}")
    return resp.json()

# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    banner = """
╔════════════════════╗
      🤖 Downr Bot 🚀
╚════════════════════╝
📥 Gửi link video/ảnh → chọn chất lượng → bot tải về và gửi cho bạn!
"""
    await update.message.reply_text(banner)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Đang xử lý link...")

    try:
        data = get_download_data(url)
        title = data.get("title", "No title")
        source = data.get("source", "unknown")
        thumbnail = data.get("thumbnail")
        medias = data.get("medias", [])

        buttons = []
        for idx, m in enumerate(medias):
            q = m.get("quality", "")
            ext = m.get("extension", "")
            size = m.get("size", "")
            link = m.get("url", "")

            text = f"{q} {ext} ({size})"
            buttons.append([InlineKeyboardButton(text, callback_data=f"dl_{idx}")])
            video_cache[f"dl_{idx}"] = {"link": link, "ext": ext, "title": title}

        reply_markup = InlineKeyboardMarkup(buttons)

        if thumbnail:
            await update.message.reply_photo(
                photo=thumbnail,
                caption=f"🎬 *{title}*\n🌐 Nguồn: {source}\n\nChọn chất lượng để tải ⬇️",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"🎬 *{title}*\n🌐 Nguồn: {source}\n\nChọn chất lượng để tải ⬇️",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = video_cache.get(query.data)
    if not data:
        await query.message.reply_text("❌ Lỗi: không tìm thấy link.")
        return

    link = data["link"]
    ext = data["ext"]
    title = data["title"]

    await query.message.reply_text("📥 Đang tải file...")

    try:
        resp = requests.get(link, stream=True, timeout=60)
        resp.raise_for_status()

        file_bytes = BytesIO(resp.content)
        file_bytes.name = f"{title}.{ext}"

        if ext in ["mp4", "mov", "mkv"]:
            await query.message.reply_video(video=InputFile(file_bytes), caption=f"🎬 {title}")
        elif ext in ["jpg", "jpeg", "png", "webp"]:
            await query.message.reply_photo(photo=InputFile(file_bytes), caption=f"🖼 {title}")
        elif ext in ["mp3", "m4a"]:
            await query.message.reply_audio(audio=InputFile(file_bytes), caption=f"🎵 {title}")
        else:
            await query.message.reply_document(document=InputFile(file_bytes), caption=f"📂 {title}")

    except Exception as e:
        await query.message.reply_text(f"⚠️ Lỗi tải file: {e}")

# ================== TELEGRAM APP ==================
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(button_callback))

# ================== FASTAPI WEBHOOK ==================
@app.post("/api/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.initialize()
    await application.process_update(update)
    return {"ok": True}

@app.get("/")
async def home():
    return {"status": "🤖 Downr Telegram Bot chạy trên Vercel!"}
