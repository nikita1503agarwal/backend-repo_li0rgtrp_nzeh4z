"""
Database Schemas for Smart Restaurant

Each Pydantic model represents a MongoDB collection. The collection name
is the lowercase of the class name (e.g., MenuItem -> "menuitem").
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl

# -----------------------------
# Core Collections
# -----------------------------

class MenuItem(BaseModel):
    name: str = Field(..., description="Dish name")
    description: Optional[str] = Field(None, description="Dish description")
    price: float = Field(..., ge=0, description="Price in local currency")
    category: Optional[str] = Field(None, description="Category like Starters, Main Course")
    image_url: Optional[HttpUrl] = Field(None, description="Image URL for the dish")
    is_available: bool = Field(True, description="Whether this item is currently available")

class Table(BaseModel):
    number: int = Field(..., ge=1, description="Table number visible in the restaurant")
    label: Optional[str] = Field(None, description="Optional label like Window-1")
    qr_path: Optional[str] = Field(None, description="Path/URL to generated QR code image for this table")

class OrderItem(BaseModel):
    item_id: str = Field(..., description="Menu item ObjectId as string")
    name: str = Field(..., description="Item name at the time of order")
    price: float = Field(..., ge=0, description="Unit price at the time of order")
    quantity: int = Field(..., ge=1, description="Quantity ordered")

class Order(BaseModel):
    table_id: str = Field(..., description="Table ObjectId as string")
    items: List[OrderItem]
    subtotal: float = Field(..., ge=0)
    payment_method: Literal["online", "cash"] = Field(...)
    status: Literal["pending", "preparing", "served", "completed", "cancelled"] = Field("pending")
    payment_status: Literal["unpaid", "pending", "paid", "failed"] = Field("unpaid")
    notes: Optional[str] = None

class PaymentRecord(BaseModel):
    order_id: str = Field(..., description="Order ObjectId as string")
    provider: Literal["razorpay", "stripe", "paytm", "mock"] = Field("mock")
    amount: float = Field(..., ge=0)
    currency: str = Field("INR")
    status: Literal["created", "pending", "succeeded", "failed"] = Field("created")
    transaction_id: Optional[str] = None
    metadata: Optional[dict] = Field(default_factory=dict)

# Notes:
# - Use create_document/get_documents from database.py for inserts/queries
# - You can import these classes for request validation in FastAPI routes
