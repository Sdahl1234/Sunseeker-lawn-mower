"""SunseekerPy."""

import logging

_LOGGER = logging.getLogger(__name__)


class SunseekerZigZag:
    """Sunseeker zigzag angles."""

    active: bool = False
    angle: int = 0


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
        self.multi_zigzag_angles: list = []
        self.zigzag_1 = SunseekerZigZag()
        self.zigzag_2 = SunseekerZigZag()
        self.zigzag_3 = SunseekerZigZag()
        self.zigzag_4 = SunseekerZigZag()
        self.blade_speed = 0
        self.blade_height = 0
        self.region_size = 0
        self.estimate_time = 0
        self.setting = False
        self.start = 0
        self.finish = 0
