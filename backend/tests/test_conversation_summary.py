"""
Unit tests for conversation_summary utility

Tests the implementation of:
- Merging farmer questions before/after FOLLOW_UP messages
- Customer context extraction (farmer_id, ward, crop, gender, age_group)
- Time threshold filtering
- DataFrame output format
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from models.customer import Customer, CustomerLanguage, OnboardingStatus
from models.message import Message, MessageFrom
from schemas.callback import MessageType
from utils.conversation_summary import (
    get_customer_context,
    get_follow_up_conversations,
    merge_questions,
)


class TestMergeQuestions:
    """Test merge_questions function"""

    def test_merge_both_messages(self):
        """Test merging when both before and after messages exist"""
        before_msg = Message(
            message_sid="before",
            customer_id=1,
            body="My crops are dying",
            from_source=MessageFrom.CUSTOMER,
        )
        after_msg = Message(
            message_sid="after",
            customer_id=1,
            body="It started last week",
            from_source=MessageFrom.CUSTOMER,
        )

        result = merge_questions(before_msg, after_msg)

        assert result == "My crops are dying. It started last week"

    def test_merge_only_before_message(self):
        """Test merging when only before message exists"""
        before_msg = Message(
            message_sid="before",
            customer_id=1,
            body="Help with pest control",
            from_source=MessageFrom.CUSTOMER,
        )

        result = merge_questions(before_msg, None)

        assert result == "Help with pest control"

    def test_merge_only_after_message(self):
        """Test merging when only after message exists"""
        after_msg = Message(
            message_sid="after",
            customer_id=1,
            body="The leaves are yellow",
            from_source=MessageFrom.CUSTOMER,
        )

        result = merge_questions(None, after_msg)

        assert result == "The leaves are yellow"

    def test_merge_no_messages(self):
        """Test merging when no messages exist"""
        result = merge_questions(None, None)

        assert result == ""

    def test_merge_with_whitespace(self):
        """Test merging strips whitespace from messages"""
        before_msg = Message(
            message_sid="before",
            customer_id=1,
            body="  Question with spaces  ",
            from_source=MessageFrom.CUSTOMER,
        )
        after_msg = Message(
            message_sid="after",
            customer_id=1,
            body="  Another with spaces  ",
            from_source=MessageFrom.CUSTOMER,
        )

        result = merge_questions(before_msg, after_msg)

        assert result == "Question with spaces. Another with spaces"


class TestGetCustomerContext:
    """Test get_customer_context function"""

    def test_get_context_with_full_data(self, db_session: Session):
        """Test getting context when all data is available"""
        # Create administrative hierarchy
        level = AdministrativeLevel(name="Ward")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            code="W001",
            name="Test Ward",
            level_id=level.id,
            path="Kenya > Murang'a > Kiharu > Test Ward",
        )
        db_session.add(admin)
        db_session.commit()

        # Create customer with profile data (birth_year 1990 = "36-50")
        customer = Customer(
            phone_number="+254712345678",
            full_name="Test Farmer",
            language=CustomerLanguage.EN,
            profile_data={
                "crop_type": "Maize",
                "gender": "male",
                "birth_year": 1990,
            },
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Link customer to administrative area
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        result = get_customer_context(db_session, customer.id)

        assert result["farmer_id"] == customer.id
        assert result["ward"] == "Test Ward"
        assert result["crop"] == "Maize"
        assert result["gender"] == "male"
        assert result["age_group"] == "36-50"

    def test_get_context_with_minimal_data(self, db_session: Session):
        """Test getting context when only basic data exists"""
        customer = Customer(
            phone_number="+254712345679",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        result = get_customer_context(db_session, customer.id)

        assert result["farmer_id"] == customer.id
        assert result["ward"] is None
        assert result["crop"] is None
        assert result["gender"] is None
        assert result["age_group"] is None

    def test_get_context_nonexistent_customer(self, db_session: Session):
        """Test getting context for nonexistent customer"""
        result = get_customer_context(db_session, 99999)

        assert result["farmer_id"] == 99999
        assert result["ward"] is None
        assert result["crop"] is None
        assert result["gender"] is None
        assert result["age_group"] is None


class TestGetFollowUpConversations:
    """Test get_follow_up_conversations function"""

    def _cleanup_messages(self, db_session: Session):
        """Clean up all messages to ensure test isolation"""
        db_session.query(Message).delete()
        db_session.commit()

    def test_returns_empty_dataframe_when_no_follow_ups(
        self, db_session: Session
    ):
        """Test that empty DataFrame is returned when no FOLLOW_UP exists"""
        self._cleanup_messages(db_session)

        # Create customer with regular message (no FOLLOW_UP)
        customer = Customer(
            phone_number="+254712345680",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        msg = Message(
            message_sid="msg_regular",
            customer_id=customer.id,
            body="Regular message",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(msg)
        db_session.commit()

        df = get_follow_up_conversations(db_session)

        assert df.empty
        assert list(df.columns) == [
            "farmer_id", "ward", "crop", "gender", "age_group",
            "query_text", "date"
        ]

    def test_merges_messages_within_threshold(self, db_session: Session):
        """Test that messages within threshold are merged"""
        self._cleanup_messages(db_session)

        # Create administrative area
        level = AdministrativeLevel(name="Ward2")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            code="W002",
            name="Test Ward 2",
            level_id=level.id,
            path="Kenya > Test > Ward2",
        )
        db_session.add(admin)
        db_session.commit()

        # Create customer with full profile
        customer = Customer(
            phone_number="+254712345681",
            full_name="Farmer One",
            language=CustomerLanguage.EN,
            profile_data={
                "crop_type": "Coffee",
                "gender": "female",
                "birth_year": 2000,  # age ~26 = "20-35"
            },
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Link customer to admin
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Create messages with specific timestamps
        base_time = datetime.now(timezone.utc)

        # Message BEFORE follow-up (2 minutes before)
        before_msg = Message(
            message_sid="msg_before_1",
            customer_id=customer.id,
            body="My coffee plants have yellow leaves",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(before_msg)
        db_session.commit()

        # Set timestamp
        db_session.execute(
            Message.__table__.update()
            .where(Message.id == before_msg.id)
            .values(created_at=base_time - timedelta(minutes=2))
        )
        db_session.commit()

        # FOLLOW_UP message
        follow_up_msg = Message(
            message_sid="msg_follow_up_1",
            customer_id=customer.id,
            body="How long have you noticed this?",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(follow_up_msg)
        db_session.commit()

        # Set timestamp
        db_session.execute(
            Message.__table__.update()
            .where(Message.id == follow_up_msg.id)
            .values(created_at=base_time)
        )
        db_session.commit()

        # Message AFTER follow-up (3 minutes after)
        after_msg = Message(
            message_sid="msg_after_1",
            customer_id=customer.id,
            body="Started about two weeks ago",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(after_msg)
        db_session.commit()

        # Set timestamp
        db_session.execute(
            Message.__table__.update()
            .where(Message.id == after_msg.id)
            .values(created_at=base_time + timedelta(minutes=3))
        )
        db_session.commit()

        df = get_follow_up_conversations(db_session, time_threshold_minutes=5)

        assert len(df) == 1
        row = df.iloc[0]
        assert row["farmer_id"] == customer.id
        assert row["ward"] == "Test Ward 2"
        assert row["crop"] == "Coffee"
        assert row["gender"] == "female"
        assert row["age_group"] == "20-35"
        assert "yellow leaves" in row["query_text"]
        assert "two weeks ago" in row["query_text"]

    def test_excludes_messages_outside_threshold(self, db_session: Session):
        """Test that messages outside threshold are excluded"""
        self._cleanup_messages(db_session)

        # Create customer
        customer = Customer(
            phone_number="+254712345682",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        base_time = datetime.now(timezone.utc)

        # Message BEFORE follow-up (10 min before - outside 5 min threshold)
        before_msg = Message(
            message_sid="msg_before_2",
            customer_id=customer.id,
            body="Old message outside threshold",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(before_msg)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == before_msg.id)
            .values(created_at=base_time - timedelta(minutes=10))
        )
        db_session.commit()

        # FOLLOW_UP message
        follow_up_msg = Message(
            message_sid="msg_follow_up_2",
            customer_id=customer.id,
            body="Follow-up question",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(follow_up_msg)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == follow_up_msg.id)
            .values(created_at=base_time)
        )
        db_session.commit()

        # No after message within threshold

        df = get_follow_up_conversations(db_session, time_threshold_minutes=5)

        # Should be empty since the before message is outside threshold
        assert df.empty

    def test_respects_custom_threshold(self, db_session: Session):
        """Test that custom time threshold is respected"""
        self._cleanup_messages(db_session)

        customer = Customer(
            phone_number="+254712345683",
            language=CustomerLanguage.EN,
            profile_data={"crop_type": "Maize"},
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        base_time = datetime.now(timezone.utc)

        # Message 8 minutes before (outside 5 min, inside 10 min)
        before_msg = Message(
            message_sid="msg_before_3",
            customer_id=customer.id,
            body="Question about maize",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(before_msg)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == before_msg.id)
            .values(created_at=base_time - timedelta(minutes=8))
        )
        db_session.commit()

        # FOLLOW_UP message
        follow_up_msg = Message(
            message_sid="msg_follow_up_3",
            customer_id=customer.id,
            body="Follow-up",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(follow_up_msg)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == follow_up_msg.id)
            .values(created_at=base_time)
        )
        db_session.commit()

        # With 5 minute threshold - should be empty
        df_5min = get_follow_up_conversations(
            db_session, time_threshold_minutes=5
        )
        assert df_5min.empty

        # With 10 minute threshold - should include the message
        df_10min = get_follow_up_conversations(
            db_session, time_threshold_minutes=10
        )
        assert len(df_10min) == 1
        assert "maize" in df_10min.iloc[0]["query_text"]

    def test_handles_multiple_follow_ups(self, db_session: Session):
        """Test handling multiple FOLLOW_UP messages"""
        self._cleanup_messages(db_session)

        customer = Customer(
            phone_number="+254712345684",
            language=CustomerLanguage.EN,
            profile_data={"crop_type": "Tomato"},
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        base_time = datetime.now(timezone.utc)

        # First conversation
        msg1_before = Message(
            message_sid="msg1_before",
            customer_id=customer.id,
            body="First question",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(msg1_before)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == msg1_before.id)
            .values(created_at=base_time - timedelta(hours=2, minutes=2))
        )
        db_session.commit()

        follow_up1 = Message(
            message_sid="follow_up_1",
            customer_id=customer.id,
            body="First follow-up",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(follow_up1)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == follow_up1.id)
            .values(created_at=base_time - timedelta(hours=2))
        )
        db_session.commit()

        # Second conversation
        msg2_before = Message(
            message_sid="msg2_before",
            customer_id=customer.id,
            body="Second question",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(msg2_before)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == msg2_before.id)
            .values(created_at=base_time - timedelta(minutes=2))
        )
        db_session.commit()

        follow_up2 = Message(
            message_sid="follow_up_2",
            customer_id=customer.id,
            body="Second follow-up",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(follow_up2)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == follow_up2.id)
            .values(created_at=base_time)
        )
        db_session.commit()

        df = get_follow_up_conversations(db_session, time_threshold_minutes=5)

        assert len(df) == 2
        questions = df["query_text"].tolist()
        assert any("First question" in q for q in questions)
        assert any("Second question" in q for q in questions)

    def test_excludes_follow_up_message_type_from_merge(
        self, db_session: Session
    ):
        """Test that FOLLOW_UP messages are not included in merged question"""
        self._cleanup_messages(db_session)

        customer = Customer(
            phone_number="+254712345685",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        base_time = datetime.now(timezone.utc)

        # Customer message before
        before_msg = Message(
            message_sid="msg_before_fu",
            customer_id=customer.id,
            body="Customer question here",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(before_msg)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == before_msg.id)
            .values(created_at=base_time - timedelta(minutes=2))
        )
        db_session.commit()

        # FOLLOW_UP message (should not be in merged text)
        follow_up = Message(
            message_sid="follow_up_exclude",
            customer_id=customer.id,
            body="System follow-up question",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(follow_up)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == follow_up.id)
            .values(created_at=base_time)
        )
        db_session.commit()

        # Customer response after
        after_msg = Message(
            message_sid="msg_after_fu",
            customer_id=customer.id,
            body="Customer response here",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(after_msg)
        db_session.commit()

        db_session.execute(
            Message.__table__.update()
            .where(Message.id == after_msg.id)
            .values(created_at=base_time + timedelta(minutes=2))
        )
        db_session.commit()

        df = get_follow_up_conversations(db_session, time_threshold_minutes=5)

        assert len(df) == 1
        question = df.iloc[0]["query_text"]
        # Should contain customer messages
        assert "Customer question here" in question
        assert "Customer response here" in question
        # Should NOT contain the follow-up message
        assert "System follow-up question" not in question
