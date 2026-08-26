from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, HttpUrl, field_validator

# Not exhaustive ISO 4217 — enough common codes for a portfolio-scale fixture set.
KNOWN_CURRENCIES = {
    "USD", "EUR", "GBP", "CHF", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK", "SGD",
}


class VendorFundingRoundRecord(BaseModel):
    vendor_round_id: str
    company_name: str
    round_type: str
    amount: Decimal
    currency: str
    announced_on: date

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: object) -> Decimal:
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"amount is not a valid decimal: {value!r}") from exc

    @field_validator("amount")
    @classmethod
    def amount_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError(f"amount must be non-negative, got {value}")
        return value

    @field_validator("currency")
    @classmethod
    def currency_is_known_iso4217(cls, value: str) -> str:
        if value not in KNOWN_CURRENCIES:
            raise ValueError(f"currency is not a recognized ISO 4217 code: {value!r}")
        return value

    @field_validator("announced_on", mode="before")
    @classmethod
    def parse_announced_on(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"announced_on is not a valid ISO date: {value!r}") from exc
        return value


class VendorInvestorRecord(BaseModel):
    vendor_investor_id: str
    investor_name: str
    domain: str
    country: str


class CommunicationRecord(BaseModel):
    communication_id: str
    communication_type: str
    sensitivity: Literal["public", "internal", "restricted"]
    occurred_at: datetime
    participants: list[str]
    raw_text: str
    redacted_text: str


class OfficialDocumentRecord(BaseModel):
    document_id: str
    source_id: str
    url: HttpUrl
    title: str
    published_at: datetime
    retrieved_at: datetime
    full_text: str
    claim_span: str
