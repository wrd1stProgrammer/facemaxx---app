from __future__ import annotations

from math import atan2, degrees
from statistics import fmean

from app.schemas.analysis import FaceGeometryPayload, FaceMetricMeasurement


def calculate_face_metrics(geometry: FaceGeometryPayload) -> list[FaceMetricMeasurement]:
    metrics: list[FaceMetricMeasurement] = []

    metrics.extend(_mesh_metrics(geometry.vertices))

    if geometry.landmarks_2d:
        metrics.extend(_landmark_metrics(geometry.landmarks_2d))

    if not metrics:
        metrics.append(
            FaceMetricMeasurement(
                metric_group="quality",
                metric_id="capture_payload",
                display_value="No geometry",
                interpretation_key="analysis.capture.metric.noGeometry",
                interpretation_label_en="No geometry",
                interpretation_label_ko="얼굴 데이터 없음",
                confidence=0,
                source=geometry.provider,
            )
        )

    return metrics


def _mesh_metrics(vertices: list[list[float]]) -> list[FaceMetricMeasurement]:
    if not vertices:
        return []

    points = [_to_xyz(vertex) for vertex in vertices if len(vertex) >= 3]
    if not points:
        return []

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]

    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    depth = max(zs) - min(zs)
    center_x = (max(xs) + min(xs)) / 2
    left_width = abs(center_x - min(xs))
    right_width = abs(max(xs) - center_x)

    metrics = [
        FaceMetricMeasurement(
            metric_group="quality",
            metric_id="face_structure_point_count",
            numeric_value=float(len(points)),
            unit="reference_points",
            display_value=f"{len(points)} reference points",
            interpretation_key="analysis.capture.metric.structureReady",
            interpretation_label_en="Structure reference ready",
            interpretation_label_ko="얼굴 구조 참고값 확보",
            confidence=1.0,
            source="face_geometry",
        )
    ]

    if width > 0 and height > 0:
        ratio = width / height
        label_en, label_ko, key = _range_label(
            ratio,
            low=0.60,
            high=0.82,
            low_label=("Longer", "세로형"),
            ok_label=("Balanced", "균형 범위"),
            high_label=("Broader", "가로형"),
            key_prefix="analysis.capture.metric.faceWidthHeight",
        )
        metrics.append(
            FaceMetricMeasurement(
                metric_group="proportions",
                metric_id="face_width_height_ratio",
                numeric_value=round(ratio, 4),
                display_value=f"{ratio:.2f} · {label_en}",
                interpretation_key=key,
                interpretation_label_en=label_en,
                interpretation_label_ko=label_ko,
                confidence=0.78,
                source="arkit_geometry",
                metadata={"width": width, "height": height},
            )
        )

    if width > 0 and depth > 0:
        ratio = depth / width
        label_en, label_ko, key = _range_label(
            ratio,
            low=0.34,
            high=0.58,
            low_label=("Flat", "평면적"),
            ok_label=("Normal Range", "정상 범위"),
            high_label=("Projected", "입체적"),
            key_prefix="analysis.capture.metric.depthWidth",
        )
        metrics.append(
            FaceMetricMeasurement(
                metric_group="proportions",
                metric_id="face_depth_width_ratio",
                numeric_value=round(ratio, 4),
                display_value=f"{ratio:.2f} · {label_en}",
                interpretation_key=key,
                interpretation_label_en=label_en,
                interpretation_label_ko=label_ko,
                confidence=0.72,
                source="arkit_geometry",
                metadata={"depth": depth, "width": width},
            )
        )

    if left_width > 0 and right_width > 0:
        symmetry = 1 - abs(left_width - right_width) / max(left_width, right_width)
        label_en, label_ko, key = _range_label(
            symmetry,
            low=0.86,
            high=1.01,
            low_label=("Asymmetric", "비대칭"),
            ok_label=("Balanced", "균형"),
            high_label=("Balanced", "균형"),
            key_prefix="analysis.capture.metric.structureSymmetry",
        )
        metrics.append(
            FaceMetricMeasurement(
                metric_group="aesthetics",
                metric_id="structure_symmetry_score",
                numeric_value=round(symmetry, 4),
                display_value=f"{symmetry * 10:.1f} · {label_en}",
                interpretation_key=key,
                interpretation_label_en=label_en,
                interpretation_label_ko=label_ko,
                confidence=0.62,
                source="arkit_geometry",
            )
        )

    return metrics


def _landmark_metrics(landmarks: dict[str, list[list[float]]]) -> list[FaceMetricMeasurement]:
    metrics: list[FaceMetricMeasurement] = []

    left_eye = _points2d(landmarks.get("leftEye", []))
    right_eye = _points2d(landmarks.get("rightEye", []))
    face_contour = _points2d(landmarks.get("faceContour", []))

    if left_eye and right_eye:
        left_eye_width = _point_width(left_eye)
        right_eye_width = _point_width(right_eye)
        eye_width_values = [value for value in [left_eye_width, right_eye_width] if value > 0]
        eye_width = fmean(eye_width_values) if eye_width_values else 0
        eye_distance = abs(_center(left_eye)[0] - _center(right_eye)[0])

        if eye_width > 0:
            ratio = eye_distance / eye_width
            label_en, label_ko, key = _range_label(
                ratio,
                low=1.85,
                high=2.35,
                low_label=("Close-set", "가까운 눈 간격"),
                ok_label=("Balanced", "균형 범위"),
                high_label=("Wide-set", "넓은 눈 간격"),
                key_prefix="analysis.capture.metric.eyeSpacing",
            )
            metrics.append(
                FaceMetricMeasurement(
                    metric_group="proportions",
                    metric_id="eye_spacing_ratio",
                    numeric_value=round(ratio, 4),
                    display_value=f"{ratio:.2f} · {label_en}",
                    interpretation_key=key,
                    interpretation_label_en=label_en,
                    interpretation_label_ko=label_ko,
                    confidence=0.82,
                    source="vision_landmarks",
                )
            )

        tilt = _average_canthal_tilt(left_eye, right_eye)
        if tilt is not None:
            if abs(tilt) > 14:
                label_en = "Angle affected"
                label_ko = "촬영 각도 영향"
                key_suffix = "angleAffected"
                confidence = 0.45
            else:
                label_en = "Positive" if tilt >= 2 else "Neutral" if tilt >= -2 else "Negative"
                label_ko = "긍정 각도" if tilt >= 2 else "중립 각도" if tilt >= -2 else "하향 각도"
                key_suffix = "positive" if tilt >= 2 else "neutral" if tilt >= -2 else "negative"
                confidence = 0.80
            metrics.append(
                FaceMetricMeasurement(
                    metric_group="proportions",
                    metric_id="canthal_tilt",
                    numeric_value=round(tilt, 4),
                    unit="degrees",
                    display_value=f"{tilt:.1f}° · {label_en}",
                    interpretation_key=f"analysis.capture.metric.canthalTilt.{key_suffix}",
                    interpretation_label_en=label_en,
                    interpretation_label_ko=label_ko,
                    confidence=confidence,
                    source="vision_landmarks",
                )
            )

    if face_contour:
        width = _point_width(face_contour)
        height = _point_height(face_contour)
        if width > 0 and height > 0:
            ratio = width / height
            label_en, label_ko, key = _range_label(
                ratio,
                low=0.62,
                high=0.82,
                low_label=("Longer", "세로형"),
                ok_label=("Balanced", "균형 범위"),
                high_label=("Broader", "가로형"),
                key_prefix="analysis.capture.metric.faceContourRatio",
            )
            metrics.append(
                FaceMetricMeasurement(
                    metric_group="proportions",
                    metric_id="face_contour_width_height_ratio",
                    numeric_value=round(ratio, 4),
                    display_value=f"{ratio:.2f} · {label_en}",
                    interpretation_key=key,
                    interpretation_label_en=label_en,
                    interpretation_label_ko=label_ko,
                    confidence=0.76,
                    source="vision_landmarks",
                )
            )

    return metrics


def _range_label(
    value: float,
    low: float,
    high: float,
    low_label: tuple[str, str],
    ok_label: tuple[str, str],
    high_label: tuple[str, str],
    key_prefix: str,
) -> tuple[str, str, str]:
    if value < low:
        return low_label[0], low_label[1], f"{key_prefix}.low"
    if value <= high:
        return ok_label[0], ok_label[1], f"{key_prefix}.balanced"
    return high_label[0], high_label[1], f"{key_prefix}.high"


def _average_canthal_tilt(left_eye: list[tuple[float, float]], right_eye: list[tuple[float, float]]) -> float | None:
    tilts = [_eye_tilt(left_eye), _eye_tilt(right_eye)]
    valid = [tilt for tilt in tilts if tilt is not None]
    if not valid:
        return None
    roll = _line_tilt(_center(left_eye), _center(right_eye))
    return fmean(valid) - roll


def _eye_tilt(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None

    sorted_points = sorted(points, key=lambda point: point[0])
    left = sorted_points[0]
    right = sorted_points[-1]
    dx = right[0] - left[0]
    if abs(dx) < 0.0001:
        return None

    return _line_tilt(left, right)


def _line_tilt(left: tuple[float, float], right: tuple[float, float]) -> float:
    dx = right[0] - left[0]
    if abs(dx) < 0.0001:
        return 0
    return -degrees(atan2(right[1] - left[1], dx))


def _point_width(points: list[tuple[float, float]]) -> float:
    return max(point[0] for point in points) - min(point[0] for point in points)


def _point_height(points: list[tuple[float, float]]) -> float:
    return max(point[1] for point in points) - min(point[1] for point in points)


def _center(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        fmean(point[0] for point in points),
        fmean(point[1] for point in points),
    )


def _points2d(points: list[list[float]]) -> list[tuple[float, float]]:
    return [(float(point[0]), float(point[1])) for point in points if len(point) >= 2]


def _to_xyz(point: list[float]) -> tuple[float, float, float]:
    return float(point[0]), float(point[1]), float(point[2])
