"""This module implements IntEnums with improved printing of values."""

from enum import IntEnum


class BetterIntEnum(IntEnum):
    """BetterIntEnum is an IntEnums type with better printing of values."""
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self):
        return f"{self.__class__.__name__}.{self.name}"
