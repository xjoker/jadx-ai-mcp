"""
Parameter Validator - input validation for Transfer API
"""

import re
from typing import List
from src.server.logging_config import get_logger

logger = get_logger("param_validator")

# Valid Java class name format: letters, digits, dots, dollar signs, underscores
CLASS_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9.$_]+$')

# Limit constants
MAX_CLASS_NAME_LENGTH = 512
MAX_CLASSES_PER_REQUEST = 100


class ValidationError(Exception):
    """Parameter validation error"""
    pass


def validate_class_names(classes_param: str) -> List[str]:
    """
    Validate class name parameter.

    Args:
        classes_param: Comma-separated string of class names

    Returns:
        List of validated class names

    Raises:
        ValidationError: If validation fails
    """
    if not classes_param or not classes_param.strip():
        raise ValidationError("Empty classes parameter")

    # Split and clean
    class_names = [c.strip() for c in classes_param.split(",") if c.strip()]

    if not class_names:
        raise ValidationError("No valid class names provided")

    # Quantity limit
    if len(class_names) > MAX_CLASSES_PER_REQUEST:
        logger.warning(f"Too many classes requested: {len(class_names)}")
        raise ValidationError(
            f"Too many classes. Maximum {MAX_CLASSES_PER_REQUEST} per request, got {len(class_names)}"
        )

    # Validate each class name
    for name in class_names:
        # Length limit
        if len(name) > MAX_CLASS_NAME_LENGTH:
            logger.warning(f"Class name too long: {name[:50]}...")
            raise ValidationError(
                f"Class name too long (max {MAX_CLASS_NAME_LENGTH} chars): {name[:50]}..."
            )

        # Format validation
        if not CLASS_NAME_PATTERN.match(name):
            logger.warning(f"Invalid class name format: {name}")
            raise ValidationError(
                f"Invalid class name format. Only alphanumeric, dots, dollar signs, "
                f"and underscores allowed: {name}"
            )

    logger.debug(f"Validated {len(class_names)} class names")
    return class_names


def validate_token(token: str) -> str:
    """
    Validate token format.

    Args:
        token: Token string

    Returns:
        Cleaned token string

    Raises:
        ValidationError: If validation fails
    """
    if not token or not token.strip():
        raise ValidationError("Empty token")

    token = token.strip()

    # Token length check (expected 32 chars, with some tolerance)
    if len(token) < 20 or len(token) > 64:
        logger.warning(f"Invalid token length: {len(token)}")
        raise ValidationError("Invalid token format")

    # Token character check (should be URL-safe Base64)
    if not re.match(r'^[A-Za-z0-9_-]+$', token):
        logger.warning("Invalid token characters")
        raise ValidationError("Invalid token format")

    return token


def validate_format(format_param: str) -> str:
    """
    Validate format parameter.

    Args:
        format_param: Format string (json/zip)

    Returns:
        Validated format string

    Raises:
        ValidationError: If validation fails
    """
    if not format_param:
        return "json"  # default

    format_lower = format_param.lower().strip()

    if format_lower not in ["json", "zip"]:
        raise ValidationError(f"Invalid format. Must be 'json' or 'zip', got '{format_param}'")

    return format_lower


def validate_compression(compression_param: str) -> str:
    """
    Validate compression parameter.

    Args:
        compression_param: Compression algorithm (br/gzip/none/auto)

    Returns:
        Validated compression algorithm string

    Raises:
        ValidationError: If validation fails
    """
    if not compression_param:
        return "auto"  # default

    compression_lower = compression_param.lower().strip()

    valid_options = ["br", "gzip", "none", "auto"]
    if compression_lower not in valid_options:
        raise ValidationError(
            f"Invalid compression. Must be one of {valid_options}, got '{compression_param}'"
        )

    return compression_lower
