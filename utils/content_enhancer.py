async def generate_missing_explanations(challenges):
    """AI-powered explanation generator"""
    prompt = """Given this programming challenge:
    Question: {question}
    Answers: {answers}
    
    Generate a 2-3 sentence explanation that:
    1. Explains why the correct answer works
    2. Mentions common pitfalls
    3. Suggests best practices
    """
    
    for ch in [c for c in challenges if not c.get('explanation')]:
        response = await ai_api.generate(
            prompt.format(question=ch['question'], answers=ch['answers'])
        )
        ch['explanation'] = response.strip()
        logger.info(f"Added explanation to challenge {ch['id']}") 