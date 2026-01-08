import pytest
from models.customer import (
    Customer,
    CustomerLanguage,
    OnboardingStatus,
)
from models.administrative import (
    AdministrativeLevel,
    Administrative,
    CustomerAdministrative,
    UserAdministrative,
)
from models.user import User, UserType
from services.onboarding_service import OnboardingService


class TestOnboardingComplete:
    @pytest.fixture
    def sample_administrative_data(self, db_session):
        """Create sample administrative hierarchy"""
        # Create levels
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        district_level = AdministrativeLevel(name="district")
        ward_level = AdministrativeLevel(name="ward")
        db_session.add_all(
            [country_level, region_level, district_level, ward_level]
        )
        db_session.commit()

        # Create hierarchy
        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="Kenya",
        )
        db_session.add(kenya)
        db_session.commit()

        nairobi = Administrative(
            code="NBI",
            name="Nairobi Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="Kenya > Nairobi Region",
        )
        db_session.add(nairobi)
        db_session.commit()

        central = Administrative(
            code="NRB-C",
            name="Central District",
            level_id=district_level.id,
            parent_id=nairobi.id,
            path="Kenya > Nairobi Region > Central District",
        )
        db_session.add(central)
        db_session.commit()

        westlands = Administrative(
            code="NRB-C-1",
            name="Westlands Ward",
            level_id=ward_level.id,
            parent_id=central.id,
            path="Kenya > Nairobi Region > Central District > Westlands Ward",
        )
        db_session.add(westlands)
        db_session.commit()

        kibera = Administrative(
            code="NRB-C-2",
            name="Kibera Ward",
            level_id=ward_level.id,
            parent_id=central.id,
            path="Kenya > Nairobi Region > Central District > Kibera Ward",
        )
        db_session.add(kibera)
        db_session.commit()

        return [westlands, kibera]

    @pytest.fixture
    def test_customer(self, db_session) -> Customer:
        """Create a test customer"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            profile_data={
                "crop_type": "Cacao",
                "gender": "male",
                "birth_year": 1990,
            },
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        return customer

    @pytest.fixture
    def test_eo_users(
        self,
        db_session,
        sample_administrative_data,
    ) -> list[User]:
        """Create test EO users"""
        ward = sample_administrative_data[0]  # Westlands Ward
        eo_user1 = User(
            email="eo_user1@example.com",
            phone_number="+254700000002",
            user_type=UserType.EXTENSION_OFFICER,
            full_name="EO User 1",
        )
        db_session.add(eo_user1)
        db_session.commit()
        db_session.refresh(eo_user1)

        eo_user2 = User(
            email="eo_user2@example.com",
            phone_number="+254700000003",
            user_type=UserType.EXTENSION_OFFICER,
            full_name="EO User 2",
        )
        db_session.add(eo_user2)
        db_session.commit()
        db_session.refresh(eo_user2)

        # Link EO users to administrative area
        user_admin1 = UserAdministrative(
            user_id=eo_user1.id,
            administrative_id=ward.id,
        )
        user_admin2 = UserAdministrative(
            user_id=eo_user2.id,
            administrative_id=ward.id,
        )
        db_session.add_all([user_admin1, user_admin2])
        db_session.commit()

        return [eo_user1, eo_user2]

    def test_onboarding_complete_with_valid_users(
        self,
        db_session,
        test_customer: Customer,
        test_eo_users: list[User],
        sample_administrative_data,
    ):
        """Test onboarding completion when users are available"""
        onboarding_service = OnboardingService(db_session)

        # Add administrative data to customer
        ward = sample_administrative_data[0]  # Westlands Ward
        customer_admin = CustomerAdministrative(
            customer_id=test_customer.id,
            administrative_id=ward.id,
        )
        db_session.add(customer_admin)
        db_session.commit()
        db_session.refresh(test_customer)

        result = onboarding_service._complete_onboarding(
            customer=test_customer
        )
        assert test_eo_users[0].full_name in result.message
        assert test_eo_users[1].full_name in result.message

    def test_onboarding_complete_with_no_users(
        self,
        db_session,
        test_customer: Customer,
        test_eo_users: list[User],
        sample_administrative_data,
    ):
        """Test onboarding completion when no valid users are found"""
        onboarding_service = OnboardingService(db_session)

        # Add administrative data to customer
        ward = sample_administrative_data[1]  # Kibera Ward
        customer_admin = CustomerAdministrative(
            customer_id=test_customer.id,
            administrative_id=ward.id,
        )
        db_session.add(customer_admin)
        db_session.commit()
        db_session.refresh(test_customer)

        result = onboarding_service._complete_onboarding(
            customer=test_customer
        )
        # default contact name from config
        assert "Admin" in result.message
        # default contact number from config
        assert "+1234567891" in result.message
        assert test_eo_users[0].full_name not in result.message
        assert test_eo_users[1].full_name not in result.message

    def test_onboarding_complete_no_customer_administrative(
        self,
        db_session,
        test_customer: Customer,
    ):
        """
        Test onboarding completion when customer has no administrative data
        """
        onboarding_service = OnboardingService(db_session)

        result = onboarding_service._complete_onboarding(
            customer=test_customer
        )
        # default contact name from config
        assert "Admin" in result.message
        # default contact number from config
        assert "+1234567891" in result.message
