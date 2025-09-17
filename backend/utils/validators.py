def validate_phone_number(phone_number: str) -> str:
    """
    Validate phone number format.

    Args:
        phone_number: The phone number to validate

    Returns:
        The validated phone number

    Raises:
        ValueError: If phone number format is invalid
    """
    if not phone_number.startswith("+") or len(phone_number) < 10:
        raise ValueError(
            "Phone number must start with + and be at least 10 characters")
    return phone_number
