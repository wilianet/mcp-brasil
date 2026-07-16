"""Validators for Brazilian documents: CPF, CNPJ, CEP."""

from __future__ import annotations

import re

_DIGITS_RE = re.compile(r"\D")
_CNPJ_FORMAT_RE = re.compile(r"[.\-/\s]")
_CNPJ_RE = re.compile(r"^[A-Z0-9]{12}\d{2}$")


def _only_digits(value: str) -> str:
    """Strip all non-digit characters."""
    return _DIGITS_RE.sub("", value)


# ---------------------------------------------------------------------------
# CPF
# ---------------------------------------------------------------------------


def validate_cpf(cpf: str) -> bool:
    """Validate a CPF using the check-digit algorithm.

    Args:
        cpf: CPF string (with or without formatting).

    Returns:
        True if valid, False otherwise.
    """
    digits = _only_digits(cpf)
    if len(digits) != 11:
        return False
    # Reject known invalid sequences (all same digit)
    if digits == digits[0] * 11:
        return False

    # First check digit
    total = sum(int(digits[i]) * (10 - i) for i in range(9))
    remainder = total % 11
    d1 = 0 if remainder < 2 else 11 - remainder
    if int(digits[9]) != d1:
        return False

    # Second check digit
    total = sum(int(digits[i]) * (11 - i) for i in range(10))
    remainder = total % 11
    d2 = 0 if remainder < 2 else 11 - remainder
    return int(digits[10]) == d2


def format_cpf(cpf: str) -> str:
    """Format a CPF string as XXX.XXX.XXX-XX.

    Args:
        cpf: CPF digits (with or without formatting).

    Returns:
        Formatted CPF string.

    Raises:
        ValueError: If CPF does not have exactly 11 digits.
    """
    digits = _only_digits(cpf)
    if len(digits) != 11:
        raise ValueError(f"CPF must have 11 digits, got {len(digits)}")
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


# ---------------------------------------------------------------------------
# CNPJ
# ---------------------------------------------------------------------------

_CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def normalize_cnpj(cnpj: str) -> str:
    """Remove CNPJ punctuation and normalize alphanumeric characters."""
    return _CNPJ_FORMAT_RE.sub("", cnpj.strip().upper())


def _cnpj_character_value(character: str) -> int:
    """Return the official CNPJ alphanumeric value (ASCII code minus 48)."""
    return ord(character) - 48


def validate_cnpj(cnpj: str) -> bool:
    """Validate a CNPJ using the check-digit algorithm.

    Args:
        cnpj: CNPJ string (with or without formatting).

    Returns:
        True if valid, False otherwise.
    """
    normalized = normalize_cnpj(cnpj)
    if not _CNPJ_RE.fullmatch(normalized):
        return False
    if normalized == normalized[0] * 14:
        return False

    # First check digit
    total = sum(_cnpj_character_value(normalized[i]) * _CNPJ_WEIGHTS_1[i] for i in range(12))
    remainder = total % 11
    d1 = 0 if remainder < 2 else 11 - remainder
    if int(normalized[12]) != d1:
        return False

    # Second check digit
    total = sum(_cnpj_character_value(normalized[i]) * _CNPJ_WEIGHTS_2[i] for i in range(13))
    remainder = total % 11
    d2 = 0 if remainder < 2 else 11 - remainder
    return int(normalized[13]) == d2


def format_cnpj(cnpj: str) -> str:
    """Format a CNPJ string as XX.XXX.XXX/XXXX-XX.

    Args:
        cnpj: CNPJ characters (with or without formatting).

    Returns:
        Formatted CNPJ string.

    Raises:
        ValueError: If CNPJ does not have exactly 14 alphanumeric characters.
    """
    normalized = normalize_cnpj(cnpj)
    if not _CNPJ_RE.fullmatch(normalized):
        raise ValueError("CNPJ must have 12 alphanumeric base characters and 2 check digits")
    return (
        f"{normalized[:2]}.{normalized[2:5]}.{normalized[5:8]}"
        f"/{normalized[8:12]}-{normalized[12:]}"
    )


# ---------------------------------------------------------------------------
# CEP
# ---------------------------------------------------------------------------


def validate_cep(cep: str) -> bool:
    """Validate a CEP (format only — 8 digits, not all zeros).

    Args:
        cep: CEP string (with or without formatting).

    Returns:
        True if valid format, False otherwise.
    """
    digits = _only_digits(cep)
    if len(digits) != 8:
        return False
    return digits != "00000000"


def format_cep(cep: str) -> str:
    """Format a CEP string as XXXXX-XXX.

    Args:
        cep: CEP digits (with or without formatting).

    Returns:
        Formatted CEP string.

    Raises:
        ValueError: If CEP does not have exactly 8 digits.
    """
    digits = _only_digits(cep)
    if len(digits) != 8:
        raise ValueError(f"CEP must have 8 digits, got {len(digits)}")
    return f"{digits[:5]}-{digits[5:]}"
