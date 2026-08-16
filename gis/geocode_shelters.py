"""Prepare and geocode Hapcheon heatwave shelters without inventing coordinates."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import pandas as pd

from .build_hapcheon_grid import load_hapcheon_boundaries
from .config import ANALYSIS_CRS, API_CRS, PROCESSED_DIR, SHELTER_GEOCODED_CSV, SHELTER_GEOCODING_INPUT_CSV, SHELTERS_CSV


@dataclass(frozen=True)
class GeocodingResult:
    status: str
    latitude: float | None = None
    longitude: float | None = None
    source: str | None = None


class AddressGeocoder(Protocol):
    def geocode(self, query: str) -> GeocodingResult: ...


class KakaoAddressGeocoder:
    """Small adapter for Kakao's address-search API; its key is never stored in code."""

    endpoint = "https://dapi.kakao.com/v2/local/search/address.json"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GEOCODING_API_KEY is required for Kakao geocoding")
        self.api_key = api_key

    def geocode(self, query: str) -> GeocodingResult:
        request = Request(
            f"{self.endpoint}?{urlencode({'query': query})}",
            headers={"Authorization": f"KakaoAK {self.api_key}"},
        )
        try:
            with urlopen(request, timeout=15) as response:  # nosec B310 - fixed HTTPS endpoint
                payload = json.load(response)
        except Exception:
            return GeocodingResult(status="FAILED", source="kakao")
        documents = payload.get("documents", [])
        if not documents:
            return GeocodingResult(status="FAILED", source="kakao")
        if len(documents) > 1:
            return GeocodingResult(status="AMBIGUOUS", source="kakao")
        try:
            return GeocodingResult(
                status="OK", latitude=float(documents[0]["y"]), longitude=float(documents[0]["x"]), source="kakao"
            )
        except (KeyError, TypeError, ValueError):
            return GeocodingResult(status="FAILED", source="kakao")


def _read_shelters(path: Path) -> pd.DataFrame:
    shelters = pd.read_csv(path, dtype="string")
    required = {"facility_name", "road_address", "lot_address"}
    if not required.issubset(shelters.columns):
        raise ValueError("shelter input is missing required address fields")
    if shelters[list(required)].isna().any().any():
        raise ValueError("shelter facility name and addresses must be non-null")
    if shelters.duplicated().any():
        raise ValueError("shelter input contains duplicate rows")
    if shelters["road_address"].duplicated().any() or shelters["lot_address"].duplicated().any():
        raise ValueError("shelter input contains duplicate addresses")
    return shelters.copy()


def prepare_geocoding_input(path: Path = SHELTERS_CSV) -> tuple[pd.DataFrame, dict[str, int]]:
    """Give every source shelter a stable ID and primary/fallback address queries."""
    shelters = _read_shelters(path)
    sort_fields = ["facility_name", "road_address", "lot_address"]
    result = shelters.sort_values(sort_fields, kind="mergesort").reset_index(drop=True).copy()
    result.insert(0, "shelter_id", [f"SHELTER_{index:03d}" for index in range(1, len(result) + 1)])
    result["geocoding_query"] = result["road_address"]
    result["fallback_query"] = result["lot_address"]
    if result["shelter_id"].isna().any() or result["shelter_id"].duplicated().any():
        raise ValueError("generated shelter_id must be unique and non-null")
    report = {
        "raw_shelter_count": len(result),
        "duplicate_row_count": int(shelters.duplicated().sum()),
        "duplicate_road_address_count": int(shelters["road_address"].duplicated().sum()),
        "duplicate_lot_address_count": int(shelters["lot_address"].duplicated().sum()),
    }
    return result, report


def write_geocoding_input(data: pd.DataFrame, output_dir: Path = PROCESSED_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_dir / SHELTER_GEOCODING_INPUT_CSV.name, index=False, encoding="utf-8")


def geocode_shelters(source: pd.DataFrame, geocoder: AddressGeocoder) -> tuple[pd.DataFrame, dict[str, int]]:
    """Geocode a prepared shelter table, retrying the lot address only after road failure."""
    result = source.copy()
    records: list[dict[str, object]] = []
    for shelter in result.itertuples(index=False):
        query = shelter.geocoding_query
        response = geocoder.geocode(query)
        if response.status == "FAILED" and shelter.fallback_query != query:
            query = shelter.fallback_query
            response = geocoder.geocode(query)
        records.append({
            "geocoding_status": response.status,
            "geocoding_source": response.source,
            "geocoding_query": query,
            "latitude": response.latitude if response.status == "OK" else None,
            "longitude": response.longitude if response.status == "OK" else None,
        })
    result = pd.concat([result, pd.DataFrame(records)], axis=1)
    valid = result["geocoding_status"].eq("OK")
    coordinates = result.loc[valid, ["latitude", "longitude"]].apply(pd.to_numeric, errors="coerce")
    valid &= coordinates["latitude"].between(-90, 90).reindex(result.index, fill_value=False)
    valid &= coordinates["longitude"].between(-180, 180).reindex(result.index, fill_value=False)
    result.loc[~valid, ["latitude", "longitude"]] = None
    result.loc[~valid & result["geocoding_status"].eq("OK"), "geocoding_status"] = "FAILED"
    result["region_code"] = pd.NA
    result["region_name"] = pd.NA
    if valid.any():
        points = gpd.GeoDataFrame(result.loc[valid, ["shelter_id"]], geometry=gpd.points_from_xy(result.loc[valid, "longitude"], result.loc[valid, "latitude"]), crs=API_CRS).to_crs(ANALYSIS_CRS)
        mapped = gpd.sjoin(points, load_hapcheon_boundaries(), how="left", predicate="within")
        result = result.merge(mapped[["shelter_id", "region_code", "region_name"]], on="shelter_id", how="left", suffixes=("", "_mapped"))
        result["region_code"] = result.pop("region_code_mapped").combine_first(result["region_code"])
        result["region_name"] = result.pop("region_name_mapped").combine_first(result["region_name"])
    report = {
        "total_shelter_count": len(result), "valid_geocoded_count": int(valid.sum()),
        "failed_count": int(result["geocoding_status"].eq("FAILED").sum()),
        "ambiguous_count": int(result["geocoding_status"].eq("AMBIGUOUS").sum()),
        "outside_hapcheon_count": int((valid & result["region_code"].isna()).sum()),
        "region_mapping_null_count": int((valid & result["region_code"].isna()).sum()),
    }
    return result, report


def write_geocoded_shelters(data: pd.DataFrame, output_dir: Path = PROCESSED_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["shelter_id", "facility_name", "road_address", "lot_address", "region_code", "region_name", "latitude", "longitude", "geocoding_status", "geocoding_source", "geocoding_query"]
    data[fields].to_csv(output_dir / SHELTER_GEOCODED_CSV.name, index=False, encoding="utf-8")


def main() -> None:
    prepared, report = prepare_geocoding_input()
    write_geocoding_input(prepared)
    api_key = os.getenv("GEOCODING_API_KEY")
    if not api_key:
        print(json.dumps({**report, "status": "GEOCODING_CREDENTIAL_REQUIRED", "credential": "GEOCODING_API_KEY"}, ensure_ascii=False, indent=2))
        return
    geocoded, geocoding_report = geocode_shelters(prepared, KakaoAddressGeocoder(api_key))
    write_geocoded_shelters(geocoded)
    print(json.dumps({**report, **geocoding_report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
