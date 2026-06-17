from __future__ import annotations

from postgrest.exceptions import APIError

from app.db.supabase import get_supabase_service_client
from app.schemas.flirtist_product import FlirtistProductSessionRequest, FlirtistProductSessionResponse
from app.services.flirtist_product_image_storage import FlirtistStoredImage


class FlirtistProductRepository:
    def save_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        response: FlirtistProductSessionResponse,
        stored_image: FlirtistStoredImage | None,
    ) -> bool:
        client = get_supabase_service_client()
        if client is None:
            return False
        payload = {
            "id": response.sessionId,
            "mode": response.mode,
            "source": response.source,
            "locale": response.locale,
            "language": response.language,
            "title": response.title,
            "input_text": request.text,
            "image_storage_path": stored_image.storage_path if stored_image else response.imageStoragePath,
            "image_url": stored_image.url if stored_image else response.imageUrl,
            "image_mime_type": stored_image.mime_type if stored_image else None,
            "chat_preview": [item.model_dump(mode="json") for item in response.chatPreview],
            "reply_coaching": response.replyCoaching.model_dump(mode="json") if response.replyCoaching else None,
            "analysis_card": response.analysisCard.model_dump(mode="json") if response.analysisCard else None,
            "raw_payload": request.model_dump(exclude={"imageBase64"}, mode="json"),
        }
        try:
            client.table("flirtist_sessions").insert(payload).execute()
        except (APIError, AttributeError, TypeError, ValueError):
            return False
        return True
