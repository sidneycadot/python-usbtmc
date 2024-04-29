"""This module implements enums with improved printing."""

from enum import IntEnum


class BetterIntEnum(IntEnum):
    """BetterIntEnum is an Enum type with better printing of values."""
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self):
        return f"{self.__class__.__name__}.{self.name}"
