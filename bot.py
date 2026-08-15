
import os
import re
import sqlite3
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, MessageEntity
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = Path(os.getenv("DB_PATH", "inline_button_bot.db"))

# Predefined Telegram Premium/Custom Emoji IDs.
# IDs are never concatenated into button text.
PREMIUM_EMOJIS = {
    "admin_inbox_left": "6158862632926319619",
    "admin_inbox_right": "6206112371308500200",
}


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Per-user temporary creation state.
states = {}

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Add Button"), KeyboardButton(text="📢 Channel Management")],
        [KeyboardButton(text="👁 Preview"), KeyboardButton(text="📤 Send")],
    ],
    resize_keyboard=True
)

CHANNEL_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Add Channel"), KeyboardButton(text="❌ Remove Channel")],
        [KeyboardButton(text="👁 View Connected Channels")],
        [KeyboardButton(text="🔙 Back")],
    ],
    resize_keyboard=True
)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS drafts (
        user_id INTEGER PRIMARY KEY,
        description TEXT DEFAULT '',
        description_entities TEXT DEFAULT '[]',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        emoji_id TEXT DEFAULT '',
        position INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        chat_id TEXT NOT NULL,
        title TEXT NOT NULL,
        username TEXT DEFAULT '',
        UNIQUE(user_id, chat_id)
    );
    """)
    con.commit()
    con.close()

def clear_draft(user_id):
    con = db()
    con.execute("DELETE FROM drafts WHERE user_id=?", (user_id,))
    con.execute("DELETE FROM buttons WHERE user_id=?", (user_id,))
    con.commit()
    con.close()

def save_draft(user_id, description, entities):
    con = db()
    con.execute(
        """INSERT INTO drafts(user_id,description,description_entities)
           VALUES(?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
           description=excluded.description,
           description_entities=excluded.description_entities""",
        (user_id, description, entities)
    )
    con.commit()
    con.close()

def add_button(user_id, name, url, emoji_id=""):
    con = db()
    pos = con.execute(
        "SELECT COALESCE(MAX(position),0)+1 FROM buttons WHERE user_id=?",
        (user_id,)
    ).fetchone()[0]
    con.execute(
        "INSERT INTO buttons(user_id,name,url,emoji_id,position) VALUES(?,?,?,?,?)",
        (user_id, name, url, emoji_id, pos)
    )
    con.commit()
    con.close()

def get_draft(user_id):
    con = db()
    row = con.execute("SELECT * FROM drafts WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row

def get_buttons(user_id):
    con = db()
    rows = con.execute(
        "SELECT * FROM buttons WHERE user_id=? ORDER BY position,id", (user_id,)
    ).fetchall()
    con.close()
    return rows

def get_channels(user_id):
    con = db()
    rows = con.execute(
        "SELECT * FROM channels WHERE user_id=? ORDER BY id", (user_id,)
    ).fetchall()
    con.close()
    return rows

def valid_url(url):
    return bool(re.match(r"^https?://\S+$", url, re.I))

def parse_emoji_id(text):
    # Supported:
    #   Button Name
    #   Button Name | 1234567890123456789
    if "|" not in text:
        return text.strip(), ""
    name, emoji_id = text.rsplit("|", 1)
    if emoji_id.strip().isdigit():
        return name.strip(), emoji_id.strip()
    return text.strip(), ""
def build_markup(rows):
    keyboard = []
    row = []
    for b in rows:
        kwargs = {
            "text": str(b["name"]),
            "url": str(b["url"]),
        }
        emoji_id = str(b["emoji_id"] or "").strip()
        if emoji_id.isdigit():
            kwargs["icon_custom_emoji_id"] = emoji_id
        row.append(InlineKeyboardButton(**kwargs))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def send_draft(chat_id, user_id):
    draft = get_draft(user_id)
    buttons = get_buttons(user_id)
    if not draft or not buttons:
        return False
    entities = []
    # Description entities are restored only for custom emoji entity data
    # that Telegram accepts. We preserve all incoming entity data.
    import json
    try:
        raw = json.loads(draft["description_entities"] or "[]")
        for e in raw:
            entities.append(MessageEntity(**e))
    except Exception:
        entities = []
    kwargs = {"chat_id": chat_id, "text": draft["description"], "reply_markup": build_markup(buttons)}
    if entities:
        kwargs["entities"] = entities
    await bot.send_message(**kwargs)
    return True

async def ask_next(message, text):
    await message.answer(text, reply_markup=ReplyKeyboardRemove())


@dp.message(CommandStart())
async def start(message: Message):
    states.pop(message.from_user.id, None)
    await message.answer(
        "🤖 <b>Inline Button Bot</b>\n\n"
        "এখান থেকে একাধিক Inline Button তৈরি করে connected channel-এ পাঠাতে পারবেন।",
        reply_markup=MAIN_KB
    )

@dp.message(F.text == "➕ Add Button")
async def add_start(message: Message):
    uid = message.from_user.id
    clear_draft(uid)
    states[uid] = {"step": "description"}
    await ask_next(message, "📝 <b>Message Description</b> পাঠান।\n\n"
                            "Telegram থেকে custom/premium emoji সহ description পাঠাতে পারবেন।")

@dp.message(F.text == "📢 Channel Management")
async def channel_menu(message: Message):
    states.pop(message.from_user.id, None)
    await message.answer("📢 <b>Channel Management</b>", reply_markup=CHANNEL_KB)

@dp.message(F.text == "🔙 Back")
async def back_main(message: Message):
    states.pop(message.from_user.id, None)
    await message.answer("🏠 Main Menu", reply_markup=MAIN_KB)

@dp.message(F.text == "👁 View Connected Channels")
async def view_channels(message: Message):
    rows = get_channels(message.from_user.id)
    if not rows:
        await message.answer("কোনো channel connected নেই।", reply_markup=CHANNEL_KB)
        return
    out = ["📋 <b>Connected Channels</b>\n"]
    for i, r in enumerate(rows, 1):
        username = f"@{r['username']}" if r["username"] else "No username"
        out.append(f"{i}. <b>{r['title']}</b>\n   ID: <code>{r['chat_id']}</code>\n   {username}")
    await message.answer("\n".join(out), reply_markup=CHANNEL_KB)

@dp.message(F.text == "➕ Add Channel")
async def add_channel_start(message: Message):
    states[message.from_user.id] = {"step": "channel"}
    await message.answer(
        "📢 যে channel-এ bot-কে <b>admin</b> করেছেন, সেই channel-এর একটি message এখানে forward করুন।\n\n"
        "Bot channel-এর ID ও title শনাক্ত করে connected list-এ যোগ করবে।",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(F.text == "❌ Remove Channel")
async def remove_channel_start(message: Message):
    rows = get_channels(message.from_user.id)
    if not rows:
        await message.answer("কোনো connected channel নেই।", reply_markup=CHANNEL_KB)
        return
    kb = []
    for r in rows:
        kb.append([InlineKeyboardButton(
            text=f"❌ {r['title'][:50]}",
            callback_data=f"rmch:{r['id']}"
        )])
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="chmenu")])
    await message.answer(
        "যে channel remove করতে চান সেটি নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data.startswith("rmch:"))
async def remove_channel(call: CallbackQuery):
    rid = int(call.data.split(":")[1])
    con = db()
    con.execute("DELETE FROM channels WHERE id=? AND user_id=?", (rid, call.from_user.id))
    con.commit()
    con.close()
    await call.answer("Channel removed.")
    await call.message.edit_text("✅ Channel removed.")

@dp.callback_query(F.data == "chmenu")
async def chmenu(call: CallbackQuery):
    await call.answer()
    await call.message.delete()
    await call.message.answer("📢 Channel Management", reply_markup=CHANNEL_KB)

@dp.message(F.text == "👁 Preview")
async def preview(message: Message):
    uid = message.from_user.id
    draft = get_draft(uid)
    buttons = get_buttons(uid)
    if not draft or not buttons:
        await message.answer(
            "⚠️ আগে Add Button থেকে একটি description এবং অন্তত একটি button তৈরি করুন।",
            reply_markup=MAIN_KB
        )
        return
    await send_draft(message.chat.id, uid)

@dp.message(F.text == "📤 Send")
async def send_start(message: Message):
    rows = get_channels(message.from_user.id)
    if not rows:
        await message.answer(
            "⚠️ আগে Channel Management → Add Channel থেকে অন্তত একটি channel connect করুন।",
            reply_markup=MAIN_KB
        )
        return
    draft = get_draft(message.from_user.id)
    buttons = get_buttons(message.from_user.id)
    if not draft or not buttons:
        await message.answer(
            "⚠️ আগে Add Button থেকে content তৈরি করুন।",
            reply_markup=MAIN_KB
        )
        return
    kb = []
    for r in rows:
        kb.append([InlineKeyboardButton(
            text=f"📤 {r['title'][:50]}",
            callback_data=f"sendch:{r['id']}"
        )])
    kb.append([InlineKeyboardButton(text="❌ Cancel", callback_data="sendcancel")])
    await message.answer(
        "কোন connected channel-এ পাঠাবেন?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data.startswith("sendch:"))
async def send_to_channel(call: CallbackQuery):
    rid = int(call.data.split(":")[1])
    con = db()
    row = con.execute(
        "SELECT * FROM channels WHERE id=? AND user_id=?",
        (rid, call.from_user.id)
    ).fetchone()
    con.close()
    if not row:
        await call.answer("Channel not found.", show_alert=True)
        return
    try:
        ok = await send_draft(row["chat_id"], call.from_user.id)
        if not ok:
            await call.answer("No draft.", show_alert=True)
            return
        await call.answer("Sent successfully.")
        await call.message.edit_text(f"✅ Sent to <b>{row['title']}</b>.")
    except Exception as e:
        await call.answer("Send failed.", show_alert=True)
        await call.message.edit_text(
            "❌ <b>Send failed</b>\n\n"
            "Bot-কে channel-এ admin করা আছে কি না এবং post permission আছে কি না দেখুন.\n\n"
            f"<code>{str(e)[:500]}</code>"
        )

@dp.callback_query(F.data == "sendcancel")
async def send_cancel(call: CallbackQuery):
    await call.answer()
    await call.message.delete()

@dp.message()
async def catch_all(message: Message):
    uid = message.from_user.id
    state = states.get(uid)
    if not state:
        await message.answer("🏠 Main Menu", reply_markup=MAIN_KB)
        return

    step = state["step"]

    if step == "description":
        # Preserve custom emoji entities exactly as Telegram sent them.
        import json
        entities = []
        source_entities = message.entities or message.caption_entities or []
        for e in source_entities:
            entities.append(e.model_dump())
        description = message.text or message.caption or ""
        if not description:
            await message.answer("❌ Description খালি রাখা যাবে না।")
            return
        save_draft(uid, description, json.dumps(entities))
        state["step"] = "button_name"
        await message.answer(
            "🔘 <b>Button Name</b> দিন।\n\n"
            "তারপর আলাদা করে Premium/Custom Emoji ID নেওয়া হবে।"
        )
        return

    if step == "button_name":
        name = (message.text or "").strip()
        if not name:
            await message.answer("❌ Button Name খালি রাখা যাবে না।")
            return
        state["button_name"] = name

        # Premium emoji is selected from the predefined list, not entered
        # into the button text and not typed as an ID by the user.
        state["step"] = "button_emoji"
        kb = []
        for key, item in PREMIUM_EMOJIS.items():
            kb.append([InlineKeyboardButton(
                text=item["name"],
                callback_data=f"pickemoji:{key}",
                icon_custom_emoji_id=item["right"]
            )])
        kb.append([InlineKeyboardButton(text="🚫 No Emoji", callback_data="pickemoji:none")])
        await message.answer(
            "✨ <b>Button-এর Premium Emoji নির্বাচন করুন:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        return
        state["emoji_id"] = emoji_id
        state["step"] = "button_link"
        await message.answer(
            "🔗 এখন Button-এর <b>Link</b> পাঠান।\n"
            "উদাহরণ: <code>https://example.com</code>"
        )
        return

    if step == "button_link":
        url = (message.text or "").strip()
        if not valid_url(url):
            await message.answer("❌ Valid http/https link দিন।")
            return
        add_button(uid, state["button_name"], url, state.get("emoji_id", ""))
        state.clear()
        state["step"] = "more"
        rows = get_buttons(uid)
        await message.answer(
            f"✅ Button added: <b>{state.get('button_name','')}</b>\n\n"
            f"বর্তমানে মোট <b>{len(rows)}</b>টি button আছে।\n"
            "আরও button যোগ করবেন?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Add Another Button", callback_data="addmore")],
                [InlineKeyboardButton(text="✅ Done", callback_data="donebuttons")]
            ])
        )
        return

    if step == "channel":
        # A forwarded channel post carries forward_origin.
        if not message.forward_origin:
            await message.answer("❌ Channel-এর একটি forwarded message পাঠান।")
            return
        origin = message.forward_origin
        chat = getattr(origin, "chat", None)
        if not chat:
            await message.answer("❌ Channel শনাক্ত করা যায়নি।")
            return
        try:
            member = await bot.get_chat_member(chat.id, uid)
            if member.status not in ("administrator", "creator"):
                await message.answer("❌ Bot ব্যবহারকারীর channel admin permission যাচাই করতে পারেনি।")
                return
        except Exception:
            # User can still connect if the bot itself is admin and the channel is identifiable.
            pass
        con = db()
        con.execute(
            """INSERT INTO channels(user_id,chat_id,title,username)
               VALUES(?,?,?,?)
               ON CONFLICT(user_id,chat_id) DO UPDATE SET
               title=excluded.title, username=excluded.username""",
            (uid, str(chat.id), chat.title or "Untitled Channel", chat.username or "")
        )
        con.commit()
        con.close()
        states.pop(uid, None)
        await message.answer(
            f"✅ <b>{chat.title or 'Channel'}</b> connected successfully.",
            reply_markup=CHANNEL_KB
        )
        return

    if step == "more":
        await message.answer("উপরের Add Another Button বা Done চাপুন।")


@dp.callback_query(F.data.startswith("pickemoji:"))
async def pick_predefined_emoji(call: CallbackQuery):
    uid = call.from_user.id
    state = states.get(uid)
    if not state:
        await call.answer("Session expired.", show_alert=True)
        return

    key = call.data.split(":", 1)[1]
    if key == "none":
        state["emoji_id"] = ""
    elif key == "admin_inbox":
        state["emoji_id"] = PREMIUM_EMOJIS["admin_inbox_right"]
    else:
        await call.answer("Emoji not found.", show_alert=True)
        return

    state["step"] = "button_link"
    await call.answer("Emoji selected.")
    await call.message.edit_text(
        "🔗 এখন Button-এর <b>Link</b> পাঠান.\n"
        "উদাহরণ: <code>https://example.com</code>"
    )

@dp.callback_query(F.data == "addmore")
async def add_more(call: CallbackQuery):
    uid = call.from_user.id
    states[uid] = {"step": "button_name"}
    await call.answer()
    await call.message.edit_text("🔘 <b>Button Name</b> দিন।")

@dp.callback_query(F.data == "donebuttons")
async def done_buttons(call: CallbackQuery):
    uid = call.from_user.id
    rows = get_buttons(uid)
    if not rows:
        await call.answer("At least one button is required.", show_alert=True)
        return
    states[uid] = None
    await call.answer()
    await call.message.edit_text(
        f"✅ <b>{len(rows)}টি Button প্রস্তুত।</b>\n\n"
        "এখন Main Menu থেকে Preview বা Send ব্যবহার করতে পারবেন।"
    )
    await call.message.answer("🏠 Main Menu", reply_markup=MAIN_KB)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
