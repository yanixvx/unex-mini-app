#!/usr/bin/env python3
"""UNEX MEDICAL — Mini App bot: приём заявок из каталога и пересылка Яну."""
import json, logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("UNEX_BOT_TOKEN", "8250319231:AAEJzp32JOmDOD0Hnxhrz3mzNT0TTnhIgzI")
OWNER_ID = int(os.environ.get("UNEX_OWNER_ID", "7808683047"))
APP_URL = "https://yanixvx.github.io/unex-mini-app/"

WEBAPP_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("🛒 Відкрити каталог UNEX", web_app=WebAppInfo(url=APP_URL))
]])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log.info("start от %s (%s)", user.first_name, user.id)
    await update.message.reply_text(
        "🧤 <b>UNEX Medical Products</b>\n\n"
        "Медичні рукавички оптом та в роздріб:\n"
        "• Нітрил, латекс, вініл, TPE\n"
        "• Склад у Києві — відправка день у день\n"
        "• Безкоштовна доставка від 50 коробок\n\n"
        "👇 Відкрийте каталог, оберіть товари та надішліть заявку — менеджер зв'яжеться з вами!",
        parse_mode="HTML", reply_markup=WEBAPP_KB,
    )

async def handle_webapp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Заявка из мини-аппа (sendData → web_app_data)."""
    msg = update.effective_message
    user = update.effective_user
    data = msg.web_app_data
    if not data:
        return
    try:
        payload = json.loads(data.data)
    except Exception:
        payload = {"raw": data.data}
    log.info("Заявка от %s: %s", user.id, json.dumps(payload, ensure_ascii=False)[:300])

    # Собираем текст заявки
    items = payload.get("items", [])
    lines = []
    total = 0
    from data import PRODUCTS
    for iid, qty in items:
        p = next((x for x in PRODUCTS if x["id"] == iid), None)
        if p:
            sub = qty * p["price"]
            total += sub
            lines.append(f"• {p['name']} ({p['size']}) × {qty} = {sub} грн")
    if payload.get("total"):
        total = payload["total"]

    text = (
        "🧤 <b>НОВА ЗАЯВКА (каталог UNEX)</b>\n\n"
        f"👤 {payload.get('name','—')}\n"
        f"📞 {payload.get('phone','—')}\n\n"
        f"📦 <b>Замовлення:</b>\n" + ("\n".join(lines) if lines else "—") + "\n\n"
        f"💰 <b>Разом: {total} грн</b>\n"
        f"{('💬 ' + payload.get('comment','')) if payload.get('comment') else ''}\n\n"
        f"🆔 TG: {user.id} @{user.username or '—'} ({user.first_name})"
    )
    try:
        await ctx.bot.send_message(OWNER_ID, text, parse_mode="HTML")
        log.info("Заявка переслана владельцу %s", OWNER_ID)
    except Exception as e:
        log.error("Не удалось переслать владельцу: %s", e)

    await msg.reply_text(
        "✅ <b>Заявку отримано!</b>\n\nМенеджер UNEX зв'яжеться з вами найближчим часом (Пн–Сб 9:00–19:00).\n\nДякуємо за звернення! 🙌",
        parse_mode="HTML",
    )

async def handle_plain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Напишіть менеджеру: @UnexMedicalProducts\n\n"
        "Або відкрийте каталог і замовте прямо тут 👇",
        reply_markup=WEBAPP_KB,
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain))
    log.info("UNEX bot запущен (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
