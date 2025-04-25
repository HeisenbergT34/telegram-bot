"""
K-Tech Somali Bot - A Telegram bot for managing tech learning communities.
"""
import logging
import asyncio
import sqlite3
import json
import re
import os
import sys
import signal
import random
from datetime import datetime, timedelta, time
from collections import defaultdict
from urllib.parse import urlparse
import html
import tempfile
from PIL import Image
import pytesseract
from PIL import ImageEnhance
from typing import Optional, List
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery, Bot, ChatPermissions
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ChatMemberHandler
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter
from telegram.request import HTTPXRequest
import telegram
from deep_translator import GoogleTranslator
import psutil

import config
from scheduler import ScheduleManager
from utils.content_validator import ContentValidator

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add handler to also log to a file
file_handler = logging.FileHandler('bot.log')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

class DatabaseManager:
    """Manage database operations."""
    
    def __init__(self):
        """Initialize database connection."""
        self.conn = sqlite3.connect('bot.db')
        self.cursor = self.conn.cursor()
        self.setup_database()
    
    def setup_database(self):
        """Create necessary tables if they don't exist."""
        # User points and progress
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_points (
                user_id INTEGER PRIMARY KEY,
                points INTEGER DEFAULT 0,
                last_updated TIMESTAMP,
                completed_challenges TEXT DEFAULT '[]'
            )
        ''')
        
        # Challenge tracking
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS challenge_progress (
                user_id INTEGER,
                challenge_id TEXT,
                category TEXT,
                difficulty TEXT,
                completed BOOLEAN DEFAULT FALSE,
                completion_date TIMESTAMP,
                PRIMARY KEY (user_id, challenge_id)
            )
        ''')
        
        # Quiz tracking
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_progress (
                user_id INTEGER,
                quiz_id TEXT,
                category TEXT,
                correct BOOLEAN,
                points_earned INTEGER DEFAULT 0,
                attempt_date TIMESTAMP,
                answer TEXT,
                PRIMARY KEY (user_id, quiz_id)
            )
        ''')
        
        # Quiz history
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                quiz_id TEXT,
                category TEXT,
                attempt_count INTEGER DEFAULT 1,
                last_attempt_date TIMESTAMP,
                best_score INTEGER DEFAULT 0,
                FOREIGN KEY (user_id, quiz_id) REFERENCES quiz_progress (user_id, quiz_id)
            )
        ''')
        
        # Translation cache
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS translation_cache (
                original_text TEXT PRIMARY KEY,
                translated_text TEXT,
                language TEXT,
                timestamp TIMESTAMP
            )
        ''')
        
        # Group management
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_settings (
                group_id INTEGER PRIMARY KEY,
                welcome_message TEXT,
                rules TEXT,
                spam_protection BOOLEAN DEFAULT TRUE,
                link_filter BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # User warnings
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_warnings (
                user_id INTEGER,
                group_id INTEGER,
                warning_count INTEGER DEFAULT 0,
                last_warning TIMESTAMP,
                reason TEXT,
                PRIMARY KEY (user_id, group_id)
            )
        ''')
        
        self.conn.commit()
    
    def get_user_progress(self, user_id: int) -> dict:
        """Get user's challenge progress."""
        self.cursor.execute(
            "SELECT completed_challenges FROM user_points WHERE user_id = ?",
            (user_id,)
        )
        result = self.cursor.fetchone()
        if result:
            return json.loads(result[0])
        return []
    
    def update_challenge_progress(self, user_id: int, challenge_id: str, 
                                category: str, difficulty: str, completed: bool = True):
        """Update user's challenge progress."""
        timestamp = datetime.now().isoformat()
        self.cursor.execute('''
            INSERT OR REPLACE INTO challenge_progress 
            (user_id, challenge_id, category, difficulty, completed, completion_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, challenge_id, category, difficulty, completed, timestamp))
        self.conn.commit()
    
    def get_translation(self, text: str, language: str = 'so') -> str:
        """Get cached translation if available."""
        self.cursor.execute(
            "SELECT translated_text FROM translation_cache WHERE original_text = ? AND language = ?",
            (text, language)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def cache_translation(self, original: str, translated: str, language: str = 'so'):
        """Cache a translation."""
        timestamp = datetime.now().isoformat()
        self.cursor.execute('''
            INSERT OR REPLACE INTO translation_cache 
            (original_text, translated_text, language, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (original, translated, language, timestamp))
        self.conn.commit()
    
    def add_warning(self, user_id: int, group_id: int, reason: str):
        """Add a warning for a user in a group."""
        self.cursor.execute('''
            INSERT INTO user_warnings (user_id, group_id, warning_count, last_warning, reason)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT (user_id, group_id) DO UPDATE SET
            warning_count = warning_count + 1,
            last_warning = excluded.last_warning,
            reason = excluded.reason
        ''', (user_id, group_id, datetime.now().isoformat(), reason))
        self.conn.commit()
    
    def get_warnings(self, user_id: int, group_id: int) -> int:
        """Get number of warnings for a user in a group."""
        self.cursor.execute(
            "SELECT warning_count FROM user_warnings WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        )
        result = self.cursor.fetchone()
        return result[0] if result else 0

    def record_quiz_attempt(self, user_id: int, quiz_id: str, category: str, 
                          correct: bool, points: int, answer: str):
        """Record a quiz attempt in the database."""
        timestamp = datetime.now().isoformat()
        
        # Record the attempt in quiz_progress
        self.cursor.execute('''
            INSERT INTO quiz_progress 
            (user_id, quiz_id, category, correct, points_earned, attempt_date, answer)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, quiz_id) DO UPDATE SET
            correct = ?,
            points_earned = CASE WHEN points_earned < ? THEN ? ELSE points_earned END,
            attempt_date = ?,
            answer = ?
        ''', (
            user_id, quiz_id, category, correct, points, timestamp, answer,
            correct, points, points, timestamp, answer
        ))
        
        # Update quiz history
        self.cursor.execute('''
            INSERT INTO quiz_history 
            (user_id, quiz_id, category, attempt_count, last_attempt_date, best_score)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT (user_id, quiz_id) DO UPDATE SET
            attempt_count = attempt_count + 1,
            last_attempt_date = ?,
            best_score = CASE WHEN best_score < ? THEN ? ELSE best_score END
        ''', (
            user_id, quiz_id, category, timestamp, points,
            timestamp, points, points
        ))
        
        # Update total user points
        self.cursor.execute('''
            INSERT INTO user_points (user_id, points, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            points = points + ?,
            last_updated = ?
        ''', (
            user_id, points, timestamp,
            points if correct else 0, timestamp
        ))
        
        self.conn.commit()
    
    def get_quiz_stats(self, user_id: int) -> dict:
        """Get quiz statistics for a user."""
        self.cursor.execute('''
            SELECT 
                COUNT(*) as total_attempts,
                SUM(CASE WHEN correct THEN 1 ELSE 0 END) as correct_answers,
                SUM(points_earned) as total_points,
                COUNT(DISTINCT category) as categories_attempted
            FROM quiz_progress
            WHERE user_id = ?
        ''', (user_id,))
        
        result = self.cursor.fetchone()
        if result:
            return {
                'total_attempts': result[0],
                'correct_answers': result[1] or 0,
                'total_points': result[2] or 0,
                'categories_attempted': result[3],
                'accuracy': (result[1] / result[0] * 100) if result[0] > 0 else 0
            }
        return {
            'total_attempts': 0,
            'correct_answers': 0,
            'total_points': 0,
            'categories_attempted': 0,
            'accuracy': 0
        }
    
    def get_quiz_history(self, user_id: int, category: str = None, limit: int = 10) -> list:
        """Get recent quiz history for a user."""
        query = '''
            SELECT 
                qp.quiz_id,
                qp.category,
                qp.correct,
                qp.points_earned,
                qp.attempt_date,
                qh.attempt_count,
                qh.best_score
            FROM quiz_progress qp
            JOIN quiz_history qh ON qp.user_id = qh.user_id AND qp.quiz_id = qh.quiz_id
            WHERE qp.user_id = ?
        '''
        params = [user_id]
        
        if category:
            query += ' AND qp.category = ?'
            params.append(category)
        
        query += ' ORDER BY qp.attempt_date DESC LIMIT ?'
        params.append(limit)
        
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

class CustomMessageHandler:
    """Handle message processing and moderation."""
    
    def __init__(self, db_manager: DatabaseManager, bot=None):
        self.user_message_counts = defaultdict(list)
        self.db_manager = db_manager
        self.spam_tracker = defaultdict(list)
        self.recently_warned_users = set()  # Initialize the set to track recently warned users
        self.bot = bot  # Store reference to the bot
        # Comprehensive regex pattern for URLs
        self.link_pattern = re.compile(
            r'(?:(?:https?:\/\/)?'  # Optional protocol
            r'(?:(?:[\w-]+\.)+[\w-]+|'  # domain name
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP address
            r'(?::\d+)?'  # Optional port
            r'(?:\/\S*)?)',  # Optional path
            re.IGNORECASE
        )

    def check_spam(self, user_id: int, message_time: datetime) -> bool:
        """Check if user is spamming."""
        self.user_message_counts[user_id] = [
            time for time in self.user_message_counts[user_id]
            if (message_time - time).total_seconds() < 60
        ]
        self.user_message_counts[user_id].append(message_time)
        return len(self.user_message_counts[user_id]) > config.MAX_MESSAGES_PER_MINUTE

    async def check_links(self, message: Message) -> tuple[bool, str]:
        """Check for unauthorized links in message."""
        if not message.text and not message.caption:
            return False, ""
            
        text = message.text or message.caption
        
        # Use multiple pattern matching approaches for better coverage
        # 1. Standard URL detection with the existing pattern
        standard_links = self.link_pattern.findall(text)
        
        # 2. Specific patterns for common platforms
        telegram_links = re.findall(r'(?:t\.me|telegram\.me|telegram\.dog)\/\S+', text, re.IGNORECASE)
        shorteners = re.findall(r'(?:bit\.ly|tinyurl\.com|goo\.gl|is\.gd|t\.co)\/\S+', text, re.IGNORECASE)
        
        # 3. Domain mentions without protocol (example.com format)
        domain_mentions = re.findall(r'\b[\w-][\w-]+\.[a-zA-Z]{2,}\b', text)
        
        # 4. Telegram username mentions
        mentions = re.findall(r'@[\w_]+', text)
        
        # Combine all detected links
        all_links = standard_links + telegram_links + shorteners + domain_mentions + mentions
        
        # Optional: Filter out allowed mentions if needed
        allowed_mentions = [f"@{config.BOT_USERNAME}"] if hasattr(config, 'BOT_USERNAME') else []
        all_links = [link for link in all_links if link not in allowed_mentions]
        
        # Log all detected links for debugging
        if all_links:
            # Group links by type for better logging
            link_types = {
                'Standard URLs': standard_links,
                'Telegram links': telegram_links,
                'URL shorteners': shorteners,
                'Domain mentions': domain_mentions,
                'Username mentions': mentions
            }
            logger.info(f"Found potential links in message: {link_types}")
            
            # Check if any whitelisted domains should be allowed
            if hasattr(config, 'ALLOWED_DOMAINS'):
                # Keep only links that aren't in allowed domains
                filtered_links = []
                for link in all_links:
                    is_allowed = False
                    for allowed_domain in config.ALLOWED_DOMAINS:
                        if allowed_domain.lower() in link.lower():
                            is_allowed = True
                            break
                    if not is_allowed:
                        filtered_links.append(link)
                
                if not filtered_links:  # All links were allowed
                    return False, ""
                all_links = filtered_links
            
            return True, (
                "⚠️ Links, URLs, or external references are not allowed in this group "
                "for security reasons.\n\n"
                "If you need to share programming resources, please use:\n"
                "1. Code snippets directly in the chat\n"
                "2. Contact an admin to post the link for you\n"
                "3. Use private messaging for sharing links"
            )
        
        return False, ""

    async def moderate_message(self, message: Message) -> tuple[bool, str]:
        """
        Moderate a message and return True if it should be deleted, along with the warning message.
        """
        # Log message for debugging
        log_content = message.text or message.caption or "No text content"
        logger.info(f"Moderating message from {message.from_user.id} in {message.chat.id}: {log_content[:50]}...")
        
        # If message is in private chat, allow all content
        if message.chat.type == "private":
            return False, ""
            
        # Skip moderation of media types if needed
        if message.photo and hasattr(config, 'ALLOW_IMAGES') and config.ALLOW_IMAGES:
            logger.info("Allowing photo as per configuration")
            return False, ""
                
        if message.video and hasattr(config, 'ALLOW_VIDEOS') and config.ALLOW_VIDEOS:
            logger.info("Allowing video as per configuration")
            return False, ""
                
        if message.document and hasattr(config, 'ALLOW_DOCUMENTS') and config.ALLOW_DOCUMENTS:
            logger.info("Allowing document as per configuration")
            return False, ""

        # Check for unauthorized links
        has_link, warning_message = await self.check_links(message)
        if has_link:
            # Add the user to a temporary warning list to avoid duplicate warnings
            user_id = message.from_user.id
            if user_id not in self.recently_warned_users:
                self.recently_warned_users.add(user_id)
                
                # Schedule removal from warning list after certain time
                asyncio.create_task(self.remove_from_warned(user_id, 60))
                
                # Add reference to the original message for context
                warning_with_context = (
                    f"Your message in {message.chat.title} was removed because it "
                    f"contained a potential link or external reference.\n\n{warning_message}"
                )
                
                # We'll let the TelegramBot class handle the actual sending of warnings
                # since we now just return the warning message along with the delete flag
                return True, warning_message

        return False, ""

    async def remove_from_warned(self, user_id: int, delay: int):
        """Remove a user from the recently warned list after a delay."""
        await asyncio.sleep(delay)
        self.recently_warned_users.discard(user_id)

class TelegramBot:
    """Main bot class."""
    
    def __init__(self, token: str):
        """Initialize the bot."""
        self.token = token
        self.application = (
            Application.builder()
            .token(token)
            .get_updates_request(HTTPXRequest(
                connection_pool_size=8,
                # timeout parameter removed - not supported in newer versions
            ))
            .build()
        )
        self.db_manager = DatabaseManager()
        self.msg_handler = CustomMessageHandler(self.db_manager, self)
        self.challenges_cache = None
        
        # Configure Tesseract path - adjust this path based on your system
        if os.name == 'nt':  # Windows
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        # On Linux/Mac, Tesseract should be in PATH
        
        logger.info("Bot initialized with database-backed challenge tracking")
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command and message handlers."""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("challenge", self.challenge_command))
        self.application.add_handler(CommandHandler("quiz", self.quiz_command))
        self.application.add_handler(CommandHandler("resources", self.resources_command))
        self.application.add_handler(CommandHandler("tip", self.tip_command))
        self.application.add_handler(CommandHandler("points", self.points_command))
        self.application.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))
        self.application.add_handler(CommandHandler("groupinfo", self.group_info_command))
        self.application.add_handler(CommandHandler("rules", self.rules_command))
        self.application.add_handler(CommandHandler("quizstats", self.quiz_stats_command))
        self.application.add_handler(CommandHandler("progress", self.progress_command))

        # Group event handlers
        self.application.add_handler(ChatMemberHandler(self.handle_member_join, ChatMemberHandler.CHAT_MEMBER))
        
        # Message handlers - handle ALL types of messages
        self.application.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND,  # Handle all non-command messages
            self.handle_message
        ))
        
        # Callback query handlers
        callback_handlers = {
            'quiz_': self.handle_quiz_selection,
            'quiz_answer_': self.handle_quiz_answer,
            'quiz_hint_': self.handle_quiz_hint,
            'quiz_submit_': self.handle_quiz_submit,
            'challenge_select_': self.handle_challenge_button,
            'challenge_hint_': self.handle_challenge_button,
            'challenge_submit_': self.handle_challenge_button,
            'challenge_another_': self.handle_challenge_button,
            'challenge_category_': self.handle_challenge_category,  # Legacy format
            'challenge_diff_': self.handle_challenge_difficulty,    # Legacy format
            'challenge_translate_': self.handle_challenge_button,   # For translation
            'challenge_categories': self.handle_challenge_categories,  # Back to categories list
            'resource_': self.handle_resource_category
        }
        
        for prefix, handler in callback_handlers.items():
            self.application.add_handler(CallbackQueryHandler(
                handler,
                pattern=f"^{prefix}"
            ))

        # Error handler
        self.application.add_error_handler(self.error_handler)

    async def start(self):
        """Start the bot."""
        try:
            # Initialize bot instance and store it in the message handler
            await self.application.initialize()
            bot = self.application.bot
            self.msg_handler.bot = bot
            
            # Load challenges on startup
            self.load_challenges()
            
            # Setup scheduled tasks
            job_queue = self.application.job_queue
            
            # Check if this is the first run and send introduction if it is
            await self.first_time_setup()
            
            # Start the application
            await self.application.start()
            
            # Delete webhook and drop pending updates
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            
            # Start polling with clean start
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            
            # Initialize and start scheduler
            self.scheduler = ScheduleManager(self.application, self)
            await self.scheduler.start_scheduler()
            
            # Create stop event
            stop_event = asyncio.Event()
            
            def signal_handler(sig, frame):
                """Handle shutdown signals."""
                logger.info("Received shutdown signal")
                stop_event.set()
            
            # Set up signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, signal_handler)
            
            logger.info("Bot is running. Press Ctrl+C to stop")
            await stop_event.wait()
            
        except Exception as e:
            logger.error(f"Bot stopped due to error: {e}", exc_info=True)
            raise
        finally:
            # Ensure proper cleanup
            try:
                logger.info("Shutting down...")
                if hasattr(self, 'scheduler'):
                    self.scheduler.stop_scheduler()
                if hasattr(self.application, 'updater') and self.application.updater.running:
                    await self.application.updater.stop()
                if hasattr(self.application, 'stop'):
                    await self.application.stop()
                if hasattr(self.application, 'shutdown'):
                    await self.application.shutdown()
                logger.info("Bot stopped gracefully")
                # Clean up PID file
                try:
                    os.remove('bot.pid')
                except OSError:
                    pass
            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in the dispatcher."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Send error message to developer
        if context.error:
            tb_string = traceback.format_exception(None, context.error, context.error.__traceback__)
            message = f"⚠️ Exception caught: {context.error}\n\n{''.join(tb_string)}"
            for admin_id in config.ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=message[:4000])
                except Exception as e:
                    logger.error(f"Failed to send error message to admin {admin_id}: {e}")
    
    async def _delete_after_delay(self, message, delay_seconds: int):
        """Helper to delete messages after a delay."""
        try:
            await asyncio.sleep(delay_seconds)
            await message.delete()
        except Exception as e:
            logger.error(f"Failed to delete message after delay: {e}")

    async def first_time_setup(self):
        """Check if this is the first run and send introduction if needed."""
        try:
            first_run_file = 'first_run.txt'
            
            # Check if the bot has run before
            if not os.path.exists(first_run_file):
                logger.info("First time setup - sending introduction message")
                
                # Send introduction message to each target group
                intro_message = (
                    "👋 *K-TECH SOMALI BOT INTRODUCTION* 👋\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Assalamu Alaykum! I'm the K-Tech Somali Bot, your interactive learning assistant.\n\n"
                    "*What I can do:*\n"
                    "• Share regular programming challenges\n"
                    "• Post quizzes to test your knowledge\n"
                    "• Send useful tech tips\n" 
                    "• Create polls to engage the community\n"
                    "• Provide learning resources in Somali and English\n\n"
                    "*Commands you can use:*\n"
                    "/challenge - Get a coding challenge\n"
                    "/quiz - Take a tech quiz\n"
                    "/resources - Find learning materials\n"
                    "/tip - Get a random programming tip\n"
                    "/help - See all available commands\n\n"
                    "I'm here to help our community learn and grow together in technology. "
                    "Feel free to interact with me through commands or buttons!\n\n"
                    "#KTechSomali #CodingCommunity"
                )
                
                success = False
                for group_id in config.TARGET_GROUPS:
                    try:
                        # First check if bot is member of the group
                        try:
                            chat = await self.application.bot.get_chat(group_id)
                            bot_member = await chat.get_member(self.application.bot.id)
                            if bot_member.status not in ['administrator', 'member']:
                                logger.error(f"Bot is not a member of group {group_id}")
                                continue
                        except Exception as e:
                            logger.error(f"Failed to check bot membership in group {group_id}: {e}")
                            continue
                            
                        await self.application.bot.send_message(
                            chat_id=group_id,
                            text=intro_message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        logger.info(f"Sent introduction message to group {group_id}")
                        success = True
                    except telegram.error.Forbidden as e:
                        logger.error(f"Bot lacks permission to send messages to group {group_id}: {e}")
                    except telegram.error.BadRequest as e:
                        if "chat not found" in str(e).lower():
                            logger.error(f"Group {group_id} not found. Please add the bot to the group first.")
                        else:
                            logger.error(f"Failed to send introduction to group {group_id}: {e}")
                    except Exception as e:
                        logger.error(f"Failed to send introduction to group {group_id}: {e}")
                
                # Only create first run file if at least one message was sent successfully
                if success:
                    # Create the first run file to indicate introduction has been sent
                    with open(first_run_file, 'w') as f:
                        f.write(str(datetime.now()))
                    
                    # Wait 24 hours before starting scheduled tasks
                    logger.info("First run detected - setting up 24 hour delay before scheduled tasks")
                    await asyncio.sleep(86400)  # 24 hours (86400 seconds) before starting scheduled tasks
                else:
                    logger.error("Failed to send introduction to any groups. Please check group IDs and bot permissions.")
            else:
                logger.info("Not first run - skipping introduction")
        except Exception as e:
            logger.error(f"Error in first time setup: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_text = (
            "👋 Welcome to K-Tech Somali Bot!\n\n"
            "I'm here to help you learn and grow in technology.\n\n"
            "Use /help to see what I can do!"
        )
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information."""
        help_text = (
            "🤖 *K-Tech Somali Bot Commands*\n\n"
            "*Learning Resources*\n"
            "/resources - Access learning materials\n"
            "/tip - Get a random tech tip\n"
            "/challenge - Get a coding challenge\n\n"
            "*Interactive Features*\n"
            "/quiz - Take a quiz\n"
            "/points - Check your points\n"
            "/leaderboard - View top performers\n\n"
            "*Group Management*\n"
            "/groupinfo - Get group information"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def challenge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a coding challenge."""
        try:
            # First, show category selection
            keyboard = []
            for category, name in config.CHALLENGE_CATEGORIES.items():
                keyboard.append([
                    InlineKeyboardButton(
                        name,
                        callback_data=f"challenge_category_{category}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎯 *Choose a Challenge Category:*\n\n"
                "Select the type of challenge you'd like to try:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error showing challenge categories: {e}")
            await update.message.reply_text(
                "Sorry, couldn't load challenges right now. Please try again later."
            )

    async def resources_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resources command."""
        try:
            with open('resources/learning_resources.json', 'r', encoding='utf-8') as f:
                resources = json.load(f)
            
            categories = list(resources.keys())
            keyboard = []
            for category in categories:
                keyboard.append([InlineKeyboardButton(category, callback_data=f"resource_{category}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "📚 *Learning Resources*\n\n"
                "Choose a category to explore:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in resources command: {e}")
            await update.message.reply_text(
                "Sorry, couldn't load resources right now. Please try again later."
            )

    async def tip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a random programming tip."""
        try:
            with open('resources/tips.json', 'r', encoding='utf-8') as f:
                tips = json.load(f)
            
            # Get random category and tip
            category = random.choice(list(tips.keys()))
            tip = random.choice(tips[category])
            
            message = (
                f"💡 *{tip['title']}*\n\n"
                f"{tip['content']}\n\n"
                f"Category: #{category}\n"
                f"Tags: {' '.join(['#' + tag for tag in tip['tags']])}"
            )
            
            await update.message.reply_text(
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in tip command: {str(e)}")
            await update.message.reply_text(
                "Sorry, I couldn't fetch a tip right now. Please try again later."
            )

    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a quiz."""
        try:
            with open('resources/quizzes.json', 'r', encoding='utf-8') as f:
                quizzes = json.load(f)
            
            categories = list(quizzes.keys())
            keyboard = []
            for category in categories:
                keyboard.append([InlineKeyboardButton(category, callback_data=f"quiz_{category}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎯 *Quiz Time!*\n\n"
                "Choose a category:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in quiz command: {e}")
            await update.message.reply_text(
                "Sorry, couldn't load quizzes right now. Please try again later."
            )

    async def points_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's points."""
        user_id = update.effective_user.id
        try:
            # Get points from database
            self.db_manager.cursor.execute(
                "SELECT points FROM user_points WHERE user_id = ?",
                (user_id,)
            )
            result = self.db_manager.cursor.fetchone()
            points = result[0] if result else 0
            
            await update.message.reply_text(
                f"🏆 *Your Points*\n\n"
                f"You have earned *{points}* points!\n"
                f"Keep participating to earn more.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in points command: {e}")
            await update.message.reply_text(
                "Sorry, couldn't fetch your points right now. Please try again later."
            )

    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the leaderboard."""
        try:
            # Get top 10 users from database
            self.db_manager.cursor.execute(
                "SELECT user_id, points FROM user_points ORDER BY points DESC LIMIT 10"
            )
            results = self.db_manager.cursor.fetchall()
            
            if not results:
                await update.message.reply_text(
                    "🏆 *Leaderboard*\n\n"
                    "No points recorded yet.\n"
                    "Be the first to earn points!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            message = "🏆 *Leaderboard*\n\n"
            for i, (user_id, points) in enumerate(results, 1):
                message += f"{i}. User {user_id}: {points} points\n"
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await update.message.reply_text(
                "Sorry, couldn't fetch the leaderboard right now. Please try again later."
            )

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the current operation."""
        if 'waiting_for_challenge_answer' in context.user_data:
            del context.user_data['waiting_for_challenge_answer']
            await update.message.reply_text(
                "Operation cancelled. Use /help to see available commands."
            )
        else:
            await update.message.reply_text(
                "No operation to cancel. Use /help to see available commands."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages."""
        try:
            message = update.message
            
            # Check if the message exists
            if not message or not update.effective_chat:
                return

            # Handle private chats
            if update.effective_chat.type == 'private':
                # Process challenge answers if waiting for one
                if context.user_data.get('waiting_for_challenge_answer'):
                    await self._handle_challenge_answer(update, context)
                    return
                
                # Handle photos for OCR in private chat
                if message.photo:
                    await self.handle_photo(update, context)
                    return
                
                # Handle other private chat interactions
                await message.reply_text(
                    "👋 Ku soo dhawoow K-Tech Somali Bot!\n\n"
                    "Waxaad isticmaali kartaa amaradan:\n"
                    "/challenge - Hel su'aal coding ah\n"
                    "/quiz - Qaado imtixaan\n"
                    "/resources - Hel kheyraadka waxbarashada\n"
                    "/help - Arag dhammaan amarrada la heli karo"
                )
                return
                    
            # From here on, we're handling group messages
            # Get user's status in the group
            try:
                chat_member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
                is_admin = chat_member.status in ['administrator', 'creator'] or update.effective_user.id in config.ADMIN_IDS
            except Exception as e:
                logger.error(f"Error checking user status: {e}")
                is_admin = False

            # Skip moderation for admins
            if is_admin:
                logger.info(f"Skipping moderation for admin: {update.effective_user.id}")
                return

            # Check rate limiting
            if self.msg_handler.check_spam(update.effective_user.id, datetime.now()):
                logger.warning(f"Rate limit exceeded for user: {update.effective_user.id}")
                try:
                    warning = await context.bot.send_message(
                        chat_id=update.effective_user.id,
                        text="⚠️ Fadlan sug daqiiqad. Farriimo badan ayaad diraysaa."
                    )
                    await message.delete()
                except Exception as e:
                    logger.error(f"Error handling rate limit message: {e}")
                    return
                    
            # Moderate message
            should_delete, warning_message = await self.msg_handler.moderate_message(message)
            
            if should_delete:
                try:
                    # Delete the message first
                    await message.delete()
                    
                    # Send warning message privately to the user
                    try:
                        # Add reference to the original message for context
                        warning_with_context = (
                            f"Your message in {message.chat.title} was removed because it "
                            f"contained a potential link or external reference.\n\n{warning_message}"
                        )
                        await context.bot.send_message(
                            chat_id=update.effective_user.id,
                            text=warning_with_context,
                            disable_web_page_preview=True
                        )
                        
                        logger.info(f"Sent private warning to user {update.effective_user.id}")
                        
                        # Let the group know a warning was sent privately (optional)
                        if hasattr(config, 'NOTIFY_GROUP_ON_DELETION') and config.NOTIFY_GROUP_ON_DELETION:
                            group_notification = await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"⚠️ {message.from_user.mention_html()}'s message was removed. A detailed explanation has been sent privately.",
                                parse_mode=ParseMode.HTML,
                                disable_notification=True
                            )
                            
                            # Auto-delete group notification after 15 seconds
                            if config.AUTO_DELETE_WARNINGS:
                                asyncio.create_task(self._delete_after_delay(group_notification, 15))
                    except telegram.error.Forbidden:
                        # If bot can't message user privately, send warning in group
                        logger.warning(f"Could not message user {update.effective_user.id} privately, sending warning to group")
                        group_warning = await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"⚠️ {message.from_user.mention_html()}, fadlan ila bilow chat gaar ah si aad u hesho digniin faahfaahsan.\n\n{warning_message}",
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True
                        )
                        
                        # Auto-delete group warning after 30 seconds
                        if config.AUTO_DELETE_WARNINGS:
                            asyncio.create_task(self._delete_after_delay(group_warning, 30))
                    
                    # Add warning to database
                    self.db_manager.add_warning(
                        user_id=update.effective_user.id,
                        group_id=update.effective_chat.id,
                        reason=warning_message
                    )
                    
                    # Check if user has multiple warnings and needs to be restricted
                    warnings_count = self.db_manager.get_warnings(
                        user_id=update.effective_user.id,
                        group_id=update.effective_chat.id
                    )
                    
                    if warnings_count >= config.MAX_WARNINGS:
                        # Apply temporary restriction instead of ban
                        await self.apply_temporary_restriction(
                            user_id=update.effective_user.id,
                            chat_id=update.effective_chat.id,
                            days=config.RESTRICT_DURATION_DAYS,
                            context=context
                    )
                    
                except telegram.error.BadRequest as e:
                    logger.error(f"Error deleting message: {e}")
                    if "Message can't be deleted" in str(e):
                        logger.warning("Bot might be missing delete permissions")
                except Exception as e:
                    logger.error(f"Error in message moderation: {e}")

        except Exception as e:
            logger.error(f"Error in message handler: {e}", exc_info=True)

    async def apply_temporary_restriction(self, user_id: int, chat_id: int, days: int, context: ContextTypes.DEFAULT_TYPE):
        """Apply a temporary restriction on a user in a group."""
        try:
            # Calculate until date (current time + restriction days)
            until_date = int((datetime.now() + timedelta(days=days)).timestamp())
            
            # Restrict the user from sending messages, media, etc.
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                ),
                until_date=until_date
            )
            
            # Notify the user about the restriction
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Due to multiple violations of group rules, your ability to send messages "
                         f"in the group has been temporarily restricted for {days} days.\n\n"
                         f"Please review the group rules. Your restriction will be lifted automatically "
                         f"after {days} days."
                )
            except telegram.error.Forbidden:
                pass  # Can't message user directly
                
            # Log the restriction
            logger.warning(f"User {user_id} has been restricted in chat {chat_id} for {days} days")
            
            # Create a job to remove all warnings after restriction period
            job_name = f"clear_warnings_{user_id}_{chat_id}"
            context.job_queue.run_once(
                self._clear_user_warnings,
                when=days * 86400,  # Convert days to seconds
                data={
                    'user_id': user_id,
                    'chat_id': chat_id
                },
                name=job_name
            )
            
        except Exception as e:
            logger.error(f"Failed to restrict user {user_id}: {e}")
    
    async def _clear_user_warnings(self, context: ContextTypes.DEFAULT_TYPE):
        """Clear all warnings for a user after restriction period."""
        job_data = context.job.data
        user_id = job_data.get('user_id')
        chat_id = job_data.get('chat_id')
        
        try:
            # Clear warnings in database
            self.db_manager.cursor.execute(
                "DELETE FROM user_warnings WHERE user_id = ? AND group_id = ?",
                (user_id, chat_id)
            )
            self.db_manager.conn.commit()
            
            logger.info(f"Cleared warnings for user {user_id} in chat {chat_id} after restriction period")
        except Exception as e:
            logger.error(f"Failed to clear warnings for user {user_id}: {e}")

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks."""
        query = update.callback_query
        await query.answer()  # acknowledge the button click

        try:
            data = query.data
            
            # Handle challenge buttons more explicitly
            if data == "challenge_categories":
                await self.handle_challenge_category(query, context)
            elif data.startswith('challenge_category_'):
                await self.handle_challenge_category(query, context)
            elif data.startswith('challenge_diff_'):
                await self.handle_challenge_difficulty(query, context)
            elif data.startswith('challenge_hint_'):
                await self.handle_challenge_hint(query, context)
            elif data.startswith('challenge_submit_'):
                await self.handle_challenge_submit(query, context)
            elif data.startswith('challenge_translate_'):
                await self.handle_challenge_translate(query, context)
            elif data.startswith('resource_'):
                await self.handle_resource_category(query, context)
            elif data.startswith('quiz_'):
                await self.handle_quiz_selection(query, context)
            else:
                logger.warning(f"Unknown callback data: {query.data}")
                await query.edit_message_text(
                    "Sorry, I don't know how to handle this button. Please try again.",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"Error handling button click: {e}", exc_info=True)
            await query.edit_message_text(
                "Sorry, something went wrong. Please try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Main Menu", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )

    async def handle_challenge_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle challenge category selection - backward compatibility."""
        query = update.callback_query
        await query.answer()
            
        try:
            # Extract the category from the callback data
            category = query.data.replace('challenge_category_', '')
            
            # Show difficulty selection
            keyboard = []
            for difficulty in ["easy", "medium", "hard"]:
                keyboard.append([
                    InlineKeyboardButton(
                        difficulty.title(),
                        callback_data=f"challenge_diff_{category}_{difficulty}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(
                    "« Back",
                    callback_data="challenge_categories"
                )
            ])
            
            await query.edit_message_text(
                text=f"🎯 Select difficulty for {category.replace('_', ' ')} challenge:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error in challenge category handling: {e}")
            await query.answer("Error processing category selection")

    async def handle_challenge_difficulty(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle difficulty selection - backward compatibility."""
        query = update.callback_query
        if not query:
            return
        
        try:
            # Parse the callback data
            data_parts = query.data.split('_')
            # Handle special case of web_development
            if len(data_parts) >= 4 and data_parts[2] == 'web' and data_parts[3] == 'development':
                category = 'web_development'
                difficulty = data_parts[4]
            else:
                category = data_parts[2]
                difficulty = data_parts[3]

            # Get a challenge
            challenge = self.get_challenge(category, difficulty)
            
            if not challenge:
                await query.edit_message_text("Sorry, couldn't load challenge. Please try again.")
                return
            
            # Format message
            message = (
                f"🎯 <b>Coding Challenge</b>\n\n"
                f"<b>{html.escape(challenge['title'])}</b>\n\n"
                f"📝 <b>Description:</b>\n{html.escape(challenge['description'])}\n\n"
                f"Category: {html.escape(challenge.get('category', category).title())}\n"
                f"Difficulty: {difficulty.title()}\n"
                f"Points: {challenge.get('points', 10)}"
            )

            keyboard = [
                [
                    InlineKeyboardButton("💡 Show Hint", callback_data=f"challenge_hint_{difficulty}_{challenge.get('id', '0')}"),
                    InlineKeyboardButton("🇸🇴 Translate", callback_data=f"challenge_translate_{category}_{difficulty}_{challenge.get('id', '0')}")
                ],
                [InlineKeyboardButton("✍️ Submit Solution", callback_data=f"challenge_submit_{difficulty}_{challenge.get('id', '0')}")],
                [InlineKeyboardButton("🔄 Try Another", callback_data=f"challenge_another_{difficulty}_{category}")],
                [InlineKeyboardButton("« Back to Difficulty", callback_data=f"challenge_category_{category}")],
                [InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")]
            ]
            
            # Store challenge in user_data for later
            context.user_data['current_challenge'] = challenge

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error in challenge difficulty handling: {e}")
            await query.edit_message_text(
                "Sorry, something went wrong. Please try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                ]]),
                parse_mode=ParseMode.HTML
            )

    async def handle_challenge_hint(self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
        """Handle challenge hint request."""
        try:
            # Parse the callback data carefully
            data_parts = query.data.split('_')
            logger.info(f"Handling hint request with data: {query.data}")
            
            # Ensure we have enough parts
            if len(data_parts) < 4:  # At minimum we need challenge_hint_difficulty_id
                logger.warning(f"Invalid hint callback data: {query.data}")
                await self._safe_edit_message(query,
                    "Sorry, couldn't process this hint request. Please try again.",
                    InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                    ]])
                )
                return
            
            # Try to extract parts based on format
            if len(data_parts) >= 5 and data_parts[2] == 'web' and data_parts[3] == 'development' and len(data_parts) >= 6:
                category = 'web_development'
                difficulty = data_parts[4]
                challenge_id = data_parts[5]
            elif len(data_parts) >= 5:
                # Standard format: challenge_hint_category_difficulty_id
                category = data_parts[2]
                difficulty = data_parts[3]
                challenge_id = data_parts[4]
            else:
                # Legacy format: challenge_hint_difficulty_id
                difficulty = data_parts[2]
                challenge_id = data_parts[3]
                
                # Try to get category from current_challenge
                category = None
                if 'current_challenge' in context.user_data:
                    current_challenge = context.user_data.get('current_challenge', {})
                    category = current_challenge.get('category')
                    
                if not category:
                    category = 'programming'  # Default category as fallback
            
            logger.info(f"Loading hint for category={category}, difficulty={difficulty}, id={challenge_id}")
            
            # Load challenges from file
            try:
                with open('resources/programming_challenges.json', 'r', encoding='utf-8') as f:
                    challenges = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load challenges file: {e}")
                await self._safe_edit_message(query,
                    "Sorry, couldn't load the challenges. Please try again later.",
                    InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                    ]]),
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Handle legacy category naming
            if category not in challenges and category.startswith('programming'):
                category = 'programming'
            
            # Find the challenge
            challenge = None
            if category in challenges and difficulty in challenges.get(category, {}):
                for c in challenges[category][difficulty]:
                    if str(c.get('id')) == challenge_id:
                        challenge = c
                        break
            
            if challenge and 'hint' in challenge:
                # Format the hint message with HTML
                message = (
                    f"🎯 <b>{html.escape(challenge['title'])}</b>\n\n"
                    f"💡 <b>Hint:</b>\n{html.escape(challenge['hint'])}\n\n"
                    f"📝 <b>Original Challenge:</b>\n{html.escape(challenge['description'])}"
                )
                        
                keyboard = [
                    [InlineKeyboardButton(
                        "🌍 Translate to Somali",
                        callback_data=f"challenge_translate_{category}_{difficulty}_{challenge_id}"
                    )],
                    [InlineKeyboardButton(
                        "✍️ Submit Solution",
                        callback_data=f"challenge_submit_{category}_{difficulty}_{challenge_id}"
                    )],
                    [InlineKeyboardButton(
                        "🔄 Try Another",
                        callback_data=f"challenge_another_{difficulty}_{category}"
                    )],
                    [InlineKeyboardButton(
                        "« Back to Categories",
                        callback_data="challenge_categories"
                    )]
                ]
                
                await self._safe_edit_message(query,
                    message,
                    InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            else:
                await self._safe_edit_message(query,
                    "Sorry, no hint is available for this challenge.",
                    InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                    ]]),
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Error in challenge hint handling: {e}", exc_info=True)
            await self._safe_edit_message(query,
                "Sorry, something went wrong with the hint. Please try again.",
                InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                ]]),
                parse_mode=ParseMode.HTML
            )
            
    async def handle_resource_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle resource category selection."""
        query = update.callback_query
        if not query:
            logger.error("No callback query in update")
            return
            
        try:
            category = query.data.replace('resource_', '')
            resources = self.get_resources_for_category(category)
            
            if not resources:
                await query.answer("No resources found for this category")
                return
                
            await query.edit_message_text(
                text=f"📚 *{category.replace('_', ' ').title()} Resources*\n\n" +
                     "\n\n".join([f"• [{r['name']}]({r['url']})\n{r['description']}" for r in resources]),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Error handling resource category: {e}")
            await query.answer("Error processing category selection")

    async def handle_quiz_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle quiz category selection."""
        query = update.callback_query
        if not query:
            logger.error("No callback query in update")
            return
            
        try:
            category = query.data.replace('quiz_', '')
            quiz = self.get_quiz_for_category(category)
            
            if not quiz:
                await query.answer("No quiz available for this category")
                return
                
            keyboard = [[
                InlineKeyboardButton(
                    option,
                    callback_data=f"quiz_answer_{quiz['id']}_{i}"
                )
            ] for i, option in enumerate(quiz['options'])]
            
            keyboard.append([
                InlineKeyboardButton(
                    "💡 Hint",
                    callback_data=f"quiz_hint_{quiz['id']}"
                )
            ])
            
            await query.edit_message_text(
                text=f"📝 *{category.title()} Quiz*\n\n{quiz['question']}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error handling quiz selection: {e}")
            await query.answer("Error processing quiz selection")

    async def handle_quiz_answer(self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
        """Handle quiz answer submission."""
        try:
            # Parse callback data
            parts = query.data.split('_')
            category = parts[2]
            quiz_id = parts[3]
            answer_index = int(parts[4])
            user_id = query.from_user.id
            
            # Get quiz from context
            quiz = context.user_data.get('current_quiz')
            if not quiz or str(quiz['id']) != quiz_id:
                await query.edit_message_text(
                    "Sorry, I couldn't find the quiz you're answering. Please try again.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Handle multiple answers
            if quiz.get('multiple_answers', False):
                # Toggle selection
                selections = context.user_data.get('quiz_selections', set())
                if answer_index in selections:
                    selections.remove(answer_index)
                else:
                    selections.add(answer_index)
                context.user_data['quiz_selections'] = selections
                
                # Update message with new checkbox states
                message = (
                    f"❓ *{quiz['question']}*\n\n"
                    f"Points: {quiz['points']}\n"
                    f"Difficulty: {quiz['difficulty'].title()}\n"
                    f"Category: {quiz.get('category', category).replace('_', ' ').title()}\n\n"
                    "_Select all correct answers_"
                )
                
                keyboard = []
                for i, option in enumerate(quiz['options']):
                    prefix = "☑" if i in selections else "☐"
                    keyboard.append([InlineKeyboardButton(
                        f"{prefix} {option}",
                        callback_data=f"quiz_answer_{category}_{quiz_id}_{i}"
                    )])
                
                if 'hint' in quiz:
                    keyboard.append([InlineKeyboardButton(
                        "💡 Show Hint",
                        callback_data=f"quiz_hint_{category}_{quiz_id}"
                    )])
                
                keyboard.append([InlineKeyboardButton(
                    "✅ Submit Answers",
                    callback_data=f"quiz_submit_{category}_{quiz_id}"
                )])
                keyboard.append([InlineKeyboardButton("« Back to Categories", callback_data="quiz")])
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Single answer handling
            selected_answer = quiz['options'][answer_index]
            is_correct = selected_answer == quiz['correct']
            points_earned = quiz['points'] if is_correct else 0
            
            # Record the attempt
            self.db_manager.record_quiz_attempt(
                user_id,
                quiz_id,
                category,
                is_correct,
                points_earned,
                selected_answer
            )
            
            # Get user's updated stats
            stats = self.db_manager.get_quiz_stats(user_id)
            
            # Format response message
            if is_correct:
                message = (
                    "✅ *Correct Answer!*\n\n"
                    f"You earned *{points_earned} points*!\n\n"
                    f"*Explanation:*\n{quiz['explanation']}\n\n"
                )
            else:
                message = (
                    "❌ *Incorrect Answer*\n\n"
                    f"The correct answer was: *{quiz['correct']}*\n\n"
                    f"*Explanation:*\n{quiz['explanation']}\n\n"
                )
            
            message += (
                "*Your Quiz Stats:*\n"
                f"Total Attempts: {stats['total_attempts']}\n"
                f"Correct Answers: {stats['correct_answers']}\n"
                f"Accuracy: {stats['accuracy']:.1f}%\n"
                f"Total Points: {stats['total_points']}\n\n"
                "Try another quiz with /quiz!"
            )
            
            # Clear the current quiz from context
            if 'current_quiz' in context.user_data:
                del context.user_data['current_quiz']
            
            keyboard = [[InlineKeyboardButton("Try Another Quiz", callback_data="quiz")]]
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Error handling quiz answer: {e}")
            await query.edit_message_text(
                "Sorry, there was an error processing your answer. Please try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Categories", callback_data="quiz")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        
    async def handle_quiz_hint(self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
        """Handle quiz hint request."""
        try:
            parts = query.data.split('_')
            category = parts[2]
            quiz_id = parts[3]
            
            quiz = context.user_data.get('current_quiz')
            if not quiz or str(quiz['id']) != quiz_id or 'hint' not in quiz:
                await query.answer("Sorry, no hint is available for this quiz.")
                return
            
            # Show hint in a popup
            await query.answer(quiz['hint'], show_alert=True)
            
        except Exception as e:
            logger.error(f"Error showing quiz hint: {e}")
            await query.answer("Sorry, couldn't show the hint right now.")

    async def handle_quiz_submit(self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
        """Handle submission of multiple answer quiz."""
        try:
            parts = query.data.split('_')
            category = parts[2]
            quiz_id = parts[3]
            user_id = query.from_user.id
            
            quiz = context.user_data.get('current_quiz')
            if not quiz or str(quiz['id']) != quiz_id:
                await query.edit_message_text(
                    "Sorry, I couldn't find the quiz you're answering. Please try again.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            # Get selected answers
            selections = context.user_data.get('quiz_selections', set())
            selected_answers = [quiz['options'][i] for i in selections]
            
            # Check if all correct answers are selected and no incorrect ones
            correct_answers = set(quiz['correct'])
            selected_answers_set = set(selected_answers)
            
            is_correct = selected_answers_set == correct_answers
            points_earned = quiz['points'] if is_correct else 0
            
            # Record the attempt
            self.db_manager.record_quiz_attempt(
                user_id,
                quiz_id,
                category,
                is_correct,
                points_earned,
                ", ".join(selected_answers)
            )
            
            # Get user's updated stats
            stats = self.db_manager.get_quiz_stats(user_id)
            
            # Format response message
            if is_correct:
                message = (
                    "✅ *All Correct!*\n\n"
                    f"You earned *{points_earned} points*!\n\n"
                )
            else:
                message = (
                    "❌ *Not Quite Right*\n\n"
                    "The correct answers were:\n" +
                    "\n".join(f"• {answer}" for answer in correct_answers) +
                    "\n\n"
                )
            
            message += f"*Explanation:*\n{quiz['explanation']}\n\n"
            
            # Add stats to message
            message += (
                "*Your Quiz Stats:*\n"
                f"Total Attempts: {stats['total_attempts']}\n"
                f"Correct Answers: {stats['correct_answers']}\n"
                f"Accuracy: {stats['accuracy']:.1f}%\n"
                f"Total Points: {stats['total_points']}\n\n"
                "Try another quiz with /quiz!"
            )
            
            # Clear quiz data from context
            if 'current_quiz' in context.user_data:
                del context.user_data['current_quiz']
            if 'quiz_selections' in context.user_data:
                del context.user_data['quiz_selections']
            
            keyboard = [[InlineKeyboardButton("Try Another Quiz", callback_data="quiz")]]
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error handling quiz submission: {e}")
            await query.edit_message_text(
                "Sorry, there was an error processing your submission. Please try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Categories", callback_data="quiz")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )

    async def quiz_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's quiz statistics."""
        try:
            user_id = update.effective_user.id
            stats = self.db_manager.get_quiz_stats(user_id)
            history = self.db_manager.get_quiz_history(user_id, limit=5)
            
            message = (
                "📊 *Your Quiz Statistics*\n\n"
                f"Total Attempts: {stats['total_attempts']}\n"
                f"Correct Answers: {stats['correct_answers']}\n"
                f"Accuracy: {stats['accuracy']:.1f}%\n"
                f"Total Points: {stats['total_points']}\n"
                f"Categories Attempted: {stats['categories_attempted']}\n\n"
            )
            
            if history:
                message += "*Recent Quiz History:*\n"
                for quiz in history:
                    status = "✅" if quiz[2] else "❌"
                    message += (
                        f"{status} {quiz[1]} - {quiz[3]} points\n"
                        f"Attempts: {quiz[5]}, Best Score: {quiz[6]}\n"
                    )
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error showing quiz stats: {e}")
            await update.message.reply_text(
                "Sorry, couldn't fetch your quiz statistics right now. Please try again later."
            )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photos for OCR processing."""
        try:
            # Only process in private chats
            if update.effective_chat.type != 'private':
                return

            message = update.message
            if not message or not message.photo:
                return

            # Get the largest photo (best quality)
            photo = message.photo[-1]
            
            # Send acknowledgment
            processing_msg = await message.reply_text(
                "🔍 Processing your error message...\n"
                "This might take a moment."
            )

            logger.info(f"Starting OCR process for image from user {update.effective_user.id}")
            
            try:
                # Download the image
                file = await context.bot.get_file(photo.file_id)
                logger.info("Image downloaded successfully")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    await file.download_to_drive(tmp_file.name)
                    logger.info(f"Image saved to temporary file: {tmp_file.name}")
                    
                    try:
                        image = Image.open(tmp_file.name)
                        logger.info(f"Original image size: {image.size}")
                        
                        # Enhanced preprocessing for better OCR
                        # Convert to grayscale
                        image = image.convert('L')
                        
                        # Increase contrast
                        enhancer = ImageEnhance.Contrast(image)
                        image = enhancer.enhance(2.0)
                        
                        # Increase sharpness
                        enhancer = ImageEnhance.Sharpness(image)
                        image = enhancer.enhance(2.0)
                        
                        # Resize if image is too small
                        if image.size[0] < 1000 or image.size[1] < 1000:
                            ratio = max(1000/image.size[0], 1000/image.size[1])
                            new_size = (int(image.size[0]*ratio), int(image.size[1]*ratio))
                            image = image.resize(new_size, Image.Resampling.LANCZOS)
                        
                        logger.info("Extracting text with Tesseract...")
                        extracted_text = pytesseract.image_to_string(
                            image,
                            config='--psm 6 --oem 3'
                        )
                        logger.info(f"Extracted text length: {len(extracted_text)}")
                        logger.info(f"First 100 chars: {extracted_text[:100]}")
                        
                        # Clean up the extracted text
                        extracted_text = extracted_text.strip()
                        # Remove multiple newlines
                        extracted_text = re.sub(r'\n{3,}', '\n\n', extracted_text)
                        
                        if not extracted_text:
                            await processing_msg.edit_text(
                                "❌ I couldn't detect any text in this image.\n"
                                "Please make sure the error message is clearly visible and the text is not blurry."
                            )
                            return

                        # Format the extracted text with better markdown escaping
                        error_type = self._detect_error_type(extracted_text)
                        error_type_display = error_type.replace('_', ' ').title()

                        formatted_text = (
                            "📝 *Extracted Error Message:*\n"
                            f"Type: _{error_type_display}_\n\n"
                            f"```\n{extracted_text[:4000].replace('`', '')}```\n\n"
                            "_You can now copy this text to search for solutions or share it with others._\n\n"
                            "💡 *Tip:* For better results, try to:\n"
                            "• Take clear screenshots with good contrast\n"
                            "• Ensure the text is not blurry\n"
                            "• Avoid background patterns or colors"
                        )

                        try:
                            await processing_msg.edit_text(
                                formatted_text,
                                parse_mode=ParseMode.MARKDOWN
                            )
                        except Exception as e:
                            if "Message is too long" in str(e):
                                # Split into multiple messages if too long
                                chunks = [formatted_text[i:i+4000] for i in range(0, len(formatted_text), 4000)]
                                await processing_msg.edit_text(chunks[0], parse_mode=ParseMode.MARKDOWN)
                                for chunk in chunks[1:]:
                                    await context.bot.send_message(
                                        chat_id=update.effective_chat.id,
                                        text=chunk,
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                            else:
                                raise

                    except Exception as e:
                        logger.error(f"OCR error: {e}")
                        await processing_msg.edit_text(
                            "❌ Sorry, I had trouble reading the text from your image.\n"
                            "Please make sure the text is clear and try again."
                        )
                        
            finally:
                # Clean up temporary file
                try:
                    if 'tmp_file' in locals():
                        os.unlink(tmp_file.name)
                except Exception as e:
                    logger.error(f"Error cleaning up temp file: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling image: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Sorry, something went wrong while processing your image.\n"
                "Please try again later."
            )

    def _detect_error_type(self, text: str) -> str:
        """Detect the type of error message from the extracted text."""
        text_lower = text.lower()
        
        # Common error types and their keywords
        error_patterns = {
            'syntax_error': ['syntaxerror', 'syntax error', 'invalid syntax'],
            'name_error': ['nameerror', 'name error', 'not defined'],
            'type_error': ['typeerror', 'type error'],
            'value_error': ['valueerror', 'value error'],
            'index_error': ['indexerror', 'index error', 'list index out of range'],
            'key_error': ['keyerror', 'key error'],
            'attribute_error': ['attributeerror', 'attribute error', 'has no attribute'],
            'import_error': ['importerror', 'import error', 'no module named'],
            'indentation_error': ['indentationerror', 'indentation error', 'unexpected indent'],
            'runtime_error': ['runtimeerror', 'runtime error'],
            'zero_division_error': ['zerodivisionerror', 'zero division error', 'division by zero'],
            'file_not_found_error': ['filenotfounderror', 'file not found', 'no such file'],
            'permission_error': ['permissionerror', 'permission error', 'permission denied'],
            'memory_error': ['memoryerror', 'memory error', 'out of memory'],
            'overflow_error': ['overflowerror', 'overflow error'],
            'recursion_error': ['recursionerror', 'recursion error', 'maximum recursion depth'],
            'assertion_error': ['assertionerror', 'assertion error', 'assertion failed'],
            'unicode_error': ['unicodeerror', 'unicode error'],
            'module_not_found_error': ['modulenotfounderror', 'module not found'],
            'connection_error': ['connectionerror', 'connection error', 'connection refused']
        }
        
        # Check for each error type
        for error_type, patterns in error_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                return error_type
                
        # If no specific error type is found
        if 'error' in text_lower or 'exception' in text_lower:
            return 'general_error'
                
        return 'unknown'

    async def handle_challenge_translate(self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
        """Handle challenge translation to Somali"""
        try:
            parts = query.data.split('_')
            category = parts[2]
            difficulty = parts[3]
            
            # Get challenge from existing user_data if available
            challenge = context.user_data.get('current_challenge')
            
            # If no challenge in user_data, get a new one using the 2-parameter get_challenge
            if not challenge:
                # Use the 2-parameter get_challenge method defined at line ~2442
                challenge = self.get_challenge(category, difficulty)
                
            if not challenge:
                await query.answer("Could not find challenge to translate")
                return
                
            # Translate components
            translated_title = await self.translate_to_somali(challenge['title'])
            translated_desc = await self.translate_to_somali(challenge['description'])
            translated_hint = await self.translate_to_somali(challenge.get('hint', ''))
            
            # Format the Somali text to make it more natural
            # Add paragraph breaks for readability and fix common translation issues
            translated_desc = translated_desc.replace(". ", ".\n\n")
            
            # Add disclaimer in both languages
            somali_disclaimer = await self.translate_to_somali("Note: This is an automated translation. Some phrases may not be accurate.")
            disclaimer = (
                f"\n\n<i>──────────────</i>\n\n"
                f"<i>🇸🇴 {somali_disclaimer}</i>\n\n"
                f"<i>🇬🇧 Note: This is an automated translation. Some phrases may not be accurate.</i>"
            )
            
            # Build translated message
            message = (
                f"🎯 <b>Su'aal Code-ka</b>\n\n"
                f"<b>{html.escape(translated_title)}</b>\n\n"
                f"📝 <b>Sharaxaad:</b>\n{html.escape(translated_desc)}\n\n"
                f"💡 <b>Tilmaan:</b>\n{html.escape(translated_hint)}\n\n"
                f"<b>Qaybta:</b> {category.replace('_', ' ').title()}\n"
                f"<b>Heerka Adkaanta:</b> {difficulty.title()}\n"
                f"<b>Dhibcaha:</b> {challenge.get('points', 10)}"
                f"{disclaimer}"
            )

            # Update keyboard with back button
            keyboard = [
                [InlineKeyboardButton("🌐 English", callback_data=f"challenge_diff_{category}_{difficulty}")],
                [InlineKeyboardButton("✍️ Soo Gudbi", callback_data=f"challenge_submit_{difficulty}_{challenge.get('id', '')}")],
                [InlineKeyboardButton("🔄 Isku Day Mid Kale", callback_data=f"challenge_another_{difficulty}_{category}")]
            ]

            await query.edit_message_text(
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logger.error(f"Translation error: {e}")
            await query.answer("Qalad ayaa dhacay marka la turjunayey. Fadlan isku day mar kale.")

    async def translate_to_somali(self, text: str) -> str:
        """Translate text to Somali with caching and post-processing for more natural results."""
        try:
            if not text:
                return text

            # Check cache first
            cached = self.db_manager.get_translation(text)
            if cached:
                logger.info("Using cached translation")
                return cached

            # Use deep_translator for reliable translation
            try:
                translator = GoogleTranslator(source='en', target='so')
                translated_text = translator.translate(text)
                
                # Post-process to make Somali more natural
                if translated_text:
                    # Common improvements for Somali translations
                    translated_text = self._improve_somali_text(translated_text)
                    
                    # Cache the improved translation
                    self.db_manager.cache_translation(text, translated_text)
                    return translated_text
                
                return text
            except Exception as inner_e:
                logger.error(f"Translation failed: {str(inner_e)}")
                return text

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text

    def _improve_somali_text(self, text: str) -> str:
        """Apply common corrections to make automatically translated Somali text more natural."""
        # Replace common awkward translations with more natural Somali phrases
        corrections = {
            "ku soo dhawaada": "kusoo dhowoow",
            "qoraalka koodhka": "koodka",
            "dhibaatooyinka": "caqabadaha",
            "class": "fasal",
            "function": "shaqo",
            "waa maxay": "maxay tahay",
            "ku dar": "ku soo dar",
            "ku soo dar": "ku dar",
            "programming language": "luuqadda barnaamijyada",
            "code": "kood",
            "variable": "doorsoon",
            "algorithm": "khwaarisinm",
            "websites": "bogag internet",
            "server": "adeege",
            "database": "kayd xogeed",
            "python": "python",
            "javascript": "javascript",
            "solution": "xal",
            "bugs": "cilado",
            "nooca": "nooca",
            "waxaa jira": "waa jiraan",
            "wuxuu": "wuxuu",
            "software": "barnaamij",
            "hardware": "qalabka",
            "security": "amniga",
            "web development": "horumarinta bogagga",
            "write": "qor",
            "program": "barnaamij",
            "application": "barnaamij"
        }
        
        for awkward, natural in corrections.items():
            text = re.sub(r'\b' + re.escape(awkward) + r'\b', natural, text, flags=re.IGNORECASE)
        
        # Fix spacing issues common in Somali machine translations
        text = re.sub(r'(\w)\s+([,.!?])', r'\1\2', text)  # Remove space before punctuation
        
        # Improve readability with better sentence spacing
        text = re.sub(r'([.!?])\s*(\w)', lambda m: m.group(1) + '\n\n' + m.group(2), text)
        
        # Make sure important technical terms are clear
        text = re.sub(r'\b([Ff]unction)\b', 'shaqada (function)', text)
        text = re.sub(r'\b([Cc]lass)\b', 'fasalka (class)', text)
        text = re.sub(r'\b([Mm]ethod)\b', 'hab (method)', text)
        
        # Fix common grammatical patterns in Somali
        text = re.sub(r'\b(waa in|waxa)\s+(\w+)\s+in\b', r'\1 \2 inuu', text)
        
        return text

    async def cleanup_translation_cache(self):
        """Clean up old translations from cache."""
        try:
            current_time = datetime.now()
            self.db_manager.cursor.execute("""
                DELETE FROM translation_cache 
                WHERE strftime('%s', 'now') - strftime('%s', timestamp) > ?
            """, (config.TRANSLATION_CACHE_DURATION,))
            self.db_manager.conn.commit()
            logger.info("Cleaned up translation cache")
        except Exception as e:
            logger.error(f"Error cleaning translation cache: {e}")

    def load_challenges(self, force_reload=False):
        """Load challenges from file with caching."""
        try:
            if self.challenges_cache is None or force_reload:
                with open('resources/programming_challenges.json', 'r', encoding='utf-8') as f:
                    self.challenges_cache = json.load(f)
                logger.info("Successfully loaded challenges into cache")
            return self.challenges_cache
        except Exception as e:
            logger.error(f"Error loading challenges: {e}")
            return None

    def get_challenge(self, category: str, difficulty: str, challenge_id: str = None):
        """Get a specific challenge or random challenge from category/difficulty."""
        try:
            # Try to find the challenges file in both possible locations
            challenges_file = 'resources/programming_challenges.json'
            custom_file = 'custom_challenges.json'
            
            # First try the regular file
            try:
                with open(challenges_file, 'r', encoding='utf-8') as f:
                    challenges = json.load(f)
                    logger.info("Loaded challenges from programming_challenges.json")
            except FileNotFoundError:
                # Try the custom file
                with open(custom_file, 'r', encoding='utf-8') as f:
                    challenges = json.load(f)
                    logger.info("Loaded challenges from custom_challenges.json")
            
            # Check if category exists, if not, use a default
            if category not in challenges:
                logger.warning(f"Category {category} not found in challenges")
                if difficulty in challenges:
                    # If difficulty is a top-level key, use it directly
                    category_challenges = challenges[difficulty]
                    if isinstance(category_challenges, list):
                        random_challenge = random.choice(category_challenges)
                        random_challenge['category'] = category  # Add category for consistent output
                        return random_challenge
                # Fall back to security category if available
                if 'security' in challenges:
                    category = 'security'
                else:
                    # Use the first available category
                    category = next(iter(challenges.keys()))
            
            # Get challenges for the category/difficulty
            if difficulty not in challenges[category]:
                logger.warning(f"Difficulty {difficulty} not found in {category} challenges")
                # Use the first available difficulty
                difficulty = next(iter(challenges[category].keys()))

            category_challenges = challenges[category][difficulty]
            
            if not category_challenges:
                logger.warning(f"No challenges found for {category}/{difficulty}")
                return None

            if challenge_id:
                # Find specific challenge by ID
                for challenge in category_challenges:
                    if str(challenge.get('id', '')) == challenge_id:
                        challenge['category'] = category  # Ensure category is included
                        challenge['difficulty'] = difficulty  # Ensure difficulty is included
                        return challenge
                # If ID not found, get random
                logger.warning(f"Challenge ID {challenge_id} not found, using random")
            
            # Get random challenge
            random_challenge = random.choice(category_challenges)
            random_challenge['category'] = category  # Ensure category is included
            random_challenge['difficulty'] = difficulty  # Ensure difficulty is included
            return random_challenge

        except Exception as e:
            logger.error(f"Error getting challenge: {e}", exc_info=True)
            return self._get_fallback_challenge(category, difficulty)
    
    def _get_fallback_challenge(self, category, difficulty):
        """Provide a fallback challenge if loading fails."""
        fallback_challenges = {
            "easy": {
                "id": "fallback1",
                "title": "Simple Security Question",
                "description": "What makes a password strong?",
                "hint": "Think about length, complexity, and uniqueness.",
                "points": 5,
                "difficulty": "easy",
                "category": category
            },
            "medium": {
                "id": "fallback2",
                "title": "Web Security Basics",
                "description": "Explain the difference between HTTP and HTTPS.",
                "hint": "Think about encryption and security.",
                "points": 10,
                "difficulty": "medium",
                "category": category
            },
            "hard": {
                "id": "fallback3",
                "title": "Advanced Security Concept",
                "description": "What is a buffer overflow attack and how can it be prevented?",
                "hint": "Think about memory management and input validation.",
                "points": 15,
                "difficulty": "hard",
                "category": category
            }
        }
        return fallback_challenges.get(difficulty, fallback_challenges["medium"])

    def get_quiz_for_category(self, category: str) -> Optional[dict]:
        """Get a random quiz for the given category."""
        try:
            with open('resources/quizzes.json', 'r', encoding='utf-8') as f:
                quizzes = json.load(f)
            
            if category in quizzes and quizzes[category]:
                return random.choice(quizzes[category])
            return None
        except Exception as e:
            logger.error(f"Error getting quiz for category {category}: {e}")
            return None

    def get_resources_for_category(self, category: str) -> List[dict]:
        """Get resources for the given category."""
        try:
            with open('resources/learning_resources.json', 'r', encoding='utf-8') as f:
                resources = json.load(f)
            
            if category in resources['categories']:
                cat_data = resources['categories'][category]
                all_resources = []
                for level in cat_data['levels'].values():
                    all_resources.extend(level['resources'])
                return all_resources
            return []
        except Exception as e:
            logger.error(f"Error getting resources for category {category}: {e}")
            return []

    async def group_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /groupinfo command."""
        try:
            chat = update.effective_chat
            if chat.type == 'private':
                await update.message.reply_text(
                    "This command only works in groups. Add me to a group and try again!"
                )
                return

            # Get chat info
            chat_info = (
                f"📊 *Group Information*\n\n"
                f"Name: {html.escape(chat.title)}\n"
                f"ID: `{chat.id}`\n"
                f"Type: {chat.type}\n"
                f"Members: {chat.get_member_count() if hasattr(chat, 'get_member_count') else 'N/A'}\n"
            )

            await update.message.reply_text(
                chat_info,
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Error in group info command: {e}")
            await update.message.reply_text(
                "Sorry, couldn't fetch group information. Make sure I have the necessary permissions."
            )

    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group rules."""
        try:
            if update.effective_chat.type == 'private':
                await update.message.reply_text("This command only works in groups!")
                return

            await update.message.reply_text(
                config.GROUP_RULES,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error showing rules: {e}")
            await update.message.reply_text("Sorry, couldn't show the rules right now.")

    async def handle_member_join(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new member joins."""
        try:
            if not update.chat_member or not update.chat_member.new_chat_member:
                return

            if update.chat_member.new_chat_member.status == "member":
                # Send welcome message
                welcome_msg = (
                    f"{config.WELCOME_MESSAGE}\n\n"
                    "Type /rules to see our group rules."
                )
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=welcome_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Log new member
                logger.info(f"New member joined: {update.chat_member.new_chat_member.user.id}")
                
        except Exception as e:
            logger.error(f"Error handling member join: {e}")

    async def _handle_challenge_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process the answer to a challenge."""
        try:
            if not context.user_data.get('waiting_for_challenge_answer'):
                # Not waiting for an answer
                return
                
            if not update.message:
                return
                
            # Get the current challenge
            challenge = context.user_data.get('current_challenge')
            if not challenge:
                await update.message.reply_text(
                    "Sorry, I couldn't find which challenge you were answering. Please try selecting a challenge again."
                )
                if 'waiting_for_challenge_answer' in context.user_data:
                    del context.user_data['waiting_for_challenge_answer']
                return
                
            # Get the user's answer
            user_answer = update.message.text.strip()
            
            # Check if there's a defined answer
            if 'answer' in challenge:
                correct_answer = str(challenge['answer']).lower()
                user_answer_lower = user_answer.lower()
                
                # Check if answer is correct
                is_correct = (
                    user_answer_lower == correct_answer or
                    correct_answer in user_answer_lower or
                    user_answer_lower in correct_answer
                )
                
                if is_correct:
                    # Award points and mark as completed
                    points = challenge.get('points', 5)
                    
                    # Update user points in database
                    self.db_manager.cursor.execute(
                        """
                        INSERT INTO user_points (user_id, points, last_updated)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(user_id) DO UPDATE SET
                            points = points + ?,
                            last_updated = CURRENT_TIMESTAMP
                        """,
                        (update.effective_user.id, points, points)
                    )
                    
                    # Mark challenge as completed
                    self.db_manager.update_challenge_progress(
                        user_id=update.effective_user.id,
                        challenge_id=challenge.get('id', '0'),
                        category=challenge.get('category', 'security'),
                        difficulty=challenge.get('difficulty', 'medium'),
                        completed=True
                    )
                    
                    self.db_manager.conn.commit()
                    
                    # Create keyboard with options for next steps
                    keyboard = [
                        [InlineKeyboardButton("🔄 Try Another Challenge", 
                            callback_data=f"challenge_another_{challenge.get('difficulty', 'medium')}_{challenge.get('category', 'programming')}")],
                        [InlineKeyboardButton("« Back to Categories", 
                            callback_data="challenge_categories")]
                    ]
                    
                    # Send success message
                    await update.message.reply_text(
                        f"✅ *Correct answer!* You've earned {points} points!\n\n"
                        f"📝 *Explanation:*\n{challenge.get('explanation', 'Great job solving this challenge!')}\n\n"
                        f"Select an option below to continue:",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    # Send incorrect message with answer instead of hint
                    explanation = challenge.get('explanation', '')
                    correct = challenge.get('answer', 'No answer provided')
                    
                    # Create keyboard with options
                    keyboard = [
                        [InlineKeyboardButton("🔄 Try Another Challenge", 
                            callback_data=f"challenge_another_{challenge.get('difficulty', 'medium')}_{challenge.get('category', 'programming')}")],
                        [InlineKeyboardButton("« Back to Categories", 
                            callback_data="challenge_categories")]
                    ]
                    
                    await update.message.reply_text(
                        f"❌ That's not quite right.\n\n"
                        f"🔑 *Correct Answer:* `{correct}`\n\n"
                        f"📝 *Explanation:*\n{explanation or 'Keep practicing to improve your skills!'}\n\n"
                        f"Select an option below to continue:",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
            else:
                # No defined answer, handle as open-ended
                # Create keyboard with options for next steps
                keyboard = [
                    [InlineKeyboardButton("🔄 Try Another Challenge", 
                        callback_data=f"challenge_another_{challenge.get('difficulty', 'medium')}_{challenge.get('category', 'programming')}")],
                    [InlineKeyboardButton("« Back to Categories", 
                        callback_data="challenge_categories")]
                ]
                
                await update.message.reply_text(
                    f"Thanks for your submission!\n\n"
                    f"*Your answer:*\n{user_answer}\n\n"
                    f"Since this is an open-ended challenge, there's no automatic grading.\n"
                    f"Consider the following key points:\n\n"
                    "{}\n\n"
                    "Select an option below to continue:".format(challenge.get('key_points', '• Think about security implications\n• Consider different approaches')),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                # Still award some points for attempting
                points = challenge.get('points', 5) // 2
                self.db_manager.cursor.execute(
                    """
                    INSERT INTO user_points (user_id, points, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        points = points + ?,
                        last_updated = CURRENT_TIMESTAMP
                    """,
                    (update.effective_user.id, points, points)
                )
                self.db_manager.conn.commit()
            
            # Clear waiting state
            if 'waiting_for_challenge_answer' in context.user_data:
                del context.user_data['waiting_for_challenge_answer']
            if 'current_challenge' in context.user_data:
                del context.user_data['current_challenge']
                
        except Exception as e:
            logger.error(f"Error handling challenge answer: {e}", exc_info=True)
            await update.message.reply_text(
                "Sorry, there was an error processing your answer. Please try again."
            )

    async def handle_challenge_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show challenge categories list."""
        query = update.callback_query
        await query.answer()
        
        try:
            # Show categories list
            keyboard = []
            for category, name in config.CHALLENGE_CATEGORIES.items():
                keyboard.append([
                    InlineKeyboardButton(
                        name,
                        callback_data=f"challenge_category_{category}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🎯 *Choose a Challenge Category:*\n\n"
                "Select the type of challenge you'd like to try:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error showing challenge categories: {e}")
            await query.edit_message_text(
                "Sorry, couldn't load categories. Please try /challenge again.",
                parse_mode=ParseMode.MARKDOWN
            )
            
    async def handle_challenge_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route challenge button presses to appropriate handlers based on the callback data."""
        query = update.callback_query
        if not query:
            return
            
        try:
            # Try to answer the callback query, but don't let it block execution
            try:
                await query.answer(timeout=2)  # Short timeout to prevent blocking
            except Exception as e:
                # This is non-critical, continue anyway
                logger.warning(f"Non-critical error answering callback: {e}")
            
            # Log the callback data for debugging
            logger.info(f"Challenge button pressed. Callback data: {query.data}")
            
            # Handle translation requests first to avoid timeout issues
            if query.data.startswith('challenge_translate_'):
                try:
                    # Process translation directly
                    await self.handle_challenge_translate(query, context)
                    return  # Exit early to avoid further processing
                except Exception as e:
                    logger.error(f"Error handling translation: {e}", exc_info=True)
                    await self._safe_edit_message(query, 
                        "Sorry, couldn't translate at this time. Please try again later.",
                        InlineKeyboardMarkup([[
                            InlineKeyboardButton("« Back", callback_data="challenge_categories")
                        ]])
                    )
                    return
                    
            # Route to appropriate handler based on callback data
            if query.data.startswith('challenge_select_'):
                # Handle challenge selection
                parts = query.data.split('_')
                if len(parts) >= 3:
                    category = parts[2]
                    difficulty = parts[3] if len(parts) > 3 else 'medium'
                    await self.handle_challenge_difficulty(update, context)
            elif query.data.startswith('challenge_hint_'):
                # Handle hint requests
                try:
                    await self.handle_challenge_hint(query, context)
                except Exception as e:
                    logger.error(f"Error in challenge hint handling: {e}", exc_info=True)
                    await self._safe_edit_message(query, "Sorry, couldn't load the hint. Please try again.")
            elif query.data.startswith('challenge_submit_'):
                # Handle submission requests
                try:
                    await self.handle_challenge_submit(query, context)
                except Exception as e:
                    logger.error(f"Error in challenge submission handling: {e}", exc_info=True)
                    await self._safe_edit_message(query, "Sorry, couldn't process your submission. Please try again.")
            elif query.data.startswith('challenge_another_'):
                # Handle request for another challenge
                parts = query.data.split('_')
                if len(parts) >= 3:
                    difficulty = parts[2]
                    
                    # Handle special case of web_development
                    if len(parts) >= 5 and parts[3] == 'web' and parts[4] == 'development':
                        category = 'web_development'
                    elif len(parts) > 3:
                        category = parts[3]
                    else:
                        category = None
                    
                    # If category is not in callback data, try to get it from current_challenge
                    if not category and 'current_challenge' in context.user_data:
                        current_challenge = context.user_data.get('current_challenge', {})
                        category = current_challenge.get('category')
                        logger.info(f"Using category from current challenge: {category}")
                    
                    if category:
                        # Don't show loading message - load challenge directly
                        try:
                            logger.info(f"Loading another challenge for category={category}, difficulty={difficulty}")
                            
                            # Get challenge with pre-loading
                            challenge = None
                            start_time = datetime.now()
                            
                            # Get and display a challenge
                            challenge = self.get_challenge(category, difficulty)
                            
                            if not challenge:
                                await self._safe_edit_message(query, 
                                    f"Sorry, no challenges available for {category} at {difficulty} level.",
                                    InlineKeyboardMarkup([[
                                        InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                                    ]])
                                )
                                return
                            
                            # Format message
                            message = (
                                f"🎯 <b>Coding Challenge</b>\n\n"
                                f"<b>{html.escape(challenge['title'])}</b>\n\n"
                                f"📝 <b>Description:</b>\n{html.escape(challenge['description'])}\n\n"
                                f"Category: {html.escape(challenge.get('category', category).title())}\n"
                                f"Difficulty: {difficulty.title()}\n"
                                f"Points: {challenge.get('points', 10)}"
                            )

                            keyboard = [
                                [
                                    InlineKeyboardButton("💡 Show Hint", 
                                        callback_data=f"challenge_hint_{category}_{difficulty}_{challenge.get('id', '0')}"),
                                    InlineKeyboardButton("🇸🇴 Translate", 
                                        callback_data=f"challenge_translate_{category}_{difficulty}_{challenge.get('id', '0')}")
                                ],
                                [InlineKeyboardButton("✍️ Submit Solution", 
                                    callback_data=f"challenge_submit_{category}_{difficulty}_{challenge.get('id', '0')}")],
                                [InlineKeyboardButton("🔄 Try Another", 
                                    callback_data=f"challenge_another_{difficulty}_{category}")],
                                [InlineKeyboardButton("« Back to Categories", 
                                    callback_data="challenge_categories")]
                            ]
                            
                            # Store challenge in user_data for later
                            context.user_data['current_challenge'] = challenge

                            # Log performance
                            elapsed = (datetime.now() - start_time).total_seconds()
                            logger.info(f"Challenge loaded in {elapsed:.2f} seconds")
                            
                            await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
                        except Exception as e:
                            logger.error(f"Error loading another challenge: {e}", exc_info=True)
                            await self._safe_edit_message(query, 
                                "Sorry, couldn't load another challenge. Please try again.",
                                InlineKeyboardMarkup([[
                                    InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                                ]])
                            )
                    else:
                        # If no category, go back to categories
                        logger.warning(f"No category found for 'Try Another' request. Callback data: {query.data}")
                        try:
                            await self.handle_challenge_categories(update, context)
                        except Exception as e:
                            logger.error(f"Error returning to categories: {e}", exc_info=True)
                            await self._safe_edit_message(query, 
                                "Sorry, couldn't return to categories. Please use /challenge to start again.")
            else:
                # Check if it's a challenge_diff_ callback
                if query.data.startswith('challenge_diff_'):
                    try:
                        parts = query.data.split('_')
                        
                        # Handle special case of web_development
                        if len(parts) >= 4 and parts[2] == 'web' and parts[3] == 'development':
                            category = 'web_development'
                            difficulty = parts[4] if len(parts) > 4 else 'medium'
                        else:
                            category = parts[2]
                            difficulty = parts[3] if len(parts) > 3 else 'medium'
                        
                        logger.info(f"Handling difficulty selection: category={category}, difficulty={difficulty}")
                        
                        # Get and display a challenge
                        challenge = self.get_challenge(category, difficulty)
                        
                        if not challenge:
                            await self._safe_edit_message(query, 
                                f"Sorry, no challenges available for {category} at {difficulty} level.",
                                InlineKeyboardMarkup([[
                                    InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                                ]])
                            )
                            return
                        
                        # Format message
                        message = (
                            f"🎯 <b>Coding Challenge</b>\n\n"
                            f"<b>{html.escape(challenge['title'])}</b>\n\n"
                            f"📝 <b>Description:</b>\n{html.escape(challenge['description'])}\n\n"
                            f"Category: {html.escape(challenge.get('category', category).title())}\n"
                            f"Difficulty: {difficulty.title()}\n"
                            f"Points: {challenge.get('points', 10)}"
                        )

                        keyboard = [
                            [
                                InlineKeyboardButton("💡 Show Hint", 
                                    callback_data=f"challenge_hint_{difficulty}_{challenge.get('id', '0')}"),
                                InlineKeyboardButton("🇸🇴 Translate", 
                                    callback_data=f"challenge_translate_{category}_{difficulty}_{challenge.get('id', '0')}")
                            ],
                            [InlineKeyboardButton("✍️ Submit Solution", 
                                callback_data=f"challenge_submit_{difficulty}_{challenge.get('id', '0')}")],
                            [InlineKeyboardButton("🔄 Try Another", 
                                callback_data=f"challenge_another_{difficulty}_{category}")],
                            [InlineKeyboardButton("« Back to Difficulty", 
                                callback_data=f"challenge_category_{category}")],
                            [InlineKeyboardButton("« Back to Categories", 
                                callback_data="challenge_categories")]
                        ]
                        
                        # Store challenge in user_data for later
                        context.user_data['current_challenge'] = challenge

                        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
                    except Exception as e:
                        logger.error(f"Error handling challenge_diff_ callback: {e}", exc_info=True)
                        await self._safe_edit_message(query, 
                            "Sorry, there was an error loading the challenge. Please try again.",
                            InlineKeyboardMarkup([[
                                InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                            ]])
                        )
                else:
                    # Unknown callback
                    logger.warning(f"Unknown challenge button callback: {query.data}")
                    await self._safe_edit_message(query, 
                        "Sorry, this action is not recognized. Please try again.",
                        InlineKeyboardMarkup([[
                            InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                        ]])
                    )
        except Exception as e:
            logger.error(f"Error in challenge button handling: {e}", exc_info=True)
            try:
                # Add a timestamp to make message content unique
                error_time = datetime.now().strftime("%H:%M:%S")
                await self._safe_edit_message(query, 
                    f"Sorry, something went wrong ({error_time}). Please try /challenge again.",
                    InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Start Over", callback_data="challenge_categories")
                    ]])
                )
            except Exception as inner_e:
                logger.error(f"Failed to send error message: {inner_e}", exc_info=True)

    async def _safe_edit_message(self, query, text, reply_markup=None, parse_mode=None):
        """Safely edit a message with error handling for 'message not modified' errors."""
        try:
            # Only add invisible character if absolutely necessary
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except telegram.error.BadRequest as e:
            # Handle "message is not modified" errors
            if "message is not modified" in str(e).lower():
                # This is ok, message is already showing the correct content
                logger.debug("Message not modified error - content already matches")
                pass
            else:
                # Re-raise other BadRequest errors
                raise

    def get_challenge(self, category, difficulty):
        """Get a random challenge from the given category and difficulty."""
        try:
            # Check if we have cached challenges
            if hasattr(self, '_challenge_cache') and category in self._challenge_cache and difficulty in self._challenge_cache[category]:
                # Use cached challenges
                challenges_for_difficulty = self._challenge_cache[category][difficulty]
                if challenges_for_difficulty:
                    challenge = random.choice(challenges_for_difficulty)
                    # Add category and difficulty info
                    challenge_copy = challenge.copy()  # Create a copy to avoid modifying the cached version
                    challenge_copy['category'] = category
                    challenge_copy['difficulty'] = difficulty
                    return challenge_copy
            
            # Load challenges
            with open('resources/programming_challenges.json', 'r', encoding='utf-8') as f:
                all_challenges = json.load(f)
            
            # Initialize cache if needed
            if not hasattr(self, '_challenge_cache'):
                self._challenge_cache = {}
            
            # Handle legacy category naming
            if category not in all_challenges and category.startswith('programming'):
                category = 'programming'
                
            # Make sure the category exists
            if category not in all_challenges:
                logger.warning(f"Invalid category selected: {category}")
                return None
                
            # Cache the entire category
            self._challenge_cache[category] = all_challenges[category]
                
            # Make sure the difficulty exists
            difficulty_challenges = all_challenges.get(category, {}).get(difficulty, [])
            if not difficulty_challenges:
                logger.warning(f"No challenges found for category {category} at {difficulty} level")
                return None
                
            # Pick a random challenge
            challenge = random.choice(difficulty_challenges)
            
            # Add category and difficulty info
            challenge_copy = challenge.copy()  # Create a copy to avoid modifying the original
            challenge_copy['category'] = category
            challenge_copy['difficulty'] = difficulty
            
            return challenge_copy
        except Exception as e:
            logger.error(f"Error getting challenge: {e}")
            return None

    async def progress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        stats = self.db_manager.get_progress_stats(user_id)  # Already implemented
        
        await update.message.reply_text(
            f"📊 *Your Progress*\n\n"
            f"▰▰▰▰▰▰▰▰▰ 72%\n"
            f"Completed: {stats['completed']}/221\n"
            f"Time Spent: {stats['time']} hours\n"
            f"Points: {stats['points']}\n\n"
            "▰ Web Dev (85%)\n▰ Security (63%)\n▰ DevOps (41%)",
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_challenge_submit(self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
        """Handle challenge submission button click."""
        try:
            # Parse the callback data to get challenge details
            data_parts = query.data.split('_')
            logger.info(f"Handling submission request with data: {query.data}")
            
            difficulty = data_parts[2]
            challenge_id = data_parts[3] if len(data_parts) > 3 else None
            
            # Get challenge from existing user_data if available
            challenge = context.user_data.get('current_challenge')
            
            # If no challenge in user_data, we can't proceed
            if not challenge:
                await self._safe_edit_message(query,
                    "Sorry, I couldn't find which challenge you're submitting. Please try selecting a challenge again.",
                    InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                    ]]),
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Set waiting state for answer
            context.user_data['waiting_for_challenge_answer'] = True
            
            # Update message to prompt for answer
            await self._safe_edit_message(query,
                f"📝 <b>Submit Your Solution</b>\n\n"
                f"Please send your solution for:\n"
                f"<b>{html.escape(challenge['title'])}</b>\n\n"
                f"You can:\n"
                f"• Send code as text\n"
                f"• Upload a file\n"
                f"• Share a GitHub link\n\n"
                f"Use /cancel to cancel submission",
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"User {query.from_user.id} started challenge submission for {challenge.get('id', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error in challenge submission handling: {e}", exc_info=True)
            await self._safe_edit_message(query,
                "Sorry, something went wrong with your submission request. Please try again.",
                InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Categories", callback_data="challenge_categories")
                ]]),
                parse_mode=ParseMode.HTML
            )

async def daily_validation_job(context: ContextTypes.DEFAULT_TYPE):
    challenges = load_challenges()  # Existing challenge loader
    resources = load_resources()    # Existing resource loader
    
    validator = ContentValidator(challenges, resources)
    
    # Run validations
    duplicates = validator.find_duplicate_challenges()
    broken_links = await validator.check_resource_links()
    difficulty_issues = validator.validate_difficulty()
    
    # Generate report
    report = f"""📊 Daily Content Report:
    - Duplicate Challenges: {len(duplicates)}
    - Broken Resources: {len(broken_links)}
    - Difficulty Issues: {sum(len(v) for v in difficulty_issues.values())}
    """
    
    # Send to admin chat
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=report,
        parse_mode=ParseMode.MARKDOWN
    )

async def main():
    # Check for existing instance in a Windows-compatible way
    pid_file = 'bot.pid'
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                old_pid = int(f.read())
            # Check if process is still running (Windows-compatible way)
            import psutil
            if psutil.pid_exists(old_pid):
                print(f"Bot is already running with PID {old_pid}")
                sys.exit(1)
        except (OSError, ValueError, ImportError):
            # Process not running, PID file is invalid, or psutil not available
            pass
    
    # Write PID file
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    try:
        # Initialize logging
        bot = TelegramBot(config.BOT_TOKEN)
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}", exc_info=True)
    finally:
        # Clean up PID file
        try:
            os.remove(pid_file)
        except OSError:
            pass
        # Ensure all tasks are cleaned up
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main()) 
