import pytest

from models import (
    Administrative,
    AdministrativeLevel,
    Customer,
    CustomerAdministrative,
)
from models.customer import CustomerLanguage


class TestCustomersEndpoint:
    """Test cases for customers list endpoint"""

    @pytest.fixture
    def setup_administrative_hierarchy(self, db_session):
        """Create a basic administrative hierarchy for testing"""
        # Create administrative levels
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        district_level = AdministrativeLevel(name="district")
        ward_level = AdministrativeLevel(name="ward")

        db_session.add_all(
            [country_level, region_level, district_level, ward_level]
        )
        db_session.commit()

        # Create administrative areas
        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        db_session.add(kenya)
        db_session.commit()

        # Nairobi Region
        nairobi = Administrative(
            code="NRB",
            name="Nairobi",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="KEN.NRB",
        )
        db_session.add(nairobi)
        db_session.commit()

        # Nairobi District
        nairobi_district = Administrative(
            code="ND1",
            name="Nairobi District",
            level_id=district_level.id,
            parent_id=nairobi.id,
            path="KEN.NRB.ND1",
        )
        db_session.add(nairobi_district)
        db_session.commit()

        # Wards
        ward1 = Administrative(
            code="W01",
            name="Ward 1",
            level_id=ward_level.id,
            parent_id=nairobi_district.id,
            path="KEN.NRB.ND1.W01",
        )
        ward2 = Administrative(
            code="W02",
            name="Ward 2",
            level_id=ward_level.id,
            parent_id=nairobi_district.id,
            path="KEN.NRB.ND1.W02",
        )
        db_session.add_all([ward1, ward2])
        db_session.commit()

        return {
            "kenya": kenya,
            "nairobi": nairobi,
            "nairobi_district": nairobi_district,
            "ward1": ward1,
            "ward2": ward2,
        }

    @pytest.fixture
    def setup_customers(self, db_session, setup_administrative_hierarchy):

        """Create test customers with various attributes"""
        wards = setup_administrative_hierarchy
        # Customer in Ward 1 with Rice
        customer1 = Customer(
            phone_number="+254700000001",
            full_name="John Doe",
            language=CustomerLanguage.EN,
            crop_type="Rice",
            birth_year=1990,
        )
        db_session.add(customer1)
        db_session.commit()

        customer_admin1 = CustomerAdministrative(
            customer_id=customer1.id, administrative_id=wards["ward1"].id
        )
        db_session.add(customer_admin1)

        # Customer in Ward 1 with Coffee
        customer2 = Customer(
            phone_number="+254700000002",
            full_name="Jane Smith",
            language=CustomerLanguage.SW,
            crop_type="Coffee",
            birth_year=1986,
        )
        db_session.add(customer2)
        db_session.commit()

        customer_admin2 = CustomerAdministrative(
            customer_id=customer2.id, administrative_id=wards["ward1"].id
        )
        db_session.add(customer_admin2)

        # Customer in Ward 2 with Chilli
        customer3 = Customer(
            phone_number="+254700000003",
            full_name="Peter Brown",
            language=CustomerLanguage.EN,
            crop_type="Chilli",
            birth_year=1970,
        )
        db_session.add(customer3)
        db_session.commit()

        customer_admin3 = CustomerAdministrative(
            customer_id=customer3.id, administrative_id=wards["ward2"].id
        )
        db_session.add(customer_admin3)

        # Customer in Ward 2 with no crop type
        customer4 = Customer(
            phone_number="+254700000004",
            full_name="Mary Johnson",
            language=CustomerLanguage.SW,
        )
        db_session.add(customer4)
        db_session.commit()

        customer_admin4 = CustomerAdministrative(
            customer_id=customer4.id, administrative_id=wards["ward2"].id
        )
        db_session.add(customer_admin4)

        db_session.commit()

        return {
            "customer1": customer1,
            "customer2": customer2,
            "customer3": customer3,
            "customer4": customer4,
        }

    def test_admin_can_see_all_customers(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test that admin users can see all customers"""
        headers, _ = auth_headers_factory(user_type="admin")

        response = client.get("/api/customers/list", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert len(data["customers"]) == 4
        assert data["page"] == 1
        assert data["size"] == 10

    def test_eo_sees_only_assigned_ward_customers(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that EO users only see customers in their assigned wards"""
        wards = setup_administrative_hierarchy

        # Create EO assigned to Ward 1
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo1@example.com",
            administrative_ids=[wards["ward1"].id],
        )

        response = client.get("/api/customers/list", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # Only 2 customers in Ward 1
        assert data["total"] == 2
        assert len(data["customers"]) == 2

        # Verify customers are from Ward 1
        for customer in data["customers"]:
            assert customer["administrative"]["id"] == wards["ward1"].id
            assert customer["administrative"]["name"] == "Ward 1"

    def test_eo_with_multiple_wards(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that EO can see customers from multiple assigned wards"""
        wards = setup_administrative_hierarchy

        # Create EO assigned to both Ward 1 and Ward 2
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo2@example.com",
            administrative_ids=[wards["ward1"].id, wards["ward2"].id],
        )

        response = client.get("/api/customers/list", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # All 4 customers across both wards
        assert data["total"] == 4
        assert len(data["customers"]) == 4

    def test_eo_with_no_ward_assignment(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test that EO with no ward assignment sees no customers"""
        # Create EO without administrative assignment
        headers, _ = auth_headers_factory(
            user_type="eo", email="eo3@example.com", administrative_ids=[]
        )

        response = client.get("/api/customers/list", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["customers"]) == 0

    def test_pagination(self, client, auth_headers_factory, setup_customers):
        """Test pagination functionality"""
        headers, _ = auth_headers_factory(user_type="admin")

        # Page 1, size 2
        response = client.get(
            "/api/customers/list?page=1&size=2", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert len(data["customers"]) == 2
        assert data["page"] == 1
        assert data["size"] == 2

        # Page 2, size 2
        response = client.get(
            "/api/customers/list?page=2&size=2", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert len(data["customers"]) == 2
        assert data["page"] == 2
        assert data["size"] == 2

    def test_search_by_name(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test search by customer name"""
        headers, _ = auth_headers_factory(user_type="admin")

        response = client.get(
            "/api/customers/list?search=John", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # John Doe and Mary Johnson
        assert len(data["customers"]) == 2

        # Verify search results
        names = [c["full_name"] for c in data["customers"]]
        assert "John Doe" in names
        assert "Mary Johnson" in names

    def test_search_by_phone(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test search by phone number"""
        headers, _ = auth_headers_factory(user_type="admin")

        response = client.get(
            "/api/customers/list?search=254700000001", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["customers"][0]["phone_number"] == "+254700000001"
        assert data["customers"][0]["full_name"] == "John Doe"

    def test_filter_by_crop_type(
        self, client, auth_headers_factory, setup_customers, db_session
    ):
        """Test filtering by single crop type"""
        headers, _ = auth_headers_factory(user_type="admin")

        ct = "Rice"
        response = client.get(
            f"/api/customers/list?crop_types={ct}",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["customers"][0]["crop_type"] == "Rice"
        assert data["customers"][0]["full_name"] == "John Doe"

    def test_filter_by_multiple_crop_types(
        self, client, auth_headers_factory, setup_customers, db_session
    ):
        """Test filtering by multiple crop types"""
        headers, _ = auth_headers_factory(user_type="admin")

        ct1 = "Rice"
        ct2 = "Coffee"
        response = client.get(
            f"/api/customers/list?crop_types={ct1}&crop_types={ct2}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        crop_types = [c["crop_type"] for c in data["customers"]]
        assert "Rice" in crop_types
        assert "Coffee" in crop_types

    def test_filter_by_age_group(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test filtering by age group"""
        headers, _ = auth_headers_factory(user_type="admin")

        response = client.get(
            "/api/customers/list?age_groups=36-50", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["customers"][0]["age_group"] == "36-50"
        assert data["customers"][0]["full_name"] == "Jane Smith"
        assert data["customers"][0]["age_group"] is not None

    def test_filter_by_multiple_age_groups(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test filtering by multiple age groups"""
        headers, _ = auth_headers_factory(user_type="admin")

        response = client.get(
            "/api/customers/list?age_groups=20-35&age_groups=51%2B",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        age_groups = [c["age_group"] for c in data["customers"]]
        assert "20-35" in age_groups
        assert "51+" in age_groups

    def test_combined_filters(
        self, client, auth_headers_factory, setup_customers, db_session
    ):
        """Test combining search with crop type filter"""
        headers, _ = auth_headers_factory(user_type="admin")

        ct = "Rice"
        response = client.get(
            f"/api/customers/list?search=John&crop_types={ct}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["customers"][0]["full_name"] == "John Doe"
        assert data["customers"][0]["crop_type"] == "Rice"

    def test_eo_filters_with_ward_restriction(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session
    ):
        """Test that EO filters only apply to their assigned wards"""
        wards = setup_administrative_hierarchy

        # EO assigned to Ward 1 (has Rice and Coffee)
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo4@example.com",
            administrative_ids=[wards["ward1"].id],
        )

        # Filter by Chilli (which only exists in Ward 2)
        ct = "Chilli"
        response = client.get(
            f"/api/customers/list?crop_types={ct}", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        # Should return 0 because Chilli is in Ward 2, not Ward 1
        assert data["total"] == 0

        # Filter by Rice (exists in Ward 1)
        ct = "Rice"
        response = client.get(
            f"/api/customers/list?crop_types={ct}", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["customers"][0]["crop_type"] == "Rice"

    def test_customer_response_structure(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test that customer response has all required fields"""
        headers, _ = auth_headers_factory(user_type="admin")

        response = client.get("/api/customers/list?size=1", headers=headers)

        assert response.status_code == 200
        data = response.json()
        customer = data["customers"][0]

        # Verify all required fields are present
        assert "id" in customer
        assert "full_name" in customer
        assert "phone_number" in customer
        assert "language" in customer
        assert "crop_type" in customer
        assert "age_group" in customer
        assert "administrative" in customer

        # Verify administrative structure
        admin = customer["administrative"]
        assert "id" in admin
        assert "name" in admin
        assert "path" in admin

        # Verify path format (should be "Nairobi - Nairobi District - Ward X")
        if admin["path"]:
            assert " - " in admin["path"]
            assert "Kenya" not in admin["path"]  # Country level excluded

    def test_empty_result_set(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test response when no customers match filters"""
        headers, _ = auth_headers_factory(user_type="admin")

        response = client.get(
            "/api/customers/list?search=NonExistent", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["customers"]) == 0
        assert data["page"] == 1
        assert data["size"] == 10

    def test_invalid_page_number(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test validation of page parameter"""
        headers, _ = auth_headers_factory(user_type="admin")

        # Page 0 should fail validation
        response = client.get("/api/customers/list?page=0", headers=headers)
        assert response.status_code == 422

        # Negative page should fail validation
        response = client.get("/api/customers/list?page=-1", headers=headers)
        assert response.status_code == 422

    def test_invalid_page_size(
        self, client, auth_headers_factory, setup_customers
    ):
        """Test validation of size parameter"""
        headers, _ = auth_headers_factory(user_type="admin")

        # Size 0 should fail validation
        response = client.get("/api/customers/list?size=0", headers=headers)
        assert response.status_code == 422

        # Size > 100 should fail validation
        response = client.get("/api/customers/list?size=101", headers=headers)
        assert response.status_code == 422

    def test_unauthenticated_request(self, client, setup_customers):
        """Test that unauthenticated requests are rejected"""
        response = client.get("/api/customers/list")
        # Should return 403 (Forbidden) or 401 (Unauthorized)
        assert response.status_code in [401, 403]

    def test_admin_filter_by_multiple_wards(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that admin can filter by multiple wards"""
        wards = setup_administrative_hierarchy
        headers, _ = auth_headers_factory(user_type="admin")

        # Filter by both Ward 1 and Ward 2
        response = client.get(
            f"/api/customers/list?administrative_ids={wards['ward1'].id}"
            f"&administrative_ids={wards['ward2'].id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4  # All 4 customers (2 from each ward)

        # Verify customers are from either Ward 1 or Ward 2
        ward_ids = {
            customer["administrative"]["id"] for customer in data["customers"]
        }
        assert ward_ids == {wards["ward1"].id, wards["ward2"].id}

    def test_admin_filter_multiple_wards_with_search(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test admin can combine multiple ward filter with search"""
        wards = setup_administrative_hierarchy
        headers, _ = auth_headers_factory(user_type="admin")

        # Filter by Ward 1 and Ward 2, search for "John" in name
        response = client.get(
            f"/api/customers/list?administrative_ids={wards['ward1'].id}"
            f"&administrative_ids={wards['ward2'].id}&search=John",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Should find John Doe (Ward 1) and Mary Johnson (Ward 2)
        assert data["total"] == 2

        names = [c["full_name"] for c in data["customers"]]
        assert "John Doe" in names
        assert "Mary Johnson" in names

    def test_admin_filter_multiple_wards_with_crop_type(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session
    ):
        """Test admin can combine multiple ward filter with crop type"""
        wards = setup_administrative_hierarchy
        headers, _ = auth_headers_factory(user_type="admin")

        # Filter by Ward 1 and Ward 2, crop type = Chilli (only in Ward 2)
        ct = "Chilli"
        response = client.get(
            f"/api/customers/list?administrative_ids={wards['ward1'].id}"
            f"&administrative_ids={wards['ward2'].id}&crop_types={ct}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["customers"][0]["full_name"] == "Peter Brown"
        assert data["customers"][0]["crop_type"] == "Chilli"
        assert (
            data["customers"][0]["administrative"]["id"] == wards["ward2"].id
        )
