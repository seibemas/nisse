from pydantic import BaseModel, field_validator
from typing import Optional

TINTS = ["teal", "indigo", "lime", "magenta"]
CATEGORIES = ["Jewelry", "Clothing", "Botanical wellness"]


class ProductCreate(BaseModel):
    name: str
    category: str
    price: str        # "$68" format
    short: str = ""
    long: str = ""
    materials: str = ""
    care: str = ""
    tint: Optional[str] = None   # auto-assigned if not provided
    sort_order: int = 0

    @field_validator("category")
    @classmethod
    def valid_category(cls, v):
        if v not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return v

    @field_validator("price")
    @classmethod
    def valid_price(cls, v):
        if not v.startswith("$") or len(v) < 2 or not v[1:].lstrip("0123456789").replace(".", "").replace(",", "") == "" or not any(c.isdigit() for c in v[1:]):
            raise ValueError('price must start with "$" and have a digit after it, e.g. "$68"')
        return v

    @field_validator("tint")
    @classmethod
    def valid_tint(cls, v):
        if v is not None and v not in TINTS:
            raise ValueError(f"tint must be one of {TINTS}")
        return v


class ProductUpdate(BaseModel):
    """All fields optional — only provided fields are updated."""
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    short: Optional[str] = None
    long: Optional[str] = None
    materials: Optional[str] = None
    care: Optional[str] = None
    tint: Optional[str] = None
    sold: Optional[bool] = None
    sort_order: Optional[int] = None

    @field_validator("category")
    @classmethod
    def valid_category(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return v

    @field_validator("price")
    @classmethod
    def valid_price(cls, v):
        if v is not None:
            if not v.startswith("$") or len(v) < 2 or not any(c.isdigit() for c in v[1:]):
                raise ValueError('price must start with "$" and have a digit after it, e.g. "$68"')
        return v

    @field_validator("tint")
    @classmethod
    def valid_tint(cls, v):
        if v is not None and v not in TINTS:
            raise ValueError(f"tint must be one of {TINTS}")
        return v


class ProductResponse(BaseModel):
    """What the API returns for a product."""
    slug: str
    name: str
    category: str
    price: str
    short: str
    long: str
    materials: str
    care: str
    tint: str
    photo: Optional[str] = None
    sold: bool
    sort_order: int
    created_at: str
    updated_at: str


class StatusResponse(BaseModel):
    unpublished_count: int
    last_published_at: Optional[str] = None
    total_products: int
