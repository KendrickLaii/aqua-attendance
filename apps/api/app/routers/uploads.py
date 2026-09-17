from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.deps import AdminOnly
from app.schemas.upload import UploadOut
from app.services.media_storage import (
    MediaStorageError,
    content_type_for_key,
    resolve_upload_path,
    save_bytes,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadOut)
async def upload_media(file: UploadFile, _admin: AdminOnly) -> UploadOut:
    content = await file.read()
    try:
        saved = save_bytes(content)
    except MediaStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UploadOut(
        url=saved.url,
        key=saved.key,
        content_type=saved.content_type,
        size=saved.size,
    )


@router.get("/{key:path}")
async def get_media(key: str) -> FileResponse:
    try:
        path = resolve_upload_path(key)
    except MediaStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc

    return FileResponse(
        path,
        media_type=content_type_for_key(key),
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
