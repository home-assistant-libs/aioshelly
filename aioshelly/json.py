"""JSON helper."""

from typing import Any

import orjson

json_loads = orjson.loads


def json_encoder_default(obj: Any) -> Any:
    """Convert objects."""
    if isinstance(obj, (set, tuple)):
        return list(obj)
    raise TypeError


def json_dumps(data: Any) -> str:
    """Dump json string.

    orjson supports serializing dataclasses natively which
    eliminates the need to implement as_dict in many places
    when the data is already in a dataclass. This works
    well as long as all the data in the dataclass can also
    be serialized.

    If it turns out to be a problem we can disable this
    with option |= orjson.OPT_PASSTHROUGH_DATACLASS and it
    will fallback to as_dict
    """
    return orjson.dumps(
        data, option=orjson.OPT_NON_STR_KEYS, default=json_encoder_default
    ).decode("utf-8")
