#!/usr/bin/env python3
"""
Bulk WhatsApp Message Sender

Send WhatsApp template messages to farmers from a CSV file.
Edit the CONFIGURATION section below, then run:

    ./dc.sh exec backend python scripts/bulk_whatsapp.py

CSV Format:
    id,company,name,phone,status,retries,last_batch_date
    1,CoopName,John,+255712345678,,,
    2,CoopName,,+255712345679,,,

The script updates status, retries, and last_batch_date columns in the CSV.
"""

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
CSV_PATH = "./source/farmers.csv"

# Twilio WhatsApp template SID (get from Twilio Console after approval)
# Example: "HXc3dfb3056770842dc80f57c24e5337ac"
TEMPLATE_SID = "HX4dfc3c613b848d2161833052d374a93b"

# Column name containing phone numbers
PHONE_COLUMN = "phone"

# Map template variables to CSV columns (set to None or {} if no variables)
# Example: {"1": "name", "2": "company"} maps {{1}} to name, {{2}} to company
VAR_COLUMNS = {
    "1": "name",
    "2": "company",
}

# Set to True to validate phones without sending messages
DRY_RUN = False

# Set to True to only retry failed messages
RETRY_FAILED_ONLY = False

# Maximum retry attempts for failed messages
MAX_RETRIES = 3

# Delay between messages in milliseconds (to avoid rate limiting)
DELAY_MS = 500

# =============================================================================
# END CONFIGURATION
# =============================================================================


# Status constants
STATUS_QUEUED = "queued"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_INVALID_PHONE = "invalid_phone"


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


def main():
    print("=" * 60)
    print("Bulk WhatsApp Message Sender")
    print("=" * 60)

    # Load Twilio credentials from environment
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    whatsapp_number = os.getenv(
        "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"
    )

    if not account_sid or not auth_token:
        print("ERROR: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")
        return 1

    if not whatsapp_number.startswith("whatsapp:"):
        whatsapp_number = f"whatsapp:{whatsapp_number}"

    # Initialize Twilio client
    client = None
    if not DRY_RUN:
        client = Client(account_sid, auth_token)
        print(f"Twilio client initialized. From: {whatsapp_number}")

    # Check CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV not found: {CSV_PATH}")
        return 1

    # Read CSV
    print(f"\nReading: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, dtype=str)

    if PHONE_COLUMN not in df.columns:
        print(f"ERROR: Column '{PHONE_COLUMN}' not found")
        print(f"Available: {list(df.columns)}")
        return 1

    # Add tracking columns if missing
    tracking_cols = [
        "status",
        "retries",
        "last_batch_date",
        "message_sid",
        "error",
    ]
    for col in tracking_cols:
        if col not in df.columns:
            df[col] = ""

    df["retries"] = (
        pd.to_numeric(df["retries"], errors="coerce").fillna(0).astype(int)
    )

    # Print config
    print(f"Total rows: {len(df)}")
    print(f"Template SID: {TEMPLATE_SID}")
    print(f"Variable columns: {VAR_COLUMNS or 'None'}")
    print(f"Delay: {DELAY_MS}ms")
    print(f"Max retries: {MAX_RETRIES}")
    print(f"Retry failed only: {RETRY_FAILED_ONLY}")
    print(f"DRY RUN: {DRY_RUN}")
    print("\n" + "-" * 60)

    # Counters
    total = len(df)
    processed = 0
    skipped = 0
    sent = 0
    failed = 0
    invalid = 0

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, row in df.iterrows():
        phone_raw = row[PHONE_COLUMN]
        status_val = row["status"]
        current_status = ""
        if pd.notna(status_val):
            current_status = str(status_val).strip().lower()
        retries_val = row["retries"]
        current_retries = int(retries_val) if pd.notna(retries_val) else 0
        row_id = row.get("id", idx)

        # Should we process this row?
        should_process = False
        if RETRY_FAILED_ONLY:
            if current_status in [STATUS_FAILED, STATUS_INVALID_PHONE, ""]:
                if current_retries < MAX_RETRIES:
                    should_process = True
                else:
                    print(f"[{row_id}] SKIP - Max retries reached")
        else:
            if current_status == "" or pd.isna(row["status"]):
                should_process = True

        if not should_process:
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
        if DRY_RUN:
            sent += 1
            processed += 1
            df.at[idx, "status"] = "dry_run"
            df.at[idx, "last_batch_date"] = now
            msg = f"[{row_id}] DRY RUN - {formatted_phone}"
            if variables:
                msg += f" vars={variables}"
            print(msg)
        else:
            result = send_template_message(
                client,
                whatsapp_number,
                formatted_phone,
                TEMPLATE_SID,
                variables,
            )

            processed += 1
            df.at[idx, "last_batch_date"] = now
            df.at[idx, "retries"] = current_retries + 1

            if result["success"]:
                sent += 1
                df.at[idx, "status"] = result["status"]
                df.at[idx, "message_sid"] = result["sid"]
                df.at[idx, "error"] = ""
                sid = result["sid"]
                print(f"[{row_id}] SENT - {formatted_phone} (SID: {sid})")
            else:
                failed += 1
                df.at[idx, "status"] = STATUS_FAILED
                df.at[idx, "error"] = result["error"]
                err = result["error"]
                print(f"[{row_id}] FAILED - {formatted_phone}: {err}")

            if DELAY_MS > 0:
                time.sleep(DELAY_MS / 1000)

    # Save updated CSV
    df.to_csv(CSV_PATH, index=False)
    print(f"\nCSV updated: {CSV_PATH}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total:         {total}")
    print(f"Processed:     {processed}")
    print(f"Skipped:       {skipped}")
    print(f"Sent:          {sent}")
    print(f"Failed:        {failed}")
    print(f"Invalid phone: {invalid}")
    if processed > 0:
        print(f"Success rate:  {(sent / processed) * 100:.1f}%")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
