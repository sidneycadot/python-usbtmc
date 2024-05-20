"""This module implements BetterIntEnum: an IntEnum type with improved printing of enumeration values."""

from enum import IntEnum


class BetterIntEnum(IntEnum):
    """BetterIntEnum is an IntEnum type with improved printing of enumeration values."""
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self):
        return f"{self.__class__.__name__}.{self.name}"
