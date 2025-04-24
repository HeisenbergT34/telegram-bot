import json
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class DiscussionManager:
    def __init__(self):
        self.discussions_file = "resources/discussions.json"
        self.active_poll = None
        self.active_discussion = None
        self.discussions = self._load_discussions()

    def _load_discussions(self) -> Dict:
        """Load discussion topics from JSON file."""
        try:
            with open(self.discussions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Discussions file not found. Creating default structure.")
            return self._create_default_discussions()
        except json.JSONDecodeError:
            logger.error("Error parsing discussions file")
            return self._create_default_discussions()

    def _create_default_discussions(self) -> Dict:
        """Create default discussion structure."""
        default_discussions = {
            "topics": {
                "security": [
                    {
                        "title": "Password Security Best Practices",
                        "description": "Let's discuss modern password security practices and their implementation.",
                        "key_points": [
                            "Password complexity requirements",
                            "Hash functions and salting",
                            "Multi-factor authentication",
                            "Password managers"
                        ],
                        "resources": [
                            "https://owasp.org/www-community/password-storage-cheat-sheet"
                        ]
                    }
                ],
                "programming": [
                    {
                        "title": "Clean Code Principles",
                        "description": "Discussion about writing maintainable and clean code.",
                        "key_points": [
                            "Naming conventions",
                            "Function length and responsibility",
                            "Code organization",
                            "Documentation practices"
                        ],
                        "resources": [
                            "https://github.com/ryanmcdermott/clean-code-javascript"
                        ]
                    }
                ]
            }
        }
        
        with open(self.discussions_file, 'w', encoding='utf-8') as f:
            json.dump(default_discussions, f, indent=4)
        
        return default_discussions

    def get_random_topics(self, count: int = 5) -> List[Dict]:
        """Get random topics for poll."""
        all_topics = []
        for category in self.discussions["topics"].values():
            all_topics.extend(category)
        
        return random.sample(all_topics, min(count, len(all_topics)))

    def start_poll(self, topics: List[Dict]) -> Dict:
        """Start a new discussion poll."""
        self.active_poll = {
            "topics": topics,
            "votes": {topic["title"]: 0 for topic in topics},
            "start_time": datetime.now().isoformat(),
            "voters": set()
        }
        return self.format_poll_message(topics)

    def format_poll_message(self, topics: List[Dict]) -> Dict:
        """Format poll message and options."""
        return {
            "message": (
                "✨ K-TECH SOMALI DISCUSSION POLL ✨\n"
                "━━━━━━━━━━━━━━━\n\n"
                "Vote for the topic you'd like to discuss!\n"
                "Poll ends in 30 minutes."
            ),
            "options": [topic["title"] for topic in topics]
        }

    def record_vote(self, topic_index: int, user_id: int) -> bool:
        """Record a vote for a topic."""
        if not self.active_poll or user_id in self.active_poll["voters"]:
            return False
            
        topic_title = list(self.active_poll["votes"].keys())[topic_index]
        self.active_poll["votes"][topic_title] += 1
        self.active_poll["voters"].add(user_id)
        return True

    def get_winning_topic(self) -> Optional[Dict]:
        """Get the topic with most votes."""
        if not self.active_poll:
            return None
            
        votes = self.active_poll["votes"]
        winning_title = max(votes.keys(), key=votes.get)
        
        for topic in self.active_poll["topics"]:
            if topic["title"] == winning_title:
                return topic
        
        return None

    def format_discussion_message(self, topic: Dict) -> str:
        """Format the discussion start message."""
        return (
            f"✨ K-TECH SOMALI DISCUSSION ✨\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📌 Topic: {topic['title']}\n\n"
            f"📝 Description:\n{topic['description']}\n\n"
            f"🔑 Key Points to Discuss:\n" +
            "\n".join(f"• {point}" for point in topic['key_points']) +
            "\n\n📚 Resources:\n" +
            "\n".join(f"• {resource}" for resource in topic['resources']) +
            "\n\nThe discussion will be active for 1 hour. Share your thoughts!"
        )

    def start_discussion(self, topic: Dict) -> str:
        """Start a new discussion."""
        self.active_discussion = {
            "topic": topic,
            "start_time": datetime.now().isoformat(),
            "participants": set()
        }
        return self.format_discussion_message(topic)

    def end_discussion(self) -> str:
        """End the current discussion."""
        if not self.active_discussion:
            return None
            
        return (
            "✨ DISCUSSION ENDED ✨\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"Thank you all for participating in the discussion about "
            f"{self.active_discussion['topic']['title']}!\n\n"
            f"Total Participants: {len(self.active_discussion['participants'])}"
        ) 