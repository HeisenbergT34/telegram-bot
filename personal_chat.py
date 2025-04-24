import logging
from telegram import Update
from telegram.ext import ContextTypes
from group_manager import GroupManager

logger = logging.getLogger(__name__)

class PersonalChatHandler:
    def __init__(self):
        self.group_manager = GroupManager()

    async def handle_personal_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in private chat."""
        if not update.effective_chat or update.effective_chat.type != 'private':
            return

        user_id = update.effective_user.id
        
        # Check if user is member of any managed group
        conn = None
        try:
            import sqlite3
            conn = sqlite3.connect('bot.db')
            c = conn.cursor()
            
            c.execute('''SELECT g.group_id, g.title 
                        FROM groups g
                        JOIN users u ON g.group_id = u.group_id
                        WHERE u.user_id = ? AND u.is_active = TRUE''',
                     (user_id,))
            
            groups = c.fetchall()
            
            if not groups:
                await update.message.reply_text(
                    "⚠️ You need to be a member of our group to use this bot.\n"
                    "Please join our group first!"
                )
                return
            
            # User is authorized, handle their message
            await self._handle_authorized_message(update, context)
            
        except Exception as e:
            logger.error(f"Error in personal chat handler: {e}")
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again later."
            )
        finally:
            if conn:
                conn.close()

    async def _handle_authorized_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages from authorized users."""
        await update.message.reply_text(
            "👋 Welcome to K-Tech Somali Bot!\n\n"
            "Use /help to see available commands.\n"
            "You can use me to:\n"
            "• Access learning resources\n"
            "• Take quizzes\n"
            "• Get daily tips\n"
            "• Participate in challenges"
        ) 