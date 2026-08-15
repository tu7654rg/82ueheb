# Premium Telegram Channel Inline Button Bot

## Features
- Premium-style Admin Panel
- Multiple inline URL buttons
- Button layout with one button per row
- Optional Premium Custom Emoji ID field per button
- GitHub + Railway ready
- Polling deployment; no webhook/domain required

## Setup
1. Create bot with @BotFather.
2. Add bot as Channel Admin with posting permission.
3. Put `BOT_TOKEN` and `ADMIN_ID` in Railway Variables.
4. Deploy.
5. In the Channel, run `/setchannel`.
6. In private bot chat, run `/panel`.
7. Create post, then add buttons.

Button input:
`Button Name | https://example.com | PremiumEmojiID`

Example:
`ADMIN INBOX | https://t.me/example | 6235336389647407554`

Important:
Telegram does not provide a Bot API setting to freely choose the background color of inline URL buttons. The design therefore uses Telegram-supported inline buttons and Premium-style UI. The emoji ID is retained for future custom-emoji rendering support; simply putting an ID into Button API text does not itself create a custom emoji entity.
