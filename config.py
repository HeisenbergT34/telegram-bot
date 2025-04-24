"""Configuration settings for the bot."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Admin Configuration
ADMIN_IDS = [
    5550928376,  # Real admin Telegram ID
]

# Bot Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')  # Using environ.get instead of getenv
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found in environment variables")

# Group Configuration
GROUP_ID = -1001992980193  # Real group ID
TARGET_GROUPS = [GROUP_ID]  # Groups for automated messages

# Scheduler Timings (in hours)
TIP_INTERVAL_HOURS = 24  # Daily tips
CHALLENGE_INTERVAL_HOURS = 48  # Challenges every 2 days
POLL_INTERVAL_HOURS = 72  # Polls every 3 days

# Scheduler Manual Trigger Settings
MANUAL_TRIGGER_COOLDOWN = 3600  # 1 hour cooldown between manual triggers
MANUAL_TRIGGER_MAX_PER_DAY = 5  # Maximum manual triggers per day per admin

# Group Feature Settings
WELCOME_MESSAGE = """👋 Welcome to K-Tech Somali!
Join us in learning and growing together.
Use /help to see available commands."""

# Group Rules
GROUP_RULES = """📜 *Group Rules*
1. Be respectful to all members
2. No spam or self-promotion
3. Stay on topic (tech & programming)
4. Use English or Somali.
5. Share knowledge and help others"""

# Group Activity Settings
MIN_MEMBERS_FOR_POLL = 2
POLL_DURATION = 3600  # 1 hour
DISCUSSION_DURATION = 7200  # 2 hours
AUTO_DELETE_WARNINGS = True
RESTRICT_DURATION_DAYS = 2  # Restrict users for 2 days instead of banning
NOTIFY_GROUP_ON_DELETION = False  # Whether to notify the group when a message is deleted

# Group Message Templates
CHALLENGE_ANNOUNCEMENT = """✨ *K-TECH SOMALI CHALLENGE* ✨
━━━━━━━━━━━━━━━
{content}
#CodingChallenge #KTechSomali"""

TIP_ANNOUNCEMENT = """💡 *K-TECH DAILY TIP* 💡
━━━━━━━━━━━━━━━
{content}
#TechTip #KTechSomali"""

POLL_ANNOUNCEMENT = """📊 *K-TECH SOMALI POLL* 📊
━━━━━━━━━━━━━━━
{content}
#TechPoll #KTechSomali"""

# Categories
CHALLENGE_CATEGORIES = {
    'programming': 'Programming',
    'web_development': 'Web Development',
    'databases': 'Databases',
    'algorithms': 'Algorithms',
    'security': 'Security'
}

RESOURCE_CATEGORIES = {
    'programming_basics': 'Programming Fundamentals',
    'web_development': 'Web Development',
    'cybersecurity': 'Cybersecurity',
    'data_science': 'Data Science',
    'mobile_dev': 'Mobile Development',
    'cloud_computing': 'Cloud Computing',
    'devops': 'DevOps',
    'machine_learning': 'Machine Learning'
}

TIP_CATEGORIES = {
    'security': 'Security Tips',
    'programming': 'Programming Tips',
    'best_practices': 'Best Practices',
    'career': 'Career Tips',
    'tools': 'Development Tools'
}

QUIZ_CATEGORIES = {
    'programming': 'Programming Concepts',
    'security': 'Security Concepts',
    'networking': 'Networking',
    'databases': 'Databases',
    'algorithms': 'Algorithms'
}

# Rate Limiting
MAX_MESSAGES_PER_MINUTE = 5
MAX_WARNINGS = 3  # After 3 warnings, user gets temporarily restricted

# Security Settings
TRUSTED_DOMAINS = [
    'github.com',
    'stackoverflow.com',
    'medium.com',
    'dev.to',
    'freecodecamp.org',
    'w3schools.com',
    'mozilla.org',
    'python.org',
    'docs.python.org'
]

# Allowed domains can bypass link filtering
ALLOWED_DOMAINS = TRUSTED_DOMAINS

# Message Moderation
DELETE_MESSAGES_CONTAINING = [
    'http://',  # Block non-HTTPS links
    'porn',
    'xxx',
    'sex',
    'drugs',
    'gambling'
]

# Spam Protection
SPAM_WORDS = [
    "spam", "advertise", "promotion", "buy now", "click here",
    "make money", "earn money", "win prize", "lottery", "casino",
    "get rich", "free money", "investment opportunity"
]

# Group configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')

# Feature Settings
TIP_INTERVAL_HOURS = 24  # Send tips every 24 hours
POLL_INTERVAL_HOURS = 72  # Send polls every 72 hours

# Blocked domains for link filtering
BLOCKED_DOMAINS = [
    'example.com',
    'spam.com'
]

# Translation settings
TRANSLATION_CACHE_DURATION = 24 * 60 * 60  # 24 hours in seconds

# Poll settings
MAX_POLL_OPTIONS = 5
MIN_POLL_VOTES = 3
POLL_DURATION = 3600  # 1 hour in seconds

# Discussion settings
DISCUSSION_DURATION = 7200  # 2 hours in seconds 