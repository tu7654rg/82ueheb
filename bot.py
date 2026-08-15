import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, ConversationHandler

TOKEN=os.getenv("BOT_TOKEN","").strip()
ADMIN_ID=int(os.getenv("ADMIN_ID","0") or 0)
CHANNEL_ID=os.getenv("CHANNEL_ID","").strip()

if not TOKEN: raise RuntimeError("BOT_TOKEN is missing")
if not ADMIN_ID: raise RuntimeError("ADMIN_ID is missing")

TEXT, LABEL, URL = range(3)

def admin(u):
    return bool(u.effective_user and u.effective_user.id == ADMIN_ID)

def target(context):
    return context.bot_data.get("channel_id") or CHANNEL_ID

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Create Post", callback_data="new")],
        [InlineKeyboardButton("🎨 Button Studio", callback_data="studio"),
         InlineKeyboardButton("⚙️ Channel", callback_data="channel")],
        [InlineKeyboardButton("👁 Preview", callback_data="preview"),
         InlineKeyboardButton("🗑 Cancel", callback_data="cancel")]
    ])

async def start(update, context):
    if not admin(update): return
    await update.message.reply_text(
        "✨ PREMIUM CHANNEL STUDIO\n\n"
        "Create Channel posts and inline buttons easily.",
        reply_markup=menu()
    )

async def panel(update, context):
    if not admin(update): return
    await update.message.reply_text("✨ PREMIUM CHANNEL STUDIO\n\nSelect an option:", reply_markup=menu())

async def setchannel(update, context):
    if not admin(update): return
    if update.effective_chat.type != "channel":
        await update.message.reply_text("⚠️ Use /setchannel inside the target Channel.")
        return
    context.bot_data["channel_id"] = str(update.effective_chat.id)
    await update.message.reply_text("✅ Channel connected successfully.")

async def ids(update, context):
    if not admin(update): return
    await update.message.reply_text(f"Your ID: {update.effective_user.id}\nChat ID: {update.effective_chat.id}")

async def callbacks(update, context):
    q=update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    if q.data=="new":
        context.user_data.clear()
        context.user_data["buttons"]=[]
        await q.message.reply_text("📝 Send your Channel post text.")
        return TEXT
    if q.data=="studio":
        await q.message.reply_text(
            "🎨 BUTTON STUDIO\n\n"
            "You can add unlimited URL buttons.\n"
            "Telegram does not allow bots to freely set inline-button background colors."
        )
    elif q.data=="channel":
        await q.message.reply_text(f"⚙️ Connected Channel: {target(context) or 'Not connected'}")
    elif q.data=="preview":
        t=context.user_data.get("text")
        if not t:
            await q.message.reply_text("No active draft.")
        else:
            await q.message.reply_text("👁 PREVIEW\n\n"+t, reply_markup=markup(context.user_data.get("buttons",[])))
    elif q.data=="cancel":
        context.user_data.clear()
        await q.message.reply_text("🗑 Draft cancelled.", reply_markup=menu())

async def get_text(update, context):
    if not admin(update): return ConversationHandler.END
    context.user_data["text"]=update.message.text
    await update.message.reply_text("🔘 Send button name.\nExample: ADMIN INBOX\n\nSend /done to publish without more buttons.")
    return LABEL

async def get_label(update, context):
    if not admin(update): return ConversationHandler.END
    if update.message.text.strip().lower()=="/done":
        return await publish(update,context)
    context.user_data["label"]=update.message.text.strip()
    await update.message.reply_text("🔗 Send button URL.\nExample: https://t.me/example")
    return URL

async def get_url(update, context):
    if not admin(update): return ConversationHandler.END
    u=update.message.text.strip()
    if not u.startswith(("https://","http://","tg://")):
        await update.message.reply_text("❌ Invalid URL. Try again.")
        return URL
    context.user_data["buttons"].append((context.user_data["label"],u))
    await update.message.reply_text("✅ Button added.\nSend another button name, or /done to publish.")
    return LABEL

def markup(buttons):
    if not buttons: return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(a,url=b)] for a,b in buttons])

async def publish(update, context):
    cid=target(context)
    text=context.user_data.get("text")
    buttons=context.user_data.get("buttons",[])
    if not cid:
        await update.message.reply_text("❌ No Channel connected. Run /setchannel inside the Channel.")
        return ConversationHandler.END
    try:
        await context.bot.send_message(chat_id=cid,text=text,reply_markup=markup(buttons))
        await update.message.reply_text(f"🚀 Published successfully!\nButtons: {len(buttons)}", reply_markup=menu())
    except Exception:
        await update.message.reply_text("❌ Publish failed. Check Channel Admin permissions.")
    context.user_data.clear()
    return ConversationHandler.END

def main():
    app=Application.builder().token(TOKEN).build()
    conv=ConversationHandler(
        entry_points=[CallbackQueryHandler(callbacks,pattern="^new$")],
        states={
            TEXT:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_text)],
            LABEL:[MessageHandler(filters.TEXT,get_label)],
            URL:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_url)]
        },
        fallbacks=[CommandHandler("done",publish), CommandHandler("cancel",lambda u,c: ConversationHandler.END)],
        per_user=True, per_chat=True
    )
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("panel",panel))
    app.add_handler(CommandHandler("setchannel",setchannel))
    app.add_handler(CommandHandler("id",ids))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(callbacks))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
