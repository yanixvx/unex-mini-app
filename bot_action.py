#!/usr/bin/env python3
"""UNEX Medical bot — одноразовый обработчик для GitHub Actions.
Обрабатывает /start (приветствие с кнопкой) и заявки из мини-аппа.
Offset хранится в /tmp/unex_offset.txt (кэш Actions) + фильтр по времени 5 минут.
"""
import json, os, time, urllib.request, urllib.parse

BOT_TOKEN = os.environ.get("UNEX_BOT_TOKEN", "")
OWNER_ID = os.environ.get("UNEX_OWNER_ID", "780868306")
APP_URL = "https://yanixvx.github.io/unex-mini-app/"
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = "/tmp/unex_offset.txt"

def tg(method, **params):
    url = f"{API}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"tg error {method}: {e}")
        return {"ok": False}

def get_last_offset():
    try:
        with open(OFFSET_FILE) as f:
            v = int(f.read().strip())
            return v
    except Exception:
        return None

def save_offset(off):
    try:
        with open(OFFSET_FILE, "w") as f:
            f.write(str(off))
        print(f"offset saved: {off}")
    except Exception as e:
        print(f"save offset error: {e}")

CHANNEL_ID = os.environ.get("UNEX_CHANNEL_ID", "-1001140128016")

def welcome_kb():
    return json.dumps({"inline_keyboard": [[{
        "text": "🛒 Відкрити каталог UNEX",
        "web_app": {"url": APP_URL}
    }]]})

def approve_kb(action_id=""):
    """Inline keyboard для согласования постов."""
    buttons = []
    if action_id:
        # Если есть action_id, показываем кнопки действий
        buttons.append([{
            "text": "✅ Опубликовать",
            "callback_data": f"approve_post:{action_id}:publish"
        }, {
            "text": "❌ Пропустить",
            "callback_data": f"approve_post:{action_id}:skip"
        }, {
            "text": "🔄 Переделать",
            "callback_data": f"approve_post:{action_id}:regenerate"
        }])
    else:
        buttons.append([{
            "text": "✅ Опубликовать",
            "callback_data": "approve_post:publish"
        }, {
            "text": "❌ Пропустить",
            "callback_data": "approve_post:skip"
        }, {
            "text": "🔄 Переделать",
            "callback_data": "approve_post:regenerate"
        }])
    return json.dumps({"inline_keyboard": buttons})

def main():
    if not BOT_TOKEN:
        print("NO TOKEN")
        return

    offset = get_last_offset()
    params = {"timeout": 0}
    if offset:
        params["offset"] = offset

    url = f"{API}/getUpdates?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            updates = json.loads(r.read().decode()).get("result", [])
    except Exception as e:
        print(f"getUpdates error: {e}")
        return

    if not updates:
        print("no updates")
        return

    # Фильтр: только свежие (моложе 5 минут) — защита от дублей при потере кэша
    now = int(time.time())
    fresh = [u for u in updates if (u.get("message") or {}).get("date", 0) >= now - 300]
    if not fresh:
        # подтверждаем offset, чтобы старые не висели
        last_id = updates[-1]["update_id"]
        save_offset(last_id + 1)
        print(f"только старые updates ({len(updates)}), offset -> {last_id + 1}")
        return

    last_id = fresh[-1]["update_id"]
    handled = 0

    for u in fresh:
        # === Обработка callback_query (нажатия inline-кнопок) ===
        cb = u.get("callback_query")
        if cb:
            action_data = cb.get("data", "")
            msg = cb.get("message") or {}
            chat_id = msg.get("chat", {}).get("id")
            message_id = msg.get("message_id")
            user = cb.get("from") or {}
            
            print(f"callback_query: data={action_data}, chat={chat_id}, msg={message_id}")
            
            if "approve_post:" not in action_data:
                tg("answerCallbackQuery", callback_query_id=cb.get("id"), text="Неизвестная команда")
                continue
            
            parts = action_data.split(":")
            cmd = parts[-1] if len(parts) >= 2 else ""
            
            state_file = "/tmp/unex_approve_state.json"
            approve_state = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file) as f:
                        approve_state = json.load(f)
                except:
                    pass
            
            if cmd == "publish":
                pending = approve_state.pop("pending", {})
                if pending:
                    photo_url = pending.get("photo_url")
                    caption_text = pending.get("caption_text", "")
                    
                    if photo_url:
                        tg("sendPhoto", chat_id=CHANNEL_ID, photo=photo_url, caption=caption_text, parse_mode="HTML")
                    else:
                        tg("sendMessage", chat_id=CHANNEL_ID, text=caption_text, parse_mode="HTML")
                    
                    tg("answerCallbackQuery", callback_query_id=cb.get("id"), text="✅ Пост опубликован!")
                    tg("editMessageText", chat_id=chat_id, message_id=message_id, 
                       text="✅ <b>Пост опубліковано!</b>", parse_mode="HTML")
                    print(f"Пост опубликован в канал {CHANNEL_ID}")
                else:
                    tg("answerCallbackQuery", callback_query_id=cb.get("id"), text="Нет поста для публикации")
            
            elif cmd == "skip":
                approve_state.pop("pending", None)
                tg("answerCallbackQuery", callback_query_id=cb.get("id"), text="⏭ Пропущено")
                tg("editMessageText", chat_id=chat_id, message_id=message_id,
                   text="⏭ Пост пропущено. Следующий будет завтра.", parse_mode="HTML")
                with open(state_file, "w") as f:
                    json.dump(approve_state, f)
            
            elif cmd == "regenerate":
                tg("answerCallbackQuery", callback_query_id=cb.get("id"), 
                   text="🔄 Запрошено переделывание. Ждите новый вариант.", show_alert=True)
            
            save_offset(last_id + 1)
            continue
        
        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        user = msg.get("from") or {}
        chat_id = msg.get("chat", {}).get("id")
        if not chat_id:
            continue

        if text in ("/start", "/help", "Старт", "Каталог"):
            tg("sendMessage",
               chat_id=chat_id,
               text="🧤 <b>UNEX Medical Products</b>\n\n"
                    "Медичні рукавички оптом та в роздріб:\n"
                    "• Нітрил, латекс, вініл, TPE\n"
                    "• Склад у Києві — відправка день у день\n"
                    "• Безкоштовна доставка від 50 коробок\n\n"
                    "👇 Відкрийте каталог, оберіть товари та надішліть заявку — менеджер зв'яжеться з вами!",
               parse_mode="HTML",
               reply_markup=welcome_kb())
            handled += 1
            print(f"start от {user.get('id')}")
            continue

        wa = msg.get("web_app_data")
        if wa and wa.get("data"):
            try:
                payload = json.loads(wa["data"])
            except Exception:
                payload = {"raw": wa["data"]}
            items = payload.get("items", [])
            lines = []
            total = 0
            try:
                import sys
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from data import PRODUCTS
                for iid, qty in items:
                    p = next((x for x in PRODUCTS if x["id"] == iid), None)
                    if p:
                        sub = qty * p["price"]
                        total += sub
                        lines.append(f"• {p['name']} × {qty} = {sub} грн")
            except Exception:
                pass
            if payload.get("total"):
                total = payload["total"]

            order_text = (
                "🧤 <b>НОВА ЗАЯВКА (каталог UNEX)</b>\n\n"
                f"👤 {payload.get('name','—')}\n"
                f"📞 {payload.get('phone','—')}\n\n"
                f"📦 <b>Замовлення:</b>\n" + ("\n".join(lines) if lines else "—") + "\n\n"
                f"💰 <b>Разом: {total} грн</b>\n"
                f"{('💬 ' + payload.get('comment','')) if payload.get('comment') else ''}\n\n"
                f"🆔 TG: {user.get('id')} @{user.get('username') or '—'} ({user.get('first_name') or ''})"
            )
            tg("sendMessage", chat_id=OWNER_ID, text=order_text, parse_mode="HTML")
            tg("sendMessage",
               chat_id=chat_id,
               text="✅ <b>Заявку отримано!</b>\n\nМенеджер UNEX зв'яжеться з вами найближчим часом (Пн–Сб 9:00–19:00).\n\nДякуємо за звернення! 🙌",
               parse_mode="HTML")
            handled += 1
            print(f"заявка от {user.get('id')}, total={total}")
            continue

        tg("sendMessage",
           chat_id=chat_id,
           text="👋 Напишіть менеджеру: @UnexMedicalProducts\n\nАбо відкрийте каталог і замовте прямо тут 👇",
           reply_markup=welcome_kb())
        handled += 1

    save_offset(last_id + 1)
    print(f"обработано {handled} сообщений, offset -> {last_id + 1}")

if __name__ == "__main__":
    main()
