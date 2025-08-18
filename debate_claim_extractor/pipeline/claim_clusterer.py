"""
Claim clustering for grouping related claims from YouTube-style transcripts
Groups claims by semantic similarity and argumentative relationships
"""

import logging
import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass

from .models import Claim, ClaimType

logger = logging.getLogger(__name__)


@dataclass
class ClaimCluster:
    """A cluster of related claims"""
    id: str
    claims: List[Claim]
    primary_claim: Claim  # The claim that best represents this cluster
    cluster_type: ClaimType
    topics: Set[str]
    stance: str = "neutral"  # "pro", "con", "neutral"
    confidence: float = 0.0


class ClaimClusterer:
    """
    Groups related claims into clusters for better analysis and presentation
    """
    
    def __init__(self, similarity_threshold: float = 0.6):
        """
        Args:
            similarity_threshold: Minimum similarity score to group claims
        """
        self.similarity_threshold = similarity_threshold
        
        # Keywords for stance detection
        self.pro_indicators = [
            'support', 'agree', 'believe', 'think', 'yes', 'true', 'correct',
            'definitely', 'absolutely', 'clearly', 'obviously'
        ]
        
        self.con_indicators = [
            'disagree', 'false', 'wrong', 'incorrect', 'not true', 'impossible',
            'never', 'not', 'reject', 'deny', 'refute', 'challenge'
        ]
        
        # Topic keywords for free will debate
        self.topic_keywords = {
            'determinism': ['deterministic', 'predetermined', 'causality', 'cause', 'effect'],
            'choice': ['choice', 'choose', 'decision', 'decide', 'option', 'alternative'],
            'consciousness': ['conscious', 'awareness', 'mind', 'brain', 'neural', 'synapses'],
            'responsibility': ['responsible', 'blame', 'fault', 'accountable', 'guilty'],
            'physics': ['physics', 'quantum', 'uncertainty', 'chaos', 'random'],
            'psychology': ['psychological', 'behavior', 'addiction', 'disorder', 'mental'],
            'society': ['society', 'criminal', 'justice', 'punishment', 'prison'],
            'philosophy': ['philosophical', 'existence', 'universe', 'reality']
        }
    
    def cluster_claims(self, claims: List[Claim]) -> List[ClaimCluster]:
        """
        Group related claims into clusters
        
        Args:
            claims: List of claims to cluster
            
        Returns:
            List of claim clusters
        """
        if not claims:
            return []
        
        logger.info(f"Clustering {len(claims)} claims")
        
        # Step 1: Calculate similarity matrix
        similarity_matrix = self._calculate_similarity_matrix(claims)
        
        # Step 2: Group claims into clusters
        clusters = self._group_claims(claims, similarity_matrix)
        
        # Step 3: Enhance clusters with metadata
        enhanced_clusters = self._enhance_clusters(clusters)
        
        logger.info(f"Created {len(enhanced_clusters)} claim clusters")
        return enhanced_clusters
    
    def _calculate_similarity_matrix(self, claims: List[Claim]) -> Dict[Tuple[int, int], float]:
        """Calculate similarity scores between all pairs of claims"""
        similarity_matrix = {}
        
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                similarity = self._calculate_claim_similarity(claims[i], claims[j])
                similarity_matrix[(i, j)] = similarity
        
        return similarity_matrix
    
    def _calculate_claim_similarity(self, claim1: Claim, claim2: Claim) -> float:
        """
        Calculate similarity between two claims
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        score = 0.0
        
        # Type similarity (same type = bonus)
        if claim1.type == claim2.type:
            score += 0.3
        
        # Text similarity (simple word overlap for now)
        words1 = set(self._extract_keywords(claim1.text.lower()))
        words2 = set(self._extract_keywords(claim2.text.lower()))
        
        if words1 and words2:
            overlap = len(words1.intersection(words2))
            union = len(words1.union(words2))
            jaccard_score = overlap / union if union > 0 else 0
            score += jaccard_score * 0.4
        
        # Speaker similarity (different speakers discussing same topic)
        if claim1.speaker == claim2.speaker:
            score += 0.1
        elif claim1.speaker != "UNKNOWN" and claim2.speaker != "UNKNOWN":
            score += 0.05  # Different speakers can still discuss same topic
        
        # Temporal proximity (claims close together are more likely related)
        char_distance = abs(claim1.char_start - claim2.char_start)
        if char_distance < 1000:  # Within ~1000 characters
            score += 0.2 * (1000 - char_distance) / 1000
        
        # Topic similarity
        topics1 = self._extract_topics(claim1.text)
        topics2 = self._extract_topics(claim2.text)
        
        if topics1.intersection(topics2):
            score += 0.3
        
        return min(score, 1.0)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from claim text"""
        # Remove stopwords and extract meaningful terms
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'has', 'have', 'had', 'that', 'this', 'it', 'they', 'we', 'you', 'i'}
        
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if len(w) > 3 and w not in stopwords]
        
        return keywords
    
    def _extract_topics(self, text: str) -> Set[str]:
        """Extract topic labels from claim text"""
        topics = set()
        text_lower = text.lower()
        
        for topic, keywords in self.topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.add(topic)
        
        return topics
    
    def _group_claims(self, claims: List[Claim], similarity_matrix: Dict[Tuple[int, int], float]) -> List[List[Claim]]:
        """Group claims into clusters based on similarity"""
        n = len(claims)
        visited = [False] * n
        clusters = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            # Start a new cluster
            cluster = [claims[i]]
            visited[i] = True
            
            # Find all claims similar to this one
            for j in range(i + 1, n):
                if visited[j]:
                    continue
                
                # Check similarity with any claim in current cluster
                should_add = False
                for cluster_claim_idx in range(len(claims)):
                    if claims[cluster_claim_idx] in cluster:
                        key = (min(cluster_claim_idx, j), max(cluster_claim_idx, j))
                        if key in similarity_matrix and similarity_matrix[key] >= self.similarity_threshold:
                            should_add = True
                            break
                
                if should_add:
                    cluster.append(claims[j])
                    visited[j] = True
            
            clusters.append(cluster)
        
        return clusters
    
    def _enhance_clusters(self, claim_groups: List[List[Claim]]) -> List[ClaimCluster]:
        """Enhance clusters with metadata and analysis"""
        clusters = []
        
        for i, claims in enumerate(claim_groups):
            if not claims:
                continue
            
            # Find primary claim (highest confidence)
            primary_claim = max(claims, key=lambda c: c.confidence)
            
            # Determine cluster type (most common type)
            type_counts = defaultdict(int)
            for claim in claims:
                type_counts[claim.type] += 1
            cluster_type = max(type_counts, key=type_counts.get)
            
            # Extract topics
            all_topics = set()
            for claim in claims:
                all_topics.update(self._extract_topics(claim.text))
            
            # Determine stance
            stance = self._determine_stance(claims)
            
            # Calculate cluster confidence (average of claim confidences)
            avg_confidence = sum(c.confidence for c in claims) / len(claims)
            
            cluster = ClaimCluster(
                id=f"cluster_{i}",
                claims=claims,
                primary_claim=primary_claim,
                cluster_type=cluster_type,
                topics=all_topics,
                stance=stance,
                confidence=avg_confidence
            )
            
            clusters.append(cluster)
        
        # Sort clusters by confidence and importance
        clusters.sort(key=lambda c: (len(c.claims), c.confidence), reverse=True)
        
        return clusters
    
    def _determine_stance(self, claims: List[Claim]) -> str:
        """Determine the overall stance of claims in a cluster"""
        pro_score = 0
        con_score = 0
        
        for claim in claims:
            text_lower = claim.text.lower()
            
            # Count pro indicators
            pro_score += sum(1 for indicator in self.pro_indicators if indicator in text_lower)
            
            # Count con indicators  
            con_score += sum(1 for indicator in self.con_indicators if indicator in text_lower)
        
        if pro_score > con_score * 1.2:  # Need clear majority
            return "pro"
        elif con_score > pro_score * 1.2:
            return "con"
        else:
            return "neutral"
