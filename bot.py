import os, json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv("BOT_TOKEN","").strip()
ADMIN_ID=int(os.getenv("ADMIN_ID","0") or 0)
if not TOKEN: raise RuntimeError("BOT_TOKEN is missing")
if not ADMIN_ID: raise RuntimeError("ADMIN_ID is missing")

DATA_FILE="channels.json"

def load():
    try:
        with open(DATA_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: return {"channels":{}, "active":None}

def save(d):
    with open(DATA_FILE,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def admin(u): return bool(u.effective_user and u.effective_user.id==ADMIN_ID)

def panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Post",callback_data="new")],
        [InlineKeyboardButton("⚙️ Channel Manager",callback_data="cm")],
        [InlineKeyboardButton("🎨 Button Studio",callback_data="studio")],
        [InlineKeyboardButton("👁 Preview",callback_data="preview")]
    ])

def manager():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Connect Channel",callback_data="connect")],
        [InlineKeyboardButton("📋 Connected Channels",callback_data="list")],
        [InlineKeyboardButton("🔄 Switch Channel",callback_data="switch")],
        [InlineKeyboardButton("🗑 Remove Channel",callback_data="remove")],
        [InlineKeyboardButton("⬅️ Back",callback_data="back")]
    ])

async def start(update,context):
    if not admin(update): return
    await update.message.reply_text("✨ PREMIUM CHANNEL STUDIO\n\nWelcome to your control panel.",reply_markup=panel())

async def callbacks(update,context):
    q=update.callback_query
    await q.answer()
    if q.from_user.id!=ADMIN_ID:return
    d=load()

    if q.data=="cm":
        await q.message.reply_text("⚙️ CHANNEL MANAGER\n\nManage all connected Channels here.",reply_markup=manager())

    elif q.data=="back":
        await q.message.reply_text("✨ PREMIUM CHANNEL STUDIO",reply_markup=panel())

    elif q.data=="connect":
        context.user_data["waiting_connect"]=True
        await q.message.reply_text(
            "➕ CONNECT CHANNEL\n\n"
            "1. Add this bot as Administrator in your Channel.\n"
            "2. Give it permission to post messages.\n"
            "3. Forward any post from that Channel to this bot.\n\n"
            "Send/forward the Channel post here now."
        )

    elif q.data=="list":
        if not d["channels"]:
            await q.message.reply_text("📋 No Channels connected yet.",reply_markup=manager())
        else:
            lines=["📋 CONNECTED CHANNELS\n"]
            for cid,name in d["channels"].items():
                mark=" ⭐ ACTIVE" if str(d.get("active"))==str(cid) else ""
                lines.append(f"• {name} ({cid}){mark}")
            await q.message.reply_text("\n".join(lines),reply_markup=manager())

    elif q.data=="switch":
        if not d["channels"]:
            await q.message.reply_text("No connected Channels.",reply_markup=manager()); return
        rows=[[InlineKeyboardButton(("⭐ " if str(d.get("active"))==str(cid) else "")+name,callback_data=f"sw:{cid}")] for cid,name in d["channels"].items()]
        rows.append([InlineKeyboardButton("⬅️ Back",callback_data="cm")])
        await q.message.reply_text("🔄 SELECT ACTIVE CHANNEL",reply_markup=InlineKeyboardMarkup(rows))

    elif q.data.startswith("sw:"):
        cid=q.data[3:]
        if cid in d["channels"]:
            d["active"]=cid; save(d)
            await q.message.reply_text(f"✅ Active Channel: {d['channels'][cid]}",reply_markup=manager())

    elif q.data=="remove":
        if not d["channels"]:
            await q.message.reply_text("No connected Channels.",reply_markup=manager()); return
        rows=[[InlineKeyboardButton(name,callback_data=f"rm:{cid}")] for cid,name in d["channels"].items()]
        rows.append([InlineKeyboardButton("⬅️ Back",callback_data="cm")])
        await q.message.reply_text("🗑 SELECT CHANNEL TO REMOVE",reply_markup=InlineKeyboardMarkup(rows))

    elif q.data.startswith("rm:"):
        cid=q.data[3:]
        if cid in d["channels"]:
            context.user_data["remove_id"]=cid
            await q.message.reply_text(
                f"⚠️ Remove {d['channels'][cid]}?\nThis only removes it from this bot.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Confirm Remove",callback_data="confirm_rm"),
                     InlineKeyboardButton("❌ Cancel",callback_data="cm")]
                ])
            )

    elif q.data=="confirm_rm":
        cid=context.user_data.pop("remove_id",None)
        if cid and cid in d["channels"]:
            name=d["channels"].pop(cid)
            if str(d.get("active"))==str(cid):
                d["active"]=next(iter(d["channels"]),None)
            save(d)
            await q.message.reply_text(f"🗑 {name} removed.",reply_markup=manager())

    elif q.data=="studio":
        await q.message.reply_text(
            "🎨 BUTTON STUDIO\n\n"
            "Add multiple URL buttons to each post.\n"
            "Telegram does not expose a free-form background-color property for inline URL buttons."
        )

    elif q.data=="new":
        d=load()
        if not d["active"]:
            await q.message.reply_text("⚠️ First connect a Channel from ⚙️ Channel Manager.")
            return
        context.user_data={"stage":"text","buttons":[]}
        await q.message.reply_text(f"📝 Create Post for: {d['channels'][d['active']]}\n\nSend the post text.")

    elif q.data=="preview":
        t=context.user_data.get("text")
        if not t: await q.message.reply_text("No active draft.")
        else: await q.message.reply_text("👁 PREVIEW\n\n"+t,reply_markup=build(context.user_data.get("buttons",[])))

async def receive(update,context):
    if not admin(update): return
    if context.user_data.get("waiting_connect"):
        # Forwarded Channel posts expose origin chat in forward_origin on modern PTB.
        origin=getattr(update.message,"forward_origin",None)
        chat=getattr(origin,"chat",None)
        if chat and chat.type=="channel":
            d=load(); cid=str(chat.id); name=chat.title or "Channel"
            d["channels"][cid]=name
            if not d["active"]: d["active"]=cid
            save(d); context.user_data.clear()
            await update.message.reply_text(f"✅ Connected: {name}\n\nThis Channel is now available in Channel Manager.",reply_markup=manager())
        else:
            await update.message.reply_text("❌ I couldn't detect a Channel post. Forward a post directly from your Channel.")
        return

    stage=context.user_data.get("stage")
    if stage=="text":
        context.user_data["text"]=update.message.text
        context.user_data["stage"]="label"
        await update.message.reply_text("🔘 Send Button Name.\nExample: ADMIN INBOX\n\nSend /done to publish without a button.")
    elif stage=="label":
        context.user_data["label"]=update.message.text.strip()
        context.user_data["stage"]="url"
        await update.message.reply_text("🔗 Send Button URL.\nExample: https://t.me/example")
    elif stage=="url":
        url=update.message.text.strip()
        if not url.startswith(("https://","http://","tg://")):
            await update.message.reply_text("❌ Invalid URL. Try again."); return
        context.user_data["buttons"].append((context.user_data["label"],url))
        context.user_data["stage"]="label"
        await update.message.reply_text("✅ Button added.\nSend another Button Name or /done.")

async def done(update,context):
    if not admin(update):return
    d=load(); cid=d.get("active")
    if not cid or cid not in d["channels"]:
        await update.message.reply_text("❌ No active Channel."); return
    text=context.user_data.get("text")
    if not text: await update.message.reply_text("❌ No draft."); return
    try:
        await context.bot.send_message(chat_id=cid,text=text,reply_markup=build(context.user_data.get("buttons",[])))
        await update.message.reply_text("🚀 Published successfully!",reply_markup=panel())
    except Exception as e:
        await update.message.reply_text("❌ Publish failed. Check that the bot is Admin and can post.")
    context.user_data.clear()

def build(buttons):
    return InlineKeyboardMarkup([[InlineKeyboardButton(a,url=b)] for a,b in buttons]) if buttons else None

def main():
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("panel",start))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,receive))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__": main()
