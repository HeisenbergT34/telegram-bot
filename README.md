# K-Tech Somali Bot

A comprehensive Telegram bot for managing tech learning communities, with a focus on Somali language users.

## Features

### Educational Features

- **Challenges**: Multi-level programming and security challenges
- **Quizzes**: Interactive quizzes with scoring and statistics
- **Resources**: Educational resources for different technology categories
- **Tips**: Daily tech tips and best practices

### Group Management

- Automated message moderation
- Link filtering and spam protection
- User warnings and activity tracking
- Welcome messages and rules

### Language Support

- English-Somali translation for challenges and content
- OCR functionality for error screenshot processing

### Automated Engagement

- Scheduled tips, challenges, and polls
- Discussion facilitation and topic management

## Commands

- `/start` - Initialize the bot
- `/help` - Display available commands
- `/challenge` - Get a coding challenge
- `/quiz` - Take a quiz on various tech topics
- `/resources` - Access learning resources
- `/tip` - Get a random tech tip
- `/points` - Check your points
- `/leaderboard` - View top performers
- `/groupinfo` - Get group information
- `/rules` - View group rules
- `/quizstats` - View your quiz statistics

## Installation & Setup

1. **Prerequisites**:

   - Python 3.7 or higher
   - Telegram Bot Token from [@BotFather](https://t.me/BotFather)

2. **Installation**:

   ```
   pip install -r requirements.txt
   ```

3. **Configuration**:

   - Create a `.env` file with:
     ```
     BOT_TOKEN=your_telegram_bot_token
     GROUP_ID=your_group_id
     BOT_ADMINS=admin_id1 admin_id2
     ```

4. **Tesseract OCR Setup** (for error image processing):

   - Windows: Download and install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
   - Linux: `sudo apt install tesseract-ocr`
   - Set path in `.env` file:
     ```
     TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe  # Windows
     # TESSERACT_PATH=/usr/bin/tesseract  # Linux
     ```

5. **Running the Bot**:
   ```
   python bot.py
   ```

## Admin Commands

These commands can only be used by administrators defined in BOT_ADMINS:

- `/send_tip` - Manually trigger a tip message
- `/send_challenge` - Manually trigger a challenge
- `/send_poll` - Manually trigger a poll

## Project Structure

- `bot.py` - Main bot implementation
- `scheduler.py` - Scheduled tasks manager
- `callback_handlers.py` - Button callback handling
- `challenge_fetcher.py` - Challenge retrieval
- `discussion_manager.py` - Group discussion system
- `group_manager.py` - Group management functionality
- `quiz_handler.py` - Quiz processing system
- `tip_manager.py` - Tech tips handling

## Resources Directory

- `programming_challenges.json` - Coding challenges database
- `quizzes.json` - Quiz questions and answers
- `learning_resources.json` - Educational resources by category
- `tips.json` - Tech tips data
- `polls.json` - Poll questions and options
- `discussions.json` - Discussion topics

## Contributing

To add content to the bot:

1. **Adding Challenges**: Add new challenges to `resources/programming_challenges.json`
2. **Adding Quizzes**: Add new quiz questions to `resources/quizzes.json`
3. **Adding Resources**: Add new learning resources to `resources/learning_resources.json`
4. **Adding Tips**: Add new tips to `resources/tips.json`

## Customization

Edit `config.py` to customize:

- Message templates
- Scheduling intervals
- Security settings
- Group rules
- Category definitions

## License

This project is open source and available under the MIT License.
