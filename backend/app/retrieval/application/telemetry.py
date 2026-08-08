import time
import json
import logging
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
import uuid

logger = logging.getLogger("ame_backend.retrieval.telemetry")


class PipelineTimer:
    """Context manager measuring execution latency of individual RAG stages."""

    def __init__(self, telemetry_tracker: "RetrievalTelemetryTracker", stage_name: str):
        self.tracker = telemetry_tracker
        self.stage_name = stage_name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        self.tracker.record_latency(self.stage_name, duration)


class RetrievalTelemetryTracker:
    """Collects and outputs pipeline execution metrics as structured JSON string logs."""

    def __init__(self, request_id: Optional[uuid.UUID] = None):
        self.request_id = request_id or uuid.uuid4()
        self.latencies: Dict[str, float] = {}
        self.success = True
        self.result_count = 0
        self.context_size_chars = 0
        self.retained_element_ratio = 1.0
        self.capability_usage: List[str] = []
        self.validation_failure_category: Optional[str] = None
        self.error_category: Optional[str] = None

    def record_latency(self, stage_name: str, duration: float) -> None:
        self.latencies[stage_name] = round(duration, 4)

    @contextmanager
    def time_stage(self, stage_name: str):
        with PipelineTimer(self, stage_name):
            yield

    def log_metrics(self) -> None:
        """Serializes pipeline stats to structured JSON string output to log handlers."""
        metrics = {
            "request_id": str(self.request_id),
            "success": self.success,
            "stage_latencies": self.latencies,
            "result_count": self.result_count,
            "context_size_chars": self.context_size_chars,
            "retained_element_ratio": round(self.retained_element_ratio, 4),
            "capability_usage": self.capability_usage,
            "validation_failure_category": self.validation_failure_category,
            "error_category": self.error_category,
        }
        logger.info(json.dumps(metrics))
