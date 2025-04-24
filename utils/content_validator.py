import hashlib
import httpx
from typing import List, Dict
import asyncio
import logging

logger = logging.getLogger(__name__)

class ContentValidator:
    def __init__(self, challenges: List[Dict], resources: List[Dict]):
        self.challenges = challenges
        self.resources = resources
        
    def find_duplicate_challenges(self) -> List[int]:
        """Find challenges with identical question/answer fingerprints"""
        fingerprints = {}
        duplicates = []
        
        for idx, ch in enumerate(self.challenges):
            fp = hashlib.md5(
                f"{ch['question'].strip()}{''.join(sorted(ch['answers']))}".encode()
            ).hexdigest()
            
            if fp in fingerprints:
                duplicates.append((fingerprints[fp], idx))
            else:
                fingerprints[fp] = idx
                
        return duplicates

    async def check_resource_links(self) -> List[Dict]:
        """Verify all resource links are accessible"""
        broken = []
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for res in self.resources:
                try:
                    r = await client.head(res['url'], timeout=10)
                    if r.status_code >= 400:
                        broken.append(res)
                except (httpx.ConnectError, httpx.TimeoutException):
                    broken.append(res)
        return broken

    def validate_difficulty(self) -> Dict[str, List[int]]:
        """Check difficulty level consistency using NLP heuristics"""
        issues = {'too_hard': [], 'too_easy': []}
        for idx, ch in enumerate(self.challenges):
            question = ch['question'].lower()
            answer_length = sum(len(a) for a in ch['answers'])
            
            # Simple heuristic - refine based on actual data patterns
            if ch['difficulty'] == 'easy' and (len(question) > 200 or answer_length > 100):
                issues['too_hard'].append(idx)
            elif ch['difficulty'] == 'hard' and (len(question) < 100 or answer_length < 50):
                issues['too_easy'].append(idx)
                
        return issues 

    async def auto_repair():
        """Fix common content issues automatically"""
        while True:
            duplicates = self.find_duplicate_challenges()
            if duplicates:
                logger.info(f"Removing {len(duplicates)} duplicates")
                clean_challenges = [c for i,c in enumerate(challenges) 
                                  if i not in duplicates]
                save_clean_version(clean_challenges)
            
            broken = await self.check_resource_links()
            if broken:
                disable_broken_links(broken)
            
            await asyncio.sleep(3600)  # Run hourly 

    def auto_tag_resources(self, resources):
        """Auto-classify resource difficulty using title analysis"""
        DIFFICULTY_KEYWORDS = {
            'easy': ['intro', 'basic', 'starter', '101'],
            'hard': ['advanced', 'expert', 'deep dive', 'optimization']
        }
        
        for res in resources:
            if 'difficulty' not in res:
                title = res['title'].lower()
                if any(kw in title for kw in DIFFICULTY_KEYWORDS['hard']):
                    res['difficulty'] = 'hard'
                elif any(kw in title for kw in DIFFICULTY_KEYWORDS['easy']):
                    res['difficulty'] = 'easy'
                else:
                    res['difficulty'] = 'medium'
        return resources 