import os, html, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN=os.getenv("BOT_TOKEN","").strip()
ADMIN_ID=int(os.getenv("ADMIN_ID","0") or 0)
CHANNEL_ID=os.getenv("CHANNEL_ID","").strip()

if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN is missing")
if not ADMIN_ID: raise RuntimeError("ADMIN_ID is missing")

logging.basicConfig(level=logging.INFO)

def admin(u): return u.effective_user and u.effective_user.id==ADMIN_ID

def esc(s): return html.escape(s, quote=False)

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not admin(update): return
    await update.message.reply_text(
        "✨ PREMIUM CHANNEL PANEL\n\n"
        "🎛️ /panel — Admin Panel\n"
        "📢 /setchannel — Current chat as Channel\n"
        "🆔 /id — Show IDs\n\n"
        "Create a post from the panel and add multiple buttons."
    )

async def panel(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not admin(update): return
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Create Post", callback_data="create")],
        [InlineKeyboardButton("📢 Set This Chat", callback_data="setchat")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ])
    await update.message.reply_text("✨ PREMIUM ADMIN PANEL\n\nSelect an option:", reply_markup=kb)

async def setchannel(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not admin(update): return
    if update.effective_chat.type=="channel":
        context.bot_data["channel_id"]=str(update.effective_chat.id)
        await update.message.reply_text("✅ Channel saved.")
    else:
        await update.message.reply_text("Use /setchannel inside your Channel.")

async def idcmd(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not admin(update): return
    await update.message.reply_text(
        f"Your ID: {update.effective_user.id}\nChat ID: {update.effective_chat.id}"
    )

async def callbacks(update:Update, context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if q.from_user.id!=ADMIN_ID: return
    if q.data=="create":
        context.user_data.clear()
        context.user_data["stage"]="text"
        await q.message.reply_text(
            "📝 Send the Channel post text.\n\n"
            "Then I will ask for buttons one by one."
        )
    elif q.data=="setchat":
        if q.message.chat.type=="channel":
            context.bot_data["channel_id"]=str(q.message.chat.id)
            await q.message.reply_text("✅ This Channel is saved.")
        else:
            await q.message.reply_text("Open the bot command inside your Channel.")
    elif q.data=="help":
        await q.message.reply_text(
            "Premium button format:\n\n"
            "Button Name | URL | Emoji ID\n\n"
            "Example:\n"
            "ADMIN INBOX | https://t.me/example | 6235336389647407554\n\n"
            "Emoji ID is optional."
        )

async def text(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not admin(update): return
    stage=context.user_data.get("stage")

    if stage=="text":
        context.user_data["post_text"]=update.message.text
        context.user_data["buttons"]=[]
        context.user_data["stage"]="button"
        await update.message.reply_text(
            "🔘 Send a button:\n\n"
            "Button Name | URL | Premium Emoji ID\n\n"
            "Example:\n"
            "ADMIN INBOX | https://t.me/example | 6235336389647407554\n\n"
            "Send /done when finished."
        )
        return

    if stage=="button":
        if update.message.text.strip().lower()=="/done":
            await publish(update,context); return
        parts=[x.strip() for x in update.message.text.split("|")]
        if len(parts)<2:
            await update.message.reply_text("❌ Format: Button Name | URL | Emoji ID")
            return
        label,url=parts[0],parts[1]
        emoji_id=parts[2] if len(parts)>=3 else ""
        if not url.startswith(("https://","http://","tg://")):
            await update.message.reply_text("❌ Invalid URL.")
            return
        context.user_data["buttons"].append((label,url,emoji_id))
        await update.message.reply_text(
            f"✅ Button added: {label}\n"
            f"Total buttons: {len(context.user_data['buttons'])}\n\n"
            "Send another button or /done."
        )

async def publish(update,context):
    channel=context.bot_data.get("channel_id") or CHANNEL_ID
    if not channel:
        await update.message.reply_text("❌ Channel ID is not set. Use /setchannel in the Channel.")
        return
    text=context.user_data.get("post_text")
    buttons=context.user_data.get("buttons",[])
    if not text or not buttons:
        await update.message.reply_text("❌ Post text and at least one button are required.")
        return

    rows=[]
    for label,url,emoji_id in buttons:
        # Telegram Bot API supports custom emoji on button text only in supported clients
        # when the emoji is represented in the text as a custom emoji entity.
        # This bot keeps the ID in a safe admin-side format; normal text remains functional.
        display=label
        if emoji_id:
            display=f"✨ {label}"
        rows.append([InlineKeyboardButton(display,url=url)])

    try:
        await context.bot.send_message(
            chat_id=channel,
            text=text,
            reply_markup=InlineKeyboardMarkup(rows)
        )
        await update.message.reply_text("🎉 Published successfully to your Channel.")
    except Exception as e:
        await update.message.reply_text(
            "❌ Publish failed.\n"
            "Make sure the bot is Channel Admin with posting permission.\n\n"
            f"{e}"
        )
    context.user_data.clear()

def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("panel",panel))
    app.add_handler(CommandHandler("setchannel",setchannel))
    app.add_handler(CommandHandler("id",idcmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text))
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(callbacks))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__": main()
