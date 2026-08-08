from app.retrieval.domain.value_objects import QueryRewriteResult
from app.retrieval.domain.services import QueryNormalizer, QueryRewriter, QueryExpansionService, MultiQueryGenerator


class QueryRewriteService:
    """Orchestrates query normalization, rewriting, expansion, and multi-query generation."""

    def __init__(
        self,
        normalizer: QueryNormalizer,
        rewriter: QueryRewriter,
        expansion: QueryExpansionService,
        generator: MultiQueryGenerator
    ):
        self.normalizer = normalizer
        self.rewriter = rewriter
        self.expansion = expansion
        self.generator = generator

    def rewrite_query(self, query: str) -> QueryRewriteResult:
        """Processes raw query through rewrite, expansion, and multi-query steps."""
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty")

        # 1. Syntactic normalization
        normalized = self.normalizer.normalize(query)
        
        # 2. Semantic query rewrite
        rewritten = self.rewriter.rewrite(normalized)
        
        # 3. Entity expansion
        variants = self.expansion.expand(rewritten)
        
        # 4. Multi-query generation
        retrieval_queries = self.generator.generate(rewritten, variants)
        
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=rewritten,
            retrieval_queries=retrieval_queries,
            metadata={
                "expanded_variants_count": len(variants),
                "total_generated_queries": len(retrieval_queries),
            }
        )
