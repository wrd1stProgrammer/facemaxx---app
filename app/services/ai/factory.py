from app.core.config import get_settings
from app.services.ai.base import FaceAnalysisProvider
from app.services.ai.dummy import DummyFaceAnalysisProvider
from app.services.ai.openai_provider import OpenAIFaceAnalysisProvider


def get_face_analysis_provider() -> FaceAnalysisProvider:
    settings = get_settings()

    if settings.ai_provider == "dummy":
        return DummyFaceAnalysisProvider()
    return OpenAIFaceAnalysisProvider(settings)
