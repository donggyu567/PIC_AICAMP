"""Derived-feature calculations kept separate from scoring logic."""

import math


def calculate_heat_exposure_value(temperature: float, humidity: float) -> float:
    """Calculate KMA summer apparent temperature from Celsius and relative humidity.

    The wet-bulb temperature uses Stull's estimate. This is the sole location
    of the P0 heat-exposure formula; callers provide backend source values
    unchanged and no grid-level spatial interpolation is performed.
    """
    wet_bulb = (
        temperature * math.atan(0.151977 * math.sqrt(humidity + 8.313659))
        + math.atan(temperature + humidity)
        - math.atan(humidity - 1.67633)
        + 0.00391838 * humidity ** 1.5 * math.atan(0.023101 * humidity)
        - 4.686035
    )
    return (
        -0.2442
        + 0.55399 * wet_bulb
        + 0.45535 * temperature
        - 0.0022 * wet_bulb ** 2
        + 0.00278 * wet_bulb * temperature
        + 3.0
    )
