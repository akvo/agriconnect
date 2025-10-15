FROM python:3.10.7

WORKDIR /app

COPY requirements.txt /app/

RUN set -e; \
    pip -q install --upgrade pip && \
    pip -q install --no-cache-dir -r requirements.txt && \
    pip check

copy . /app/

# Apply fastapi-mail Pydantic 2.12 compatibility fix
# Fix for: https://github.com/sabuhish/fastapi-mail/issues/236
RUN if [ -f patches/apply_fastapi_mail_fix.py ]; then \
    python patches/apply_fastapi_mail_fix.py; \
    fi


CMD ["./run.sh"]
