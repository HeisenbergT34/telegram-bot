import json
import random
import logging
import uuid

class ChallengeFetcher:
    def __init__(self):
        self.challenges_file = "resources/programming_challenges.json"
        self.challenges = self._load_challenges()

    def _load_challenges(self):
        try:
            with open(self.challenges_file, "r", encoding='utf-8') as f:
                challenges = json.load(f)
                logging.info("Successfully loaded custom challenges")
                return challenges
        except Exception as e:
            logging.error(f"Error loading custom challenges: {e}")
            return self._get_fallback_challenges()

    def get_challenge(self, category="programming", difficulty="medium"):
        """Get a challenge with consistent structure."""
        try:
            difficulty = difficulty.lower()
            if difficulty not in ["easy", "medium", "hard"]:
                difficulty = "medium"
            
            # Try to get challenges from the specified category
            if category in self.challenges and difficulty in self.challenges[category]:
                challenges = self.challenges[category][difficulty]
            else:
                # Fall back to programming category
                challenges = self.challenges.get("programming", {}).get(difficulty, [])
            
            if not challenges:
                return self._get_fallback_challenge(difficulty)
            
            challenge = random.choice(challenges)
            
            # Ensure all required fields are present
            if 'id' not in challenge:
                challenge['id'] = str(uuid.uuid4())[:8]
            
            if 'difficulty' not in challenge:
                challenge['difficulty'] = difficulty
                
            if 'category' not in challenge:
                challenge['category'] = category
                
            if 'hint' not in challenge:
                challenge['hint'] = "Think about the problem carefully and break it down into steps."
                
            if 'points' not in challenge:
                points = {"easy": 5, "medium": 10, "hard": 15}
                challenge['points'] = points.get(difficulty, 10)
                
            if 'title' not in challenge and 'name' in challenge:
                challenge['title'] = challenge['name']
            elif 'title' not in challenge:
                challenge['title'] = f"{category.title()} Challenge"
                
            return challenge
            
        except Exception as e:
            logging.error(f"Error getting challenge: {e}")
            return self._get_fallback_challenge(difficulty)

    def _get_fallback_challenges(self):
        return {
            "easy": [{
                "title": "Basic Password Security",
                "platform": "Basic Challenge",
                "difficulty": "easy",
                "description": "What makes a password weak? List three common password mistakes.",
                "category": "Security Basics",
                "hint": "Think about length, complexity, and personal information.",
                "points": 5,
                "id": "ps123"
            }],
            "medium": [{
                "title": "Safe Browsing",
                "platform": "Basic Challenge",
                "difficulty": "medium",
                "description": "How can you tell if a website is using HTTPS? Why is it important?",
                "category": "Web Security",
                "hint": "Look at the browser address bar and think about encryption.",
                "points": 10,
                "id": "sb456"
            }],
            "hard": [{
                "title": "Social Engineering",
                "platform": "Basic Challenge",
                "difficulty": "hard",
                "description": "What is phishing? How can you identify a phishing email?",
                "category": "Security Awareness",
                "hint": "Consider email sender addresses, urgency in messages, and suspicious links.",
                "points": 15,
                "id": "se789"
            }]
        }

    def _get_fallback_challenge(self, difficulty):
        return self._get_fallback_challenges()[difficulty][0]
