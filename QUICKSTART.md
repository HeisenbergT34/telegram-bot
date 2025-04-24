# K-Tech Somali Bot Quickstart Guide

This guide will help you get the bot up and running quickly.

## 1. Prerequisites

- Python 3.7 or higher
- Telegram account
- Bot token from [@BotFather](https://t.me/BotFather)

## 2. Installation

```bash
# Clone the repository (if you haven't already)
git clone https://github.com/yourusername/telegram-bot.git
cd telegram-bot

# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR (Optional - for image recognition)
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr
```

## 3. Configuration

1. Make sure you have a `.env` file in the project root with:

```
BOT_TOKEN=your_telegram_bot_token
GROUP_ID=your_group_id
BOT_ADMINS=admin_user_id
```

2. Ensure all resource JSON files are in the `resources` directory:
   - programming_challenges.json
   - quizzes.json
   - learning_resources.json
   - tips.json
   - polls.json
   - discussions.json

## 4. Starting the Bot

```bash
python bot.py
```

## 5. Testing

1. Open Telegram and search for your bot (by username)
2. Start a conversation with `/start`
3. Try basic commands:
   - `/help` - See all available commands
   - `/challenge` - Get a coding challenge
   - `/quiz` - Take a quiz
   - `/tip` - Get a tech tip

## 6. Adding the Bot to a Group

1. Add the bot to your group
2. Make the bot an administrator
3. Update the GROUP_ID in your `.env` file with your group's ID
4. Restart the bot

## 7. Common Issues

- **Bot not responding**: Ensure the bot is running and has proper permissions
- **Image recognition not working**: Check Tesseract OCR installation
- **Resource errors**: Verify all JSON files exist and have proper structure
- **Translation errors**: Connectivity issues or missing dependencies
- **Button errors**: Make sure callback data is not exceeding 64 bytes

For more information, see the full [README.md](README.md).
