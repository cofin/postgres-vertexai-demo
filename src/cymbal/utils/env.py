"""Environment variable utilities with type-safe parsing."""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeVar, cast, get_args, get_origin, overload

TRUE_VALUES: Final[frozenset[str]] = frozenset({"True", "true", "1", "yes", "YES", "Y", "y", "T", "t"})

T = TypeVar("T")
ParseTypes = bool | int | float | str | list[str] | Path | list[Path] | dict[str, Any]


class UnsetType:
    """Placeholder for an Unset type."""


_UNSET = UnsetType()


@overload
def get_env(key: str, default: bool, type_hint: UnsetType = _UNSET) -> Callable[[], bool]: ...


@overload
def get_env(key: str, default: int, type_hint: UnsetType = _UNSET) -> Callable[[], int]: ...


@overload
def get_env(key: str, default: str, type_hint: UnsetType = _UNSET) -> Callable[[], str]: ...


@overload
def get_env(key: str, default: float, type_hint: UnsetType = _UNSET) -> Callable[[], float]: ...


@overload
def get_env(key: str, default: Path, type_hint: UnsetType = _UNSET) -> Callable[[], Path]: ...


@overload
def get_env(key: str, default: list[str], type_hint: UnsetType = _UNSET) -> Callable[[], list[str]]: ...


@overload
def get_env(key: str, default: None, type_hint: UnsetType = _UNSET) -> Callable[[], None]: ...


@overload
def get_env(key: str, default: ParseTypes | None, type_hint: type[T]) -> Callable[[], T]: ...


@overload
def get_env(key: str, default: dict[str, Any], type_hint: UnsetType = _UNSET) -> Callable[[], dict[str, Any]]: ...


def get_env(
    key: str, default: ParseTypes | None, type_hint: type[T] | UnsetType = _UNSET
) -> Callable[[], ParseTypes | T | None]:
    """Return a lambda that gets configuration value from environment."""
    return lambda: get_config_val(key=key, default=default, type_hint=type_hint)


def _determine_final_type(default: ParseTypes | None, type_hint: type[T] | UnsetType) -> type | None:
    """Determine the final type for parsing."""
    if type_hint != _UNSET and isinstance(type_hint, type):
        return type_hint
    if default is not None:
        return type(default)
    return None


def _parse_basic_type(key: str, value: str, final_type: type | None, default: ParseTypes | None) -> ParseTypes | None:
    """Parse basic types (str, int, float, bool)."""
    if final_type is str or default is None:
        return value
    if final_type is int:
        try:
            return int(value)
        except ValueError as e:
            msg = f"Cannot convert '{value}' to int for key '{key}'"
            raise ValueError(msg) from e
    if final_type is float:
        try:
            return float(value)
        except ValueError as e:
            msg = f"Cannot convert '{value}' to float for key '{key}'"
            raise ValueError(msg) from e
    if final_type is bool:
        return value in TRUE_VALUES
    return value


def get_config_val(
    key: str, default: ParseTypes | None, type_hint: type[T] | UnsetType = _UNSET
) -> ParseTypes | T | None:
    """Parse environment variables with proper type handling.

    Args:
        key: Environment variable key
        default: Default value if key not found
        type_hint: Optional type hint override

    Returns:
        Parsed value of specified type
    """
    str_value = os.getenv(key)
    if str_value is None:
        return default

    value: str = str_value
    final_type = _determine_final_type(default, type_hint)

    # Handle Path type
    if final_type is Path or isinstance(default, Path):
        return Path(value)

    # Handle list types
    if final_type and get_origin(final_type) is list:
        args = get_args(final_type)
        item_type = cast("type", args[0]) if args else str
        return _parse_list(key, value, item_type)
    if isinstance(default, list):
        item_type = type(default[0]) if default else str
        return cast("list[str]", _parse_list(key, value, item_type))

    # Handle dict types
    if final_type is dict or isinstance(default, dict):
        return _parse_dict(key, value)

    # Handle basic types
    return _parse_basic_type(key, value, final_type, default)


def _parse_list(key: str, value: str, item_constructor: type[T]) -> list[T]:
    """Parse list from environment value."""

    def _coerce_item(item: Any) -> T:
        if item_constructor is bool:
            if isinstance(item, bool):
                return cast("T", item)
            if isinstance(item, (int, float)):
                return cast("T", bool(item))
            return cast("T", str(item).strip() in TRUE_VALUES)
        return item_constructor(item)  # type: ignore[call-arg]

    if value.startswith("[") and value.endswith("]"):
        try:
            parsed_json = json.loads(value)
            if not isinstance(parsed_json, list):
                msg = f"'{key}' is not a valid list representation"
                raise TypeError(msg)
            return [_coerce_item(item) for item in parsed_json]
        except (json.JSONDecodeError, ValueError) as e:
            msg = f"'{key}' is not a valid JSON list"
            raise ValueError(msg) from e

    # Split by comma
    items = [item.strip() for item in value.split(",") if item.strip()]
    try:
        return [_coerce_item(item) for item in items]
    except (ValueError, TypeError) as e:
        msg = f"Error parsing list items for '{key}': {e}"
        raise ValueError(msg) from e


def _parse_dict(key: str, value: str) -> dict[str, Any]:
    """Parse dict from environment value."""
    # Try JSON first
    if value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                msg = f"'{key}' is not a valid dict representation"
                raise TypeError(msg)
            return parsed  # noqa: TRY300
        except json.JSONDecodeError as e:
            msg = f"'{key}' is not valid JSON"
            raise ValueError(msg) from e

    # Try comma-separated key=value pairs
    result: dict[str, Any] = {}
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            msg = f"'{key}' invalid format: missing '=' in '{item}'"
            raise ValueError(msg)
        k, v = item.split("=", 1)
        result[k.strip()] = v.strip()

    return result
