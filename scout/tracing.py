# Connects Scout to Arize Phoenix so every agent step is recorded as a "trace".
# OpenInference auto-instruments LangChain/LangGraph: each model call and tool call becomes
# a span (a timed record with its inputs and outputs) that Phoenix shows as a tree.
# Phoenix must be running separately: `uv run phoenix serve`, then open localhost:6006.

import urllib.request

from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.otel import register

from scout import config

# Remember whether we've already set up tracing, so calling setup_tracing() twice
# (e.g. on every Streamlit rerun later) doesn't record every span twice.
_tracing_started = False


def phoenix_is_running() -> bool:
    """Return True if the Phoenix server answers at PHOENIX_ENDPOINT within 1 second."""
    try:
        urllib.request.urlopen(config.PHOENIX_ENDPOINT, timeout=1)
        return True
    except OSError:  # connection refused, timeout, etc.
        return False


def setup_tracing() -> bool:
    """Send traces of all LangChain/LangGraph activity to the local Phoenix server.

    Returns True if tracing is on. Safe to call many times; only the first successful call
    sets things up. If Phoenix isn't running, prints one line and skips tracing (instead of
    a stream of connection errors); the next call tries again, e.g. after you start Phoenix.
    """
    global _tracing_started
    if _tracing_started:
        return True
    if not phoenix_is_running():
        print(f"Phoenix not running at {config.PHOENIX_ENDPOINT}, tracing off for this run. "
              "Start it with `uv run phoenix serve`.")
        return False

    # register() creates an OpenTelemetry "tracer provider": the object that collects spans
    # and ships them to Phoenix's collector URL in the background.
    # [A11 Observability] OpenTelemetry + OpenInference: every model call and tool call becomes a
    # span in Phoenix, with inputs, outputs, tokens and latency. No tracing code inside the tools.
    tracer_provider = register(
        project_name=config.PHOENIX_PROJECT,
        endpoint=f"{config.PHOENIX_ENDPOINT}/v1/traces",
        batch=True,  # send spans in batches in the background, so tracing doesn't slow the agent
        verbose=False,  # don't print a setup banner every run
    )
    # Hook into LangChain so model calls, tool calls, and graph steps all create spans.
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    _tracing_started = True
    return True
