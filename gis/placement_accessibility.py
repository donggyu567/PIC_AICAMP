"""Authoritative accessibility recalculation for proposed shelter placements."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import pandas as pd

from .build_shelter_accessibility import calculate_shelter_accessibility
from .placement_coverage import validate_placements


def calculate_accessibility_with_placements(
    grids: pd.DataFrame,
    existing_shelters: pd.DataFrame,
    placements: Iterable[Mapping[str, Any]],
) -> pd.DataFrame:
    """Recalculate access using existing shelters plus validated placements.

    The shared accessibility calculator performs the actual EPSG:5179 distance
    work. Candidate ``covered_grid_ids`` are intentionally not accepted here.
    """
    records = validate_placements(placements)
    shelters = existing_shelters.copy(deep=True)
    if not records:
        return calculate_shelter_accessibility(grids, shelters)

    placement_shelters = pd.DataFrame(
        [
            {
                "shelter_id": f"PLACEMENT::{record['placement_id']}",
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "geocoding_status": "OK",
            }
            for record in records
        ]
    )
    shelters = pd.concat([shelters, placement_shelters], ignore_index=True, sort=False)
    return calculate_shelter_accessibility(grids, shelters)
