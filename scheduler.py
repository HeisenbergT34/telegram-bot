"""Scheduler for periodic tasks."""
import asyncio
import logging
import random
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import ContextTypes, Application, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
from discussion_manager import DiscussionManager
from tip_manager import TipManager
from challenge_fetcher import ChallengeFetcher
import config
from deep_translator import GoogleTranslator
import html

logger = logging.getLogger(__name__)

class ScheduleManager:
    def __init__(self, application: Application, bot_instance=None):
        """Initialize the scheduler."""
        self.app = application
        self.bot = bot_instance
        self.active_tasks = {}
        self.last_run_times = self._load_last_run_times()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up handlers for interactive buttons and commands."""
        self.app.add_handler(CallbackQueryHandler(
            self.handle_scheduled_button,
            pattern="^(translate_|poll_|challenge_)"
        ))
        
        # Add manual trigger commands
        self.app.add_handler(CommandHandler("send_tip", self.manual_send_tip))
        self.app.add_handler(CommandHandler("send_challenge", self.manual_send_challenge))
        self.app.add_handler(CommandHandler("send_poll", self.manual_send_poll))

    def _load_last_run_times(self):
        """Load last run times from persistent storage."""
        try:
            if Path('scheduler_state.pkl').exists():
                with open('scheduler_state.pkl', 'rb') as f:
                    return pickle.load(f)
            return {
                'tips': datetime.now() - timedelta(hours=config.TIP_INTERVAL_HOURS),
                'challenges': datetime.now() - timedelta(hours=config.CHALLENGE_INTERVAL_HOURS),
                'polls': datetime.now() - timedelta(hours=config.POLL_INTERVAL_HOURS)
            }
        except Exception as e:
            logger.error(f"Error loading scheduler state: {e}")
            return {}

    def _save_last_run_times(self):
        """Save last run times to persistent storage."""
        try:
            with open('scheduler_state.pkl', 'wb') as f:
                pickle.dump(self.last_run_times, f)
            logger.info("Saved scheduler state")
        except Exception as e:
            logger.error(f"Error saving scheduler state: {e}")

    async def start_scheduler(self):
        """Start all scheduled tasks."""
        logger.info("Starting scheduler...")
        
        try:
            # Calculate initial delays based on last run times
            now = datetime.now()
            
            for task_name, interval_hours in [
                ('tips', config.TIP_INTERVAL_HOURS),
                ('challenges', config.CHALLENGE_INTERVAL_HOURS),
                ('polls', config.POLL_INTERVAL_HOURS),
                ('cleanup', 24)  # Run cleanup daily
            ]:
                last_run = self.last_run_times.get(task_name)
                if last_run:
                    next_run = last_run + timedelta(hours=interval_hours)
                    if next_run < now:
                        initial_delay = 60  # Run in 1 minute if overdue
                    else:
                        initial_delay = (next_run - now).total_seconds()
                else:
                    initial_delay = 60
                
                task_func = getattr(self, f'schedule_{task_name}')
                self.active_tasks[task_name] = asyncio.create_task(
                self._run_periodic_task(
                        task_func,
                        interval_hours * 3600,
                        task_name,
                    initial_delay
                )
            )
            
            logger.info("Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}", exc_info=True)
            raise

    async def _run_periodic_task(self, task_func, interval, task_name, initial_delay=0):
        """Run a task periodically with proper error handling."""
        try:
            if initial_delay > 0:
                logger.info(f"Waiting {initial_delay} seconds before starting {task_name}")
                await asyncio.sleep(initial_delay)
            
            while True:
                try:
                    logger.info(f"Running scheduled task: {task_name}")
                    await task_func()
                    self.last_run_times[task_name] = datetime.now()
                    self._save_last_run_times()
                    logger.info(f"Completed scheduled task: {task_name}")
                except Exception as e:
                    logger.error(f"Error in {task_name} task: {e}", exc_info=True)
                
                next_run = datetime.now() + timedelta(seconds=interval)
                logger.info(f"Next {task_name} scheduled for: {next_run}")
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info(f"Task {task_name} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in {task_name} task: {e}", exc_info=True)
            raise

    async def schedule_tips(self):
        """Schedule tech tips."""
        try:
            with open('resources/tips.json', 'r', encoding='utf-8') as f:
                tips_data = json.load(f)
            
            # Get all tips into a flat list
            all_tips = []
            if isinstance(tips_data, dict):
                # If it's a dictionary, collect all tips from each category
                for category_tips in tips_data.values():
                    all_tips.extend(category_tips)
            else:
                # If it's already a list, use it directly
                all_tips = tips_data
            
            if all_tips:
                tip = random.choice(all_tips)
                
                message = (
                    "💡 *K-TECH DAILY TIP* 💡\n"
                    "━━━━━━━━━━━━━━━\n\n"
                    f"*{tip.get('category', 'Tech Tip')}*\n\n"
                    f"{tip.get('content', tip.get('title', 'No content available'))}\n\n"
                    "#TechTip #KTechSomali"
                )

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🌍 Translate to Somali",
                            callback_data=f"translate_tip_{tip.get('id', '1')}"
                        )
                    ]
                ]
                
                for group_id in config.TARGET_GROUPS:
                    try:
                        await self.app.bot.send_message(
                            chat_id=group_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        logger.info(f"Sent tip to group {group_id}")
                    except Exception as e:
                        logger.error(f"Failed to send tip to group {group_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error scheduling tip: {e}", exc_info=True)
            raise

    async def schedule_challenges(self):
        """Schedule and send coding challenges."""
        try:
            # Get random category from available categories
            categories = list(config.CHALLENGE_CATEGORIES.keys())
            if not categories:
                logger.error("No challenge categories configured")
                return
                
            category = random.choice(categories)
            
            # Get challenge for category
            challenge = self.bot.get_challenge(category, "medium")
            if not challenge:
                logger.error(f"No challenge found for category: {category}")
                return

            # Set default difficulty if not present
            difficulty = challenge.get('difficulty', 'medium')

            message = (
                f"✨ *K-TECH SOMALI CHALLENGE* ✨\n"
                f"━━━━━━━━━━━━━━━\n\n"
                f"🔍 Category: {config.CHALLENGE_CATEGORIES.get(category, 'General')}\n"
                f"📝 Challenge:\n{challenge['description']}\n\n"
                f"💡 Difficulty: {difficulty}\n"
                f"⏰ Time Limit: {challenge.get('time_limit', 30)} minutes\n\n"
                f"#CodingChallenge #KTechSomali"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "💡 Show Hint",
                        callback_data=f"challenge_hint_{category}_{difficulty}_{challenge['id']}"
                    ),
                    InlineKeyboardButton(
                        "✍️ Submit Solution",
                        callback_data=f"challenge_submit_{category}_{difficulty}_{challenge['id']}"
                    )
                ]
            ]

            for group_id in config.TARGET_GROUPS:
                try:
                    await self.app.bot.send_message(
                        chat_id=group_id,
                        text=message,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"Sent challenge to group {group_id}")
                except Exception as e:
                    logger.error(f"Error sending challenge to group {group_id}: {e}")

            # Save last run time
            self.last_run_times['challenges'] = datetime.now().isoformat()
            self._save_last_run_times()
            
            # Schedule next run
            next_run = datetime.now() + timedelta(hours=config.CHALLENGE_INTERVAL_HOURS)
            logger.info(f"Next challenges scheduled for: {next_run}")

        except Exception as e:
            logger.error(f"Error scheduling challenge: {e}")
            raise

    async def schedule_polls(self):
        """Schedule interactive polls."""
        try:
            with open('resources/polls.json', 'r', encoding='utf-8') as f:
                polls_data = json.load(f)
            
            # Get all polls into a flat list
            all_polls = []
            if isinstance(polls_data, dict):
                # If it's a dictionary, collect all polls from each category
                for category_polls in polls_data.values():
                    if isinstance(category_polls, list):
                        all_polls.extend(category_polls)
            else:
                # If it's already a list, use it directly
                all_polls = polls_data
            
            if all_polls:
                poll = random.choice(all_polls)
                
                # Create the poll message
                message = (
                    "📊 *K-TECH SOMALI POLL* 📊\n"
                    "━━━━━━━━━━━━━━━\n\n"
                    f"*{poll.get('category', 'Community Poll')}*\n\n"
                    f"{poll.get('question', 'No question available')}\n\n"
                    "#TechPoll #KTechSomali"
                )

                # Send poll to all target groups
                for group_id in config.TARGET_GROUPS:
                    try:
                        # First send the message
                        await self.app.bot.send_message(
                            chat_id=group_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        # Then send the actual poll
                        await self.app.bot.send_poll(
                            chat_id=group_id,
                            question=poll['question'],
                            options=poll['options'],
                            is_anonymous=False,
                            allows_multiple_answers=poll.get('multiple_answers', False),
                            type=poll.get('type', Poll.REGULAR)
                        )
                        logger.info(f"Sent poll to group {group_id}")
                    except Exception as e:
                        logger.error(f"Failed to send poll to group {group_id}: {e}")

        except Exception as e:
            logger.error(f"Error scheduling poll: {e}", exc_info=True)
            raise

    async def schedule_cleanup(self):
        """Run cleanup tasks."""
        try:
            logger.info("Starting cleanup tasks")
            
            # Clean up translation cache
            if self.bot:
                await self.bot.cleanup_translation_cache()
            
            # Clean up old scheduler states
            current_time = datetime.now()
            for task_name in list(self.last_run_times.keys()):
                last_run = self.last_run_times[task_name]
                if (current_time - last_run).days > 7:  # Remove entries older than 7 days
                    del self.last_run_times[task_name]
            self._save_last_run_times()
            
            logger.info("Cleanup tasks completed")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            raise

    async def handle_scheduled_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks from scheduled messages."""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data.startswith('translate_'):
                if self.bot:  # Use bot's translation method if available
                    try:
                        text = query.message.text
                        translated = await self.bot.translate_to_somali(text)
                        await query.edit_message_text(
                            text + "\n\n" + translated,
                            reply_markup=query.message.reply_markup,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Translation error: {e}")
                        await query.edit_message_text(
                            query.message.text + "\n\n[Somali translation will be added soon]",
                            reply_markup=query.message.reply_markup,
                            parse_mode=ParseMode.MARKDOWN
                        )
            elif query.data.startswith('challenge_'):
                if self.bot:  # Use bot's challenge handling methods
                    try:
                        await self.bot.handle_challenge_button(query, context)
                    except Exception as e:
                        logger.error(f"Error handling challenge button: {e}")
                        await query.edit_message_text(
                            "Sorry, there was an error processing your request. Please try using the /challenge command again.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                else:
                    await query.edit_message_text(
                        "Challenge interaction is currently unavailable.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            elif query.data.startswith('poll_'):
                # Handle poll-related button clicks
                pass
                    
        except Exception as e:
            logger.error(f"Error handling scheduled button: {e}", exc_info=True)
            await query.edit_message_text(
                "Sorry, there was an error processing your request.",
                parse_mode=ParseMode.MARKDOWN
            )

    async def manual_send_tip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger sending a tip."""
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("You don't have permission to use this command.")
            return
        
        try:
            await self.schedule_tips()
            await update.message.reply_text("Tip sent successfully!")
        except Exception as e:
            logger.error(f"Error sending manual tip: {e}")
            await update.message.reply_text("Failed to send tip. Check logs for details.")

    async def manual_send_challenge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger sending a challenge."""
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("You don't have permission to use this command.")
            return
        
        try:
            await self.schedule_challenges()
            await update.message.reply_text("Challenge sent successfully!")
        except Exception as e:
            logger.error(f"Error sending manual challenge: {e}")
            await update.message.reply_text("Failed to send challenge. Check logs for details.")

    async def manual_send_poll(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger sending a poll."""
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("You don't have permission to use this command.")
            return
        
        try:
            await self.schedule_polls()
            await update.message.reply_text("Poll sent successfully!")
        except Exception as e:
            logger.error(f"Error sending manual poll: {e}")
            await update.message.reply_text("Failed to send poll. Check logs for details.")

    def stop_scheduler(self):
        """Stop all scheduled tasks."""
        logger.info("Stopping scheduler...")
        for task_name, task in self.active_tasks.items():
            if not task.done():
                task.cancel()
        self._save_last_run_times()
        logger.info("Scheduler stopped")