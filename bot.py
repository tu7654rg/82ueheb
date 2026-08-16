import os, json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv("BOT_TOKEN","").strip()
ADMIN_ID=int(os.getenv("ADMIN_ID","0") or 0)
if not TOKEN: raise RuntimeError("BOT_TOKEN is missing")
if not ADMIN_ID: raise RuntimeError("ADMIN_ID is missing")

DATA_FILE="channels.json"

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
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label,url=url)] for label,url in buttons]
    )

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

    elif data=="button_studio":
        await q.message.reply_text(
            "🎨 BUTTON STUDIO\n\n"
            "During Create Post, add as many URL buttons as you want.\n"
            "Telegram Bot API does not provide a free-form background-color setting for inline URL buttons."
        )

    elif data=="preview_draft":
        text=context.user_data.get("post_text")
        if not text:
            await q.message.reply_text("👁 No active draft.")
        else:
            await q.message.reply_text(
                "👁 PREVIEW\n\n"+text,
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
        context.user_data["button_label"]=update.message.text.strip()
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
            (context.user_data.get("button_label","Button"),url)
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
        await context.bot.send_message(
            chat_id=cid,
            text=text,
            reply_markup=button_markup(context.user_data.get("buttons",[]))
        )
        count=len(context.user_data.get("buttons",[]))
        context.user_data.clear()
        await update.message.reply_text(
            f"🚀 PUBLISHED SUCCESSFULLY\n\nButtons: {count}",
            reply_markup=main_menu()
        )
    except Exception:
        await update.message.reply_text(
            "❌ Publish failed.\n\n"
            "Make sure the bot is still an Admin in the Channel and has permission to post."
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
