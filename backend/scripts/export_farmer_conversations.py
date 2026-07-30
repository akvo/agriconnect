#!/usr/bin/env python3
"""
Export farmer questions with their AI / extension-officer responses to CSV.

READ-ONLY: only SELECT queries are issued; nothing is committed.

Columns:
    date, farmer_id, farmer_name, administrative, primary_crop, age,
    gender, weather_subscription, question, response, response_by

Pairing logic (deterministic, mirrors the app's own reply linkage):
- Messages are walked per customer in chronological order (created_at, id).
- A customer message (from_source=CUSTOMER) becomes the "pending question".
  A newer customer message supersedes an unanswered older one.
- The first subsequent response message is paired with the pending question:
    * AI response  : from_source=LLM  AND message_type == REPLY
    * EO response  : from_source=USER AND message_type IS NULL
- Explicitly excluded (never treated as questions or responses):
    * message_type == WHISPER    (AI suggestion to EO, never sent to farmer)
    * message_type == FOLLOW_UP  (automated clarifying question)
    * message_type == BROADCAST  (broadcast + weather notification messages)
- Onboarding / welcome / escalation-confirmation / weather-subscription
  messages are never stored in the `messages` table, so they cannot appear.

Usage:
    # From backend container
    ./dc.sh exec backend python scripts/export_farmer_conversations.py \\
        -o /tmp/farmer_conversations.csv
"""

import argparse
import csv
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from database import SessionLocal  # noqa: E402
from models.administrative import (  # noqa: E402
    Administrative,
    CustomerAdministrative,
)
from models.customer import Customer  # noqa: E402
from models.message import Message, MessageFrom  # noqa: E402
from schemas.callback import MessageType  # noqa: E402

HEADER = [
    "date",
    "farmer_id",
    "farmer_name",
    "administrative",
    "primary_crop",
    "age",
    "gender",
    "weather_subscription",
    "question",
    "response",
    "response_by",
]


def build_admin_paths(db):
    """id -> 'Country > Region > District > Ward' (top to most specific)."""
    nodes = {}
    for row in db.query(
        Administrative.id, Administrative.name, Administrative.parent_id
    ).all():
        nodes[row.id] = (row.name, row.parent_id)

    paths = {}
    for admin_id in nodes:
        chain = []
        cur = admin_id
        seen = set()
        while cur is not None and cur in nodes and cur not in seen:
            seen.add(cur)
            name, parent_id = nodes[cur]
            chain.append(name or "")
            cur = parent_id
        paths[admin_id] = " > ".join(reversed(chain))
    return paths


def load_customer_profiles(db):
    """customer_id -> dict of CSV profile fields ('' when missing)."""
    current_year = datetime.now().year
    profiles = {}
    query = db.query(
        Customer.id, Customer.full_name, Customer.profile_data
    ).yield_per(500)
    for row in query:
        pd = row.profile_data or {}

        age = ""
        birth_year = pd.get("birth_year")
        if birth_year:
            try:
                age = current_year - int(birth_year)
            except (TypeError, ValueError):
                age = ""

        ws = pd.get("weather_subscribed")
        weather = "" if ws is None else ("yes" if ws else "no")

        profiles[row.id] = {
            "farmer_name": row.full_name or "",
            "primary_crop": pd.get("crop_type") or "",
            "age": age,
            "gender": pd.get("gender") or "",
            "weather_subscription": weather,
        }
    return profiles


def load_customer_admin_map(db):
    """customer_id -> administrative_id (first assignment if multiple)."""
    mapping = {}
    rows = (
        db.query(
            CustomerAdministrative.customer_id,
            CustomerAdministrative.administrative_id,
        )
        .order_by(CustomerAdministrative.id)
        .all()
    )
    for row in rows:
        mapping.setdefault(row.customer_id, row.administrative_id)
    return mapping


def is_response(from_source, message_type):
    """True only for AI REPLY messages or plain EO replies."""
    if from_source == MessageFrom.LLM:
        return message_type == MessageType.REPLY
    if from_source == MessageFrom.USER:
        # EO replies have no message_type; BROADCAST/weather are excluded
        return message_type is None
    return False


def export(output_path: str) -> int:
    db = SessionLocal()
    exported = 0
    try:
        admin_paths = build_admin_paths(db)
        profiles = load_customer_profiles(db)
        customer_admin = load_customer_admin_map(db)

        messages = (
            db.query(
                Message.id,
                Message.customer_id,
                Message.body,
                Message.from_source,
                Message.message_type,
                Message.created_at,
            )
            .order_by(Message.customer_id, Message.created_at, Message.id)
            .yield_per(1000)
        )

        current_customer = None
        pending_question = None

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(HEADER)

            for msg in messages:
                if msg.customer_id != current_customer:
                    current_customer = msg.customer_id
                    pending_question = None

                if msg.from_source == MessageFrom.CUSTOMER:
                    # latest unanswered farmer message becomes the question
                    pending_question = msg
                    continue

                if pending_question is None:
                    continue

                if not is_response(msg.from_source, msg.message_type):
                    continue

                profile = profiles.get(msg.customer_id, {})
                admin_id = customer_admin.get(msg.customer_id)
                admin_path = (
                    admin_paths.get(admin_id, "") if admin_id else ""
                )

                question_ts = ""
                if pending_question.created_at:
                    question_ts = pending_question.created_at.isoformat(
                        sep=" "
                    )

                writer.writerow(
                    [
                        question_ts,
                        msg.customer_id,
                        profile.get("farmer_name", ""),
                        admin_path,
                        profile.get("primary_crop", ""),
                        profile.get("age", ""),
                        profile.get("gender", ""),
                        profile.get("weather_subscription", ""),
                        pending_question.body or "",
                        msg.body or "",
                        (
                            "AI"
                            if msg.from_source == MessageFrom.LLM
                            else "extension_officer"
                        ),
                    ]
                )
                exported += 1
                pending_question = None

        print(f"Exported {exported} rows to {output_path}")
        return 0
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Export farmer questions and AI/EO responses to CSV"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="/tmp/farmer_conversations.csv",
        help="Output CSV path (default: /tmp/farmer_conversations.csv)",
    )
    args = parser.parse_args()

    try:
        return export(args.output)
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
