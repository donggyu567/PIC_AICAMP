"""Feature interfaces kept separate from scoring logic."""

from typing import Optional


def compute_heat_exposure_value(*_: object) -> Optional[float]:
    """Placeholder for a future temperature/humidity-derived heat feature.

    v0.1 receives ``heat_exposure_value`` directly and does not invoke this
    function. The signature intentionally remains open for later GIS/weather
    feature integration.
    """
    # TODO: define the approved heat-exposure formula when source data is fixed.
    return None
