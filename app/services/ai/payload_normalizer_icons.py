from __future__ import annotations


class FaceAnalysisPayloadIconMixin:
    @staticmethod
    def _default_metric_section(mode_id: str) -> str:
        if mode_id == "proportions":
            return "proportions"
        if mode_id == "aesthetics":
            return "detailed_metrics"
        if mode_id == "best-photo-selector":
            return "photo_selection"
        if mode_id == "best-angle-finder":
            return "angle_breakdown"
        if mode_id == "dating-profile-score":
            return "dating_profile"
        if mode_id == "instagram-profile-score":
            return "instagram_profile"
        return "facial_analysis"

    @staticmethod
    def _default_icon(metric_id: str) -> str:
        if "eye" in metric_id:
            return "eye.fill"
        if "skin" in metric_id:
            return "drop.fill"
        if "jaw" in metric_id:
            return "triangle.fill"
        if "hair" in metric_id:
            return "comb.fill"
        if "symmetry" in metric_id:
            return "circle.lefthalf.filled"
        if "lip" in metric_id or "mouth" in metric_id:
            return "mouth.fill"
        if "confidence" in metric_id:
            return "heart.fill"
        if "photo" in metric_id or "composition" in metric_id or "crop" in metric_id:
            return "camera.fill"
        if "angle" in metric_id:
            return "viewfinder"
        if "lighting" in metric_id:
            return "sun.max.fill"
        if "background" in metric_id:
            return "rectangle.dashed"
        if "trust" in metric_id or "readiness" in metric_id:
            return "checkmark.seal.fill"
        if "instagram" in metric_id or "feed" in metric_id:
            return "square.grid.3x3.fill"
        return "face.smiling"

    @classmethod
    def _safe_icon_name(cls, value: object, metric_id: str) -> str:
        icon_name = cls._optional_string(value)
        aliases = {
            "bolt.heart.fill": "bolt.fill",
            "camera.viewfinder": "viewfinder",
            "checkmark.shield.fill": "checkmark.seal.fill",
            "circle.grid.cross.fill": "circle.grid.3x3.fill",
            "quote.bubble.fill": "text.bubble.fill",
            "shield.checkmark.fill": "checkmark.seal.fill",
        }
        if icon_name in aliases:
            return aliases[icon_name]
        safe_icons = {
            "arrow.left.and.right.circle",
            "arrow.turn.up.left",
            "arrow.turn.up.right",
            "bolt.fill",
            "bubble.left.and.bubble.right.fill",
            "calendar",
            "camera.fill",
            "checkmark.seal.fill",
            "circle.grid.3x3.fill",
            "circle.lefthalf.filled",
            "comb.fill",
            "crop",
            "drop.fill",
            "exclamationmark.triangle.fill",
            "eye.circle.fill",
            "eye.fill",
            "eyeglasses",
            "face.smiling",
            "heart.fill",
            "mouth.fill",
            "mustache.fill",
            "person.crop.square.fill",
            "rectangle.dashed",
            "rectangle.fill",
            "rectangle.portrait",
            "rectangle.stack.fill",
            "slider.horizontal.3",
            "sparkles",
            "square.grid.3x3.fill",
            "star.fill",
            "sun.max.fill",
            "text.bubble.fill",
            "triangle.fill",
            "viewfinder",
            "wand.and.stars",
            "xmark.circle.fill",
            "xmark.octagon.fill",
        }
        if icon_name in safe_icons:
            return icon_name
        return cls._default_icon(metric_id)
