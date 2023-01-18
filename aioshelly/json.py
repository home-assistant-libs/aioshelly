"""JSON helper."""

from typing import Any

import orjson

JSONDecodeError = orjson.JSONDecodeError  # pylint: disable=no-member
json_loads = orjson.loads  # pylint: disable=no-member


def json_encoder_default(obj: Any) -> Any:
    """Convert objects."""
    if isinstance(obj, (set, tuple)):
        return list(obj)
    raise TypeError


def json_dumps(data: Any) -> str:
    """Dump json string."""
    return orjson.dumps(  # pylint: disable=no-member
        data,
        option=orjson.OPT_NON_STR_KEYS,  # pylint: disable=no-member
        default=json_encoder_default,
    ).decode("utf-8")
