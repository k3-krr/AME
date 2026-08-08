# Advanced RAG Pipeline: Production Readiness Guide

This document outlines the architecture, configuration boundaries, security isolation, and telemetry metrics of the finalized Advanced RAG Pipeline in the Adaptive Memory Engine (AME).

---

## 1. End-to-End Pipeline Architecture

The retrieval workflow operates sequentially, leveraging clean boundaries and domain objects:

1.  **User Query Sanitization**: The API router validates query length limits before routing payload requests.
2.  **Query Understanding & Classification**: Translates queries into structured intent types and resolves recommended memory capabilities.
3.  **Query Rewriting & Multi-Query Generation**: Standardizes abbreviations and generates retrieval subqueries with priority scores.
4.  **Retrieval Orchestration**: Executes capability-specific retrieval modules sequentially to prevent concurrency conflicts on SQLAlchemy sessions.
5.  **Adaptive Ranking**: Merges vector similarities and context relevance scores.
6.  **Context Fusion**: Aggregates duplicate memories, recording all source paths.
7.  **Context Compression**: Truncates trailing segments using a rank-preserving sequence limits filter.
8.  **Citation & Grounding Validation**: Maps sequentially indexed citations (1-indexed) and validates formatting markers.

---

## 2. Telemetry & Observability

Observability uses standard application logging streams, writing JSON-formatted traces to ensure ingestion compatibility.

### 2.1 JSON Schema properties
```json
{
  "request_id": "uuid-string",
  "success": true,
  "stage_latencies": {
    "query_analysis": 0.012,
    "query_rewrite": 0.008,
    "retrieval_executors": 0.125,
    "ranking": 0.042,
    "fusion": 0.005,
    "compression": 0.002,
    "citation": 0.001,
    "prompt_assembly": 0.003
  },
  "result_count": 5,
  "context_size_chars": 1250,
  "retained_element_ratio": 1.0,
  "capability_usage": ["SEMANTIC_SEARCH", "KNOWLEDGE_GRAPH"],
  "validation_failure_category": null,
  "error_category": null
}
```

*Note: Telemetry strictly avoids logging user queries, raw memory content, prompt texts, or system secrets.*

---

## 3. Configuration Parameters

The following app configurations are defined inside the `AppSettings` module in `app/config.py`:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `RETRIEVAL_TIMEOUT_SECONDS` | `float` | `5.0` | Total request timeout budget for the retrieval execution. |
| `RETRIEVAL_MAX_QUERY_LENGTH` | `int` | `1000` | Max character length constraint allowed for user queries. |

---

## 4. Concurrency & Connection Safety

*   **Sequential Execution Policy**: Capability executors query repositories using a shared connection context. SQLAlchemy `AsyncSession` instances do **not** support concurrent async calls; executing them in parallel causes transaction failures. The orchestrator enforces sequential runs for runtime database safety.
*   **Request Timeouts**: The overall workflow uses `asyncio.wait_for` wrapping connection tasks. On timeout, all pending async connection handlers are cancelled and connection pools are safely returned to standard states.

---

## 5. Security & Isolation

*   **Tenant Boundaries**: Database operations propagate `user_id` context filters. Users cannot query, view, or parse memories belonging to other tenants.
*   **Injection Protections**: Repository queries leverage parameterized bindings. Input length controls mitigate resource exhaustion attempts.
