import pytest
from pydantic import ValidationError

from app.chart_annotations import ChartAnnotation, ChartAnnotationPlan, ImagePoint
from app.errors import AnalysisUnavailableError


def test_annotation_rejects_coordinates_outside_image() -> None:
    with pytest.raises(ValidationError):
        ImagePoint(x=1.2, y=0.3)


def test_annotation_rejects_zero_length_mark() -> None:
    point = ImagePoint(x=0.3, y=0.4)
    with pytest.raises(ValidationError):
        ChartAnnotation(id="a1", kind="line", title="지지 확인", detail="확인 가능한 지지 구간입니다.",
                        outlook="이탈하면 지지 해석을 무효화합니다.", tone="mint", points=[point, point], label_anchor=point)


def test_plan_accepts_unreadable_chart_without_inventing_marks() -> None:
    plan = ChartAnnotationPlan(summary="판독 가능한 가격 차트가 없습니다.", annotations=[])
    assert plan.annotations == []


def test_plan_rejects_duplicate_ids() -> None:
    mark = ChartAnnotation(id="a1", kind="line", title="고점 저항", detail="두 고점이 형성한 저항입니다.",
                           outlook="돌파 확인 전까지 저항이 유지됩니다.", tone="coral", points=[ImagePoint(x=0.2, y=0.3), ImagePoint(x=0.8, y=0.3)],
                           label_anchor=ImagePoint(x=0.5, y=0.15))
    with pytest.raises(ValidationError):
        ChartAnnotationPlan(summary="두 고점의 저항선입니다.", annotations=[mark, mark])


def test_channel_accepts_two_baseline_points_and_opposite_swing() -> None:
    mark = ChartAnnotation(id="a1", kind="channel", title="하락 채널", detail="평행 경계의 반복 접점입니다.",
                           outlook="상단 돌파 시 채널 지속 해석이 약해집니다.", tone="blue", points=[ImagePoint(x=0.2, y=0.3), ImagePoint(x=0.8, y=0.6), ImagePoint(x=0.5, y=0.2)],
                           label_anchor=ImagePoint(x=0.5, y=0.1))
    assert mark.kind == "channel"


def test_channel_rejects_opposite_boundary_outside_image() -> None:
    with pytest.raises(ValidationError):
        ChartAnnotation(id="a1", kind="channel", title="하락 채널", detail="평행 경계의 반복 접점입니다.",
                        outlook="상단 돌파 시 채널 지속 해석이 약해집니다.", tone="blue", points=[ImagePoint(x=0.2, y=0.3), ImagePoint(x=0.8, y=0.9), ImagePoint(x=0.5, y=0.95)],
                        label_anchor=ImagePoint(x=0.5, y=0.1))


def test_report_link_rejects_a_scenario_not_in_the_report() -> None:
    # Given a drawing linked to the third scenario, but a report with only two.
    mark = ChartAnnotation(id="a1", kind="line", title="상승 추세선", detail="높아지는 두 저점이 연결됩니다.",
                           outlook="선을 지키면 반등 유지, 이탈하면 반등 구조가 약해집니다.", scenario_index=2,
                           tone="mint", points=[ImagePoint(x=0.2, y=0.7), ImagePoint(x=0.8, y=0.5)],
                           label_anchor=ImagePoint(x=0.5, y=0.8))
    plan = ChartAnnotationPlan(summary="추세선 유지 여부로 반등 지속을 판단합니다.", annotations=[mark])
    # When the generated link is checked against the actual report, reject it.
    with pytest.raises(AnalysisUnavailableError):
        plan.validate_scenario_links(scenario_count=2)


@pytest.mark.parametrize("provider_name,use_fallback", [("codex_cli", False), ("codex_cli", True), ("openai_api", False)])
def test_v2_uses_report_context_and_dedicated_providers(monkeypatch, valid_payload, provider_name, use_fallback):
    from io import BytesIO
    from fastapi.testclient import TestClient
    from PIL import Image
    from app import chart_annotations as annotations, main
    from app.providers.codex_cli import CodexCLIError

    context = annotations.AnnotationReportContext(consensus=valid_payload.consensus,
        scenarios=[], structure=[], trend_evidence=["두 저점이 높아집니다."])
    calls = []

    class Provider:
        def __init__(self, name):
            self.name = name

        async def complete(self, *, prompt, image_path, response_model):
            calls.append(self.name)
            assert "두 저점이 높아집니다." in prompt
            assert image_path.exists()
            if self.name == "codex" and use_fallback:
                raise CodexCLIError("process_exit")
            return response_model(summary="추세선 유지 여부를 확인합니다.", annotations=[])

    settings = annotations.get_settings().model_copy(update={"chart_annotation_provider": provider_name})
    monkeypatch.setattr(annotations, "get_settings", lambda: settings)
    legacy_codex = main.service.codex
    monkeypatch.setattr(annotations, "_codex", Provider("codex"))
    monkeypatch.setattr(annotations, "_fallback", Provider("fallback"))
    image = BytesIO()
    Image.new("RGB", (640, 480)).save(image, format="PNG")
    client = TestClient(main.app)
    response = client.post("/v2/chart-annotations", data={"locale": "ko", "report_context": context.model_dump_json()},
        files={"image": ("chart.png", image.getvalue(), "image/png")})
    assert response.status_code == 200, response.text
    assert response.json()["image_width"] == 640
    assert response.json()["locale"] == "ko"
    expected = ["fallback"] if provider_name == "openai_api" else (["codex", "fallback"] if use_fallback else ["codex"])
    assert calls == expected
    assert main.service.codex is legacy_codex
    assert legacy_codex.model == "gpt-5.6-luna"
    assert legacy_codex.reasoning_effort == "low"
    assert annotations._admission.borrowed_tokens == 0
    assert client.post("/v1/chart-annotations").status_code == 404


def test_v2_rejects_invalid_context_and_can_be_disabled_without_disabling_v1(monkeypatch):
    from fastapi.testclient import TestClient
    from app import chart_annotations as annotations, main

    client = TestClient(main.app)
    files = {"image": ("chart.png", b"unused", "image/png")}
    response = client.post("/v2/chart-annotations", data={"report_context": "{}"}, files=files)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_annotation_context"
    assert annotations._admission.borrowed_tokens == 0
    settings = annotations.get_settings().model_copy(update={"chart_annotations_enabled": False})
    monkeypatch.setattr(annotations, "get_settings", lambda: settings)
    response = client.post("/v2/chart-annotations", data={"report_context": "{}"}, files=files)
    assert response.status_code == 503
    assert response.json()["code"] == "annotations_disabled"
    assert client.get("/health").json()["codex_model"] == "gpt-5.6-luna"
    assert "/v1/analysis-jobs" in client.get("/openapi.json").json()["paths"]


def test_trendline_extension_preserves_real_pivots() -> None:
    mark = ChartAnnotation(id="a1", kind="line", title="상승 추세선", detail="두 저점을 연결합니다.",
                           outlook="연장선 위에서 지지하면 반등이 유지됩니다.", tone="mint",
                           points=[ImagePoint(x=0.2, y=0.7), ImagePoint(x=0.5, y=0.5)],
                           label_anchor=ImagePoint(x=0.3, y=0.8), extend_to_x=0.8)
    assert mark.points[-1] == ImagePoint(x=0.5, y=0.5)
    assert mark.extend_to_x == 0.8


def test_trendline_rejects_extension_outside_the_image() -> None:
    with pytest.raises(ValidationError):
        ChartAnnotation(id="a1", kind="line", title="상승 추세선", detail="두 저점을 연결합니다.",
                        outlook="연장선 위에서 지지하면 반등이 유지됩니다.", tone="mint",
                        points=[ImagePoint(x=0.2, y=0.7), ImagePoint(x=0.5, y=0.2)],
                        label_anchor=ImagePoint(x=0.3, y=0.8), extend_to_x=0.9)
