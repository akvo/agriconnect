from typing import List, Tuple

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from models.customer import AgeGroup, CropType, Customer, CustomerLanguage


class CustomerService:
    def __init__(self, db: Session):
        self.db = db

    def get_customer_by_phone(self, phone_number: str) -> Customer:
        """Get customer by phone number."""
        return (
            self.db.query(Customer)
            .filter(Customer.phone_number == phone_number)
            .first()
        )

    def create_customer(
        self,
        phone_number: str,
        language: CustomerLanguage = CustomerLanguage.EN,
    ) -> Customer:
        """Create a new customer with minimal fields."""
        customer = Customer(phone_number=phone_number, language=language)
        try:
            self.db.add(customer)
            self.db.commit()
            self.db.refresh(customer)
            return customer
        except IntegrityError:
            self.db.rollback()
            return self.get_customer_by_phone(phone_number)

    def get_or_create_customer(
        self, phone_number: str, message_text: str = None
    ) -> Customer:
        """Get existing customer or create new one with language detection."""
        customer = self.get_customer_by_phone(phone_number)
        if customer:
            return customer

        language = (
            self._detect_language_from_message(message_text)
            if message_text
            else CustomerLanguage.EN
        )
        return self.create_customer(phone_number, language)

    def update_customer_profile(self, customer_id: int, **kwargs) -> Customer:
        """Update customer profile with new information."""
        customer = (
            self.db.query(Customer).filter(Customer.id == customer_id).first()
        )
        if not customer:
            return None

        for key, value in kwargs.items():
            if hasattr(customer, key):
                # Handle empty strings as None for optional fields like
                # full_name
                if key == "full_name" and value == "":
                    value = None
                setattr(customer, key, value)

        self.db.commit()
        self.db.refresh(customer)
        return customer

    def _detect_language_from_message(
        self, message_text: str
    ) -> CustomerLanguage:
        """Detect language from greeting message."""
        if not message_text:
            return CustomerLanguage.EN

        message_lower = message_text.lower().strip()

        swahili_greetings = [
            "hujambo",
            "mambo",
            "habari",
            "salama",
            "shikamoo",
            "vipi",
            "hodi",
            "pole",
            "karibu",
            "asante",
            "ahsante",
        ]

        english_greetings = [
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "greetings",
            "howdy",
        ]

        for greeting in swahili_greetings:
            if greeting in message_lower:
                return CustomerLanguage.SW

        for greeting in english_greetings:
            if greeting in message_lower:
                return CustomerLanguage.EN

        return CustomerLanguage.EN

    def delete_customer(self, customer_id: int) -> bool:
        """Delete a customer and all associated messages."""
        customer = (
            self.db.query(Customer).filter(Customer.id == customer_id).first()
        )
        if not customer:
            return False

        try:
            # Delete the customer (messages will be cascaded if configured)
            self.db.delete(customer)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def get_customers_list(
        self,
        page: int = 1,
        size: int = 10,
        search: str = None,
        administrative_ids: List[int] = None,
        crop_types: List[str] = None,
        age_groups: List[str] = None,
    ) -> Tuple[List[dict], int]:
        """Get paginated list of customers with optional filters.

        Args:
            page: Page number (1-indexed)
            size: Number of items per page
            search: Optional search term (searches name and phone)
            administrative_ids: Optional list of administrative IDs
                to filter by. If None or empty, no filtering applied.
            crop_types: Optional list of crop types to filter by
            age_groups: Optional list of age groups to filter by

        Returns:
            Tuple of (list of customer dicts, total count)
        """
        # Base query with eager loading of relationships
        query = self.db.query(Customer).options(
            joinedload(Customer.customer_administrative).joinedload(
                CustomerAdministrative.administrative
            )
        )

        # Filter by administrative areas (wards) if provided
        if administrative_ids:
            query = query.join(Customer.customer_administrative).filter(
                CustomerAdministrative.administrative_id.in_(
                    administrative_ids
                )
            )

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Customer.full_name.ilike(search_term),
                    Customer.phone_number.ilike(search_term),
                )
            )

        # Filter by crop types (convert strings to enum objects)
        if crop_types:
            crop_type_enums = [
                CropType(ct)
                for ct in crop_types
                if ct in [e.value for e in CropType]
            ]
            if crop_type_enums:
                query = query.filter(
                    Customer.crop_type.in_(crop_type_enums)
                )

        # Filter by age groups (convert strings to enum objects)
        if age_groups:
            age_group_enums = [
                AgeGroup(ag)
                for ag in age_groups
                if ag in [e.value for e in AgeGroup]
            ]
            if age_group_enums:
                query = query.filter(
                    Customer.age_group.in_(age_group_enums)
                )

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        customers = (
            query.order_by(Customer.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        # Convert to dict format with administrative info
        customer_data = []
        for customer in customers:
            # Get administrative info (ward)
            admin_info = {"id": None, "name": None, "path": None}
            if customer.customer_administrative:
                # Get the first administrative assignment
                # (assuming one ward per customer)
                customer_admin = customer.customer_administrative[0]
                if customer_admin.administrative:
                    admin = customer_admin.administrative
                    admin_info = {
                        "id": admin.id,
                        "name": admin.name,
                        "path": self._build_administrative_path(
                            admin.id
                        ),
                    }

            customer_dict = {
                "id": customer.id,
                "full_name": customer.full_name,
                "phone_number": customer.phone_number,
                "language": customer.language,
                "crop_type": customer.crop_type,
                "age_group": customer.age_group,
                "administrative": admin_info,
            }
            customer_data.append(customer_dict)

        return customer_data, total

    def _build_administrative_path(self, administrative_id: int) -> str:
        """Build the full administrative path (Region - District - Ward).

        Args:
            administrative_id: The administrative area ID

        Returns:
            Human-readable path string or None
        """
        if not administrative_id:
            return None

        admin = (
            self.db.query(Administrative)
            .filter(Administrative.id == administrative_id)
            .first()
        )
        if not admin:
            return None

        # Split the path to get all administrative codes
        path_parts = admin.path.split(".") if admin.path else []

        # Query all administrative areas in the path with their levels
        areas = (
            self.db.query(Administrative)
            .join(AdministrativeLevel)
            .filter(Administrative.code.in_(path_parts))
            .order_by(AdministrativeLevel.id)
            .all()
        )

        # Build the path string, excluding country level
        path_names = []
        for area in areas:
            # Skip country level (identified by level name)
            if area.level and area.level.name != "country":
                path_names.append(area.name)

        return " - ".join(path_names) if path_names else None
