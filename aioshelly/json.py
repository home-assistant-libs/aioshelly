"""JSON helper."""

from typing import Any

import orjson

JSONDecodeError = orjson.JSONDecodeError
json_loads = orjson.loads


def json_encoder_default(obj: Any) -> Any:
    """Convert objects."""
    if isinstance(obj, set | tuple):
        return list(obj)
    raise TypeError


def json_dumps(data: Any) -> str:
    """Dump json string."""
    return orjson.dumps(
        data,
        option=orjson.OPT_NON_STR_KEYS,
        default=json_encoder_default,
    ).decode("utf-8")


def json_bytes(data: Any) -> bytes:
    """Dump json bytes."""
    return orjson.dumps(
        data,
        option=orjson.OPT_NON_STR_KEYS,
        default=json_encoder_default,
    )
