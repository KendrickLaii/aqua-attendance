from pydantic import BaseModel, Field, field_validator


class LocationDetailPhoto(BaseModel):
    """One gallery/detail image for a location (URL only in v1)."""

    url: str = Field(min_length=1, max_length=500)
    caption: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("url", "caption", mode="before")
    @classmethod
    def strip_strings(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("must be a string")
        trimmed = v.strip()
        return trimmed if trimmed else None
