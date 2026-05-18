import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import DB, AdminOnly
from app.models.product import Product
from app.schemas.auth import QRPayload
from app.services.qr import issue_qr_token

router = APIRouter(prefix="/qr", tags=["qr"])


@router.get("/token/{product_id}", response_model=QRPayload)
async def get_qr_token(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    """Issue a short-lived signed QR token for a product (staff/student)."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=400, detail="Product is inactive")

    token, lifetime = issue_qr_token(str(product.id))
    return {"qr_token": token, "expires_in": lifetime}
