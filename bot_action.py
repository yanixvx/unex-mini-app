#!/usr/bin/env python3
"""UNEX Medical bot — одноразовый обработчик для GitHub Actions.
Запускается каждую минуту, обрабатывает /start и заявки из мини-аппа.
Offset хранится в переменной репозитория UNEX_LAST_UPDATE.
"""
import json, os, subprocess, urllib.request, urllib.parse

BOT_TOKEN = os.environ.get("UNEX_BOT_TOKEN", "")
OWNER_ID = os.environ.get("UNEX_OWNER_ID", "780868306")
APP_URL = "https://yanixvx.github.io/unex-mini-app/"
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
REPO = os.environ.get("GITHUB_REPOSITORY", "")

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
    if not REPO:
        return None
    try:
        r = subprocess.run(
            ["gh", "api", f"/repos/{REPO}/actions/variables/UNEX_LAST_UPDATE", "--jq", ".value"],
            capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip())
    except Exception as e:
        print(f"read offset error: {e}")
    return None

def save_offset(off):
    if not REPO:
        return
    try:
        subprocess.run(
            ["gh", "api", "-X", "PATCH", f"/repos/{REPO}/actions/variables/UNEX_LAST_UPDATE",
             "-f", f"value={off}"],
            capture_output=True, text=True, timeout=20)
        print(f"offset saved: {off}")
    except Exception as e:
        print(f"save offset error: {e}")

def welcome_kb():
    return json.dumps({"inline_keyboard": [[{
        "text": "🛒 Відкрити каталог UNEX",
        "web_app": {"url": APP_URL}
    }]]})

def main():
    if not BOT_TOKEN:
        print("NO TOKEN")
        return
    me = tg("getMe")
    if not me.get("ok"):
        print("bot token invalid")
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

    last_id = updates[-1]["update_id"]
    handled = 0

    for u in updates:
        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        user = msg.get("from") or {}
        chat_id = msg.get("chat", {}).get("id")
        if not chat_id:
            continue

        # /start и /help — приветствие с кнопкой каталога
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

        # Заявка из мини-аппа (web_app_data)
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

        # Любое другое сообщение — кнопка каталога
        tg("sendMessage",
           chat_id=chat_id,
           text="👋 Напишіть менеджеру: @UnexMedicalProducts\n\nАбо відкрийте каталог і замовте прямо тут 👇",
           reply_markup=welcome_kb())
        handled += 1

    save_offset(last_id + 1)
    print(f"обработано {handled} сообщений, offset -> {last_id + 1}")

if __name__ == "__main__":
    main()
