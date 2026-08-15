import os, json, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv("BOT_TOKEN","").strip()
ADMIN_ID=int(os.getenv("ADMIN_ID","0") or 0)
if not TOKEN: raise RuntimeError("BOT_TOKEN is missing")
if not ADMIN_ID: raise RuntimeError("ADMIN_ID is missing")

DATA_FILE="channels.json"
EMOJI_FILE="emojis.json"

def admin(update):
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)

def load():
    try:
        with open(DATA_FILE,"r",encoding="utf-8") as f:
            d=json.load(f)
            d.setdefault("channels",{})
            d.setdefault("active",None)
            return d
    except Exception:
        return {"channels":{}, "active":None}

def save(d):
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(d,f,ensure_ascii=False,indent=2)

def load_emojis():
    try:
        with open(EMOJI_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def save_emojis(d):
    with open(EMOJI_FILE,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def build_message_entities(raw):
    pattern=re.compile(r"\[emoji:(\d+)\]")
    out=[]; entities=[]; pos=0; out_utf16=0
    for m in pattern.finditer(raw):
        chunk=raw[pos:m.start()]
        out.append(chunk)
        out_utf16 += len(chunk.encode("utf-16-le"))//2
        emoji="🙂"
        out.append(emoji)
        entities.append(MessageEntity(type="custom_emoji", offset=out_utf16,
                                      length=len(emoji.encode("utf-16-le"))//2,
                                      custom_emoji_id=m.group(1)))
        out_utf16 += len(emoji.encode("utf-16-le"))//2
        pos=m.end()
    tail=raw[pos:]; out.append(tail)
    return "".join(out), entities

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Create Post", callback_data="create_post")],
        [InlineKeyboardButton("⚙️ Channel Manager", callback_data="channel_manager")],
        [InlineKeyboardButton("🎨 Button Studio", callback_data="button_studio")],
        [InlineKeyboardButton("👁 Preview Draft", callback_data="preview_draft")]
    ])

def channel_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Connect Channel", callback_data="connect_channel")],
        [InlineKeyboardButton("📋 Connected Channels", callback_data="connected_channels")],
        [InlineKeyboardButton("🔄 Switch Channel", callback_data="switch_channel")],
        [InlineKeyboardButton("🗑 Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ])

def button_markup(buttons):
    if not buttons: return None
    rows=[]
    for item in buttons:
        label,url=item[0],item[1]
        emoji_id=item[2] if len(item)>2 else ""
        kwargs={"text":label,"url":url}
        if emoji_id: kwargs["icon_custom_emoji_id"]=emoji_id
        rows.append([InlineKeyboardButton(**kwargs)])
    return InlineKeyboardMarkup(rows)

async def start(update, context):
    if not admin(update): return
    await update.message.reply_text(
        "✨ PREMIUM CHANNEL STUDIO\n\n"
        "Your Channel posting control panel is ready.",
        reply_markup=main_menu()
    )

async def callbacks(update, context):
    q=update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("Not authorized.", show_alert=True)
        return
    await q.answer()
    data=q.data
    d=load()

    if data=="back_main":
        context.user_data.clear()
        await q.message.reply_text("✨ PREMIUM CHANNEL STUDIO",reply_markup=main_menu())

    elif data=="create_post":
        if not d.get("active") or str(d["active"]) not in d["channels"]:
            await q.message.reply_text(
                "⚠️ No active Channel.\n\n"
                "Open ⚙️ Channel Manager → ➕ Connect Channel first.",
                reply_markup=channel_menu()
            )
            return
        context.user_data.clear()
        context.user_data["stage"]="post_text"
        context.user_data["buttons"]=[]
        await q.message.reply_text(
            "📝 CREATE CHANNEL POST\n\n"
            f"Active Channel: {d['channels'][str(d['active'])]}\n\n"
            "Send the text you want to publish."
        )

    elif data=="channel_manager":
        await q.message.reply_text("⚙️ CHANNEL MANAGER",reply_markup=channel_menu())

    elif data=="connect_channel":
        context.user_data["stage"]="connect"
        await q.message.reply_text(
            "➕ CONNECT CHANNEL\n\n"
            "1. Add this bot as Administrator to your Channel.\n"
            "2. Give it permission to post messages.\n"
            "3. Forward a post from that Channel to this private bot chat.\n\n"
            "I will detect and save the Channel automatically."
        )

    elif data=="connected_channels":
        if not d["channels"]:
            await q.message.reply_text("📋 No connected Channels.",reply_markup=channel_menu())
            return
        lines=["📋 CONNECTED CHANNELS\n"]
        for cid,name in d["channels"].items():
            active="  ⭐ ACTIVE" if str(d.get("active"))==str(cid) else ""
            lines.append(f"• {name}{active}")
        await q.message.reply_text("\n".join(lines),reply_markup=channel_menu())

    elif data=="switch_channel":
        if not d["channels"]:
            await q.message.reply_text("No Channels connected yet.",reply_markup=channel_menu())
            return
        rows=[]
        for cid,name in d["channels"].items():
            prefix="⭐ " if str(d.get("active"))==str(cid) else ""
            rows.append([InlineKeyboardButton(prefix+name,callback_data="switch:"+cid)])
        rows.append([InlineKeyboardButton("⬅️ Back",callback_data="channel_manager")])
        await q.message.reply_text("🔄 SELECT ACTIVE CHANNEL",reply_markup=InlineKeyboardMarkup(rows))

    elif data.startswith("switch:"):
        cid=data.split(":",1)[1]
        if cid in d["channels"]:
            d["active"]=cid
            save(d)
            await q.message.reply_text(
                f"✅ Active Channel changed to:\n{d['channels'][cid]}",
                reply_markup=channel_menu()
            )

    elif data=="remove_channel":
        if not d["channels"]:
            await q.message.reply_text("No Channels connected yet.",reply_markup=channel_menu())
            return
        rows=[
            [InlineKeyboardButton(name,callback_data="remove:"+cid)]
            for cid,name in d["channels"].items()
        ]
        rows.append([InlineKeyboardButton("⬅️ Back",callback_data="channel_manager")])
        await q.message.reply_text("🗑 SELECT CHANNEL TO REMOVE",reply_markup=InlineKeyboardMarkup(rows))

    elif data.startswith("remove:"):
        cid=data.split(":",1)[1]
        if cid not in d["channels"]: return
        context.user_data["remove_id"]=cid
        await q.message.reply_text(
            f"⚠️ Remove **{d['channels'][cid]}** from the bot?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Remove",callback_data="confirm_remove")],
                [InlineKeyboardButton("❌ Cancel",callback_data="channel_manager")]
            ])
        )

    elif data=="confirm_remove":
        cid=context.user_data.pop("remove_id",None)
        if cid and cid in d["channels"]:
            name=d["channels"].pop(cid)
            if str(d.get("active"))==str(cid):
                d["active"]=next(iter(d["channels"]),None)
            save(d)
            await q.message.reply_text(f"🗑️ {name} removed successfully.",reply_markup=channel_menu())

    elif data=="emoji_manager":
        await q.message.reply_text(
            "✨ PREMIUM EMOJI MANAGER\n\n"
            "Message: use [emoji:CUSTOM_EMOJI_ID]\n"
            "Button: Button Name | CUSTOM_EMOJI_ID",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Emoji",callback_data="emoji_add")],
                [InlineKeyboardButton("📋 Saved Emojis",callback_data="emoji_list")],
                [InlineKeyboardButton("🗑 Remove Emoji",callback_data="emoji_remove")],
                [InlineKeyboardButton("⬅️ Back",callback_data="back_main")]
            ])
        )

    elif data=="emoji_add":
        context.user_data["stage"]="emoji_add"
        await q.message.reply_text("➕ Send: Name | Custom Emoji ID\nExample: Inbox | 6235336389647407554")

    elif data=="emoji_list":
        e=load_emojis()
        await q.message.reply_text("📋 SAVED EMOJIS\n\n"+("\n".join(f"• {n} — {i}" for n,i in e.items()) if e else "No saved emojis."))

    elif data=="emoji_remove":
        e=load_emojis()
        if not e:
            await q.message.reply_text("No saved emojis."); return
        rows=[[InlineKeyboardButton(n,callback_data="emoji_del:"+n)] for n in e]
        rows.append([InlineKeyboardButton("⬅️ Back",callback_data="emoji_manager")])
        await q.message.reply_text("🗑 Select emoji",reply_markup=InlineKeyboardMarkup(rows))

    elif data.startswith("emoji_del:"):
        n=data.split(":",1)[1]; e=load_emojis(); e.pop(n,None); save_emojis(e)
        await q.message.reply_text("🗑 Removed.",reply_markup=main_menu())

    elif data=="button_studio":
        await q.message.reply_text(
            "🎨 BUTTON STUDIO\n\n"
            "During Create Post, add as many URL buttons as you want.\n"
            "Premium Custom Emoji can be added to a button when supported."
        )

    elif data=="preview_draft":
        text=context.user_data.get("post_text")
        if not text:
            await q.message.reply_text("👁 No active draft.")
        else:
            clean_text, _ = build_message_entities(text)
            await q.message.reply_text(
                "👁 PREVIEW\n\n"+clean_text,
                reply_markup=button_markup(context.user_data.get("buttons",[]))
            )

    elif data=="publish":
        await publish(update,context)

    elif data=="cancel_draft":
        context.user_data.clear()
        await q.message.reply_text("🗑 Draft cancelled.",reply_markup=main_menu())

    elif data=="add_another":
        context.user_data["stage"]="button_label"
        await q.message.reply_text("🔘 Send the next button name.")

async def text_messages(update, context):
    if not admin(update): return
    stage=context.user_data.get("stage")

    if stage=="emoji_add":
        raw=update.message.text.strip()
        if "|" not in raw:
            await update.message.reply_text("❌ Format: Name | Custom Emoji ID"); return
        name,eid=[x.strip() for x in raw.split("|",1)]
        if not name or not eid.isdigit():
            await update.message.reply_text("❌ Invalid Emoji ID."); return
        e=load_emojis(); e[name]=eid; save_emojis(e); context.user_data.clear()
        await update.message.reply_text(f"✅ Saved {name}\nID: {eid}",reply_markup=main_menu())
        return

    # Channel connection via forwarded message
    if stage=="connect":
        origin=getattr(update.message,"forward_origin",None)
        chat=getattr(origin,"chat",None)
        if chat and chat.type=="channel":
            d=load()
            cid=str(chat.id)
            name=chat.title or "Channel"
            d["channels"][cid]=name
            if not d.get("active"):
                d["active"]=cid
            save(d)
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ CHANNEL CONNECTED\n\n{name}\n\n"
                "This Channel is now your active Channel.",
                reply_markup=main_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Channel not detected.\n"
                "Forward a post directly from the Channel to this private chat."
            )
        return

    if stage=="post_text":
        context.user_data["post_text"]=update.message.text
        context.user_data["stage"]="button_label"
        await update.message.reply_text(
            "🔘 BUTTON 1\n\n"
            "Send the button name.\n"
            "Example: ADMIN INBOX\n\n"
            "Or send /done to publish without buttons."
        )
        return

    if stage=="button_label":
        parts=[x.strip() for x in update.message.text.split("|")]
        context.user_data["button_label"]=parts[0]
        context.user_data["button_emoji_id"]=parts[1] if len(parts)>1 and parts[1].isdigit() else ""
        context.user_data["stage"]="button_url"
        await update.message.reply_text(
            "🔗 Send the URL for this button.\n"
            "Example: https://t.me/example"
        )
        return

    if stage=="button_url":
        url=update.message.text.strip()
        if not url.startswith(("https://","http://","tg://")):
            await update.message.reply_text("❌ Invalid URL. Please send a valid URL.")
            return
        context.user_data.setdefault("buttons",[]).append(
            (context.user_data.get("button_label","Button"),url,context.user_data.get("button_emoji_id",""))
        )
        context.user_data["stage"]="button_label"
        n=len(context.user_data["buttons"])
        await update.message.reply_text(
            f"✅ Button {n} added.\n\n"
            "Send another button name, or /done to publish."
        )

async def done(update,context):
    if not admin(update): return
    await publish(update,context)

async def publish(update,context):
    d=load()
    cid=str(d.get("active") or "")
    if not cid or cid not in d["channels"]:
        await update.message.reply_text("⚠️ No active Channel. Open Channel Manager and connect one.")
        return
    text=context.user_data.get("post_text")
    if not text:
        await update.message.reply_text("⚠️ No draft found. Tap Create Post first.",reply_markup=main_menu())
        return
    try:
        clean_text, entities = build_message_entities(text)
        # Telegram currently allows bot-sent custom emoji messages to private/group/supergroup chats,
        # but not as bot-sent custom-emoji entities in channels. Use the normal emoji fallback
        # for Channel posts so publishing never fails.
        await context.bot.send_message(
            chat_id=cid,
            text=clean_text,
            reply_markup=button_markup(context.user_data.get("buttons",[]))
        )
        count=len(context.user_data.get("buttons",[]))
        context.user_data.clear()
        await update.message.reply_text(
            f"🚀 PUBLISHED SUCCESSFULLY\n\nButtons: {count}",
            reply_markup=main_menu()
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ Publish failed.\n\n"
            f"Telegram error: {e}\n\n"
            "Check that the bot is an Admin and can post in the selected Channel."
        )

def main():
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("panel",start))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_messages))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
