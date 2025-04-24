import json
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
import os

@dataclass
class QuizTracker:
    current_streak: int = 0
    correct_answers: int = 0
    total_questions: int = 0
    questions_until_summary: int = 10

    def record_answer(self, is_correct: bool):
        self.total_questions += 1
        if is_correct:
            self.correct_answers += 1
            self.current_streak += 1
        else:
            self.current_streak = 0

    def should_show_summary(self) -> bool:
        return self.total_questions > 0 and self.total_questions % self.questions_until_summary == 0

    def get_performance_message(self) -> str:
        score_percentage = (self.correct_answers / self.total_questions) * 100
        if score_percentage >= 90:
            return "🌟 Outstanding! You're mastering these concepts brilliantly!"
        elif score_percentage >= 70:
            return "🎯 Great job! You're showing strong understanding!"
        elif score_percentage >= 50:
            return "💪 Good effort! Keep practicing to improve further!"
        else:
            return "📚 Keep learning! Every question is a chance to grow!"

    def get_summary(self) -> str:
        return (
            "✨ K-TECH SOMALI QUIZ SUMMARY ✨\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"Questions Attempted: {self.total_questions}\n"
            f"Correct Answers: {self.correct_answers}\n"
            f"Success Rate: {(self.correct_answers / self.total_questions) * 100:.1f}%\n\n"
            f"{self.get_performance_message()}"
        )

    def reset(self):
        self.current_streak = 0
        self.correct_answers = 0
        self.total_questions = 0

class QuizHandler:
    def __init__(self, questions_dir: str = 'quiz_questions'):
        self.questions_dir = questions_dir
        self.tracker = QuizTracker()
        self.questions = {}
        self.asked_questions = {}  # Track asked questions per category
        self.load_questions()

    def load_questions(self):
        """Load questions from separate JSON files in the questions directory."""
        try:
            # Create questions directory if it doesn't exist
            if not os.path.exists(self.questions_dir):
                os.makedirs(self.questions_dir)

            # Load questions from each category file
            for filename in os.listdir(self.questions_dir):
                if filename.endswith('_questions.json'):
                    category = filename.replace('_questions.json', '')
                    with open(os.path.join(self.questions_dir, filename), 'r') as f:
                        data = json.load(f)
                        self.questions[category] = data['questions']
                        self.asked_questions[category] = set()  # Initialize set for tracking asked questions
        except Exception as e:
            print(f"Error loading questions: {str(e)}")
            self.questions = {}
            self.asked_questions = {}

    def get_random_question(self, category: Optional[str] = None) -> Dict:
        """Get a random question from the specified category that hasn't been asked yet."""
        if not category:
            raise ValueError("Category must be specified")
            
        if category not in self.questions:
            raise ValueError(f"Invalid category: {category}")

        # Get list of questions that haven't been asked yet
        available_questions = [
            q for i, q in enumerate(self.questions[category])
            if i not in self.asked_questions[category]
        ]

        # If all questions have been asked, reset tracking for this category
        if not available_questions:
            self.asked_questions[category] = set()
            available_questions = self.questions[category]

        question = random.choice(available_questions)
        
        # Track this question as asked using its index
        question_index = self.questions[category].index(question)
        self.asked_questions[category].add(question_index)
        
        # Ensure consistent branding and formatting
        question['formatted_text'] = (
            "✨ K-TECH SOMALI QUIZ ✨\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"{question['question']}\n\n"
            "Select your answer:"
        )
        
        # Add category to question for proper next question handling
        question['category'] = category
        
        return question

    def format_answer_response(self, question: Dict, selected_option: int) -> str:
        is_correct = selected_option == question['correct']
        self.tracker.record_answer(is_correct)

        response = (
            "✨ K-TECH SOMALI QUIZ ✨\n"
            "━━━━━━━━━━━━━━━\n\n"
        )

        if is_correct:
            response += "✅ Correct! Well done!\n\n"
        else:
            correct_option = question['options'][question['correct']]
            response += f"❌ Incorrect.\nThe correct answer was: {correct_option}\n\n"

        response += (
            "📚 Explanation:\n"
            f"{question['explanation']}\n\n"
            "🔑 Key Points:\n"
            f"{question.get('key_points', '• Remember this concept for future questions\n• Practice similar problems to reinforce learning')}"
        )

        return response

    def should_show_summary(self) -> bool:
        return self.tracker.should_show_summary()

    def get_summary(self) -> str:
        return self.tracker.get_summary()

    def reset_tracker(self):
        """Reset both the score tracker and asked questions tracking."""
        self.tracker.reset()
        for category in self.asked_questions:
            self.asked_questions[category] = set()

    def get_progress(self, category: str) -> Dict:
        """Get progress information for a category."""
        if category not in self.questions:
            return {"total": 0, "completed": 0, "remaining": 0}
            
        total = len(self.questions[category])
        completed = len(self.asked_questions.get(category, set()))
        return {
            "total": total,
            "completed": completed,
            "remaining": total - completed
        } 