from typing import List, Dict

def generate_hard_challenges(base_challenges: List[Dict], count: int) -> List[Dict]:
    """Transform medium challenges into hard versions"""
    boosted = []
    for ch in base_challenges[:count]:
        boosted.append({
            **ch,
            'difficulty': 'hard',
            'question': f"{ch['question']} (Optimized Version)",
            'constraints': [
                "Time complexity must be O(n)",
                "Space complexity must be O(1)",
                "No external libraries allowed"
            ]
        })
    return boosted 