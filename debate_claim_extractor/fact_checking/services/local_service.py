"""
Local database fact-checking service for offline verification
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import difflib

from .base_service import FactCheckService
from ..fact_models import (
    FactCheckResult,
    VerificationSource,
    VerificationStatus,
    SourceType
)


class LocalFactCheckService(FactCheckService):
    """Local database fact-checking service"""
    
    def __init__(self, database_path: Optional[str] = None, **kwargs):
        super().__init__("local_database", **kwargs)
        
        self.database_path = Path(database_path or "data/fact_checks.db")
        self.similarity_threshold = 0.7  # Minimum similarity for matches
        
        # Ensure database directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def is_available(self) -> bool:
        """Check if local database is available"""
        return self.database_path.exists() or self._can_create_database()
    
    def _can_create_database(self) -> bool:
        """Check if we can create the database"""
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except:
            return False
    
    def _init_database(self):
        """Initialize the local fact-check database"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                
                # Create fact_checks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fact_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_text TEXT NOT NULL,
                        normalized_text TEXT NOT NULL,
                        verification_status TEXT NOT NULL,
                        verification_score REAL NOT NULL,
                        source_name TEXT NOT NULL,
                        source_url TEXT,
                        explanation TEXT,
                        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        credibility_score REAL DEFAULT 0.6
                    )
                """)
                
                # Create indexes for better search performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_normalized_text 
                    ON fact_checks(normalized_text)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_claim_text 
                    ON fact_checks(claim_text)
                """)
                
                conn.commit()
                
                # Add some sample data if database is empty
                self._add_sample_data_if_empty(cursor)
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
    
    def _add_sample_data_if_empty(self, cursor):
        """Add sample fact-check data if database is empty"""
        cursor.execute("SELECT COUNT(*) FROM fact_checks")
        count = cursor.fetchone()[0]
        
        if count == 0:
            sample_data = [
                {
                    'claim_text': 'The unemployment rate is 3.7%',
                    'normalized_text': 'unemployment rate 3.7%',
                    'verification_status': 'likely_true',
                    'verification_score': 0.8,
                    'source_name': 'Bureau of Labor Statistics',
                    'source_url': 'https://bls.gov',
                    'explanation': 'Current unemployment rate according to BLS data',
                    'credibility_score': 0.9
                },
                {
                    'claim_text': 'Climate change is not real',
                    'normalized_text': 'climate change not real',
                    'verification_status': 'verified_false',
                    'verification_score': 0.1,
                    'source_name': 'NASA Climate Science',
                    'source_url': 'https://climate.nasa.gov',
                    'explanation': 'Scientific consensus confirms climate change is real',
                    'credibility_score': 0.95
                },
                {
                    'claim_text': 'Vaccines cause autism',
                    'normalized_text': 'vaccines cause autism',
                    'verification_status': 'verified_false', 
                    'verification_score': 0.05,
                    'source_name': 'CDC',
                    'source_url': 'https://cdc.gov',
                    'explanation': 'Multiple studies show no link between vaccines and autism',
                    'credibility_score': 0.95
                }
            ]
            
            for data in sample_data:
                cursor.execute("""
                    INSERT INTO fact_checks 
                    (claim_text, normalized_text, verification_status, verification_score,
                     source_name, source_url, explanation, credibility_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['claim_text'],
                    data['normalized_text'],
                    data['verification_status'],
                    data['verification_score'],
                    data['source_name'],
                    data['source_url'],
                    data['explanation'],
                    data['credibility_score']
                ))
            
            self.logger.info("Added sample fact-check data to database")
    
    async def verify_claim(self, claim_text: str, **kwargs) -> FactCheckResult:
        """
        Verify claim against local database
        
        Args:
            claim_text: Claim text to verify
            **kwargs: Additional parameters (similarity_threshold, etc.)
            
        Returns:
            FactCheckResult with verification data
        """
        if not self.is_available():
            return self.create_error_result(claim_text, "Local database not available")
        
        query = self.preprocess_claim(claim_text)
        normalized_query = self._normalize_text(query)
        
        try:
            # Search for similar claims in database
            matches = self._search_similar_claims(normalized_query)
            
            if not matches:
                return FactCheckResult(
                    service_name=self.name,
                    query=query,
                    claim_text=claim_text,
                    status=VerificationStatus.UNVERIFIED,
                    confidence=0.0,
                    verification_score=0.5,
                    explanation="No similar claims found in local database",
                    sources=[]
                )
            
            # Use the best match
            best_match = matches[0]
            
            # Create verification source
            source = VerificationSource(
                name=best_match['source_name'],
                url=best_match['source_url'],
                source_type=SourceType.LOCAL_DATABASE,
                credibility_score=best_match['credibility_score'],
                date_published=None
            )
            
            # Parse verification status
            status = VerificationStatus(best_match['verification_status'])
            
            explanation = self._create_explanation(best_match, matches)
            
            return FactCheckResult(
                service_name=self.name,
                query=query,
                claim_text=claim_text,
                status=status,
                confidence=best_match['similarity'],
                verification_score=best_match['verification_score'],
                sources=[source],
                explanation=explanation
            )
            
        except Exception as e:
            self.logger.error(f"Local database error: {e}")
            return self.create_error_result(claim_text, str(e), query)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching"""
        import re
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation and extra whitespace
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common words that don't affect meaning
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [word for word in text.split() if word not in stopwords]
        
        return ' '.join(words)
    
    def _search_similar_claims(self, normalized_query: str) -> List[Dict[str, Any]]:
        """Search for similar claims in the database"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                
                # Get all claims for similarity comparison
                cursor.execute("""
                    SELECT claim_text, normalized_text, verification_status, verification_score,
                           source_name, source_url, explanation, credibility_score
                    FROM fact_checks
                """)
                
                all_claims = cursor.fetchall()
                matches = []
                
                for row in all_claims:
                    claim_text, normalized_text, status, score, source_name, source_url, explanation, credibility = row
                    
                    # Calculate similarity using difflib
                    similarity = difflib.SequenceMatcher(
                        None, 
                        normalized_query, 
                        normalized_text
                    ).ratio()
                    
                    if similarity >= self.similarity_threshold:
                        matches.append({
                            'claim_text': claim_text,
                            'normalized_text': normalized_text,
                            'verification_status': status,
                            'verification_score': score,
                            'source_name': source_name,
                            'source_url': source_url,
                            'explanation': explanation,
                            'credibility_score': credibility,
                            'similarity': similarity
                        })
                
                # Sort by similarity (best matches first)
                matches.sort(key=lambda x: x['similarity'], reverse=True)
                return matches
                
        except Exception as e:
            self.logger.error(f"Database search error: {e}")
            return []
    
    def _create_explanation(self, best_match: Dict[str, Any], all_matches: List[Dict[str, Any]]) -> str:
        """Create explanation for the verification result"""
        similarity_pct = int(best_match['similarity'] * 100)
        
        explanation_parts = [
            f"Found {len(all_matches)} similar claim(s) in local database.",
            f"Best match: '{best_match['claim_text']}' (similarity: {similarity_pct}%)",
        ]
        
        if best_match['explanation']:
            explanation_parts.append(f"Details: {best_match['explanation']}")
        
        return " ".join(explanation_parts)
    
    def add_fact_check(self, 
                      claim_text: str,
                      verification_status: VerificationStatus,
                      verification_score: float,
                      source_name: str,
                      source_url: Optional[str] = None,
                      explanation: Optional[str] = None,
                      credibility_score: float = 0.6):
        """
        Add a new fact-check to the local database
        
        Args:
            claim_text: The claim being fact-checked
            verification_status: Verification result
            verification_score: Numeric score (0.0-1.0)
            source_name: Name of the fact-checking source
            source_url: URL to the fact-check (optional)
            explanation: Explanation of the verification (optional)
            credibility_score: Credibility of the source (0.0-1.0)
        """
        try:
            normalized_text = self._normalize_text(claim_text)
            
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO fact_checks 
                    (claim_text, normalized_text, verification_status, verification_score,
                     source_name, source_url, explanation, credibility_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    claim_text,
                    normalized_text,
                    verification_status.value,
                    verification_score,
                    source_name,
                    source_url,
                    explanation,
                    credibility_score
                ))
                
                conn.commit()
                self.logger.info(f"Added fact-check for: {claim_text[:50]}...")
                
        except Exception as e:
            self.logger.error(f"Failed to add fact-check: {e}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about the local database"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                
                # Total count
                cursor.execute("SELECT COUNT(*) FROM fact_checks")
                total_count = cursor.fetchone()[0]
                
                # Status distribution
                cursor.execute("""
                    SELECT verification_status, COUNT(*) 
                    FROM fact_checks 
                    GROUP BY verification_status
                """)
                status_counts = dict(cursor.fetchall())
                
                return {
                    'total_fact_checks': total_count,
                    'status_distribution': status_counts,
                    'database_path': str(self.database_path),
                    'database_size_kb': self.database_path.stat().st_size // 1024 if self.database_path.exists() else 0
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
            return {'error': str(e)}
