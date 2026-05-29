#!/usr/bin/env python3
"""
Bulk WhatsApp Message Sender

Send WhatsApp template messages to farmers from a CSV file.

Usage:
    ./dc.sh exec backend python scripts/bulk_whatsapp.py --dry-run
    ./dc.sh exec backend python scripts/bulk_whatsapp.py --run
    ./dc.sh exec backend python scripts/bulk_whatsapp.py --check-status

Options:
    --dry-run       Validate phones without sending messages
    --run           Send messages (skips delivered, retries failed/undelivered)
    --check-status  Fetch actual delivery status from Twilio API

CSV Format:
    id,phone,name
    1,+254712345678,John
    2,+254712345679,Jane
"""

import argparse
import json
import os
import time
from datetime import datetime

import pandas as pd
import phonenumbers
from phonenumbers import NumberParseException
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


# =============================================================================
# CONFIGURATION - Edit these values before running
# =============================================================================

# Path to input CSV file (will be updated with status)
# Using ./private/ directory for persistent storage (not exposed, git-ignored)
CSV_PATH = "./private/farmers.csv"

# Twilio WhatsApp template SID (get from Twilio Console after approval)
# Example: "HXc3dfb3056770842dc80f57c24e5337ac"
# TEMPLATE_SID = "HX4dfc3c613b848d2161833052d374a93b"
TEMPLATE_SID = "HX71d61f9e559e872f9a48d5f0721c8c66"

# Column name containing phone numbers
PHONE_COLUMN = "phone"

# Map template variables to CSV columns (set to None or {} if no variables)
# Example: {"1": "name", "2": "company"} maps {{1}} to name, {{2}} to company
VAR_COLUMNS = {
    "1": "name",
}

# Maximum retry attempts for failed messages
MAX_RETRIES = 3

# Delay between messages in milliseconds (to avoid rate limiting)
DELAY_MS = 500

# =============================================================================
# END CONFIGURATION
# =============================================================================


# Status constants (Twilio statuses + custom)
STATUS_QUEUED = "queued"
STATUS_SENT = "sent"
STATUS_DELIVERED = "delivered"
STATUS_UNDELIVERED = "undelivered"
STATUS_FAILED = "failed"
STATUS_READ = "read"
STATUS_INVALID_PHONE = "invalid_phone"

# Statuses that should be retried
RETRY_STATUSES = [STATUS_FAILED, STATUS_UNDELIVERED, STATUS_INVALID_PHONE, ""]


def validate_phone(phone: str) -> tuple:
    """Validate and format phone number to E.164 format."""
    if pd.isna(phone) or not phone:
        return False, "Empty phone number"

    phone = str(phone).strip()
    phone = phone.replace("whatsapp:", "").strip()
    for char in [" ", "-", "(", ")"]:
        phone = phone.replace(char, "")

    if not phone.startswith("+"):
        phone = "+" + phone

    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return False, f"Invalid: {phone}"

        formatted = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
        return True, formatted
    except NumberParseException as e:
        return False, f"Parse error: {e}"


def send_template_message(
    client, from_number, to_number, template_sid, variables=None
):
    """Send WhatsApp template message via Twilio."""
    try:
        params = {
            "from_": from_number,
            "to": f"whatsapp:{to_number}",
            "content_sid": template_sid,
        }
        if variables:
            params["content_variables"] = json.dumps(variables)

        message = client.messages.create(**params)
        return {
            "success": True,
            "sid": message.sid,
            "status": message.status,
            "error": None,
        }
    except TwilioRestException as e:
        return {
            "success": False,
            "sid": None,
            "status": STATUS_FAILED,
            "error": f"Twilio {e.code}: {e.msg}",
        }
    except Exception as e:
        return {
            "success": False,
            "sid": None,
            "status": STATUS_FAILED,
            "error": str(e),
        }


def check_message_status(client, message_sid):
    """Fetch message status from Twilio API."""
    try:
        message = client.messages(message_sid).fetch()
        return {
            "success": True,
            "status": message.status,
            "error": message.error_message or "",
        }
    except TwilioRestException as e:
        return {
            "success": False,
            "status": None,
            "error": f"Twilio {e.code}: {e.msg}",
        }
    except Exception as e:
        return {
            "success": False,
            "status": None,
            "error": str(e),
        }


def load_csv():
    """Load CSV and add tracking columns if missing."""
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV not found: {CSV_PATH}")
        return None

    print(f"Reading: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, dtype=str)

    if PHONE_COLUMN not in df.columns:
        print(f"ERROR: Column '{PHONE_COLUMN}' not found")
        print(f"Available: {list(df.columns)}")
        return None

    # Add tracking columns if missing
    tracking_cols = [
        "status", "retries", "last_batch_date", "message_sid", "error"
    ]
    for col in tracking_cols:
        if col not in df.columns:
            df[col] = ""

    df["retries"] = (
        pd.to_numeric(df["retries"], errors="coerce").fillna(0).astype(int)
    )

    return df


def run_check_status(client, df):
    """Check delivery status for all queued messages."""
    print("\n" + "-" * 60)
    print("Checking message status from Twilio API...")
    print("-" * 60)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    checked = 0
    updated = 0

    for idx, row in df.iterrows():
        message_sid = row.get("message_sid", "")
        current_status = str(row.get("status", "")).strip().lower()
        row_id = row.get("id", idx)

        # Only check rows with message_sid and status queued/sent
        if not message_sid or pd.isna(message_sid) or message_sid == "":
            continue

        if current_status not in [STATUS_QUEUED, STATUS_SENT]:
            continue

        result = check_message_status(client, message_sid)
        checked += 1

        if result["success"]:
            new_status = result["status"]
            if new_status != current_status:
                df.at[idx, "status"] = new_status
                df.at[idx, "last_batch_date"] = now
                df.at[idx, "error"] = result["error"]
                updated += 1
                print(f"[{row_id}] {current_status} -> {new_status}")
            else:
                print(f"[{row_id}] {current_status} (unchanged)")
        else:
            print(f"[{row_id}] ERROR: {result['error']}")

        if DELAY_MS > 0:
            time.sleep(DELAY_MS / 1000)

    return checked, updated


def run_send(client, whatsapp_number, df, dry_run=False):
    """Send messages to eligible rows."""
    print("\n" + "-" * 60)
    mode = "DRY RUN" if dry_run else "SENDING"
    print(f"Mode: {mode}")
    print(f"Template SID: {TEMPLATE_SID}")
    print(f"Variables: {VAR_COLUMNS or 'None'}")
    print("-" * 60)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    processed = 0
    skipped = 0
    sent = 0
    failed = 0
    invalid = 0

    for idx, row in df.iterrows():
        phone_raw = row[PHONE_COLUMN]
        status_val = row["status"]
        current_status = ""
        if pd.notna(status_val):
            current_status = str(status_val).strip().lower()
        retries_val = row["retries"]
        current_retries = int(retries_val) if pd.notna(retries_val) else 0
        row_id = row.get("id", idx)

        # Skip if already delivered/read or max retries reached
        if current_status in [STATUS_DELIVERED, STATUS_READ]:
            skipped += 1
            continue

        # Skip queued/sent - need to check status first
        if current_status in [STATUS_QUEUED, STATUS_SENT]:
            skipped += 1
            continue

        # Check max retries for failed statuses
        if current_status in RETRY_STATUSES and current_status != "":
            if current_retries >= MAX_RETRIES:
                print(f"[{row_id}] SKIP - Max retries reached")
                skipped += 1
                continue

        # Validate phone
        is_valid, phone_result = validate_phone(phone_raw)

        if not is_valid:
            invalid += 1
            processed += 1
            df.at[idx, "status"] = STATUS_INVALID_PHONE
            df.at[idx, "error"] = phone_result
            df.at[idx, "last_batch_date"] = now
            df.at[idx, "retries"] = current_retries + 1
            print(f"[{row_id}] INVALID - {phone_result}")
            continue

        formatted_phone = phone_result

        # Build template variables
        variables = None
        if VAR_COLUMNS:
            variables = {}
            for var_num, col_name in VAR_COLUMNS.items():
                if col_name in df.columns:
                    var_value = row.get(col_name, "")
                    if pd.notna(var_value) and str(var_value).strip():
                        variables[var_num] = str(var_value).strip()
            if not variables:
                variables = None

        # Send or dry run
        if dry_run:
            sent += 1
            processed += 1
            df.at[idx, "status"] = "dry_run"
            df.at[idx, "last_batch_date"] = now
            msg = f"[{row_id}] OK - {formatted_phone}"
            if variables:
                msg += f" vars={variables}"
            print(msg)
        else:
            result = send_template_message(
                client, whatsapp_number, formatted_phone,
                TEMPLATE_SID, variables
            )

            processed += 1
            df.at[idx, "last_batch_date"] = now
            df.at[idx, "retries"] = current_retries + 1

            if result["success"]:
                sent += 1
                df.at[idx, "status"] = result["status"]
                df.at[idx, "message_sid"] = result["sid"]
                df.at[idx, "error"] = ""
                print(f"[{row_id}] QUEUED - {formatted_phone}")
            else:
                failed += 1
                df.at[idx, "status"] = STATUS_FAILED
                df.at[idx, "error"] = result["error"]
                print(f"[{row_id}] FAILED - {result['error']}")

            if DELAY_MS > 0:
                time.sleep(DELAY_MS / 1000)

    return {
        "processed": processed,
        "skipped": skipped,
        "sent": sent,
        "failed": failed,
        "invalid": invalid,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Bulk WhatsApp Message Sender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run", action="store_true",
        help="Validate phones without sending"
    )
    group.add_argument(
        "--run", action="store_true",
        help="Send messages (retries failed/undelivered)"
    )
    group.add_argument(
        "--check-status", action="store_true",
        help="Fetch delivery status from Twilio"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Bulk WhatsApp Message Sender")
    print("=" * 60)

    # Load CSV
    df = load_csv()
    if df is None:
        return 1

    print(f"Total rows: {len(df)}")

    # Load Twilio credentials
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    whatsapp_number = os.getenv(
        "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"
    )

    if not whatsapp_number.startswith("whatsapp:"):
        whatsapp_number = f"whatsapp:{whatsapp_number}"

    # Initialize Twilio client (not needed for dry-run)
    client = None
    if not args.dry_run:
        if not account_sid or not auth_token:
            print("ERROR: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN required")
            return 1
        client = Client(account_sid, auth_token)
        print(f"Twilio client initialized. From: {whatsapp_number}")

    # Execute command
    if args.check_status:
        checked, updated = run_check_status(client, df)
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Checked:  {checked}")
        print(f"Updated:  {updated}")

    else:
        stats = run_send(client, whatsapp_number, df, dry_run=args.dry_run)
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total:         {len(df)}")
        print(f"Processed:     {stats['processed']}")
        print(f"Skipped:       {stats['skipped']}")
        print(f"Sent/Queued:   {stats['sent']}")
        print(f"Failed:        {stats['failed']}")
        print(f"Invalid phone: {stats['invalid']}")
        if stats["processed"] > 0:
            rate = (stats["sent"] / stats["processed"]) * 100
            print(f"Success rate:  {rate:.1f}%")

    # Save CSV
    df.to_csv(CSV_PATH, index=False)
    print(f"\nCSV updated: {CSV_PATH}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
