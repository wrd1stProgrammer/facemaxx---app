"""One real API request with transport/stream timings; no user data or DB writes."""
import asyncio
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from unittest.mock import patch
from types import SimpleNamespace

import httpx
from openai import AsyncOpenAI
from app.core.config import Settings
from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.openai_provider import OpenAIFaceAnalysisProvider


async def main():
    settings = Settings(ai_provider='openai', openai_model='gpt-6-luna')
    start = perf_counter()
    attempts = []

    async def request_hook(request):
        attempts.append(perf_counter() - start)

    async def response_hook(response):
        print(json.dumps(dict(event='http_headers', seconds=round(perf_counter()-start, 3),
                              status=response.status_code, attempt=len(attempts))), flush=True)

    async with AsyncOpenAI(api_key=settings.openai_api_key,
        http_client=httpx.AsyncClient(event_hooks={'request':[request_hook], 'response':[response_hook]})) as client:
        async def traced_create(**kwargs):
            text = kwargs['input'][0]['content'][0]['text']
            print(json.dumps(dict(event='request', model=kwargs['model'], prompt_chars=len(text),
                schema_chars=len(json.dumps(kwargs['text'])), photo_bytes=len(photo))), flush=True)
            seen = set()
            async with client.responses.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type in ('response.created', 'response.output_text.delta') and event.type not in seen:
                        seen.add(event.type)
                        print(json.dumps(dict(event=event.type, seconds=round(perf_counter()-start, 3))), flush=True)
                result = await stream.get_final_response()
            print(json.dumps(dict(event='completed', seconds=round(perf_counter()-start, 3),
                attempts=len(attempts), returned_model=result.model,
                usage=result.usage.model_dump() if result.usage else None,
                reasoning=result.reasoning.model_dump() if result.reasoning else None,
                output_chars=len(result.output_text))), flush=True)
            raw = json.loads(result.output_text)
            metrics = raw.get('metrics', [])
            print(json.dumps(dict(event='quality', raw_metrics=len(metrics),
                empty_details=sum(not m.get('detail_text') for m in metrics),
                detail_chars=[len(m.get('detail_text') or '') for m in metrics],
                summary=raw.get('summary_text'),
                example_details=[m.get('detail_text') for m in metrics[:2]]), ensure_ascii=False), flush=True)
            return result

        photo = Path('../Facemaxx/Resources/Assets.xcassets/StudioCover_makeup.imageset/cover.jpg').read_bytes()
        with patch('app.services.ai.openai_provider._shared_client', return_value=SimpleNamespace(
                responses=SimpleNamespace(create=traced_create))):
            result = await OpenAIFaceAnalysisProvider(settings).analyze(ProviderAnalysisRequest(
                user_id=None, mode_id='proportions', locale='ko', photo_id=uuid4(),
                photo_bytes=photo, photo_mime_type='image/jpeg'))
        print(json.dumps(dict(event='validated', seconds=round(perf_counter()-start, 3), metrics=len(result.metrics))), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
