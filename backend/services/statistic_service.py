"""
Service layer for Statistics API.

Provides business logic and database queries for farmer and EO statistics.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
    UserAdministrative,
)
from models.broadcast import BroadcastMessage
from models.customer import Customer, OnboardingStatus
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.user import User, UserType
from services.administrative_service import AdministrativeService


class StatisticService:
    """Service for computing statistics."""

    def __init__(self, db: Session):
        self.db = db

    def _apply_date_filter(
        self,
        query,
        date_column,
        start_date: Optional[str],
        end_date: Optional[str],
    ):
        """Apply date range filters to a query."""
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(date_column >= start_dt)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(date_column <= end_dt)
            except ValueError:
                pass
        return query

    def _apply_phone_prefix_filter(
        self,
        query,
        phone_prefix: Optional[str],
    ):
        """Apply phone number prefix filter to a query."""
        if phone_prefix:
            query = query.filter(
                Customer.phone_number.like(f"{phone_prefix}%")
            )
        return query

    def _get_administrative_customer_ids(
        self, administrative_id: int
    ) -> List[int]:
        """
        Get all customer IDs in a specific administrative area.

        Supports any administrative level (Region, District, Ward).
        For higher levels, aggregates customers from all descendant wards.
        """
        # Get all ward IDs under this administrative area
        ward_ids = AdministrativeService.get_descendant_ward_ids(
            self.db, administrative_id
        )

        if not ward_ids:
            # If no descendant wards found, maybe it's directly assigned
            ward_ids = [administrative_id]

        return [
            ca.customer_id
            for ca in self.db.query(CustomerAdministrative)
            .filter(CustomerAdministrative.administrative_id.in_(ward_ids))
            .all()
        ]

    def _get_administrative_ward_ids(
        self, administrative_id: int
    ) -> List[int]:
        """
        Get all ward IDs under an administrative area.

        Returns descendant ward IDs for filtering by-ward results.
        """
        return AdministrativeService.get_descendant_ward_ids(
            self.db, administrative_id
        )

    def _get_base_customer_query(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        administrative_id: Optional[int] = None,
        phone_prefix: Optional[str] = None,
        crop_type: Optional[str] = None,
    ):
        """Build base customer query with common filters."""
        query = self.db.query(Customer)

        # Date filter on customer creation
        query = self._apply_date_filter(
            query, Customer.created_at, start_date, end_date
        )

        # Phone prefix filter
        query = self._apply_phone_prefix_filter(query, phone_prefix)

        # Administrative area filter (supports any level)
        if administrative_id:
            customer_ids = self._get_administrative_customer_ids(
                administrative_id
            )
            query = query.filter(Customer.id.in_(customer_ids))

        # Crop type filter
        if crop_type:
            query = query.filter(
                Customer.profile_data.op("->>")("crop_type") == crop_type
            )

        return query

    def get_farmer_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        administrative_id: Optional[int] = None,
        phone_prefix: Optional[str] = None,
        crop_type: Optional[str] = None,
        active_days: int = 30,
    ) -> dict:
        """
        Get comprehensive farmer statistics.

        Args:
            start_date: Filter customers created on or after this date
            end_date: Filter customers created on or before this date
            administrative_id: Filter by administrative area (any level).
                              Aggregates data from all descendant wards.
            phone_prefix: Filter by phone number prefix (e.g., "+254")
            crop_type: Filter by crop type (e.g., "maize", "coffee")
            active_days: Days to consider a farmer as "active"

        Returns:
            Dict with onboarding, activity, features, escalation stats
        """
        base_query = self._get_base_customer_query(
            start_date, end_date, administrative_id, phone_prefix, crop_type
        )

        # Build customer_ids list for subqueries
        customer_ids = [c.id for c in base_query.all()]

        # Onboarding stats
        onboarding_started = (
            self.db.query(func.count(Customer.id))
            .filter(
                Customer.id.in_(customer_ids),
                Customer.onboarding_status != OnboardingStatus.NOT_STARTED,
            )
            .scalar()
            or 0
        )

        onboarding_completed = (
            self.db.query(func.count(Customer.id))
            .filter(
                Customer.id.in_(customer_ids),
                Customer.onboarding_status == OnboardingStatus.COMPLETED,
            )
            .scalar()
            or 0
        )

        completion_rate = (
            onboarding_completed / onboarding_started
            if onboarding_started > 0
            else 0.0
        )

        # Activity stats
        active_threshold = datetime.utcnow() - timedelta(days=active_days)

        # Get completed farmers in the filtered set
        completed_farmer_ids = [
            c.id
            for c in self.db.query(Customer)
            .filter(
                Customer.id.in_(customer_ids),
                Customer.onboarding_status == OnboardingStatus.COMPLETED,
            )
            .all()
        ]

        # Active farmers: completed onboarding and sent a message recently
        active_farmers = (
            self.db.query(func.count(distinct(Message.customer_id)))
            .filter(
                Message.customer_id.in_(completed_farmer_ids),
                Message.from_source == MessageFrom.CUSTOMER,
                Message.created_at >= active_threshold,
            )
            .scalar()
            or 0
        )

        dormant_farmers = len(completed_farmer_ids) - active_farmers

        active_rate = (
            active_farmers / len(completed_farmer_ids)
            if len(completed_farmer_ids) > 0
            else 0.0
        )

        # Average days to first question
        first_messages = (
            self.db.query(
                Message.customer_id,
                func.min(Message.created_at).label("first_message_at"),
            )
            .filter(
                Message.customer_id.in_(customer_ids),
                Message.from_source == MessageFrom.CUSTOMER,
            )
            .group_by(Message.customer_id)
            .subquery()
        )

        avg_days_result = (
            self.db.query(
                func.avg(
                    func.extract(
                        "epoch",
                        first_messages.c.first_message_at - Customer.created_at
                    ) / 86400  # Convert seconds to days
                )
            )
            .join(
                first_messages,
                Customer.id == first_messages.c.customer_id
            )
            .filter(Customer.id.in_(customer_ids))
            .scalar()
        )
        avg_days_to_first_question = (
            round(float(avg_days_result), 2) if avg_days_result else None
        )

        # Average questions per farmer
        total_questions = (
            self.db.query(func.count(Message.id))
            .filter(
                Message.customer_id.in_(customer_ids),
                Message.from_source == MessageFrom.CUSTOMER,
            )
            .scalar()
            or 0
        )

        farmers_with_questions = (
            self.db.query(func.count(distinct(Message.customer_id)))
            .filter(
                Message.customer_id.in_(customer_ids),
                Message.from_source == MessageFrom.CUSTOMER,
            )
            .scalar()
            or 0
        )

        avg_questions_per_farmer = (
            round(total_questions / farmers_with_questions, 2)
            if farmers_with_questions > 0
            else None
        )

        # Weather subscribers (filter in Python since it's a JSON field)
        weather_subscribers = 0
        for customer in base_query.all():
            if customer.weather_subscribed is True:
                weather_subscribers += 1

        # Escalation stats (tickets)
        total_escalated = (
            self.db.query(func.count(Ticket.id))
            .filter(Ticket.customer_id.in_(customer_ids))
            .scalar()
            or 0
        )

        farmers_who_escalated = (
            self.db.query(func.count(distinct(Ticket.customer_id)))
            .filter(Ticket.customer_id.in_(customer_ids))
            .scalar()
            or 0
        )

        return {
            "onboarding": {
                "started": onboarding_started,
                "completed": onboarding_completed,
                "completion_rate": round(completion_rate, 2),
            },
            "activity": {
                "active_farmers": active_farmers,
                "dormant_farmers": dormant_farmers,
                "active_rate": round(active_rate, 2),
                "total_questions": total_questions,
                "avg_days_to_first_question": avg_days_to_first_question,
                "avg_questions_per_farmer": avg_questions_per_farmer,
            },
            "features": {
                "weather_subscribers": weather_subscribers,
            },
            "escalations": {
                "total_escalated": total_escalated,
                "farmers_who_escalated": farmers_who_escalated,
            },
        }

    def get_farmer_stats_by_ward(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        phone_prefix: Optional[str] = None,
        crop_type: Optional[str] = None,
        administrative_id: Optional[int] = None,
    ) -> List[dict]:
        """
        Get farmer statistics grouped by ward.

        Args:
            start_date: Filter customers created on or after this date
            end_date: Filter customers created on or before this date
            phone_prefix: Filter by phone number prefix
            crop_type: Filter by crop type (e.g., "maize", "coffee")
            administrative_id: Filter to wards under this administrative area.
                              If Region/District, shows stats for all wards
                              under that area.

        Returns:
            List of ward statistics dictionaries
        """
        # Get all wards (level_id = 4 for ward level)
        ward_level = (
            self.db.query(AdministrativeLevel)
            .filter(AdministrativeLevel.name == "Ward")
            .first()
        )

        if not ward_level:
            return []

        # If administrative_id is provided, filter to wards under that area
        if administrative_id:
            ward_ids = self._get_administrative_ward_ids(administrative_id)
            wards = (
                self.db.query(Administrative)
                .filter(
                    Administrative.level_id == ward_level.id,
                    Administrative.id.in_(ward_ids)
                )
                .all()
            )
        else:
            wards = (
                self.db.query(Administrative)
                .filter(Administrative.level_id == ward_level.id)
                .all()
            )

        results = []

        for ward in wards:
            # Get customer IDs in this ward
            customer_admin_query = (
                self.db.query(CustomerAdministrative.customer_id)
                .filter(CustomerAdministrative.administrative_id == ward.id)
            )

            # Apply filters
            base_customer_query = self.db.query(Customer.id).filter(
                Customer.id.in_(customer_admin_query)
            )

            base_customer_query = self._apply_date_filter(
                base_customer_query, Customer.created_at, start_date, end_date
            )

            if phone_prefix:
                base_customer_query = self._apply_phone_prefix_filter(
                    base_customer_query, phone_prefix
                )

            if crop_type:
                base_customer_query = base_customer_query.filter(
                    Customer.profile_data.op("->>")("crop_type") == crop_type
                )

            customer_ids = [c.id for c in base_customer_query.all()]

            if not customer_ids:
                continue

            # Registered farmers (completed onboarding)
            registered_farmers = (
                self.db.query(func.count(Customer.id))
                .filter(
                    Customer.id.in_(customer_ids),
                    Customer.onboarding_status == OnboardingStatus.COMPLETED,
                )
                .scalar()
                or 0
            )

            # Incomplete registration
            incomplete_registration = (
                self.db.query(func.count(Customer.id))
                .filter(
                    Customer.id.in_(customer_ids),
                    Customer.onboarding_status.in_([
                        OnboardingStatus.IN_PROGRESS,
                        OnboardingStatus.FAILED,
                    ]),
                )
                .scalar()
                or 0
            )

            # Farmers with questions
            farmers_with_questions = (
                self.db.query(func.count(distinct(Message.customer_id)))
                .filter(
                    Message.customer_id.in_(customer_ids),
                    Message.from_source == MessageFrom.CUSTOMER,
                )
                .scalar()
                or 0
            )

            # Total questions
            total_questions = (
                self.db.query(func.count(Message.id))
                .filter(
                    Message.customer_id.in_(customer_ids),
                    Message.from_source == MessageFrom.CUSTOMER,
                )
                .scalar()
                or 0
            )

            # Farmers who escalated
            farmers_who_escalated = (
                self.db.query(func.count(distinct(Ticket.customer_id)))
                .filter(Ticket.customer_id.in_(customer_ids))
                .scalar()
                or 0
            )

            # Total escalations
            total_escalations = (
                self.db.query(func.count(Ticket.id))
                .filter(Ticket.customer_id.in_(customer_ids))
                .scalar()
                or 0
            )

            results.append({
                "ward_id": ward.id,
                "ward_name": ward.name,
                "ward_path": ward.path,
                "registered_farmers": registered_farmers,
                "incomplete_registration": incomplete_registration,
                "farmers_with_questions": farmers_with_questions,
                "total_questions": total_questions,
                "farmers_who_escalated": farmers_who_escalated,
                "total_escalations": total_escalations,
            })

        return results

    def get_registration_chart_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        administrative_id: Optional[int] = None,
        phone_prefix: Optional[str] = None,
        crop_type: Optional[str] = None,
        group_by: str = "day",
    ) -> Tuple[List[dict], int]:
        """
        Get registration data for charting.

        Args:
            start_date: Filter customers created on or after this date
            end_date: Filter customers created on or before this date
            administrative_id: Filter by administrative area (any level).
                              Aggregates data from all descendant wards.
            phone_prefix: Filter by phone number prefix
            crop_type: Filter by crop type (e.g., "maize", "coffee")
            group_by: "day", "week", or "month"

        Returns:
            Tuple of (data points, total count)
        """
        # Build date truncation based on group_by
        if group_by == "month":
            date_trunc = func.date_trunc("month", Customer.created_at)
        elif group_by == "week":
            date_trunc = func.date_trunc("week", Customer.created_at)
        else:  # day
            date_trunc = func.date_trunc("day", Customer.created_at)

        # Base query
        query = self.db.query(
            date_trunc.label("date"),
            func.count(Customer.id).label("count"),
        )

        # Apply filters
        query = self._apply_date_filter(
            query, Customer.created_at, start_date, end_date
        )

        if phone_prefix:
            query = query.filter(
                Customer.phone_number.like(f"{phone_prefix}%")
            )

        if administrative_id:
            customer_ids = self._get_administrative_customer_ids(
                administrative_id
            )
            query = query.filter(Customer.id.in_(customer_ids))

        if crop_type:
            query = query.filter(
                Customer.profile_data.op("->>")("crop_type") == crop_type
            )

        # Group and order
        query = query.group_by(date_trunc).order_by(date_trunc)

        results = query.all()

        data = []
        total = 0
        for row in results:
            date_str = row.date.strftime("%Y-%m-%d") if row.date else None
            count = row.count or 0
            total += count
            data.append({
                "date": date_str,
                "count": count,
            })

        return data, total

    def get_eo_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        eo_id: Optional[int] = None,
        administrative_id: Optional[int] = None,
    ) -> dict:
        """
        Get EO statistics.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date
            eo_id: Filter by specific EO
            administrative_id: Filter by administrative area (any level).
                              Filters tickets by customers in that area.

        Returns:
            Dictionary with ticket and message stats
        """
        # Get customer IDs if filtering by administrative area
        customer_ids = None
        if administrative_id:
            customer_ids = self._get_administrative_customer_ids(
                administrative_id
            )

        # Open tickets
        open_tickets_query = (
            self.db.query(func.count(Ticket.id))
            .filter(Ticket.resolved_at.is_(None))
        )
        if customer_ids is not None:
            open_tickets_query = open_tickets_query.filter(
                Ticket.customer_id.in_(customer_ids)
            )
        open_tickets = open_tickets_query.scalar() or 0

        # Closed tickets with date filters
        closed_query = self.db.query(func.count(Ticket.id)).filter(
            Ticket.resolved_at.isnot(None)
        )

        if eo_id:
            closed_query = closed_query.filter(Ticket.resolved_by == eo_id)

        if customer_ids is not None:
            closed_query = closed_query.filter(
                Ticket.customer_id.in_(customer_ids)
            )

        closed_query = self._apply_date_filter(
            closed_query, Ticket.resolved_at, start_date, end_date
        )

        closed_tickets = closed_query.scalar() or 0

        # Average response time (in hours)
        response_time_query = self.db.query(
            func.avg(
                func.extract(
                    "epoch",
                    Ticket.resolved_at - Ticket.created_at
                ) / 3600  # Convert to hours
            )
        ).filter(Ticket.resolved_at.isnot(None))

        if eo_id:
            response_time_query = response_time_query.filter(
                Ticket.resolved_by == eo_id
            )

        if customer_ids is not None:
            response_time_query = response_time_query.filter(
                Ticket.customer_id.in_(customer_ids)
            )

        response_time_query = self._apply_date_filter(
            response_time_query, Ticket.resolved_at, start_date, end_date
        )

        avg_response_time = response_time_query.scalar()
        avg_response_time_hours = (
            round(float(avg_response_time), 2) if avg_response_time else None
        )

        # Bulk messages sent
        bulk_query = self.db.query(func.count(BroadcastMessage.id))

        if eo_id:
            bulk_query = bulk_query.filter(
                BroadcastMessage.created_by == eo_id
            )

        bulk_query = self._apply_date_filter(
            bulk_query, BroadcastMessage.created_at, start_date, end_date
        )

        bulk_messages_sent = bulk_query.scalar() or 0

        return {
            "tickets": {
                "open": open_tickets,
                "closed": closed_tickets,
                "avg_response_time_hours": avg_response_time_hours,
            },
            "messages": {
                "bulk_messages_sent": bulk_messages_sent,
            },
        }

    def get_eo_stats_by_eo(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        administrative_id: Optional[int] = None,
    ) -> List[dict]:
        """
        Get EO statistics grouped by individual EO.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date
            administrative_id: Filter to EOs assigned to this area or
                              its descendants.

        Returns:
            List of EO statistics dictionaries
        """
        # Get all EOs
        eos_query = (
            self.db.query(User)
            .filter(User.user_type == UserType.EXTENSION_OFFICER)
            .filter(User.is_active == True)  # noqa: E712
        )

        # Filter EOs by administrative area
        if administrative_id:
            # Get all administrative areas under this one (including itself)
            ward_ids = self._get_administrative_ward_ids(administrative_id)
            area_ids = ward_ids + [administrative_id]

            # Get EO IDs assigned to these areas
            eo_ids_in_area = [
                ua.user_id
                for ua in self.db.query(UserAdministrative)
                .filter(UserAdministrative.administrative_id.in_(area_ids))
                .all()
            ]
            eos_query = eos_query.filter(User.id.in_(eo_ids_in_area))

        eos = eos_query.all()

        results = []

        for eo in eos:
            # Get EO's district (from administrative assignment)
            user_admin = (
                self.db.query(UserAdministrative)
                .filter(UserAdministrative.user_id == eo.id)
                .first()
            )

            district_name = None
            if user_admin:
                admin = (
                    self.db.query(Administrative)
                    .filter(Administrative.id == user_admin.administrative_id)
                    .first()
                )
                if admin:
                    # Extract district from path
                    path_parts = admin.path.split(" > ")
                    if len(path_parts) >= 3:
                        district_name = path_parts[2]  # District is 3rd level
                    else:
                        district_name = admin.name

            # Total replies from this EO
            replies_query = (
                self.db.query(func.count(Message.id))
                .filter(
                    Message.user_id == eo.id,
                    Message.from_source == MessageFrom.USER,
                )
            )

            replies_query = self._apply_date_filter(
                replies_query, Message.created_at, start_date, end_date
            )

            total_replies = replies_query.scalar() or 0

            # Tickets closed by this EO
            tickets_query = (
                self.db.query(func.count(Ticket.id))
                .filter(
                    Ticket.resolved_by == eo.id,
                    Ticket.resolved_at.isnot(None),
                )
            )

            tickets_query = self._apply_date_filter(
                tickets_query, Ticket.resolved_at, start_date, end_date
            )

            tickets_closed = tickets_query.scalar() or 0

            results.append({
                "eo_id": eo.id,
                "eo_name": eo.full_name,
                "district": district_name,
                "total_replies": total_replies,
                "tickets_closed": tickets_closed,
            })

        return results

    def get_eo_count(
        self,
        administrative_id: Optional[int] = None,
    ) -> int:
        """
        Get EO count for an administrative area.

        Args:
            administrative_id: Filter to EOs in this area and its descendants.
                              Works with any level (region, district, ward).

        Returns:
            Total count of active EOs in the area
        """
        query = (
            self.db.query(func.count(distinct(UserAdministrative.user_id)))
            .join(User)
            .filter(
                User.user_type == UserType.EXTENSION_OFFICER,
                User.is_active == True,  # noqa: E712
            )
        )

        if administrative_id:
            # Get all areas under this administrative area (including itself)
            ward_ids = self._get_administrative_ward_ids(administrative_id)
            area_ids = ward_ids + [administrative_id]

            query = query.filter(
                UserAdministrative.administrative_id.in_(area_ids)
            )

        return query.scalar() or 0

    def get_eo_list(self) -> List[dict]:
        """
        Get list of all active EOs for filter dropdown.

        Returns:
            List of EO dictionaries sorted by name
        """
        eos = (
            self.db.query(User)
            .filter(
                User.user_type == UserType.EXTENSION_OFFICER,
                User.is_active == True,  # noqa: E712
            )
            .order_by(User.full_name)
            .all()
        )

        return [
            {"id": eo.id, "name": eo.full_name}
            for eo in eos
        ]

    def _get_available_filters(
        self,
        crop_type: Optional[str] = None,
    ) -> dict:
        """
        Get available filter options that have farmer data.

        Returns dict with regions, districts, wards, and crop_types
        that have at least one farmer.
        """
        # Base query for customers with completed onboarding
        base_customer_ids = (
            self.db.query(Customer.id)
            .filter(Customer.onboarding_status == OnboardingStatus.COMPLETED)
        )

        # Apply crop_type filter if provided
        if crop_type:
            base_customer_ids = base_customer_ids.filter(
                Customer.profile_data.op("->>")("crop_type") == crop_type
            )

        customer_ids = [c.id for c in base_customer_ids.all()]

        # Get ward IDs that have farmers
        ward_ids_with_data = (
            self.db.query(distinct(CustomerAdministrative.administrative_id))
            .filter(CustomerAdministrative.customer_id.in_(customer_ids))
            .all()
        )
        ward_ids_with_data = [w[0] for w in ward_ids_with_data]

        # Get regions, districts, wards that have data
        regions = []
        districts = []
        wards = []

        # Get all wards with data
        if ward_ids_with_data:
            ward_admins = (
                self.db.query(Administrative)
                .filter(Administrative.id.in_(ward_ids_with_data))
                .all()
            )

            seen_regions = set()
            seen_districts = set()

            for ward in ward_admins:
                wards.append({"id": ward.id, "name": ward.name})

                # Extract region and district from path
                # Path format: "Country > Region > District > Ward"
                path_parts = ward.path.split(" > ")
                if len(path_parts) >= 2:
                    # Get region (second level)
                    region_name = (
                        path_parts[1] if len(path_parts) > 1 else None
                    )
                    if region_name and region_name not in seen_regions:
                        # Find region admin
                        region_admin = (
                            self.db.query(Administrative)
                            .filter(
                                Administrative.name == region_name,
                                Administrative.level.has(name="region")
                            )
                            .first()
                        )
                        if region_admin:
                            regions.append({
                                "id": region_admin.id,
                                "name": region_admin.name
                            })
                            seen_regions.add(region_name)

                if len(path_parts) >= 3:
                    # Get district (third level)
                    district_name = (
                        path_parts[2] if len(path_parts) > 2 else None
                    )
                    if district_name and district_name not in seen_districts:
                        # Find district admin
                        district_admin = (
                            self.db.query(Administrative)
                            .filter(
                                Administrative.name == district_name,
                                Administrative.level.has(name="district")
                            )
                            .first()
                        )
                        if district_admin:
                            districts.append({
                                "id": district_admin.id,
                                "name": district_admin.name
                            })
                            seen_districts.add(district_name)

        # Get unique crop types from farmers
        crop_types = []
        crop_type_col = Customer.profile_data.op("->>")("crop_type")
        crop_type_results = (
            self.db.query(distinct(crop_type_col))
            .filter(
                Customer.onboarding_status == OnboardingStatus.COMPLETED,
                crop_type_col.isnot(None),
                crop_type_col != "",
            )
            .all()
        )
        crop_types = sorted([c[0] for c in crop_type_results if c[0]])

        return {
            "regions": sorted(regions, key=lambda x: x["name"]),
            "districts": sorted(districts, key=lambda x: x["name"]),
            "wards": sorted(wards, key=lambda x: x["name"]),
            "crop_types": crop_types,
        }

    def get_farmer_aggregate(
        self,
        level: str,
        administrative_id: Optional[int] = None,
        crop_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        Get farmer data aggregated by administrative level.

        Args:
            level: "region", "district", or "ward"
            administrative_id: Filter to children of this area
            crop_type: Filter by crop type
            start_date: Filter customers created on or after this date
            end_date: Filter customers created on or before this date

        Returns:
            Dict with data, filters, and available options
        """
        # Validate level
        valid_levels = ["region", "district", "ward"]
        if level not in valid_levels:
            level = "region"

        # Get the level object
        admin_level = (
            self.db.query(AdministrativeLevel)
            .filter(AdministrativeLevel.name == level)
            .first()
        )

        if not admin_level:
            return {
                "data": [],
                "filters": {
                    "level": level,
                    "administrative_id": administrative_id,
                    "crop_type": crop_type,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "available": self._get_available_filters(crop_type),
            }

        # Get administrative areas at this level
        areas_query = (
            self.db.query(Administrative)
            .filter(Administrative.level_id == admin_level.id)
        )

        # Filter by parent administrative area
        if administrative_id:
            parent_admin = (
                self.db.query(Administrative)
                .filter(Administrative.id == administrative_id)
                .first()
            )
            if parent_admin:
                # Filter areas that are under this parent
                areas_query = areas_query.filter(
                    Administrative.path.like(f"{parent_admin.path}%")
                )

        areas = areas_query.order_by(Administrative.name).all()

        results = []

        for area in areas:
            # Get ward IDs under this area
            if level == "ward":
                ward_ids = [area.id]
            else:
                ward_ids = AdministrativeService.get_descendant_ward_ids(
                    self.db, area.id
                )
                if not ward_ids:
                    ward_ids = [area.id]

            # Get customer IDs in these wards
            customer_query = (
                self.db.query(Customer.id)
                .join(CustomerAdministrative)
                .filter(CustomerAdministrative.administrative_id.in_(ward_ids))
            )

            # Apply date filters
            customer_query = self._apply_date_filter(
                customer_query, Customer.created_at, start_date, end_date
            )

            # Apply crop_type filter
            if crop_type:
                customer_query = customer_query.filter(
                    Customer.profile_data.op("->>")("crop_type") == crop_type
                )

            customer_ids = [c.id for c in customer_query.all()]

            if not customer_ids:
                continue

            # Count farmers
            farmer_count = len(customer_ids)

            # Completed onboarding
            completed_onboarding = (
                self.db.query(func.count(Customer.id))
                .filter(
                    Customer.id.in_(customer_ids),
                    Customer.onboarding_status == OnboardingStatus.COMPLETED,
                )
                .scalar()
                or 0
            )

            # Incomplete onboarding
            incomplete_onboarding = (
                self.db.query(func.count(Customer.id))
                .filter(
                    Customer.id.in_(customer_ids),
                    Customer.onboarding_status.in_([
                        OnboardingStatus.IN_PROGRESS,
                        OnboardingStatus.FAILED,
                    ]),
                )
                .scalar()
                or 0
            )

            # Questions count
            questions_count = (
                self.db.query(func.count(Message.id))
                .filter(
                    Message.customer_id.in_(customer_ids),
                    Message.from_source == MessageFrom.CUSTOMER,
                )
                .scalar()
                or 0
            )

            # Escalations count
            escalations_count = (
                self.db.query(func.count(Ticket.id))
                .filter(Ticket.customer_id.in_(customer_ids))
                .scalar()
                or 0
            )

            # Weather subscribers
            weather_sub_filter = (
                Customer.profile_data.op("->>")("weather_subscribed") == "true"
            )
            weather_subscribers = (
                self.db.query(func.count(Customer.id))
                .filter(Customer.id.in_(customer_ids), weather_sub_filter)
                .scalar()
                or 0
            )

            results.append({
                "id": area.id,
                "name": area.name,
                "path": area.path,
                "farmer_count": farmer_count,
                "completed_onboarding": completed_onboarding,
                "incomplete_onboarding": incomplete_onboarding,
                "questions_count": questions_count,
                "escalations_count": escalations_count,
                "weather_subscribers": weather_subscribers,
            })

        return {
            "data": results,
            "filters": {
                "level": level,
                "administrative_id": administrative_id,
                "crop_type": crop_type,
                "start_date": start_date,
                "end_date": end_date,
            },
            "available": self._get_available_filters(crop_type),
        }

    def get_eo_aggregate(
        self,
        level: str,
        administrative_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        Get EO data aggregated by administrative level.

        Args:
            level: "region", "district", or "ward"
            administrative_id: Filter to children of this area
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Dict with data, filters, and available options
        """
        # Validate level
        valid_levels = ["region", "district", "ward"]
        if level not in valid_levels:
            level = "region"

        # Get the level object
        admin_level = (
            self.db.query(AdministrativeLevel)
            .filter(AdministrativeLevel.name == level)
            .first()
        )

        if not admin_level:
            return {
                "data": [],
                "filters": {
                    "level": level,
                    "administrative_id": administrative_id,
                    "crop_type": None,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "available": self._get_available_filters(),
            }

        # Get administrative areas at this level
        areas_query = (
            self.db.query(Administrative)
            .filter(Administrative.level_id == admin_level.id)
        )

        # Filter by parent administrative area
        if administrative_id:
            parent_admin = (
                self.db.query(Administrative)
                .filter(Administrative.id == administrative_id)
                .first()
            )
            if parent_admin:
                areas_query = areas_query.filter(
                    Administrative.path.like(f"{parent_admin.path}%")
                )

        areas = areas_query.order_by(Administrative.name).all()

        results = []

        for area in areas:
            # Get all area IDs under this area (including itself)
            if level == "ward":
                area_ids = [area.id]
            else:
                ward_ids = AdministrativeService.get_descendant_ward_ids(
                    self.db, area.id
                )
                area_ids = ward_ids + [area.id]

            # Get EO IDs assigned to these areas
            eo_ids = [
                ua.user_id
                for ua in self.db.query(UserAdministrative)
                .filter(UserAdministrative.administrative_id.in_(area_ids))
                .all()
            ]

            # Filter to active EOs
            eo_count = (
                self.db.query(func.count(User.id))
                .filter(
                    User.id.in_(eo_ids),
                    User.user_type == UserType.EXTENSION_OFFICER,
                    User.is_active == True,  # noqa: E712
                )
                .scalar()
                or 0
            )

            # Get customer IDs in these areas for ticket queries
            customer_ids = [
                ca.customer_id
                for ca in self.db.query(CustomerAdministrative)
                .filter(
                    CustomerAdministrative.administrative_id.in_(
                        area_ids if level == "ward"
                        else AdministrativeService.get_descendant_ward_ids(
                            self.db, area.id
                        ) or [area.id]
                    )
                )
                .all()
            ]

            # Open tickets
            open_tickets = 0
            closed_tickets = 0
            total_replies = 0

            if customer_ids:
                open_tickets = (
                    self.db.query(func.count(Ticket.id))
                    .filter(
                        Ticket.customer_id.in_(customer_ids),
                        Ticket.resolved_at.is_(None),
                    )
                    .scalar()
                    or 0
                )

                # Closed tickets with date filters
                closed_query = (
                    self.db.query(func.count(Ticket.id))
                    .filter(
                        Ticket.customer_id.in_(customer_ids),
                        Ticket.resolved_at.isnot(None),
                    )
                )
                closed_query = self._apply_date_filter(
                    closed_query, Ticket.resolved_at, start_date, end_date
                )
                closed_tickets = closed_query.scalar() or 0

                # Total replies from EOs to customers in this area
                replies_query = (
                    self.db.query(func.count(Message.id))
                    .filter(
                        Message.customer_id.in_(customer_ids),
                        Message.from_source == MessageFrom.USER,
                    )
                )
                replies_query = self._apply_date_filter(
                    replies_query, Message.created_at, start_date, end_date
                )
                total_replies = replies_query.scalar() or 0

            if eo_count == 0 and open_tickets == 0 and closed_tickets == 0:
                continue

            results.append({
                "id": area.id,
                "name": area.name,
                "path": area.path,
                "eo_count": eo_count,
                "open_tickets": open_tickets,
                "closed_tickets": closed_tickets,
                "total_replies": total_replies,
            })

        return {
            "data": results,
            "filters": {
                "level": level,
                "administrative_id": administrative_id,
                "crop_type": None,
                "start_date": start_date,
                "end_date": end_date,
            },
            "available": self._get_available_filters(),
        }

    def get_crop_distribution(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        administrative_id: Optional[int] = None,
    ) -> dict:
        """
        Get farmer count per crop type.

        Args:
            start_date: Filter customers created on or after this date
            end_date: Filter customers created on or before this date
            administrative_id: Filter by administrative area (any level)

        Returns:
            Dict with crops list, total, and filters
        """
        crop_type_col = Customer.profile_data.op("->>")("crop_type")

        # Base query: count farmers by crop type
        query = self.db.query(
            crop_type_col.label("crop"),
            func.count(Customer.id).label("count"),
        ).filter(
            Customer.onboarding_status == OnboardingStatus.COMPLETED,
            crop_type_col.isnot(None),
            crop_type_col != "",
        )

        # Filter by administrative area
        if administrative_id:
            customer_ids = self._get_administrative_customer_ids(
                administrative_id
            )
            if customer_ids:
                query = query.filter(Customer.id.in_(customer_ids))
            else:
                return {
                    "crops": [],
                    "total": 0,
                    "filters": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "administrative_id": administrative_id,
                    },
                }

        # Apply date filters
        query = self._apply_date_filter(
            query, Customer.created_at, start_date, end_date
        )

        # Group by crop type and execute
        results = query.group_by(crop_type_col).order_by(
            func.count(Customer.id).desc()
        ).all()

        # Build response
        crops = []
        total = 0
        for crop, count in results:
            crops.append({"crop": crop, "count": count})
            total += count

        return {
            "crops": crops,
            "total": total,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "administrative_id": administrative_id,
            },
        }

    def _get_child_level(
        self, administrative_id: Optional[int]
    ) -> Tuple[Optional[AdministrativeLevel], str]:
        """
        Determine the child level based on administrative_id.

        Args:
            administrative_id: The parent administrative area ID

        Returns:
            Tuple of (child_level, level_name)
            - No filter → Region level
            - Region filter → District level
            - District filter → Ward level
            - Ward filter → Ward level (same)
        """
        # Level hierarchy mapping: parent level -> child level name
        level_hierarchy = {
            "country": "region",
            "region": "district",
            "district": "ward",
            "ward": "ward",  # Ward has no children, show itself
        }

        if not administrative_id:
            # No filter: show regions
            child_level = (
                self.db.query(AdministrativeLevel)
                .filter(AdministrativeLevel.name == "region")
                .first()
            )
            return child_level, "Region"

        # Get the parent administrative area
        parent_admin = (
            self.db.query(Administrative)
            .filter(Administrative.id == administrative_id)
            .first()
        )

        if not parent_admin or not parent_admin.level:
            # Fallback to region
            child_level = (
                self.db.query(AdministrativeLevel)
                .filter(AdministrativeLevel.name == "region")
                .first()
            )
            return child_level, "Region"

        parent_level_name = parent_admin.level.name.lower()
        child_level_name = level_hierarchy.get(parent_level_name, "region")

        child_level = (
            self.db.query(AdministrativeLevel)
            .filter(AdministrativeLevel.name == child_level_name)
            .first()
        )

        # Capitalize for display
        level_display_name = child_level_name.capitalize()

        return child_level, level_display_name

    def get_crop_distribution_matrix(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        administrative_id: Optional[int] = None,
    ) -> dict:
        """
        Get crop distribution matrix by administrative level.

        The level shown depends on the administrative_id filter:
        - No filter → Show regions
        - Region filter → Show districts under that region
        - District filter → Show wards under that district
        - Ward filter → Show that ward only

        Args:
            start_date: Filter customers created on or after this date
            end_date: Filter customers created on or before this date
            administrative_id: Filter by administrative area (any level)

        Returns:
            Dict with matrix, crop_types, level_name, and filters
        """
        crop_type_col = Customer.profile_data.op("->>")("crop_type")

        # Determine the child level based on filter
        target_level, level_name = self._get_child_level(administrative_id)

        if not target_level:
            return {
                "matrix": [],
                "crop_types": [],
                "level_name": "Region",
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "administrative_id": administrative_id,
                },
            }

        # Get areas at the target level
        areas_query = (
            self.db.query(Administrative)
            .filter(Administrative.level_id == target_level.id)
        )

        # Filter areas by parent administrative area
        if administrative_id:
            parent_admin = (
                self.db.query(Administrative)
                .filter(Administrative.id == administrative_id)
                .first()
            )
            if parent_admin:
                # Filter areas that are under this parent
                areas_query = areas_query.filter(
                    Administrative.path.like(f"{parent_admin.path}%")
                )

        areas = areas_query.order_by(Administrative.name).all()

        # Collect all crop types for columns
        all_crop_types = set()
        matrix_data = []

        for area in areas:
            # Get ward IDs under this area (or itself if it's a ward)
            if target_level.name == "ward":
                ward_ids = [area.id]
            else:
                ward_ids = AdministrativeService.get_descendant_ward_ids(
                    self.db, area.id
                )
                if not ward_ids:
                    ward_ids = [area.id]

            # Get customer IDs in these wards
            customer_query = (
                self.db.query(Customer.id)
                .join(CustomerAdministrative)
                .filter(
                    CustomerAdministrative.administrative_id.in_(ward_ids),
                    Customer.onboarding_status == OnboardingStatus.COMPLETED,
                )
            )

            # Apply date filters
            customer_query = self._apply_date_filter(
                customer_query, Customer.created_at, start_date, end_date
            )

            customer_ids = [c.id for c in customer_query.all()]

            if not customer_ids:
                continue

            # Count farmers by crop type in this area
            crop_counts_query = (
                self.db.query(
                    crop_type_col.label("crop"),
                    func.count(Customer.id).label("count"),
                )
                .filter(
                    Customer.id.in_(customer_ids),
                    crop_type_col.isnot(None),
                    crop_type_col != "",
                )
                .group_by(crop_type_col)
            )

            crop_counts = {}
            total_in_area = 0
            for crop, count in crop_counts_query.all():
                crop_counts[crop] = count
                total_in_area += count
                all_crop_types.add(crop)

            if total_in_area > 0:
                matrix_data.append({
                    "county": area.name,
                    "county_id": area.id,
                    "crops": crop_counts,
                    "total": total_in_area,
                })

        # Sort crop types alphabetically
        sorted_crop_types = sorted(list(all_crop_types))

        return {
            "matrix": matrix_data,
            "crop_types": sorted_crop_types,
            "level_name": level_name,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "administrative_id": administrative_id,
            },
        }

    def get_tickets_waiting_response(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        administrative_id: Optional[int] = None,
    ) -> dict:
        """
        Get tickets waiting for EO response, categorized by wait time.

        This shows tickets where the farmer has escalated but the EO
        has not yet responded, grouped by:
        - 2-24 hours waiting
        - 24-48 hours waiting
        - >48 hours waiting

        For each ticket, identifies the responsible EO (may be at ward,
        district, or region level) and marks if assigned to parent area.

        Args:
            start_date: Filter by ticket creation start date
            end_date: Filter by ticket creation end date
            administrative_id: Filter to tickets in this area and descendants

        Returns:
            Dictionary with summary stats and ticket lists by wait time
        """
        from datetime import datetime, timezone

        # Get current time for calculating wait time
        now = datetime.now(timezone.utc)

        # Base query: open tickets only
        query = (
            self.db.query(Ticket)
            .filter(Ticket.resolved_at.is_(None))
        )

        # Apply date filters on ticket creation
        query = self._apply_date_filter(
            query, Ticket.created_at, start_date, end_date
        )

        # Filter by administrative area
        if administrative_id:
            ward_ids = self._get_administrative_ward_ids(administrative_id)
            if ward_ids:
                query = query.filter(Ticket.administrative_id.in_(ward_ids))
            else:
                # If no ward IDs, use the administrative_id directly
                query = query.filter(
                    Ticket.administrative_id == administrative_id
                )

        # Get all open tickets
        open_tickets = query.all()

        # Process each ticket to determine wait time and assigned EO
        tickets_data = []

        for ticket in open_tickets:
            # Get last message from customer
            last_customer_msg = (
                self.db.query(Message)
                .filter(Message.customer_id == ticket.customer_id)
                .filter(Message.from_source == MessageFrom.CUSTOMER)
                .order_by(Message.created_at.desc())
                .first()
            )

            if not last_customer_msg:
                continue

            # Check if EO has replied after last customer message
            eo_reply = (
                self.db.query(Message)
                .filter(Message.customer_id == ticket.customer_id)
                .filter(Message.from_source == MessageFrom.USER)
                .filter(Message.created_at > last_customer_msg.created_at)
                .first()
            )

            # Only include if no EO reply after last customer message
            if eo_reply:
                continue

            # Calculate waiting time in hours
            waiting_time = now - last_customer_msg.created_at
            waiting_hours = waiting_time.total_seconds() / 3600

            # Only include if waiting >= 2 hours
            if waiting_hours < 2:
                continue

            # Get customer info
            customer = ticket.customer

            # Get ward info
            ward = (
                self.db.query(Administrative)
                .filter(Administrative.id == ticket.administrative_id)
                .first()
            )

            if not ward:
                continue

            # Find responsible EO (check ward, then district, then region)
            assigned_to_parent = False
            responsible_eo = None

            # First check ward level
            ward_eo = (
                self.db.query(User)
                .join(UserAdministrative)
                .filter(UserAdministrative.administrative_id == ward.id)
                .filter(User.user_type == UserType.EXTENSION_OFFICER)
                .filter(User.is_active == True)  # noqa: E712
                .first()
            )

            if ward_eo:
                responsible_eo = ward_eo
            else:
                # No ward EO, check parent areas
                assigned_to_parent = True
                ancestor_ids = AdministrativeService.get_ancestor_ids(
                    self.db, ward.id
                )

                # Try to find EO in parent areas (district, then region)
                for ancestor_id in ancestor_ids:
                    parent_eo = (
                        self.db.query(User)
                        .join(UserAdministrative)
                        .filter(
                            UserAdministrative.administrative_id == ancestor_id
                        )
                        .filter(User.user_type == UserType.EXTENSION_OFFICER)
                        .filter(User.is_active == True)  # noqa: E712
                        .first()
                    )
                    if parent_eo:
                        responsible_eo = parent_eo
                        break

            # Build ticket data
            ticket_item = {
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "customer_name": customer.full_name or "Unknown",
                "customer_phone": customer.phone_number,
                "ward_name": ward.name,
                "ward_path": ward.path,
                "eo_name": (
                    responsible_eo.full_name if responsible_eo else None
                ),
                "eo_phone": (
                    responsible_eo.phone_number if responsible_eo else None
                ),
                "assigned_to_parent": assigned_to_parent,
                "waiting_hours": round(waiting_hours, 1),
                "created_at": ticket.created_at.isoformat(),
                "last_customer_message_at": (
                    last_customer_msg.created_at.isoformat()
                ),
            }

            tickets_data.append(ticket_item)

        # Categorize by wait time
        tickets_2_24 = [
            t for t in tickets_data if 2 <= t["waiting_hours"] < 24
        ]
        tickets_24_48 = [
            t for t in tickets_data if 24 <= t["waiting_hours"] < 48
        ]
        tickets_over_48 = [
            t for t in tickets_data if t["waiting_hours"] >= 48
        ]

        # Sort each list by waiting_hours descending
        tickets_2_24.sort(key=lambda x: x["waiting_hours"], reverse=True)
        tickets_24_48.sort(key=lambda x: x["waiting_hours"], reverse=True)
        tickets_over_48.sort(key=lambda x: x["waiting_hours"], reverse=True)

        return {
            "summary": {
                "waiting_2_24_hours": len(tickets_2_24),
                "waiting_24_48_hours": len(tickets_24_48),
                "waiting_over_48_hours": len(tickets_over_48),
                "total_waiting": len(tickets_data),
            },
            "tickets_2_24_hours": tickets_2_24,
            "tickets_24_48_hours": tickets_24_48,
            "tickets_over_48_hours": tickets_over_48,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "administrative_id": administrative_id,
            },
        }
