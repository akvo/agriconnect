"""
Background tasks package for AgriConnect

Contains scheduled tasks and background workers for:
- Message retry with exponential backoff
- Broadcast messaging
- Weather broadcast messaging
"""

# Import tasks to register them with Celery
from tasks.broadcast_tasks import (
    process_broadcast,
    send_actual_message,
    retry_failed_broadcasts,
)
from tasks.weather_tasks import (
    send_weather_broadcasts,
    send_weather_templates,
    send_weather_message,
    retry_failed_weather_broadcasts,
)

__all__ = [
    "process_broadcast",
    "send_actual_message",
    "retry_failed_broadcasts",
    "send_weather_broadcasts",
    "send_weather_templates",
    "send_weather_message",
    "retry_failed_weather_broadcasts",
]
