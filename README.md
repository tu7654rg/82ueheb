# Inline Button Bot

## Features
- Multiple inline buttons per message
- 2 buttons per row
- Message description with Telegram custom/premium emoji entities preserved
- Optional custom emoji ID storage for button records
- Channel Management: Add / Remove / View Connected Channels
- Preview
- Send to connected channel
- SQLite storage

## Setup
Set:
BOT_TOKEN=your_bot_token

Then:
pip install -r requirements.txt
python bot.py

For channel sending, add the bot as an administrator in the target channel with permission to post messages.

## Important Telegram limitation
Telegram Bot API inline keyboard button labels do not support MessageEntity custom_emoji entities. Therefore a premium/custom emoji ID can be stored with a button, but it cannot be rendered as a true custom-emoji entity inside the button label. Custom/premium emojis in the message description are preserved through Telegram message entities.
