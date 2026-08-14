from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChartAgentError(Exception):
    code: str
    message: str
    status_code: int
    recovery: str | None = None

    def __str__(self) -> str:
        return self.message


class InvalidSymbolError(ChartAgentError):
    def __init__(self, symbol: str) -> None:
        super().__init__(
            code="invalid_symbol",
            message=f"이미지에서 판독한 {symbol} 심볼을 확인할 수 없습니다.",
            status_code=422,
            recovery="종목 심볼과 시간대가 보이는 차트 캡처를 올려 주세요.",
        )


class InvalidChartError(ChartAgentError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=422,
            recovery="종목명, 시간대, 캔들, 가격 축이 보이는 차트 캡처를 올려 주세요.",
        )


class DependencyError(ChartAgentError):
    def __init__(self, service: str) -> None:
        super().__init__(
            code="dependency_unavailable",
            message=f"{service} 연결을 사용할 수 없습니다.",
            status_code=503,
            recovery="잠시 후 다시 시도해 주세요.",
        )


class AnalysisUnavailableError(ChartAgentError):
    def __init__(self) -> None:
        super().__init__(
            code="analysis_unavailable",
            message="분석을 완료하지 못했습니다.",
            status_code=502,
            recovery="네트워크를 확인한 뒤 다시 시도해 주세요.",
        )
