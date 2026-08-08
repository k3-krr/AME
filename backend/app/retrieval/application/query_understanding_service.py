from app.retrieval.domain.value_objects import QueryAnalysisResult
from app.retrieval.domain.services import QueryNormalizer, IntentDetector, QueryClassifier


class QueryUnderstandingService:
    """Orchestrates query normalization, intent detection, and capability classification."""

    def __init__(
        self,
        normalizer: QueryNormalizer,
        detector: IntentDetector,
        classifier: QueryClassifier
    ):
        self.normalizer = normalizer
        self.detector = detector
        self.classifier = classifier

    def analyze_query(self, query: str) -> QueryAnalysisResult:
        """Runs the query through normalization, intent detection, and classification."""
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty")
            
        normalized = self.normalizer.normalize(query)
        intent, confidence, keywords = self.detector.detect_intent(normalized)
        plan = self.classifier.classify(normalized, intent, confidence, keywords)
        
        return QueryAnalysisResult(
            original_query=query,
            normalized_query=normalized,
            retrieval_plan=plan
        )
