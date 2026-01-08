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

    def test_onboarding_complete_profile_summary_included(
        self,
        db_session,
        test_customer: Customer,
    ):
        """Test that profile summary is included in completion message"""
        onboarding_service = OnboardingService(db_session)

        result = onboarding_service._complete_onboarding(
            customer=test_customer
        )
        # Check profile information is in the message
        assert "John Doe" in result.message
        # Age based on birth year 1990
        assert "36" in result.message
        # Should show age, not year
        assert "1990" not in result.message
        assert "cacao" in result.message

    def test_onboarding_complete_admin_user_included(
        self,
        db_session,
        test_customer: Customer,
        sample_administrative_data,
    ):
        """Test that admin users are now included in contact list"""
        onboarding_service = OnboardingService(db_session)

        ward = sample_administrative_data[0]  # Westlands Ward

        # Create admin user
        admin_user = User(
            email="admin@example.com",
            phone_number="+254700000020",
            user_type=UserType.ADMIN,
            full_name="Admin User",
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

        # Link admin to administrative area
        user_admin = UserAdministrative(
            user_id=admin_user.id,
            administrative_id=ward.id,
        )
        db_session.add(user_admin)
        db_session.commit()

        # Add administrative data to customer
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

        # Admin should be in the message
        assert "Admin User" in result.message
        assert "+254700000020" in result.message

    def test_onboarding_complete_swahili_language(
        self,
        db_session,
        test_customer: Customer,
    ):
        """Test onboarding completion message in Swahili"""
        onboarding_service = OnboardingService(db_session)

        # Update customer to use Swahili language
        test_customer.language = CustomerLanguage.SW
        test_customer.full_name = "Jane Doe"
        test_customer.phone_number = "+254700000030"
        test_customer.profile_data = {
            "crop_type": "Avocado",
            "gender": "female",
            "birth_year": 1995,
        }
        db_session.commit()
        db_session.refresh(test_customer)

        result = onboarding_service._complete_onboarding(
            customer=test_customer
        )

        # Check for Swahili translations in the message
        assert result.message is not None
        # Check for Swahili words from i18n.py
        assert "Bora!" in result.message  # "Perfect!"
        assert "profaili" in result.message.lower()  # "profile"
        assert "muhtasari" in result.message.lower()  # "summary"

    def test_onboarding_complete_with_incomplete_profile(
        self,
        db_session,
        test_customer: Customer,
    ):
        """Test onboarding completion with minimal profile data"""
        onboarding_service = OnboardingService(db_session)

        # Update customer with minimal data
        test_customer.full_name = "Minimal User"
        test_customer.phone_number = "+254700000040"
        test_customer.profile_data = {}
        db_session.commit()
        db_session.refresh(test_customer)

        result = onboarding_service._complete_onboarding(
            customer=test_customer
        )

        # Should still complete successfully
        assert result.message is not None
        assert "Minimal User" in result.message
        # Show admin contact as no EOs linked
        assert "Admin" in result.message
        assert "+1234567891" in result.message

    def test_onboarding_complete_eo_mixed_with_admin(
        self,
        db_session,
        test_customer: Customer,
        test_eo_users: list[User],
        sample_administrative_data,
    ):
        """Test that both EO and Admin users are included (up to 2 total)"""
        onboarding_service = OnboardingService(db_session)

        ward = sample_administrative_data[0]  # Westlands Ward

        # Create admin user
        admin_user = User(
            email="admin@example.com",
            phone_number="+254700000051",
            user_type=UserType.ADMIN,
            full_name="Admin User",
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

        # Link admin to administrative area
        # (EO users already linked via fixture)
        user_admin_admin = UserAdministrative(
            user_id=admin_user.id,
            administrative_id=ward.id,
        )
        db_session.add(user_admin_admin)
        db_session.commit()

        # Add administrative data to customer
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

        # Count users in the message (should be 2 total)
        user_count = 0
        if test_eo_users[0].full_name in result.message:
            user_count += 1
        if test_eo_users[1].full_name in result.message:
            user_count += 1
        if "Admin User" in result.message:
            user_count += 1

        # Should have exactly 2 users total (first 2 linked to ward)
        assert user_count == 2, (
            f"Expected 2 users in message, found {user_count}"
        )

    def test_onboarding_complete_exactly_two_eo_limit(
        self,
        db_session,
        test_customer: Customer,
        test_eo_users: list[User],
        sample_administrative_data,
    ):
        """Test that exactly 2 EO users are shown when exactly 2 exist"""
        onboarding_service = OnboardingService(db_session)

        ward = sample_administrative_data[0]  # Westlands Ward

        # Add administrative data to customer
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

        # Both EO users should be in the message
        assert test_eo_users[0].full_name in result.message
        assert test_eo_users[1].full_name in result.message
        assert test_eo_users[0].phone_number in result.message
        assert test_eo_users[1].phone_number in result.message

    def test_onboarding_complete_more_than_two_eos_only_shows_two(
        self,
        db_session,
        test_customer: Customer,
        sample_administrative_data,
    ):
        """Test that when more than 2 EOs exist, only first 2 are shown"""
        onboarding_service = OnboardingService(db_session)

        ward = sample_administrative_data[0]  # Westlands Ward

        # Create 4 EO users
        eo_users = []
        for i in range(4):
            eo_user = User(
                email=f"eo_many_{i}@example.com",
                phone_number=f"+25470000007{i}",
                user_type=UserType.EXTENSION_OFFICER,
                full_name=f"EO Many User {i}",
            )
            db_session.add(eo_user)
            db_session.commit()
            db_session.refresh(eo_user)
            eo_users.append(eo_user)

            # Link to administrative area
            user_admin = UserAdministrative(
                user_id=eo_user.id,
                administrative_id=ward.id,
            )
            db_session.add(user_admin)

        db_session.commit()

        # Add administrative data to customer
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

        # Count how many EO users are in the message
        eo_count = sum(
            1 for eo_user in eo_users if eo_user.full_name in result.message
        )

        # Should be exactly 2
        assert eo_count == 2, f"Expected exactly 2 EO users, found {eo_count}"

        # At least 2 phone numbers should be present
        phone_count = sum(
            1
            for eo_user in eo_users
            if eo_user.phone_number in result.message
        )
        assert phone_count == 2, (
            f"Expected 2 phone numbers, found {phone_count}"
        )
