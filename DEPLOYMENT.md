# K-Tech Somali Bot Deployment Guide

## Prerequisites

- Python 3.7 or higher
- Bot token from BotFather
- Target group ID

## Local Setup and Testing

1. Clone the repository

   ```
   git clone https://github.com/yourusername/telegram-bot.git
   cd telegram-bot
   ```

2. Create a virtual environment

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies

   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your bot token

   ```
   BOT_TOKEN=your_bot_token_here
   ```

5. Update the target group ID in `config.py`

   ```python
   GROUP_ID = -1001234567890  # Replace with your real group ID
   ```

6. Test the bot locally
   ```
   python bot.py
   ```

## Deployment Options

### Option 1: Oracle Cloud Free Tier (Recommended)

1. Sign up for an Oracle Cloud account at https://www.oracle.com/cloud/free/

   - This requires a credit card but won't charge you
   - You get 2 small VMs forever free

2. Create an Always Free compute instance (Ubuntu 20.04)

   - Select "Always Free Eligible" instance (VM.Standard.E2.1.Micro)
   - Create SSH keys and download them
   - Allow SSH traffic in security list

3. SSH into your server

   ```
   ssh -i /path/to/private_key ubuntu@your_server_ip
   ```

4. Install Python and dependencies

   ```
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git
   ```

5. Clone the repository

   ```
   git clone https://github.com/yourusername/telegram-bot.git
   cd telegram-bot
   ```

6. Create a virtual environment and install dependencies

   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

7. Create a `.env` file with your bot token

   ```
   echo "BOT_TOKEN=your_bot_token_here" > .env
   ```

8. Create a systemd service to keep the bot running

   ```
   sudo cp telegram-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-bot.service
   sudo systemctl start telegram-bot.service
   ```

9. Check the status of your bot

   ```
   sudo systemctl status telegram-bot.service
   ```

10. View logs
    ```
    sudo journalctl -u telegram-bot.service -f
    ```

### Option 2: PythonAnywhere (Easy Setup)

1. Sign up for a free PythonAnywhere account at https://www.pythonanywhere.com/

2. Go to the "Files" tab and upload your bot files or use git:

   ```
   git clone https://github.com/yourusername/telegram-bot.git
   ```

3. Create a `.env` file with your bot token

   ```
   BOT_TOKEN=your_bot_token_here
   ```

4. Go to the "Tasks" tab and create a new Always-on task

   - Command: `cd ~/telegram-bot && python3 bot.py`
   - Select "Daily"

5. The task will now run continuously and restart daily

### Option 3: Railway.app (Easiest Setup)

1. Sign up for a Railway account at https://railway.app/

   - Connect your GitHub account

2. Create a new project and select your GitHub repository

3. Add your bot token as an environment variable

   - Variable name: `BOT_TOKEN`
   - Value: your bot token

4. Deploy the project

   - Railway will automatically build and run your bot

5. Your bot is now running 24/7

## Maintenance

### Updating the Bot

1. Make changes to your code locally and test
2. Push changes to your GitHub repository
3. Pull changes on your server (if using Oracle or PythonAnywhere)
   ```
   cd ~/telegram-bot
   git pull
   ```
4. Restart the bot
   - On Oracle Cloud: `sudo systemctl restart telegram-bot.service`
   - On PythonAnywhere: Restart the "Always-on task"
   - On Railway: Automatic redeploy on Git push

### Checking Logs

- Oracle Cloud: `sudo journalctl -u telegram-bot.service -f`
- PythonAnywhere: Check the task log in the "Tasks" tab
- Railway: View logs in the project dashboard

## Troubleshooting

### Bot Not Responding

1. Check if the bot is running
2. Verify the bot token is correct
3. Ensure the bot has been added to the target group with proper permissions

### Bot Crashing

1. Check the logs for errors
2. Make sure all dependencies are installed
3. Verify you have the latest code

### Rate Limiting

If you encounter Telegram API rate limiting:

1. Avoid sending too many messages in short periods
2. Add random delays between operations
3. Implement exponential backoff for retries
