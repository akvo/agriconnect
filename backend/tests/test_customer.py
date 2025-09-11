import pytest
from sqlalchemy.orm import Session
from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom
from services.customer_service import CustomerService


class TestCustomerModel:
    def test_create_customer(self, db_session: Session):
        customer = Customer(
            phone_number="+255123456789",
            language=CustomerLanguage.EN
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.id is not None
        assert customer.phone_number == "+255123456789"
        assert customer.language == CustomerLanguage.EN
        assert customer.full_name is None
        assert customer.created_at is not None

    def test_customer_with_full_name(self, db_session: Session):
        customer = Customer(
            phone_number="+255987654321",
            full_name="John Farmer",
            language=CustomerLanguage.SW
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.full_name == "John Farmer"
        assert customer.language == CustomerLanguage.SW

    def test_unique_phone_constraint(self, db_session: Session):
        customer1 = Customer(phone_number="+255111111111")
        customer2 = Customer(phone_number="+255111111111")
        
        db_session.add(customer1)
        db_session.commit()
        
        db_session.add(customer2)
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()


class TestCustomerService:
    def test_get_customer_by_phone_exists(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        service = CustomerService(db_session)
        found_customer = service.get_customer_by_phone("+255123456789")

        assert found_customer is not None
        assert found_customer.phone_number == "+255123456789"

    def test_get_customer_by_phone_not_exists(self, db_session: Session):
        service = CustomerService(db_session)
        found_customer = service.get_customer_by_phone("+255999999999")

        assert found_customer is None

    def test_create_customer(self, db_session: Session):
        service = CustomerService(db_session)
        customer = service.create_customer("+255123456789", CustomerLanguage.SW)

        assert customer.phone_number == "+255123456789"
        assert customer.language == CustomerLanguage.SW

    def test_create_customer_duplicate_returns_existing(self, db_session: Session):
        existing = Customer(phone_number="+255123456789", full_name="John")
        db_session.add(existing)
        db_session.commit()
        db_session.refresh(existing)

        service = CustomerService(db_session)
        customer = service.create_customer("+255123456789")

        assert customer.id == existing.id
        assert customer.full_name == "John"

    def test_get_or_create_customer_new(self, db_session: Session):
        service = CustomerService(db_session)
        customer = service.get_or_create_customer("+255123456789", "Hello there")

        assert customer.phone_number == "+255123456789"
        assert customer.language == CustomerLanguage.EN  # Default for English greeting

    def test_get_or_create_customer_existing(self, db_session: Session):
        existing = Customer(phone_number="+255123456789", full_name="Jane")
        db_session.add(existing)
        db_session.commit()

        service = CustomerService(db_session)
        customer = service.get_or_create_customer("+255123456789")

        assert customer.id == existing.id
        assert customer.full_name == "Jane"

    def test_update_customer_profile(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        service = CustomerService(db_session)
        updated = service.update_customer_profile(
            customer.id, 
            full_name="Updated Name",
            language=CustomerLanguage.SW
        )

        assert updated.full_name == "Updated Name"
        assert updated.language == CustomerLanguage.SW

    def test_update_nonexistent_customer(self, db_session: Session):
        service = CustomerService(db_session)
        result = service.update_customer_profile(999, full_name="Test")

        assert result is None

    def test_detect_language_swahili(self, db_session: Session):
        service = CustomerService(db_session)
        
        # Test various Swahili greetings
        swahili_messages = [
            "Hujambo",
            "mambo vipi",
            "Habari za leo",
            "SALAMA",
            "shikamoo mzee"
        ]
        
        for message in swahili_messages:
            language = service._detect_language_from_message(message)
            assert language == CustomerLanguage.SW, f"Failed for message: {message}"

    def test_detect_language_english(self, db_session: Session):
        service = CustomerService(db_session)
        
        english_messages = [
            "Hello",
            "Hi there",
            "Good morning",
            "GOOD AFTERNOON",
            "hey how are you"
        ]
        
        for message in english_messages:
            language = service._detect_language_from_message(message)
            assert language == CustomerLanguage.EN, f"Failed for message: {message}"

    def test_detect_language_default(self, db_session: Session):
        service = CustomerService(db_session)
        
        # Test unknown language defaults to English
        unknown_messages = [
            "Bonjour",
            "Guten Tag",
            "Konnichiwa",
            ""
        ]
        
        for message in unknown_messages:
            language = service._detect_language_from_message(message)
            assert language == CustomerLanguage.EN

    def test_detect_language_none(self, db_session: Session):
        service = CustomerService(db_session)
        language = service._detect_language_from_message(None)
        assert language == CustomerLanguage.EN