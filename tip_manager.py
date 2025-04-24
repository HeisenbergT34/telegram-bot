import json
import random
import logging

class TipManager:
    def __init__(self):
        try:
            with open('resources/tips.json', 'r', encoding='utf-8') as f:
                self.tips_data = json.load(f)
            
            # Handle both old and new format
            if isinstance(self.tips_data, dict) and 'categories' in self.tips_data:
                self.categories = self.tips_data['categories']
            else:
                # Create categories from the data
                self.categories = {}
                for tip in self.tips_data:
                    cat = tip.get('category', 'general')
                    if cat not in self.categories:
                        self.categories[cat] = []
                    self.categories[cat].append(tip)
            
            logging.info("Successfully loaded tips data")
        except Exception as e:
            logging.error(f"Error loading tips data: {e}")
            # Default empty data
            self.tips_data = {}
            self.categories = {}
        
    def get_random_tip(self, category=None, subcategory=None):
        """Get a random tip, optionally filtered by category and subcategory."""
        if not self.categories:
            return {
                "title": "Default Tip",
                "tip": "Always keep learning new technologies.",
                "category": "general",
                "tags": ["learning"]
            }
            
        try:
            if category and category in self.categories:
                if isinstance(self.categories[category], dict) and subcategory and subcategory in self.categories[category]:
                    tips = self.categories[category][subcategory]
                elif isinstance(self.categories[category], dict):
                    tips = [tip for subcat in self.categories[category].values() for tip in subcat]
                else:
                    tips = self.categories[category]
            else:
                all_tips = []
                for cat, content in self.categories.items():
                    if isinstance(content, dict):
                        # Handle nested structure
                        for subcat, subcat_tips in content.items():
                            all_tips.extend(subcat_tips)
                    else:
                        # Handle flat structure
                        all_tips.extend(content)
                tips = all_tips
            
            return random.choice(tips) if tips else None
        except Exception as e:
            logging.error(f"Error getting random tip: {e}")
            return None

    def format_tip(self, tip):
        """Format a tip with beautiful formatting and branding."""
        if not tip:
            return "No tip available at this time."
            
        # Non-translatable header
        header = (
            "✨ K-Tech Somali Tip ✨\n"
            "━━━━━━━━━━━━━━━\n\n"
        )
        
        # Format content based on available fields
        content = []
        
        # Title/category
        if 'title' in tip:
            content.append(f"🎯 {tip['title']}")
        elif 'category' in tip:
            content.append(f"🎯 {tip['category'].title()} Tip")
        
        # Main tip content
        if 'tip' in tip:
            content.append(f"\n💡 Tip:\n{tip['tip']}")
        elif 'content' in tip:
            content.append(f"\n💡 Tip:\n{tip['content']}")
        
        # Additional sections if available
        if 'explanation' in tip:
            content.append(f"\n📚 Explanation:\n{tip['explanation']}")
            
        if 'example' in tip:
            content.append(f"\n🔍 Example:\n{tip['example']}")
            
        if 'importance' in tip:
            content.append(f"\n⚡️ Importance: {tip['importance']}")
            
        if 'tags' in tip:
            if isinstance(tip['tags'], list):
                content.append(f"\n🏷 Tags: {', '.join(tip['tags'])}")
        elif 'category' in tip:
            content.append(f"\n🏷 Category: {tip['category']}")
        
        return header + "\n".join(content)

    def get_categories(self):
        """Get list of available categories."""
        return list(self.categories.keys())

    def get_subcategories(self, category):
        """Get list of subcategories for a given category."""
        if category in self.categories and isinstance(self.categories[category], dict):
            return list(self.categories[category].keys())
        return [] 