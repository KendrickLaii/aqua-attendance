import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import DB, AdminOnly
from app.models.product import Product
from app.schemas.auth import QRPayload
from app.services import attendance as att_svc
from app.services.qr import issue_qr_token

router = APIRouter(prefix="/qr", tags=["qr"])


def _build_payload(product: Product) -> dict:
    token = issue_qr_token(str(product.id), product.qr_token_version)
    return {"qr_token": token, "token_version": product.qr_token_version}


@router.get("/token/{product_id}", response_model=QRPayload)
async def get_qr_token(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    """Return the current QR token for a product.

    The token has no expiry — it stays valid until the product's
    `qr_token_version` is bumped via the refresh endpoint.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=400, detail="Product is inactive")
    return _build_payload(product)


@router.post("/token/{product_id}/refresh", response_model=QRPayload)
async def refresh_qr_token(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    """Rotate the product's QR — invalidates any previously-issued QR.

    Use only when the existing QR has been lost or compromised; normal
    check-in / check-out does not need refresh.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=400, detail="Product is inactive")
    product = await att_svc.rotate_product_qr(db, product=product)
    return _build_payload(product)
