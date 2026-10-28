"""MLflow tracing: every request becomes a *trace*, a tree of timed *spans*.

    simple_rag (2.9 s)
    ├── retrieve (0.9 s)           question in, chunk citations out
    └── ChatOpenAI (2.0 s)         prompt in, answer out, token usage

`mlflow.langchain.autolog()` records every LangChain/LangGraph call automatically; our own
code adds spans with `@mlflow.trace` / `mlflow.start_span`. Traces are viewed in the MLflow
UI (http://127.0.0.1:5000 → Experiments → agentic-rag → Traces).

Tracing must never break the app: if MLflow is down at startup, tracing is switched off with
a warning and everything else keeps working.
"""

import mlflow
import structlog

from app.config import Settings

log = structlog.get_logger(__name__)


def setup_tracing(settings: Settings) -> bool:
    """Turn tracing on (or off, per TRACING_ENABLED). Returns whether tracing is active."""
    if not settings.tracing_enabled:
        mlflow.tracing.disable()  # also stops @mlflow.trace writing to a local ./mlruns folder
        return False
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment_name)  # contacts the MLflow server
        mlflow.langchain.autolog(silent=True)
        mlflow.tracing.enable()
    except Exception as exc:  # tracing is optional: log it and carry on without it
        mlflow.tracing.disable()
        log.warning("tracing_disabled", reason=f"{type(exc).__name__}: {exc}"[:200])
        return False
    log.info(
        "tracing_enabled",
        uri=settings.mlflow_tracking_uri,
        experiment=settings.mlflow_experiment_name,
    )
    return True
