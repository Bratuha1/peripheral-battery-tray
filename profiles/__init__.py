"""Registry of verified USB profiles."""

from .ipi import PROFILE as IPI
from .logitech import PROFILE as LOGITECH

USB_PROFILES = (IPI, LOGITECH)
