"""SunseekerPy."""

import logging

_LOGGER = logging.getLogger(__name__)


class SunseekerConsumableItems:
    """Sunseeker consumable items class."""

    def __init__(self) -> None:
        """Init."""
        self.blade = CIBlade()
        self.cutter = CICutter()


class CIBlade:
    """Blade class."""

    def __init__(self) -> None:
        """Init."""
        self.twt: int = 0
        self.at: int = 0
        self.mp: int = 0
        self.loop: int = 0
        self.ls: int = 0


class CICutter:
    """Cutter class."""

    def __init__(self) -> None:
        """Init."""
        self.twt: int = 0
        self.at: int = 0
        self.mp: int = 0
        self.loop: int = 0
        self.ls: int = 0
