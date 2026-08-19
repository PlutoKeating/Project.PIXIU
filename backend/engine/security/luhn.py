"""Luhn checksum for bank card candidates."""

from __future__ import annotations


def passes_luhn(number: str) -> bool:
    if not number.isdigit():
        return False
    total = 0
    reverse = number[::-1]
    for idx, ch in enumerate(reverse):
        digit = int(ch)
        if idx % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
