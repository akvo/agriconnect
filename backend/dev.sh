#!/usr/bin/env bash
set -eu
pip -q install --upgrade pip
pip -q install --cache-dir=.pip -r requirements.txt
pip check

# Apply fastapi-mail Pydantic 2.12 compatibility fix
# Fix for: https://github.com/sabuhish/fastapi-mail/issues/236
if [ -f patches/apply_fastapi_mail_fix.py ]; then
    python patches/apply_fastapi_mail_fix.py
fi

alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
