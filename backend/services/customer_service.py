from typing import List, Tuple, Dict

from sqlalchemy import or_, and_, Integer, cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from models.customer import (
    Customer,
    CustomerLanguage,
    OnboardingStatus,
)
from models.ticket import Ticket
from datetime import datetime, timezone


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
        language: CustomerLanguage = None,
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
            # Handle ward_id specially (not a direct customer attribute)
            if key == "ward_id":
                # Update or create CustomerAdministrative entry
                # Flush any pending changes to ensure we see existing records
                self.db.flush()
                cust_admin = (
                    self.db.query(CustomerAdministrative)
                    .filter(
                        CustomerAdministrative.customer_id
                        == customer.id
                    )
                    .first()
                )
                if cust_admin:
                    cust_admin.administrative_id = value
                else:
                    new_cust_admin = CustomerAdministrative(
                        customer_id=customer.id,
                        administrative_id=value,
                    )
                    self.db.add(new_cust_admin)
                continue
            if hasattr(customer, key):
                if key in [
                    "crop_type",
                    "gender",
                ]:
                    # IMPORTANT:
                    # Create a copy to trigger SQLAlchemy's change tracking
                    profile_data = (customer.profile_data or {}).copy()
                    # Convert enum values to their string value
                    # for JSON serialization
                    if hasattr(value, 'value'):
                        profile_data[key] = value.value
                    else:
                        profile_data[key] = value
                    customer.profile_data = profile_data
                    continue
                if key == "age":
                    # Calculate birth_year from age
                    current_year = datetime.now().year
                    birth_year = None
                    # Only set birth_year if age is a valid number
                    if value and str(value).strip() != "":
                        birth_year = current_year - value
                    # IMPORTANT:
                    # Create a copy to trigger SQLAlchemy's change tracking
                    profile_data = (customer.profile_data or {}).copy()
                    profile_data["birth_year"] = birth_year
                    customer.profile_data = profile_data
                    continue
                # Handle empty strings as None for optional fields like
                # full_name
                if key == "full_name" and value == "":
                    value = None
                setattr(customer, key, value)
        # If onboarding fields are set, mark onboarding as completed
        if customer.onboarding_attempts is not None:
            customer.onboarding_attempts = None
            customer.onboarding_status = OnboardingStatus.COMPLETED

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
        profile_filters: Dict[str, List[str]] = None,
    ) -> Tuple[List[dict], int]:
        """Get paginated list of customers with optional filters.

        Args:
            page: Page number (1-indexed)
            size: Number of items per page
            search: Optional search term (searches name and phone)
            administrative_ids: Optional list of administrative IDs
                to filter by. If None or empty, no filtering applied.
            profile_filters: Optional dict of profile field filters
                (e.g., {"crop_type": ["Maize"], "gender": ["male"]})

        Returns:
            Tuple of (list of customer dicts, total count)
        """
        # Base query with eager loading of relationships
        query = self.db.query(Customer).options(
            joinedload(Customer.customer_administrative).joinedload(
                CustomerAdministrative.administrative
            ),
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

        # Apply profile filters
        if profile_filters:
            query = self._apply_profile_filters(query, profile_filters)

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
                        "path": self._build_administrative_path(admin.id),
                    }

            customer_dict = {
                "id": customer.id,
                "full_name": customer.full_name,
                "phone_number": customer.phone_number,
                "language": customer.language,
                "crop_type": customer.crop_type,
                "age_group": customer.age_group,
                "gender": customer.gender,
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

    def _apply_profile_filters(
        self, query, profile_filters: Dict[str, List[str]]
    ):
        """Apply dynamic filters to profile_data JSON column.

        Args:
            query: SQLAlchemy query object
            profile_filters: Dict of field names to lists of values
                Example: {"crop_type": ["Maize"], "gender": ["male"]}

        Returns:
            Updated query with filters applied
        """
        for field_name, field_values in profile_filters.items():
            if not isinstance(field_values, list):
                field_values = [field_values]

            if field_name == "age_group":
                query = self._filter_by_age_groups(query, field_values)
            else:
                # JSON field filter with OR logic
                # Use ->> operator to extract text value without quotes
                if len(field_values) == 1:
                    query = query.filter(
                        Customer.profile_data.op("->>")(field_name)
                        == str(field_values[0])
                    )
                else:
                    or_conditions = [
                        Customer.profile_data.op("->>")(field_name)
                        == str(value)
                        for value in field_values
                    ]
                    query = query.filter(or_(*or_conditions))

        return query

    def _filter_by_age_groups(self, query, age_groups: List[str]):
        """Filter by age groups (calculated from birth_year).

        Args:
            query: SQLAlchemy query object
            age_groups: List of age group strings
                (e.g., ["20-35", "36-50"])

        Returns:
            Updated query with age group filters applied
        """
        current_year = datetime.now().year

        age_conditions = []
        for age_group in age_groups:
            if age_group == "20-35":
                min_birth_year = current_year - 35
                max_birth_year = current_year - 20
            elif age_group == "36-50":
                min_birth_year = current_year - 50
                max_birth_year = current_year - 36
            elif age_group == "51+":
                min_birth_year = 1900
                max_birth_year = current_year - 51
            else:
                continue

            age_conditions.append(
                and_(
                    cast(
                        Customer.profile_data.op("->>")(
                            "birth_year"
                        ),
                        Integer,
                    )
                    >= min_birth_year,
                    cast(
                        Customer.profile_data.op("->>")(
                            "birth_year"
                        ),
                        Integer,
                    )
                    <= max_birth_year,
                )
            )

        if age_conditions:
            query = query.filter(or_(*age_conditions))

        return query

    def create_ticket_for_customer(
        self, customer: Customer, message_id: int
    ) -> Ticket:
        """Create a new ticket for the customer."""
        national_adm = (
            self.db.query(Administrative.id)
            .filter(Administrative.parent_id.is_(None))
            .first()
        )
        admin_id = None
        if national_adm:
            admin_id = national_adm.id
        if (
            hasattr(customer, "customer_administrative")
            and len(customer.customer_administrative) > 0
        ):
            admin_id = customer.customer_administrative[0].administrative_id
        # Skip if admin_id is still None
        if admin_id is None:
            return None
        now = datetime.now(timezone.utc)
        ticket_number = now.strftime("%Y%m%d%H%M%S")
        ticket = Ticket(
            ticket_number=ticket_number,
            administrative_id=admin_id,
            customer_id=customer.id,
            message_id=message_id,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
