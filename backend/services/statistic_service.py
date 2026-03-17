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

    def _get_ward_customer_ids(self, ward_id: int) -> List[int]:
        """Get all customer IDs in a specific ward."""
        return [
            ca.customer_id
            for ca in self.db.query(CustomerAdministrative)
            .filter(CustomerAdministrative.administrative_id == ward_id)
            .all()
        ]

    def _get_base_customer_query(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ward_id: Optional[int] = None,
        phone_prefix: Optional[str] = None,
    ):
        """Build base customer query with common filters."""
        query = self.db.query(Customer)

        # Date filter on customer creation
        query = self._apply_date_filter(
            query, Customer.created_at, start_date, end_date
        )

        # Phone prefix filter
        query = self._apply_phone_prefix_filter(query, phone_prefix)

        # Ward filter
        if ward_id:
            customer_ids = self._get_ward_customer_ids(ward_id)
            query = query.filter(Customer.id.in_(customer_ids))

        return query

    def get_farmer_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ward_id: Optional[int] = None,
        phone_prefix: Optional[str] = None,
        active_days: int = 30,
    ) -> dict:
        """
        Get comprehensive farmer statistics.

        Args:
            start_date: Filter customers created on or after this date
            end_date: Filter customers created on or before this date
            ward_id: Filter by specific ward
            phone_prefix: Filter by phone number prefix (e.g., "+254")
            active_days: Days to consider a farmer as "active"

        Returns:
            Dict with onboarding, activity, features, escalation stats
        """
        base_query = self._get_base_customer_query(
            start_date, end_date, ward_id, phone_prefix
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
    ) -> List[dict]:
        """
        Get farmer statistics grouped by ward.

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
        ward_id: Optional[int] = None,
        phone_prefix: Optional[str] = None,
        group_by: str = "day",
    ) -> Tuple[List[dict], int]:
        """
        Get registration data for charting.

        Args:
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

        if ward_id:
            customer_ids = self._get_ward_customer_ids(ward_id)
            query = query.filter(Customer.id.in_(customer_ids))

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
    ) -> dict:
        """
        Get EO statistics.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date
            eo_id: Filter by specific EO

        Returns:
            Dictionary with ticket and message stats
        """
        # Build EO filter
        eo_filter = []
        if eo_id:
            eo_filter.append(Ticket.resolved_by == eo_id)

        # Open tickets
        open_tickets_query = (
            self.db.query(func.count(Ticket.id))
            .filter(Ticket.resolved_at.is_(None))
        )
        open_tickets = open_tickets_query.scalar() or 0

        # Closed tickets with date filters
        closed_query = self.db.query(func.count(Ticket.id)).filter(
            Ticket.resolved_at.isnot(None)
        )

        if eo_id:
            closed_query = closed_query.filter(Ticket.resolved_by == eo_id)

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
    ) -> List[dict]:
        """
        Get EO statistics grouped by individual EO.

        Returns:
            List of EO statistics dictionaries
        """
        # Get all EOs
        eos = (
            self.db.query(User)
            .filter(User.user_type == UserType.EXTENSION_OFFICER)
            .filter(User.is_active == True)  # noqa: E712
            .all()
        )

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

    def get_eo_count_by_district(self) -> List[dict]:
        """
        Get EO counts grouped by district.

        Returns:
            List of district EO count dictionaries
        """
        # Get district level
        district_level = (
            self.db.query(AdministrativeLevel)
            .filter(AdministrativeLevel.name == "District")
            .first()
        )

        if not district_level:
            return []

        # Get all districts
        districts = (
            self.db.query(Administrative)
            .filter(Administrative.level_id == district_level.id)
            .all()
        )

        results = []

        for district in districts:
            # Count EOs assigned to this district or its wards
            # First, get all administrative areas under this district
            child_areas = (
                self.db.query(Administrative.id)
                .filter(
                    Administrative.path.like(f"{district.path}%")
                )
                .all()
            )
            area_ids = [a.id for a in child_areas] + [district.id]

            # Count active EOs in these areas
            eo_count = (
                self.db.query(func.count(distinct(UserAdministrative.user_id)))
                .join(User)
                .filter(
                    UserAdministrative.administrative_id.in_(area_ids),
                    User.user_type == UserType.EXTENSION_OFFICER,
                    User.is_active == True,  # noqa: E712
                )
                .scalar()
                or 0
            )

            if eo_count > 0:
                results.append({
                    "district_id": district.id,
                    "district_name": district.name,
                    "eo_count": eo_count,
                })

        return results

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
