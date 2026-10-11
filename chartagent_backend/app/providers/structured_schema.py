from pydantic import BaseModel


def _strict_schema(model: type[BaseModel]) -> dict[str, object]:
    schema = model.model_json_schema()
    _normalize_schema(schema)
    return schema


def _normalize_schema(value: object) -> None:
    if isinstance(value, list):
        for child in value:
            _normalize_schema(child)
        return
    if not isinstance(value, dict):
        return
    properties = value.get("properties")
    if isinstance(properties, dict):
        value["additionalProperties"] = False
        value["required"] = list(properties.keys())
    value.pop("default", None)
    for child in value.values():
        _normalize_schema(child)
