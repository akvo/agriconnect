import argparse
import os
import random
import secrets
import sys

import requests
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from database import SessionLocal  # noqa: E402
from models.ticket import Ticket  # noqa: E402
from models.message import Message, MessageType  # noqa: E402

# Base URL for the API
BASE_URL = os.getenv("WEBDOMAIN", "http://localhost:8000")

# Suggestion templates by crop type
suggestions = {
    "rice": [
        "Plant rice in well-drained, fertile soil with sunlight.",
        "Ensure consistent water supply during growing season.",
        "Use high-quality seeds and consider crop rotation.",
    ],
    "chilli": [
        "Chilli plants thrive in warm climates (20-30°C).",
        "Use well-drained soil rich in organic matter.",
        "Water regularly but avoid waterlogging.",
    ],
    "coffee": [
        "Coffee plants prefer high altitudes (15-24°C).",
        "Ensure soil is rich in organic matter with drainage.",
        "Provide partial shade to protect from direct sunlight.",
    ],
    "maize": [
        "Plant maize during the rainy season for optimal yield.",
        "Ensure adequate spacing between plants to promote airflow.",
        "Use nitrogen-rich fertilizers to enhance growth."
    ],
    "tomato": [
        "Tomatoes need well-drained soil rich in organic matter.",
        "Provide support stakes or cages for growing plants.",
        "Water regularly but avoid wetting leaves."
    ]
}


def get_customer_ticket_info(db: Session, phone_number: str) -> dict:
    """Get customer, active ticket, and latest message information."""
    from models.customer import Customer

    # Find customer by phone number
    customer = (
        db.query(Customer)
        .filter(Customer.phone_number == phone_number)
        .first()
    )

    if not customer:
        return None

    # Find open ticket for this customer
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.customer_id == customer.id,
            Ticket.resolved_at.is_(None)
        )
        .order_by(Ticket.created_at.desc())
        .first()
    )

    if not ticket:
        return {
            "customer": customer,
            "ticket": None,
            "message": None
        }

    # Get the initial message from the ticket
    message = (
        db.query(Message)
        .filter(Message.id == ticket.message_id)
        .first()
    )

    return {
        "customer": customer,
        "ticket": ticket,
        "message": message
    }


def send_callback(
    ticket_id: int,
    message_id: int,
    status: str,
    suggestion_key: str,
    base_url: str = BASE_URL,
):
    """Send AI callback webhook to the backend."""
    # Generate job and trace IDs
    job_id = f"whisper_job_{secrets.token_hex(8)}"
    trace_id = f"trace_{secrets.token_hex(8)}"

    # Get suggestion text
    suggestion_list = suggestions.get(
        suggestion_key.lower(),
        suggestions["maize"]
    )
    suggestion_text = random.choice(suggestion_list)

    # Build the payload
    payload = {
        "job_id": job_id,
        "status": status,
        "job": "chat",
        "trace_id": trace_id,
        "callback_params": {
            "message_id": message_id,
            "message_type": MessageType.WHISPER.value,
            "ticket_id": ticket_id
        }
    }

    # Add output if status is completed
    if status == "completed":
        payload["output"] = {
            "answer": suggestion_text,
            "citations": [
                {
                    "title": f"{suggestion_key.capitalize()} Guide",
                    "url": (
                        f"https://example.com/"
                        f"{suggestion_key.lower()}-guide"
                    )
                }
            ]
        }

    # Send the request
    url = f"{base_url}/api/callback/ai"
    headers = {
        "Content-Type": "application/json",
    }

    print(f"\nSending callback to {url}...")
    print(f"Job ID: {job_id}")
    print(f"Status: {status}")
    print(f"Message ID: {message_id}")
    print(f"Ticket ID: {ticket_id}")
    print("Message Type: WHISPER (2)")
    if status == "completed":
        print(f"Suggestion: {suggestion_text[:80]}...")

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        print("\n✓ Callback successful!")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")

        return True

    except requests.exceptions.RequestException as e:
        print("\n✗ Callback failed!")
        print(f"  Error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Status: {e.response.status_code}")
            print(f"  Response: {e.response.text}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test AI callback webhook with whisper message type"
    )
    parser.add_argument(
        "--customer",
        type=str,
        required=True,
        help="Customer phone number (e.g., +255123456789)"
    )
    parser.add_argument(
        "--status",
        type=str,
        default="completed",
        choices=["queued", "completed", "failed", "timeout"],
        help="Callback status (default: completed)"
    )
    parser.add_argument(
        "--suggestion",
        type=str,
        default="maize",
        choices=list(suggestions.keys()),
        help="Crop type for suggestion template (default: maize)"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=BASE_URL,
        help=f"Base URL for the API (default: {BASE_URL})"
    )

    args = parser.parse_args()

    # Get database session
    db = SessionLocal()

    try:
        print("=" * 60)
        print("AI Callback Whisper Test")
        print("=" * 60)

        # Get customer, ticket, and message info
        print(f"\n1. Looking up customer {args.customer}...")
        info = get_customer_ticket_info(db, args.customer)

        if not info:
            print(f"✗ Customer {args.customer} not found!")
            print("  Make sure the phone number exists in database.")
            return 1

        customer = info["customer"]
        ticket = info["ticket"]
        message = info["message"]

        customer_name = customer.full_name or customer.phone_number
        print(f"✓ Found customer: {customer_name}")
        print(f"  Phone: {customer.phone_number}")
        if customer.crop_type:
            print(f"  Crop type: {customer.crop_type.name}")

        # Check for open ticket
        if not ticket:
            print("\n✗ No open ticket found for this customer!")
            print("  The customer must have an active ticket.")
            print(
                "  Create a ticket first or use a customer "
                "with open ticket."
            )
            return 1

        ticket_id = ticket.id
        print(
            f"\n✓ Found open ticket: "
            f"{ticket.ticket_number} (ID: {ticket_id})"
        )
        print(f"  Created: {ticket.created_at}")

        # Get message ID from ticket
        if not message:
            print("\n✗ No message found for this ticket!")
            print("  Ticket should have an initial message.")
            return 1

        message_id = message.id
        print(f"\n✓ Found ticket message: ID {message_id}")
        print(f"  Body: {message.body[:60]}...")
        print(f"  From: {message.from_source}")

        # Send the callback
        print("\n3. Sending AI callback webhook...")
        success = send_callback(
            ticket_id=ticket_id,
            message_id=message_id,
            status=args.status,
            suggestion_key=args.suggestion,
            base_url=args.base_url,
        )

        if success:
            print("\n" + "=" * 60)
            print("✓ Test completed successfully!")
            print("=" * 60)
            print(
                "\nCheck your WebSocket client for "
                "the whisper_created event:"
            )
            print("  Event: whisper_created")
            print(f"  Room: ticket:{ticket_id}")
            print(
                "  Data: {ticket_id: " + str(ticket_id) +
                ", message_id: <new_id>, suggestion: \"...\"}"
            )
            return 0
        else:
            print("\n" + "=" * 60)
            print("✗ Test failed!")
            print("=" * 60)
            return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
