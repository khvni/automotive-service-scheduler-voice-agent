"""VIN decoding tools using NHTSA API."""

from typing import Any, Dict, Optional

import httpx
from app.config import settings


async def decode_vin(vin: str) -> Optional[Dict[str, Any]]:
    """
    Decode VIN using NHTSA API.

    Args:
        vin: 17-character VIN

    Returns:
        Vehicle information if VIN is valid, None otherwise
    """
    if len(vin) != 17:
        return None

    url = f"{settings.NHTSA_API_URL}/vehicles/DecodeVin/{vin}?format=json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)

        if response.status_code != 200:
            return None

        data = response.json()
        results = data.get("Results", [])

        # Extract key vehicle information
        vehicle_info = {}
        field_mapping = {
            "Make": "make",
            "Model": "model",
            "Model Year": "year",
            "Vehicle Type": "vehicle_type",
            "Body Class": "body_class",
            "Manufacturer Name": "manufacturer",
        }

        for result in results:
            variable = result.get("Variable")
            value = result.get("Value")

            if variable in field_mapping and value:
                vehicle_info[field_mapping[variable]] = value

        if not vehicle_info:
            return None

        vehicle_info["vin"] = vin
        return vehicle_info


async def suggest_service_for_vehicle(year: int, mileage: Optional[int] = None) -> list[str]:
    """
    Suggest maintenance services based on vehicle age and mileage.

    Args:
        year: Vehicle year
        mileage: Current mileage (optional)

    Returns:
        List of suggested services
    """
    suggestions = []
    current_year = 2025  # TODO: Use datetime.now().year

    vehicle_age = current_year - year

    # Age-based suggestions
    if vehicle_age >= 5:
        suggestions.append("Complete inspection")
        suggestions.append("Coolant system check")

    if vehicle_age >= 3:
        suggestions.append("Brake system inspection")
        suggestions.append("Battery test")

    # Mileage-based suggestions
    if mileage:
        if mileage >= 75000:
            suggestions.append("Transmission service")
            suggestions.append("Timing belt inspection")
        elif mileage >= 50000:
            suggestions.append("Brake pad replacement")
        elif mileage >= 30000:
            suggestions.append("Air filter replacement")

        if mileage % 5000 <= 1000:  # Due for oil change
            suggestions.append("Oil change")

    if not suggestions:
        suggestions.append("Standard maintenance check")

    return suggestions
