from automation.platforms.base import PlatformAdapter
from automation.platforms.generic import GenericAdapter
from automation.platforms.greenhouse import GreenhouseAdapter
from automation.platforms.lever import LeverAdapter
from automation.platforms.workday import WorkdayAdapter

PLATFORM_ADAPTERS = [
    GreenhouseAdapter(),
    LeverAdapter(),
    WorkdayAdapter(),
    GenericAdapter(),
]

__all__ = [
    "PLATFORM_ADAPTERS",
    "PlatformAdapter",
    "GreenhouseAdapter",
    "LeverAdapter",
    "WorkdayAdapter",
    "GenericAdapter",
]
