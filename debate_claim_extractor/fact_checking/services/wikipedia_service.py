"""
Wikipedia-based fact-checking service implementation.
"""
import asyncio
import aiohttp
import logging
import time
from typing import Optional, List, Dict, Any
from urllib.parse import quote
import re

from ..fact_models import FactCheckResult, VerificationSource, VerificationStatus, SourceType
from .base_service import FactCheckService

logger = logging.getLogger(__name__)

class WikipediaFactCheckService(FactCheckService):
    """Fact-checking service using Wikipedia API."""
    
    def __init__(self, timeout_seconds: int = 10):
        """Initialize Wikipedia fact-checking service.
        
        Args:
            timeout_seconds: Request timeout in seconds
        """
        super().__init__(name="wikipedia", timeout_seconds=timeout_seconds)
        self.timeout = timeout_seconds
        self.base_url = "https://en.wikipedia.org/api/rest_v1"
        self.search_url = "https://en.wikipedia.org/w/api.php"
        
        # User agent for API requests
        self.headers = {
            'User-Agent': 'DebateFactChecker/1.0 (https://github.com/user/debate-check)'
        }
    
    async def verify_claim(self, claim_text: str) -> FactCheckResult:
        """Verify a claim using Wikipedia search and content.
        
        Args:
            claim_text: The claim to verify
            
        Returns:
            FactCheckResult with verification details
        """
        try:
            logger.debug(f"Wikipedia verifying: {claim_text[:100]}...")
            start_time = time.time()
            
            # Extract key entities/topics from the claim
            search_terms = self._extract_search_terms(claim_text)
            
            if not search_terms:
                logger.debug(f"No searchable terms found for claim: {claim_text[:50]}...")
                return FactCheckResult(
                    service_name=self.name,
                    query=claim_text,
                    claim_text=claim_text,
                    status=VerificationStatus.UNVERIFIED,
                    confidence=0.0,
                    verification_score=0.5,
                    sources=[],
                    explanation="No searchable terms found in claim"
                )
            
            logger.debug(f"Wikipedia search terms: {search_terms}")
            
            # Search Wikipedia for relevant articles
            articles = await self._search_wikipedia(search_terms)
            
            if not articles:
                logger.debug(f"No Wikipedia articles found for terms: {search_terms}")
                return FactCheckResult(
                    service_name=self.name,
                    query=' '.join(search_terms),
                    claim_text=claim_text,
                    status=VerificationStatus.UNVERIFIED,
                    confidence=0.0,
                    verification_score=0.5,
                    sources=[],
                    explanation="No relevant Wikipedia articles found"
                )
            
            logger.debug(f"Found {len(articles)} Wikipedia articles for analysis")
            
            # Get content from top articles and analyze
            verification_result = await self._analyze_articles(claim_text, articles)
            
            elapsed = time.time() - start_time
            logger.debug(f"Wikipedia verification completed in {elapsed:.2f}s for: {claim_text[:50]}...")
            
            return verification_result
            
        except asyncio.TimeoutError:
            logger.warning(f"Wikipedia verification timeout for: {claim_text[:50]}...")
            return FactCheckResult(
                service_name=self.name,
                query=claim_text,
                claim_text=claim_text,
                status=VerificationStatus.UNVERIFIED,
                confidence=0.0,
                verification_score=0.5,
                sources=[],
                explanation="Request timeout"
            )
        
        except Exception as e:
            logger.error(f"Wikipedia verification error for '{claim_text[:50]}...': {e}")
            return FactCheckResult(
                service_name=self.name,
                query=claim_text,
                claim_text=claim_text,
                status=VerificationStatus.ERROR,
                confidence=0.0,
                verification_score=0.5,
                sources=[],
                explanation=f"Verification error: {str(e)}"
            )
    
    def _extract_search_terms(self, claim_text: str) -> List[str]:
        """
        Args:
            claim_text: The claim text
            
        Returns:
            List of search terms
        """
        # Remove common filler words and extract key terms
        filler_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'can', 'shall', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
        
        # Extract multi-word phrases first (for named entities)
        multi_word_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Za-z][a-z]+)+\b', claim_text)
        named_entities = [phrase for phrase in multi_word_phrases]
        
        # Extract technical terms and numbers
        technical_terms = re.findall(r'\b[A-Za-z][a-z]*(?:-[a-z]+)+\b', claim_text.lower())
        numbers = re.findall(r'\b\d+(?:[.,]\d+)*\b', claim_text)
        
        # Extract important single words
        words = re.findall(r'\b[A-Za-z]+\b', claim_text.lower())
        meaningful_words = [w for w in words if w not in filler_words and len(w) > 2]
        
        # Find proper nouns (capitalized words)
        proper_nouns = re.findall(r'\b[A-Z][a-z]{2,}\b', claim_text)
        
        # Prioritize search terms in this order: named entities, technical terms, numbers, proper nouns, meaningful words
        search_candidates = named_entities + technical_terms + numbers + proper_nouns + meaningful_words
        
        # Deduplicate while preserving order
        seen = set()
        unique_terms = []
        for term in search_candidates:
            term_lower = term.lower()
            if term_lower not in seen:
                seen.add(term_lower)
                unique_terms.append(term)
        
        # Build optimal search terms: include at least one multi-word phrase if available
        # and prioritize longer, more specific terms
        final_terms = []
        
        # Add named entities and multi-word phrases first
        for term in unique_terms:
            if ' ' in term and len(final_terms) < 2:
                final_terms.append(term)
        
        # Then add single but important terms (proper nouns, technical terms)
        for term in unique_terms:
            if ' ' not in term and term.lower() not in [t.lower() for t in final_terms] and len(final_terms) < 3:
                if term[0].isupper() or term in technical_terms or term in numbers:
                    final_terms.append(term)
        
        # Fill remaining slots with other meaningful words
        remaining_slots = 4 - len(final_terms)
        if remaining_slots > 0:
            for term in meaningful_words:
                if term.lower() not in [t.lower() for t in final_terms] and len(final_terms) < 4:
                    final_terms.append(term)
        
        return final_terms  # Return optimized search terms
    
    async def _search_wikipedia(self, search_terms: List[str]) -> List[Dict[str, Any]]:
        """Search Wikipedia for articles related to search terms.
        
        Args:
            search_terms: List of terms to search for
            
        Returns:
            List of article information
        """
        articles = []
        
        # First try searching with multi-word phrases intact
        for term in search_terms:
            try:
                # Use Wikipedia search API with exact phrase matching when possible
                if ' ' in term:
                    # For multi-word terms, try exact phrase matching first
                    search_query = f'"{term}"'
                else:
                    search_query = term
                
                params = {
                    'action': 'query',
                    'format': 'json',
                    'list': 'search',
                    'srsearch': search_query,
                    'srlimit': 2,  # Get top 2 results per term to focus on relevance
                    'srwhat': 'text'  # Search in article text, not just titles
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.search_url, 
                        params=params, 
                        headers=self.headers,
                        timeout=self.timeout
                    ) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            search_results = data.get('query', {}).get('search', [])
                            
                            for result in search_results:
                                # Skip disambiguation pages unless they're the only result
                                title = result.get('title', '')
                                if '(disambiguation)' in title and len(search_results) > 1:
                                    continue
                                    
                                articles.append({
                                    'title': title,
                                    'snippet': result.get('snippet', ''),
                                    'pageid': result.get('pageid'),
                                    'search_term': term,
                                    'score': result.get('score', 0)
                                })
                        
                        # Small delay to be respectful to Wikipedia
                        await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.warning(f"Wikipedia search error for term '{term}': {e}")
                continue
        
        # If we have multi-word search terms, also try combined searches
        if len(search_terms) >= 2:
            try:
                # Create a combined search for better context
                combined_query = ' '.join(search_terms[:2])  # Use first two terms
                params = {
                    'action': 'query',
                    'format': 'json',
                    'list': 'search',
                    'srsearch': combined_query,
                    'srlimit': 2,
                    'srwhat': 'text'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.search_url, 
                        params=params, 
                        headers=self.headers,
                        timeout=self.timeout
                    ) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            search_results = data.get('query', {}).get('search', [])
                            
                            for result in search_results:
                                title = result.get('title', '')
                                if '(disambiguation)' in title:
                                    continue
                                    
                                articles.append({
                                    'title': title,
                                    'snippet': result.get('snippet', ''),
                                    'pageid': result.get('pageid'),
                                    'search_term': combined_query,
                                    'score': result.get('score', 0)
                                })
                        
                        await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.warning(f"Wikipedia combined search error: {e}")
        
        # Remove duplicates, prioritize higher scores
        unique_articles = {}
        for article in articles:
            title = article['title']
            if title not in unique_articles or article.get('score', 0) > unique_articles[title].get('score', 0):
                unique_articles[title] = article
        
        # Sort by search score and relevance, then limit
        sorted_articles = sorted(unique_articles.values(), key=lambda x: x.get('score', 0), reverse=True)
        return sorted_articles[:5]  # Return top 5 unique articles
    
    async def _analyze_articles(self, claim_text: str, articles: List[Dict[str, Any]]) -> FactCheckResult:
        """Analyze Wikipedia articles to verify the claim.
        
        Args:
            claim_text: Original claim text
            articles: List of Wikipedia articles
            
        Returns:
            FactCheckResult with analysis
        """
        sources = []
        total_relevance = 0.0
        supporting_evidence = []
        
        for article in articles:
            try:
                # Get article summary
                title = article['title']
                encoded_title = quote(title.replace(' ', '_'))
                
                summary_url = f"{self.base_url}/page/summary/{encoded_title}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        summary_url, 
                        headers=self.headers,
                        timeout=self.timeout
                    ) as response:
                        
                        if response.status == 200:
                            summary_data = await response.json()
                            
                            # Create source
                            source = VerificationSource(
                                name=summary_data.get('title', title),
                                url=summary_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                                source_type=SourceType.ACADEMIC,  # Wikipedia is academic/educational
                                credibility_score=0.8,  # Wikipedia is generally credible
                                date_published=None  # Wikipedia doesn't have single publication dates
                            )
                            sources.append(source)
                            
                            # Analyze relevance
                            extract = summary_data.get('extract', '')
                            snippet = article.get('snippet', '')
                            
                            relevance = self._calculate_relevance(claim_text, extract + ' ' + snippet)
                            total_relevance += relevance
                            
                            if relevance > 0.3:  # Consider it supporting evidence
                                supporting_evidence.append({
                                    'title': title,
                                    'extract': extract[:200] + '...' if len(extract) > 200 else extract,
                                    'relevance': relevance
                                })
                        
                        # Be respectful to Wikipedia's servers
                        await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.warning(f"Error analyzing article '{article.get('title', 'Unknown')}': {e}")
                continue
        
        # Calculate overall verification result
        if not sources:
            return FactCheckResult(
                service_name=self.name,
                query=' '.join([a.get('search_term', '') for a in articles]),
                claim_text=claim_text,
                status=VerificationStatus.UNVERIFIED,
                confidence=0.0,
                verification_score=0.5,
                sources=[],
                explanation="No sources could be analyzed"
            )
        
        avg_relevance = total_relevance / len(sources) if sources else 0.0
        
        # Determine status based on evidence (adjusted thresholds for Wikipedia)
        if avg_relevance > 0.4:  # Lower threshold since Wikipedia summaries are brief
            status = VerificationStatus.LIKELY_TRUE
            confidence = min(0.8, avg_relevance + 0.2)  # Boost confidence for Wikipedia
        elif avg_relevance > 0.2:  # Mixed evidence threshold
            status = VerificationStatus.MIXED  
            confidence = avg_relevance * 0.8
        else:
            status = VerificationStatus.UNVERIFIED
            confidence = avg_relevance * 0.5
        
        # Generate explanation
        if supporting_evidence:
            evidence_desc = ', '.join([ev['title'] for ev in supporting_evidence[:3]])
            explanation = f"Found relevant information in Wikipedia articles: {evidence_desc}"
        else:
            explanation = f"Searched {len(sources)} Wikipedia articles but found limited relevant information"
        
        return FactCheckResult(
            service_name=self.name,
            query=' '.join([a.get('search_term', '') for a in articles]),
            claim_text=claim_text,
            status=status,
            confidence=confidence,
            verification_score=avg_relevance,
            sources=sources,
            explanation=explanation
        )
    
    def _calculate_relevance(self, claim_text: str, content: str) -> float:
        """Calculate relevance between claim and content.
        
        Args:
            claim_text: The claim text
            content: The content to compare against
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not content or not claim_text:
            return 0.0
            
        claim_lower = claim_text.lower()
        content_lower = content.lower()
        
        # Extract key terms from claim
        claim_key_terms = self._extract_key_terms(claim_text)
        
        # Remove HTML tags from content
        content_clean = re.sub(r'<[^>]+>', '', content_lower)
        
        # Score components
        scores = []
        
        # 1. Exact phrase matching (highest weight)
        exact_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Za-z][a-z]+)+\b', claim_text)
        for phrase in exact_phrases:
            if phrase.lower() in content_clean:
                scores.append(1.0)  # Perfect match for exact phrases
        
        # 2. Key term presence (high weight)
        key_term_matches = 0
        for term in claim_key_terms:
            if term.lower() in content_clean:
                key_term_matches += 1
                
        if claim_key_terms:
            key_term_score = key_term_matches / len(claim_key_terms)
            scores.append(key_term_score * 0.8)  # Weight key terms highly
        
        # 3. Scientific/technical term matching (high weight for scientific claims)
        scientific_terms = self._extract_scientific_terms(claim_text)
        scientific_matches = 0
        for term in scientific_terms:
            # Check for exact match or variations
            term_pattern = rf'\b{re.escape(term.lower())}\b'
            if re.search(term_pattern, content_clean):
                scientific_matches += 1
                
        if scientific_terms:
            scientific_score = scientific_matches / len(scientific_terms)
            scores.append(scientific_score * 0.9)  # High weight for scientific accuracy
        
        # 4. Proper noun matching (names, places, etc.)
        proper_nouns = re.findall(r'\b[A-Z][a-z]{2,}\b', claim_text)
        proper_noun_matches = 0
        for noun in proper_nouns:
            if noun.lower() in content_clean:
                proper_noun_matches += 1
                
        if proper_nouns:
            proper_noun_score = proper_noun_matches / len(proper_nouns)
            scores.append(proper_noun_score * 0.7)
        
        # 5. Number/measurement matching
        claim_numbers = re.findall(r'\b\d+(?:[.,]\d+)*\b', claim_text)
        for number in claim_numbers:
            if number in content_clean:
                scores.append(0.8)  # High score for matching numbers
        
        # 6. Semantic word overlap (lower weight)
        claim_words = set(re.findall(r'\b[a-z]{3,}\b', claim_lower))
        content_words = set(re.findall(r'\b[a-z]{3,}\b', content_clean))
        
        # Remove common words
        common_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'was', 'one', 'our', 
            'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see',
            'two', 'way', 'who', 'boy', 'did', 'does', 'each', 'she', 'use', 'been', 'have', 'her', 
            'here', 'they', 'will', 'would', 'could', 'should', 'this', 'that', 'these', 'those',
            'into', 'from', 'with', 'over', 'such', 'then', 'them', 'well', 'were', 'what', 'when',
            'where', 'which', 'while', 'about', 'after', 'before', 'being', 'between', 'during',
            'through', 'under', 'above', 'below', 'within'
        }
        
        claim_words -= common_words
        content_words -= common_words
        
        if claim_words:
            intersection = len(claim_words & content_words)
            claim_coverage = intersection / len(claim_words)
            scores.append(claim_coverage * 0.4)  # Lower weight for general word overlap
        
        # Calculate final score
        if not scores:
            return 0.0
        
        # Use weighted average, favoring higher scores
        final_score = max(scores) * 0.6 + (sum(scores) / len(scores)) * 0.4
        
        return min(1.0, final_score)
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms that are important for fact-checking."""
        # Extract proper nouns, technical terms, and important concepts
        proper_nouns = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
        multi_word = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Za-z][a-z]+)+\b', text)
        numbers = re.findall(r'\b\d+(?:[.,]\d+)*\b', text)
        
        # Important scientific/technical keywords
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        
        # Filter for potentially important terms
        important_words = []
        for word in words:
            # Skip common words but keep scientific/technical terms
            if (len(word) >= 6 or 
                any(suffix in word for suffix in ['tion', 'sion', 'ment', 'ness', 'ity', 'ism', 'ogy', 'ics']) or
                any(prefix in word for prefix in ['bio', 'geo', 'photo', 'electr', 'therm', 'chrom'])):
                important_words.append(word)
        
        return proper_nouns + multi_word + numbers + important_words[:3]
    
    def _extract_scientific_terms(self, text: str) -> List[str]:
        """Extract scientific and technical terms from text."""
        # Common scientific terms and patterns
        scientific_patterns = [
            r'\b(?:DNA|RNA|proteins?|genes?|chromosomes?)\b',
            r'\b(?:evolution|natural selection|mutation|adaptation)\b',
            r'\b(?:photosynthesis|respiration|metabolism)\b',
            r'\b(?:climate change|global warming|greenhouse)\b',
            r'\b(?:vaccines?|immunization|antibodies|immunity)\b',
            r'\b(?:relativity|quantum|physics|theory)\b',
            r'\b(?:carbon dioxide|oxygen|hydrogen|molecules?)\b',
            r'\b(?:bacteria|virus|pathogen|microorganism)\b',
            r'\b(?:polio|measles|smallpox|tuberculosis)\b',
            r'\b(?:Watson|Crick|Einstein|Darwin|Newton)\b',
            r'\b(?:helix|structure|discovery|experiment)\b',
            r'\b(?:glucose|sunlight|energy|chemical)\b',
            r'\b(?:universe|expansion|cosmic|stellar)\b',
            r'\b(?:fossil fuels?|emissions?|atmosphere)\b',
            r'\b\d+(?:[.,]\d+)*(?:\s*(?:meters?|seconds?|degrees?|percent))\b'
        ]
        
        scientific_terms = []
        for pattern in scientific_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            scientific_terms.extend(matches)
        
        return list(set(scientific_terms))  # Remove duplicates
    
    async def is_available(self) -> bool:
        """Check if Wikipedia API is available.
        
        Returns:
            True if service is available
        """
        try:
            async with aiohttp.ClientSession() as session:
                test_url = f"{self.base_url}/page/summary/Test"
                async with session.get(
                    test_url, 
                    headers=self.headers,
                    timeout=5
                ) as response:
                    return response.status in [200, 404]  # 404 is fine, means API is working
        except:
            return False
