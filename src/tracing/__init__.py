"""Logging and tracing infrastructure"""

import json
import os
import logging
from datetime import datetime
from typing import Any, Dict
from src.config import get_settings


class TraceLogger:
    """Logs structured trace events for observability and replay"""

    def __init__(self, data_dir: str = None):
        """Initialize trace logger
        
        Args:
            data_dir: Directory for trace files (defaults to settings.data_dir)
        """
        settings = get_settings()
        self.data_dir = data_dir or settings.data_dir
        self.traces_dir = os.path.join(self.data_dir, "traces")
        os.makedirs(self.traces_dir, exist_ok=True)
        
        # Current run trace file
        self.current_run_file = None
        self.current_run_id = None

    def start_run(self, run_id: str):
        """Start logging for a new run
        
        Args:
            run_id: Unique run identifier
        """
        self.current_run_id = run_id
        date = datetime.utcnow().strftime("%Y-%m-%d")
        self.current_run_file = os.path.join(
            self.traces_dir, 
            f"run_{date}_{run_id}.jsonl"
        )
        self._log_event("run_started", {"run_id": run_id})

    def log_step(self, actor: str, intent: str, status: str, payload: Dict[str, Any], metadata: Dict = None):
        """Log a step execution
        
        Args:
            actor: Agent name
            intent: Operation intent
            status: success | error | partial
            payload: Step result
            metadata: Additional context
        """
        event = {
            "type": "step",
            "actor": actor,
            "intent": intent,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "payload_keys": list(payload.keys()) if payload else [],
            "metadata": metadata or {}
        }
        self._log_event("step", event)

    def log_cost(self, actor: str, cost_usd: float, tokens: int):
        """Log cost and token usage
        
        Args:
            actor: Agent name
            cost_usd: Cost in USD
            tokens: Tokens used
        """
        event = {
            "actor": actor,
            "cost_usd": cost_usd,
            "tokens": tokens,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._log_event("cost", event)

    def log_error(self, actor: str, error: str, context: Dict = None):
        """Log an error
        
        Args:
            actor: Agent name
            error: Error message
            context: Additional context
        """
        event = {
            "actor": actor,
            "error": error,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self._log_event("error", event)

    def end_run(self, run_context):
        """End logging for a run
        
        Args:
            run_context: Final run context
        """
        event = {
            "run_id": run_context.run_id,
            "status": run_context.status,
            "fetch_count": run_context.fetch_count,
            "deduplicated_count": run_context.deduplicated_count,
            "summarized_count": run_context.summarized_count,
            "cost_usd": run_context.budget_spent_usd,
            "tokens_used": run_context.tokens_used,
            "duration_sec": (run_context.end_time - run_context.start_time).total_seconds() if run_context.end_time else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._log_event("run_ended", event)
        self.current_run_file = None
        self.current_run_id = None

    def _log_event(self, event_type: str, event_data: Dict):
        """Write event to trace file
        
        Args:
            event_type: Type of event
            event_data: Event data
        """
        if not self.current_run_file:
            return
        
        try:
            with open(self.current_run_file, "a") as f:
                entry = {
                    "type": event_type,
                    "data": event_data
                }
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.error(f"Failed to write trace: {e}")


# Global trace logger instance
_trace_logger: TraceLogger = None


def get_trace_logger() -> TraceLogger:
    """Get or create global trace logger"""
    global _trace_logger
    if _trace_logger is None:
        _trace_logger = TraceLogger()
    return _trace_logger
