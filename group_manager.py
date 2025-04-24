import logging
from telegram import Update, Chat
from telegram.ext import ContextTypes
import sqlite3

logger = logging.getLogger(__name__)

class GroupManager:
    def __init__(self):
        self.db_path = 'bot.db'

    async def setup_group(self, chat: Chat, context: ContextTypes.DEFAULT_TYPE):
        """Set up a new group in the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Add group to database
            c.execute('''INSERT OR REPLACE INTO groups 
                        (group_id, title, is_active) 
                        VALUES (?, ?, TRUE)''',
                     (chat.id, chat.title))
            
            # Add current members
            async for member in context.bot.get_chat_members(chat.id):
                if not member.user.is_bot:
                    c.execute('''INSERT OR IGNORE INTO users 
                                (user_id, username, group_id, is_active, joined_date) 
                                VALUES (?, ?, ?, TRUE, CURRENT_TIMESTAMP)''',
                             (member.user.id, member.user.username, chat.id))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error setting up group: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def is_member_active(self, user_id: int, group_id: int) -> bool:
        """Check if a user is an active member of the group."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''SELECT is_active FROM users 
                        WHERE user_id = ? AND group_id = ?''',
                     (user_id, group_id))
            
            result = c.fetchone()
            return bool(result and result[0])
            
        except Exception as e:
            logger.error(f"Error checking member status: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def get_group_members(self, group_id: int):
        """Get all active members of a group."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''SELECT user_id, username FROM users 
                        WHERE group_id = ? AND is_active = TRUE''',
                     (group_id,))
            
            return c.fetchall()
            
        except Exception as e:
            logger.error(f"Error getting group members: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close() 