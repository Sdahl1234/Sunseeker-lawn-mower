"""SunseekerPy."""

import logging

_LOGGER = logging.getLogger(__name__)


class SunseekerZone:
    """Sunseeker zone class."""

    def __init__(self) -> None:
        """Init."""
        self.id = None
        self.name = None
        self.work_speed = 0
        self.gap = 0
        self.plan_mode = 0
        self.plan_angle = 0
        self.blade_speed = 0
        self.blade_height = 0
        self.region_size = 0
        self.estimate_time = 0
        self.setting = False
