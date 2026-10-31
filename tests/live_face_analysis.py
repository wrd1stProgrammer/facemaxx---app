"""Explicit paid API smoke test; no production database or credit mutations."""
import asyncio
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.core.config import Settings
from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.openai_provider import OpenAIFaceAnalysisProvider, close_face_analysis_client


async def main():
    settings = Settings(ai_provider='openai', openai_model='gpt-6-luna')
    print(json.dumps(dict(test_model=settings.openai_model)), flush=True)
    photo = Path('../Facemaxx/Resources/Assets.xcassets/StudioCover_makeup.imageset/cover.jpg').read_bytes()
    provider = OpenAIFaceAnalysisProvider(settings)
    try:
        for mode in ('proportions', 'aesthetics'):
            started = perf_counter()
            try:
                result = await asyncio.wait_for(provider.analyze(ProviderAnalysisRequest(
                    user_id=None, mode_id=mode, locale='ko', photo_id=uuid4(),
                    photo_bytes=photo, photo_mime_type='image/jpeg',
                )), timeout=540)
                print(json.dumps(dict(mode=mode, model=provider.model_name,
                    seconds=round(perf_counter()-started, 2),
                    summary_chars=len(result.summary_text or ''),
                    rings=len(result.rings), metrics=len(result.metrics),
                    empty_details=sum(not m.detail_text for m in result.metrics),
                    valid=True)), flush=True)
            except Exception as exc:
                print(json.dumps(dict(mode=mode, model=provider.model_name,
                    seconds=round(perf_counter()-started, 2), valid=False,
                    error_type=type(exc).__name__, status=getattr(exc, 'status_code', None))), flush=True)
                break
    finally:
        await close_face_analysis_client()


if __name__ == '__main__':
    asyncio.run(main())
