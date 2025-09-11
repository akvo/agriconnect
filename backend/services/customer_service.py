from sqlalchemy.orm import Session
from models.customer import Customer, CustomerLanguage
from sqlalchemy.exc import IntegrityError
import re


class CustomerService:
    def __init__(self, db: Session):
        self.db = db

    def get_customer_by_phone(self, phone_number: str) -> Customer:
        """Get customer by phone number."""
        return self.db.query(Customer).filter(Customer.phone_number == phone_number).first()

    def create_customer(self, phone_number: str, language: CustomerLanguage = CustomerLanguage.EN) -> Customer:
        """Create a new customer with minimal fields."""
        customer = Customer(
            phone_number=phone_number,
            language=language
        )
        try:
            self.db.add(customer)
            self.db.commit()
            self.db.refresh(customer)
            return customer
        except IntegrityError:
            self.db.rollback()
            return self.get_customer_by_phone(phone_number)

    def get_or_create_customer(self, phone_number: str, message_text: str = None) -> Customer:
        """Get existing customer or create new one with language detection."""
        customer = self.get_customer_by_phone(phone_number)
        if customer:
            return customer
        
        language = self._detect_language_from_message(message_text) if message_text else CustomerLanguage.EN
        return self.create_customer(phone_number, language)

    def update_customer_profile(self, customer_id: int, **kwargs) -> Customer:
        """Update customer profile with new information."""
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return None
        
        for key, value in kwargs.items():
            if hasattr(customer, key):
                # Handle empty strings as None for optional fields like full_name
                if key == 'full_name' and value == '':
                    value = None
                setattr(customer, key, value)
        
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def _detect_language_from_message(self, message_text: str) -> CustomerLanguage:
        """Detect language from greeting message."""
        if not message_text:
            return CustomerLanguage.EN
        
        message_lower = message_text.lower().strip()
        
        swahili_greetings = [
            'hujambo', 'mambo', 'habari', 'salama', 'shikamoo', 'vipi',
            'hodi', 'pole', 'karibu', 'asante', 'ahsante'
        ]
        
        english_greetings = [
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 
            'good evening', 'greetings', 'howdy'
        ]
        
        for greeting in swahili_greetings:
            if greeting in message_lower:
                return CustomerLanguage.SW
        
        for greeting in english_greetings:
            if greeting in message_lower:
                return CustomerLanguage.EN
        
        return CustomerLanguage.EN

