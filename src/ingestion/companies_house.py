"""Typed connector for the UK Companies House REST API.

Not wired into the default ingestion/demo pipeline — see README's Quick
Start, which loads synthetic_vendor/synthetic_communications/
official_documents only. Requires COMPANIES_HOUSE_API_KEY; raises if
invoked without one rather than silently no-op'ing.
"""

from typing import Any

import httpx
from pydantic import BaseModel

from src.settings import get_settings

API_BASE_URL = "https://api.company-information.service.gov.uk"


class CompanyProfile(BaseModel):
    company_number: str
    company_name: str
    company_status: str
    date_of_creation: str | None = None
    registered_office_address: dict[str, Any] | None = None


class CompaniesHouseClient:
    def __init__(self, api_key: str | None = None, base_url: str = API_BASE_URL) -> None:
        self.api_key = api_key or get_settings().companies_house_api_key
        if not self.api_key:
            raise RuntimeError(
                "COMPANIES_HOUSE_API_KEY is not set. This connector is not used by the "
                "synthetic-data demo pipeline; set the key only if you intend to call the "
                "live Companies House API directly."
            )
        self._client = httpx.Client(base_url=base_url, auth=(self.api_key, ""))

    def get_company_profile(self, company_number: str) -> CompanyProfile:
        response = self._client.get(f"/company/{company_number}")
        response.raise_for_status()
        return CompanyProfile.model_validate(response.json())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CompaniesHouseClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
