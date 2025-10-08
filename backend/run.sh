#!/usr/bin/env bash

alembic upgrade head

# Use uvicorn for production with WebSocket support
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

