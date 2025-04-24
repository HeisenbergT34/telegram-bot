import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import json

logger = logging.getLogger(__name__)

class CallbackHandlers:
    def __init__(self):
        self.resources_file = "resources/learning_resources.json"

    async def handle_resource_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callbacks for resource navigation."""
        query = update.callback_query
        await query.answer()
        
        try:
            # Load resources
            with open(self.resources_file, 'r', encoding='utf-8') as f:
                resources = json.load(f)
            
            # Parse callback data
            data = query.data.split('_', 3)  # Split into max 4 parts
            action = data[1]  # 'category' or 'level'
            
            if action == 'category':
                category_id = '_'.join(data[2:])  # Handle categories with underscores
                if category_id == 'web':
                    category_id = 'web_development'
                
                # Show levels for category
                levels = resources['categories'][category_id]['levels']
                keyboard = []
                for level in levels:
                    keyboard.append([
                        InlineKeyboardButton(
                            level.title(),
                            callback_data=f"resource_level_{category_id}_{level}"
                        )
                    ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"Choose your level in {category_id.replace('_', ' ').title()}:",
                    reply_markup=reply_markup
                )
                
            elif action == 'level':
                category_id = data[2]
                level = data[3]
                
                # Show resources for level
                resources_list = resources['categories'][category_id]['levels'][level]
                message = f"📚 {category_id.replace('_', ' ').title()} - {level.title()} Resources:\n\n"
                
                for i, resource in enumerate(resources_list, 1):
                    message += (
                        f"{i}. [{resource['name']}]({resource['url']})\n"
                        f"   {resource['description']}\n"
                        f"   Type: {resource['type']}\n\n"
                    )
                
                # Add back button
                keyboard = [[
                    InlineKeyboardButton(
                        "◀️ Back to Levels",
                        callback_data=f"resource_category_{category_id}"
                    )
                ]]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                
        except Exception as e:
            logger.error(f"Error handling resource callback: {e}")
            await query.edit_message_text(
                "Sorry, this category is not available. Please try again."
            )

    async def handle_button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general button callbacks."""
        query = update.callback_query
        await query.answer()
        
        try:
            # Handle other button callbacks here
            pass
            
        except Exception as e:
            logger.error(f"Error handling button callback: {e}")
            await query.edit_message_text(
                "Sorry, something went wrong. Please try again."
            ) 