"""
Inngest Background Worker - Video Generation Pipeline.

Handles asynchronous video generation using Inngest for durable workflows
with automatic retries, rate limit handling, and checkpoint recovery.
"""
import os
import logging
from inngest import Inngest
from inngest.experimental import step_run

logger = logging.getLogger(__name__)

# Initialize Inngest client
inngest_client = Inngest(
    app_id="video-factory",
    event_key=os.getenv("INNGEST_EVENT_KEY", "local-dev-key"),
)


def get_inngest_client():
    """Get the Inngest client instance."""
    return inngest_client
