"""
Elevation Service

Provides altitude lookup functionality using Open-Elevation API.
Caches results in customer profile_data to minimize API calls.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"
TIMEOUT_SECONDS = 5


class ElevationService:
    """Service for looking up altitude from coordinates."""

    async def get_altitude(
        self, latitude: float, longitude: float
    ) -> Optional[int]:
        """
        Get altitude in meters for given coordinates.

        Uses Open-Elevation API with 5-second timeout.
        Returns None if API fails or times out.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Altitude in meters, or None if lookup fails
        """
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(
                    OPEN_ELEVATION_URL,
                    params={"locations": f"{latitude},{longitude}"},
                )
                response.raise_for_status()

                data = response.json()
                results = data.get("results", [])

                if not results:
                    logger.warning(
                        f"No elevation data returned for "
                        f"{latitude},{longitude}"
                    )
                    return None

                elevation = results[0].get("elevation")
                if elevation is None:
                    return None

                return int(round(elevation))

        except httpx.TimeoutException:
            logger.warning(
                f"Elevation API timeout for "
                f"{latitude},{longitude}"
            )
            return None
        except httpx.HTTPError as e:
            logger.warning(
                f"Elevation API HTTP error for {latitude},{longitude}: {e}"
            )
            return None
        except (ValueError, KeyError, IndexError) as e:
            logger.warning(
                f"Elevation API parse error for {latitude},{longitude}: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected elevation API error for "
                f"{latitude},{longitude}: {e}"
            )
            return None

    async def get_or_fetch_altitude(
        self, customer, latitude: float, longitude: float, db=None
    ) -> Optional[int]:
        """
        Get altitude from customer profile cache or fetch from API.

        If altitude is not cached, fetches from API and caches the result.

        Args:
            customer: Customer model instance
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            db: Database session (optional, for saving cached value)

        Returns:
            Altitude in meters, or None if lookup fails
        """
        # Check cache first
        if customer.altitude_m is not None:
            return customer.altitude_m

        # Fetch from API
        altitude = await self.get_altitude(latitude, longitude)

        # Cache the result (even if None to avoid repeated failed lookups)
        if db is not None:
            customer.altitude_m = altitude
            db.commit()

        return altitude


# Singleton instance
_elevation_service = None


def get_elevation_service() -> ElevationService:
    """Get singleton ElevationService instance."""
    global _elevation_service
    if _elevation_service is None:
        _elevation_service = ElevationService()
    return _elevation_service
