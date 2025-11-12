import os
from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from io import BytesIO

from database import (
    db,
    create_document,
    get_documents,
    get_document_by_id,
    update_document,
)

app = FastAPI(title="Smart Restaurant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Schemas for request bodies
# -----------------------------

class MenuCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool = True

class MenuUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None

class OrderItemIn(BaseModel):
    item_id: str
    quantity: int = Field(..., ge=1)

class OrderCreate(BaseModel):
    table_id: str
    items: List[OrderItemIn]
    payment_method: Literal["online", "cash"]
    notes: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "preparing", "served", "completed", "cancelled"]

class PaymentConfirm(BaseModel):
    order_id: str
    status: Literal["succeeded", "failed"]

# -----------------------------
# Health/Test
# -----------------------------

@app.get("/")
def root():
    return {"message": "Smart Restaurant API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    return response

# -----------------------------
# Menu Endpoints
# -----------------------------

@app.get("/api/menu")
def list_menu(category: Optional[str] = None):
    filt = {"is_available": True}
    if category:
        filt["category"] = category
    items = get_documents("menuitem", filt, sort=[("name", 1)])
    return {"items": items}

@app.post("/api/menu")
def create_menu_item(payload: MenuCreate):
    item_id = create_document("menuitem", payload.model_dump())
    return {"id": item_id}

@app.put("/api/menu/{item_id}")
def update_menu_item(item_id: str, payload: MenuUpdate):
    ok = update_document("menuitem", item_id, {k: v for k, v in payload.model_dump().items() if v is not None})
    if not ok:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return {"success": True}

# -----------------------------
# Order Endpoints
# -----------------------------

@app.post("/api/order")
def create_order(payload: OrderCreate):
    # Fetch menu to price securely
    ids = [it.item_id for it in payload.items]
    from bson import ObjectId
    menu_docs = list(db.menuitem.find({"_id": {"$in": [ObjectId(i) for i in ids]}}))
    price_map = {str(doc["_id"]): float(doc.get("price", 0)) for doc in menu_docs}
    name_map = {str(doc["_id"]): doc.get("name", "Item") for doc in menu_docs}

    order_items = []
    subtotal = 0.0
    for it in payload.items:
        price = price_map.get(it.item_id)
        if price is None:
            raise HTTPException(status_code=400, detail=f"Invalid item_id {it.item_id}")
        line_total = price * it.quantity
        subtotal += line_total
        order_items.append({
            "item_id": it.item_id,
            "name": name_map.get(it.item_id, "Item"),
            "price": price,
            "quantity": it.quantity,
            "line_total": line_total,
        })

    order_doc = {
        "table_id": payload.table_id,
        "items": order_items,
        "subtotal": round(subtotal, 2),
        "payment_method": payload.payment_method,
        "status": "pending",
        "payment_status": "unpaid" if payload.payment_method == "cash" else "pending",
        "notes": payload.notes,
    }
    order_id = create_document("order", order_doc)

    # For online, create a mock payment record and return a test URL
    payment = None
    if payload.payment_method == "online":
        payment = {
            "order_id": order_id,
            "provider": "mock",
            "amount": round(subtotal, 2),
            "currency": "INR",
            "status": "pending",
            "transaction_id": None,
        }
        payment_id = create_document("paymentrecord", payment)
        payment = {"id": payment_id, **payment}

    return {"order_id": order_id, "subtotal": round(subtotal, 2), "payment": payment}

@app.get("/api/order/{order_id}")
def get_order(order_id: str):
    order = get_document_by_id("order", order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return order

@app.get("/api/orders")
def list_orders(table_id: Optional[str] = Query(None)):
    filt = {"table_id": table_id} if table_id else {}
    orders = get_documents("order", filt, sort=[("created_at", -1)])
    return {"orders": orders}

@app.patch("/api/order/{order_id}/status")
def set_order_status(order_id: str, payload: OrderStatusUpdate):
    ok = update_document("order", order_id, {"status": payload.status})
    if not ok:
        raise HTTPException(404, "Order not found")
    return {"success": True}

# -----------------------------
# Mock Payment Endpoints
# -----------------------------

@app.post("/api/payment/mock/confirm")
def confirm_mock_payment(payload: PaymentConfirm):
    order = get_document_by_id("order", payload.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if payload.status == "succeeded":
        update_document("order", payload.order_id, {"payment_status": "paid"})
        return {"success": True, "order_id": payload.order_id, "payment_status": "paid"}
    else:
        update_document("order", payload.order_id, {"payment_status": "failed"})
        return {"success": True, "order_id": payload.order_id, "payment_status": "failed"}

# -----------------------------
# Admin helpers
# -----------------------------

@app.get("/api/admin/orders")
def admin_orders():
    return {"orders": get_documents("order", {}, sort=[("created_at", -1)])}

@app.get("/api/admin/stats")
def admin_stats():
    # simple aggregates
    total_orders = db["order"].count_documents({})
    paid_orders = list(db["order"].find({"payment_status": "paid"}))
    sales = sum(float(o.get("subtotal", 0)) for o in paid_orders)
    return {"total_orders": total_orders, "paid_orders": len(paid_orders), "total_sales": round(sales, 2)}

# -----------------------------
# QR Code generation for a table
# -----------------------------

@app.get("/api/qr/{table_number}")
def generate_qr(table_number: int):
    try:
        import qrcode
    except Exception:
        raise HTTPException(500, "QR library not installed")

    base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    url = f"{base_url}/?table={table_number}"

    qr_img = qrcode.make(url)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
