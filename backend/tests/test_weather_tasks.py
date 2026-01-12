"""
Unit tests for weather_tasks.py Celery tasks.
"""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from models.weather_broadcast import (
    WeatherBroadcast,
    WeatherBroadcastRecipient,
)
from models.customer import Customer, CustomerLanguage
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from models.message import DeliveryStatus
from tasks.weather_tasks import (
    send_weather_broadcasts,
    send_weather_templates,
    send_weather_message,
    retry_failed_weather_broadcasts,
)


# Ensure we're in test mode
os.environ["TESTING"] = "true"


@pytest.fixture
def test_administrative(db_session):
    """Create a test administrative area (ward)"""
    # Create administrative level first
    level = AdministrativeLevel(name="WeatherTestWard")
    db_session.add(level)
    db_session.commit()
    db_session.refresh(level)

    # Create administrative area
    admin = Administrative(
        code="WTH001",
        name="Test Ward",
        level_id=level.id,
        path="WTH001",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def test_customer_subscribed(db_session, test_administrative):
    """Create a test customer with weather subscription"""
    customer = Customer(
        phone_number="+255700001001",
        language=CustomerLanguage.EN,
        full_name="Subscribed Customer",
        profile_data={"weather_subscribed": True},
    )
    db_session.add(customer)
    db_session.flush()

    # Link customer to administrative area
    link = CustomerAdministrative(
        customer_id=customer.id,
        administrative_id=test_administrative.id,
    )
    db_session.add(link)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_customers_subscribed(db_session, test_administrative):
    """Create multiple test customers with weather subscription"""
    customers = []
    for i in range(1, 4):
        lang = CustomerLanguage.EN if i % 2 == 0 else CustomerLanguage.SW
        customer = Customer(
            phone_number=f"+255700002{i:03d}",
            language=lang,
            full_name=f"Weather Customer {i}",
            profile_data={"weather_subscribed": True},
        )
        db_session.add(customer)
        db_session.flush()

        link = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=test_administrative.id,
        )
        db_session.add(link)
        customers.append(customer)

    db_session.commit()
    for customer in customers:
        db_session.refresh(customer)

    return customers


@pytest.fixture
def test_weather_broadcast(db_session, test_administrative):
    """Create a test weather broadcast"""
    broadcast = WeatherBroadcast(
        administrative_id=test_administrative.id,
        location_name=test_administrative.name,
        status="pending",
        scheduled_at=datetime.utcnow(),
    )
    db_session.add(broadcast)
    db_session.commit()
    db_session.refresh(broadcast)
    return broadcast


@pytest.fixture
def test_weather_setup(
    db_session, test_administrative, test_customers_subscribed
):
    """Create complete weather broadcast setup for testing"""
    # Create weather broadcast
    broadcast = WeatherBroadcast(
        administrative_id=test_administrative.id,
        location_name=test_administrative.name,
        weather_data={"temp": 25, "humidity": 60},
        generated_message_en="Today's weather: Sunny, 25°C",
        generated_message_sw="Hali ya hewa leo: Jua, 25°C",
        status="completed",
        scheduled_at=datetime.utcnow(),
    )
    db_session.add(broadcast)
    db_session.flush()

    # Create recipients
    for customer in test_customers_subscribed:
        recipient = WeatherBroadcastRecipient(
            weather_broadcast_id=broadcast.id,
            customer_id=customer.id,
            status=DeliveryStatus.PENDING,
        )
        db_session.add(recipient)

    db_session.commit()
    db_session.refresh(broadcast)

    return {
        "broadcast": broadcast,
        "administrative": test_administrative,
        "customers": test_customers_subscribed,
    }


class TestSendWeatherBroadcasts:
    """Tests for send_weather_broadcasts task"""

    def test_send_weather_broadcasts_no_subscribers(self):
        """Test task returns early when no subscribers"""
        with patch("tasks.weather_tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db

            # Mock weather service as configured
            with patch(
                "tasks.weather_tasks.get_weather_broadcast_service"
            ) as mock_ws:
                mock_service = MagicMock()
                mock_service.is_configured.return_value = True
                mock_ws.return_value = mock_service

                # Return empty list for customer query
                mock_query = mock_db.query.return_value
                mock_query.join.return_value.all.return_value = []

                result = send_weather_broadcasts()

        assert result["areas_processed"] == 0
        assert result["broadcasts_created"] == 0

    def test_send_weather_broadcasts_service_not_configured(self):
        """Test task returns error when service not configured"""
        with patch("tasks.weather_tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db

            with patch(
                "tasks.weather_tasks.get_weather_broadcast_service"
            ) as mock_ws:
                mock_service = MagicMock()
                mock_service.is_configured.return_value = False
                mock_ws.return_value = mock_service

                result = send_weather_broadcasts()

        assert "error" in result
        assert "not configured" in result["error"]

    @patch("tasks.weather_tasks.SessionLocal")
    @patch("tasks.weather_tasks.send_weather_templates")
    def test_send_weather_broadcasts_creates_broadcasts(
        self, mock_templates_task, mock_sl, db_session,
        test_administrative, test_customers_subscribed
    ):
        """Test task creates broadcasts for areas with subscribers"""
        mock_sl.return_value = db_session

        with patch(
            "tasks.weather_tasks.get_weather_broadcast_service"
        ) as mock_ws:
            mock_service = MagicMock()
            mock_service.is_configured.return_value = True
            mock_ws.return_value = mock_service

            # Mock the delay method
            mock_templates_task.delay = MagicMock()

            result = send_weather_broadcasts()

        assert result["broadcasts_created"] >= 1
        assert "error" not in result or result.get("errors") is None

        # Verify broadcast was created
        broadcasts = db_session.query(WeatherBroadcast).filter(
            WeatherBroadcast.administrative_id == test_administrative.id
        ).all()
        assert len(broadcasts) >= 1


class TestSendWeatherTemplates:
    """Tests for send_weather_templates task"""

    def test_send_weather_templates_broadcast_not_found(self):
        """Test task returns error when broadcast not found"""
        with patch("tasks.weather_tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_filter = mock_db.query.return_value.filter.return_value
            mock_filter.first.return_value = None

            result = send_weather_templates(weather_broadcast_id=99999)

        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("tasks.weather_tasks.SessionLocal")
    def test_send_weather_templates_weather_data_failure(
        self, mock_sl, db_session, test_weather_broadcast
    ):
        """Test task handles weather data fetch failure"""
        mock_sl.return_value = db_session

        with patch(
            "tasks.weather_tasks.get_weather_broadcast_service"
        ) as mock_ws:
            mock_service = MagicMock()
            mock_service.get_forecast_raw.return_value = None
            mock_ws.return_value = mock_service

            result = send_weather_templates(test_weather_broadcast.id)

        assert "error" in result
        assert "weather data" in result["error"].lower()

        # Verify broadcast status updated to failed
        db_session.expire_all()
        broadcast = db_session.query(WeatherBroadcast).get(
            test_weather_broadcast.id
        )
        assert broadcast.status == "failed"

    @patch("tasks.weather_tasks.SessionLocal")
    def test_send_weather_templates_success(
        self, mock_sl, db_session, test_weather_broadcast,
        test_customers_subscribed
    ):
        """Test successful template sending"""
        mock_sl.return_value = db_session

        # Store the ID before it gets detached
        broadcast_id = test_weather_broadcast.id
        num_customers = len(test_customers_subscribed)

        with patch(
            "tasks.weather_tasks.get_weather_broadcast_service"
        ) as mock_ws:
            mock_service = MagicMock()
            mock_service.get_forecast_raw.return_value = {"temp": 25}

            # Create async mock for generate_message
            async def mock_generate(*args, **kwargs):
                return "Test weather message"

            mock_service.generate_message = mock_generate
            mock_ws.return_value = mock_service

            result = send_weather_templates(broadcast_id)

        assert "error" not in result
        assert result["sent"] == num_customers

        # Verify broadcast completed
        db_session.expire_all()
        broadcast = db_session.query(WeatherBroadcast).get(broadcast_id)
        assert broadcast.status == "completed"
        assert broadcast.generated_message_en is not None

        # Verify recipients created and sent
        recipients = db_session.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.weather_broadcast_id == broadcast_id
        ).all()
        assert len(recipients) == num_customers
        for recipient in recipients:
            assert recipient.status == DeliveryStatus.SENT
            assert recipient.confirm_message_sid is not None

    @patch("tasks.weather_tasks.SessionLocal")
    def test_send_weather_templates_no_subscribers(
        self, mock_sl, db_session, test_weather_broadcast
    ):
        """Test task handles area with no subscribers"""
        mock_sl.return_value = db_session

        with patch(
            "tasks.weather_tasks.get_weather_broadcast_service"
        ) as mock_ws:
            mock_service = MagicMock()
            mock_service.get_forecast_raw.return_value = {"temp": 25}

            async def mock_generate(*args, **kwargs):
                return "Test weather message"

            mock_service.generate_message = mock_generate
            mock_ws.return_value = mock_service

            result = send_weather_templates(test_weather_broadcast.id)

        assert result["sent"] == 0
        assert "No subscribers" in result.get("message", "")


class TestSendWeatherMessage:
    """Tests for send_weather_message task"""

    def test_send_weather_message_recipient_not_found(self):
        """Test task returns error when recipient not found"""
        with patch("tasks.weather_tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_filter = mock_db.query.return_value.filter.return_value
            mock_filter.first.return_value = None

            result = send_weather_message(
                recipient_id=99999,
                phone_number="+255700000000"
            )

        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("tasks.weather_tasks.SessionLocal")
    def test_send_weather_message_success(
        self, mock_sl, db_session, test_weather_setup
    ):
        """Test successful weather message sending"""
        mock_sl.return_value = db_session

        # Get a recipient and store IDs
        broadcast_id = test_weather_setup["broadcast"].id
        recipient = db_session.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.weather_broadcast_id == broadcast_id
        ).first()

        recipient.status = DeliveryStatus.SENT
        recipient.confirm_message_sid = "SM_CONFIRM_123"
        db_session.commit()

        # Store IDs before they might get detached
        recipient_id = recipient.id
        customer_phone = test_weather_setup["customers"][0].phone_number

        result = send_weather_message(
            recipient_id=recipient_id,
            phone_number=customer_phone
        )

        assert "status" in result
        assert result["status"] == "sent"

        # Verify recipient updated
        db_session.expire_all()
        updated_recipient = db_session.query(WeatherBroadcastRecipient).get(
            recipient_id
        )
        assert updated_recipient.actual_message_sid is not None
        assert updated_recipient.confirmed_at is not None
        assert updated_recipient.message_id is not None

    @patch("tasks.weather_tasks.SessionLocal")
    def test_send_weather_message_no_content(
        self, mock_sl, db_session, test_administrative,
        test_customer_subscribed
    ):
        """Test task handles missing message content"""
        mock_sl.return_value = db_session

        # Create broadcast without generated messages
        broadcast = WeatherBroadcast(
            administrative_id=test_administrative.id,
            location_name=test_administrative.name,
            status="completed",
        )
        db_session.add(broadcast)
        db_session.flush()

        recipient = WeatherBroadcastRecipient(
            weather_broadcast_id=broadcast.id,
            customer_id=test_customer_subscribed.id,
            status=DeliveryStatus.SENT,
            confirm_message_sid="SM_CONFIRM_456",
        )
        db_session.add(recipient)
        db_session.commit()

        result = send_weather_message(
            recipient_id=recipient.id,
            phone_number=test_customer_subscribed.phone_number
        )

        assert "error" in result
        assert "content" in result["error"].lower()


class TestRetryFailedWeatherBroadcasts:
    """Tests for retry_failed_weather_broadcasts task"""

    def test_retry_failed_weather_broadcasts_no_failures(self):
        """Test retry task with no failed recipients"""
        with patch("tasks.weather_tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            # Return empty list for all retry intervals
            mock_filter = mock_db.query.return_value.filter.return_value
            mock_filter.all.return_value = []

            result = retry_failed_weather_broadcasts()

        assert "error" not in result
        assert "retried" in result
        assert "succeeded" in result
        assert "failed" in result

    @patch("tasks.weather_tasks.SessionLocal")
    def test_retry_failed_weather_broadcasts_first_retry(
        self, mock_sl, db_session, test_weather_setup
    ):
        """Test first retry after 5 minutes"""
        mock_sl.return_value = db_session

        # Get a recipient and mark as failed
        recipient = db_session.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.weather_broadcast_id
            == test_weather_setup["broadcast"].id
        ).first()

        recipient_id = recipient.id
        recipient.status = DeliveryStatus.FAILED
        recipient.retry_count = 0
        recipient.sent_at = datetime.utcnow() - timedelta(minutes=6)
        recipient.error_message = "Initial failure"
        db_session.commit()

        result = retry_failed_weather_broadcasts()

        assert "error" not in result
        assert result["retried"] >= 1
        assert result["succeeded"] >= 1

        # Verify recipient was retried
        db_session.expire_all()
        updated_recipient = db_session.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.id == recipient_id
        ).first()
        assert updated_recipient.status == DeliveryStatus.SENT
        assert updated_recipient.error_message is None

    @patch("tasks.weather_tasks.SessionLocal")
    def test_retry_failed_weather_broadcasts_max_retries(
        self, mock_sl, db_session, test_weather_setup
    ):
        """Test that recipients stop retrying after max attempts"""
        mock_sl.return_value = db_session

        recipient = db_session.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.weather_broadcast_id
            == test_weather_setup["broadcast"].id
        ).first()

        recipient_id = recipient.id
        # Set to max retries already exhausted
        recipient.status = DeliveryStatus.FAILED
        recipient.retry_count = 3
        recipient.sent_at = datetime.utcnow() - timedelta(minutes=70)
        db_session.commit()

        result = retry_failed_weather_broadcasts()

        assert "error" not in result

        # Verify recipient status unchanged
        db_session.expire_all()
        updated_recipient = db_session.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.id == recipient_id
        ).first()
        assert updated_recipient.retry_count == 3

    def test_retry_failed_weather_broadcasts_exception(self):
        """Test exception handling in retry task"""
        with patch("tasks.weather_tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_db.query.side_effect = Exception("Retry error")
            mock_sl.return_value = mock_db

            result = retry_failed_weather_broadcasts()

        assert "error" in result
        assert "Retry error" in result["error"]


class TestWeatherTasksIntegration:
    """Integration tests for weather tasks"""

    @patch("tasks.weather_tasks.SessionLocal")
    @patch("tasks.weather_tasks.WhatsAppService")
    def test_send_weather_templates_non_test_mode(
        self, mock_ws_class, mock_sl, db_session, test_weather_broadcast,
        test_customers_subscribed
    ):
        """Test actual WhatsApp send in non-test mode"""
        mock_sl.return_value = db_session

        # Mock WhatsApp service
        mock_service = MagicMock()
        mock_service.send_template_message.return_value = {
            "sid": "SM_REAL_123"
        }
        mock_service.get_template_sid.return_value = "HX_TEMPLATE"
        mock_ws_class.return_value = mock_service

        with patch(
            "tasks.weather_tasks.get_weather_broadcast_service"
        ) as mock_wbs:
            weather_service = MagicMock()
            weather_service.get_forecast_raw.return_value = {"temp": 25}

            async def mock_generate(*args, **kwargs):
                return "Test weather message"

            weather_service.generate_message = mock_generate
            mock_wbs.return_value = weather_service

            # Temporarily disable test mode
            original_testing = os.environ.pop("TESTING", None)

            try:
                result = send_weather_templates(test_weather_broadcast.id)

                assert "error" not in result
                assert result["sent"] == len(test_customers_subscribed)
                assert mock_service.send_template_message.call_count == len(
                    test_customers_subscribed
                )
            finally:
                # Restore test mode
                if original_testing:
                    os.environ["TESTING"] = original_testing

    @patch("tasks.weather_tasks.SessionLocal")
    @patch("tasks.weather_tasks.WhatsAppService")
    def test_send_weather_message_non_test_mode(
        self, mock_ws_class, mock_sl, db_session, test_weather_setup
    ):
        """Test actual weather message send"""
        mock_sl.return_value = db_session

        # Mock WhatsApp service
        mock_service = MagicMock()
        mock_service.send_message.return_value = {"sid": "SM_ACTUAL_456"}
        mock_ws_class.return_value = mock_service

        # Get recipient
        recipient = db_session.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.weather_broadcast_id
            == test_weather_setup["broadcast"].id
        ).first()

        recipient.status = DeliveryStatus.SENT
        recipient.confirm_message_sid = "SM_CONFIRM_123"
        db_session.commit()

        customer = test_weather_setup["customers"][0]

        # Temporarily disable test mode
        original_testing = os.environ.pop("TESTING", None)

        try:
            result = send_weather_message(
                recipient_id=recipient.id,
                phone_number=customer.phone_number
            )

            assert "status" in result
            assert mock_service.send_message.called
        finally:
            # Restore test mode
            if original_testing:
                os.environ["TESTING"] = original_testing
