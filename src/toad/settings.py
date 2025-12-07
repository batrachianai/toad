from __future__ import annotations

from collections.abc import Mapping
import copy
from functools import cached_property
from json import dumps
from dataclasses import dataclass
from typing import Callable, Iterable, KeysView, Sequence, TypedDict, Required

from toad._loop import loop_last


@dataclass
class Setting:
    """A setting or group of setting."""

    key: str
    title: str
    type: str = "object"
    help: str = ""
    choices: list[str] | None = None
    default: object | None = None
    validate: list[dict] | None = None
    children: dict[str, Setting] | None = None
    editable: bool = True


class SchemaDict(TypedDict, total=False):
    """Typing for schema data structure."""

    key: Required[str]
    title: Required[str]
    type: Required[str]
    help: str
    choices: list[str] | list[tuple[str, str]] | None
    default: object
    fields: list[SchemaDict]
    validate: list[dict]
    editable: bool


type SettingsType = dict[str, object]


INPUT_TYPES = {"boolean", "integer", "number", "string", "choices", "text"}


class SettingsError(Exception):
    """Base class for settings related errors."""


class InvalidKey(SettingsError):
    """The key is not in the schema."""


class InvalidValue(SettingsError):
    """The value was not of the expected type."""


def parse_key(key: str) -> Sequence[str]:
    return key.split(".")


def get_setting[ExpectType](
    settings: dict[str, object], key: str, expect_type: type[ExpectType] = object
) -> ExpectType:
    """Get a key from a settings structure.

    Args:
        settings: A settings dictionary.
        key: A dot delimited key, e.g. "ui.column"
        expect_type: The expected type of the value.

    Raises:
        InvalidValue: If the value is not the expected type.
        KeyError: If the key doesn't exist in settings.

    Returns:
        The value matching they key.
    """
    for last, key_component in loop_last(parse_key(key)):
        if last:
            result = settings[key_component]
            if not isinstance(result, expect_type):
                raise InvalidValue(
                    f"Expected {expect_type.__name__} type; found {result!r}"
                )
            return result
        else:
            sub_settings = settings.setdefault(key_component, {})
            assert isinstance(sub_settings, dict)
            settings = sub_settings
    raise KeyError(key)


class Schema:
    def __init__(self, schema: list[SchemaDict]) -> None:
        self.schema = schema

    def set_value(self, settings: SettingsType, key: str, value: object) -> None:
        schema = self.schema
        keys = parse_key(key)
        for last, key in loop_last(keys):
            if last:
                settings[key] = value
            if key not in schema:
                raise InvalidKey()
            schema = schema[key]
            assert isinstance(schema, dict)
            if key not in settings:
                settings = settings[key] = {}

    def get_default(self, key: str) -> object | None:
        """Get a default for the given key.

        Args:
            key: Key in dotted notation

        Returns:
            Default, or `None`.
        """
        defaults = self.defaults

        schema_object = defaults
        for last, sub_key in loop_last(parse_key(key)):
            if last:
                return schema_object.get(sub_key, None)
            else:
                if isinstance(schema_object, dict):
                    schema_object = schema_object.get(sub_key, {})
                else:
                    return None
        return None

    @cached_property
    def defaults(self) -> dict[str, object]:
        settings: dict[str, object] = {}

        def set_defaults(schema: list[SchemaDict], settings: dict[str, object]) -> None:
            sub_settings: SettingsType
            for sub_schema in schema:
                key = sub_schema["key"]
                assert isinstance(sub_schema, dict)
                type = sub_schema["type"]

                if type == "object":
                    if fields := sub_schema.get("fields"):
                        sub_settings = settings[key] = {}
                        set_defaults(fields, sub_settings)

                else:
                    if (default := sub_schema.get("default")) is not None:
                        settings[key] = default

        set_defaults(self.schema, settings)
        return settings

    @cached_property
    def key_to_type(self) -> Mapping[str, type]:
        TYPE_MAP = {
            "object": SchemaDict,
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "choices": str,
            "text": str,
        }

        def get_keys(setting: Setting) -> Iterable[tuple[str, type]]:
            if setting.type == "object" and setting.children:
                for child in setting.children.values():
                    yield from get_keys(child)
            else:
                yield (setting.key, TYPE_MAP[setting.type])

        keys = {
            key: value_type
            for setting in self.settings_map.values()
            for key, value_type in get_keys(setting)
        }
        return keys

    @property
    def keys(self) -> KeysView:
        return self.key_to_type.keys()

    @cached_property
    def settings_map(self) -> dict[str, Setting]:
        form_settings: dict[str, Setting] = {}

        def build_settings(
            name: str, schema: SchemaDict, default: object = None
        ) -> Setting:
            schema_type = schema.get("type")
            assert schema_type is not None
            if schema_type == "object":
                return Setting(
                    name,
                    schema["title"],
                    schema_type,
                    help=schema.get("help") or "",
                    default=schema.get("default", default),
                    validate=schema.get("validate"),
                    children={
                        schema["key"]: build_settings(f"{name}.{schema['key']}", schema)
                        for schema in schema.get("fields", [])
                    },
                    editable=schema.get("editable", True),
                )
            else:
                return Setting(
                    name,
                    schema["title"],
                    schema_type,
                    choices=schema.get("choices"),
                    help=schema.get("help") or "",
                    default=schema.get("default", default),
                    validate=schema.get("validate"),
                    editable=schema.get("editable", True),
                )

        for sub_schema in self.schema:
            form_settings[sub_schema["key"]] = build_settings(
                sub_schema["key"], sub_schema
            )
        return form_settings


class Settings:
    """Stores schema backed settings."""

    def __init__(
        self,
        schema: Schema,
        settings: dict[str, object],
        on_set_callback: Callable[[str, object]] | None = None,
    ) -> None:
        self._schema = schema
        self._settings = settings
        self._on_set_callback = on_set_callback
        self._changed: bool = False

    @property
    def changed(self) -> bool:
        return self._changed

    @property
    def schema(self) -> Schema:
        return self._schema

    def up_to_date(self) -> None:
        """Set settings as up to date (clears changed flag)."""
        self._changed = False

    @property
    def json(self) -> str:
        """Settings in JSON form."""
        settings_json = dumps(self._settings, indent=4, separators=(", ", ": "))
        return settings_json

    def set_all(self) -> None:
        if self._on_set_callback is not None:
            for key in self._schema.keys:
                self._on_set_callback(key, self.get(key))

    def get[ExpectType](
        self,
        key: str,
        expect_type: type[ExpectType] = object,
        *,
        expand: bool = True,
    ) -> ExpectType:
        from os.path import expandvars

        sub_settings = self._settings

        for last, sub_key in loop_last(parse_key(key)):
            if last:
                if (value := sub_settings.get(sub_key)) is None:
                    default = self._schema.get_default(key)
                    if default is None:
                        default = expect_type()
                    if not isinstance(default, expect_type):
                        default = expect_type(default)
                    assert isinstance(default, expect_type)
                    return default

                if isinstance(value, str) and expand:
                    value = expandvars(value)
                if not isinstance(value, expect_type):
                    value = expect_type(value)
                if not isinstance(value, expect_type):
                    raise InvalidValue(
                        f"key {sub_key!r} is not of expected type {expect_type.__name__}"
                    )
                return value
            if not isinstance((sub_settings := sub_settings.get(sub_key, {})), dict):
                default = self._schema.get_default(key)
                if default is None:
                    default = expect_type()
                if not isinstance(default, expect_type):
                    default = expect_type(default)
                assert isinstance(default, expect_type)
                return default
        assert False, "Can't get here"

    def set(self, key: str, value: object) -> None:
        """Set a setting value.

        Args:
            key: Key in dot notation.
            value: New value.
        """
        current_value = self.get(key, expand=False)

        updated_settings = copy.deepcopy(self._settings)

        setting = updated_settings
        for last, sub_key in loop_last(parse_key(key)):
            if last:
                if current_value != value:
                    self._changed = True
                    self._settings = updated_settings
                assert isinstance(setting, dict)
                setting[sub_key] = value
            else:
                setting_node = setting.setdefault(sub_key, {})
                if isinstance(setting_node, dict):
                    setting = setting_node
                else:
                    assert isinstance(setting, dict)
                    setting[sub_key] = {}
                    setting = setting[sub_key]

        if self._on_set_callback is not None:
            self._on_set_callback(key, value)


if __name__ == "__main__":
    from rich import print
    from rich.traceback import install

    from toad.settings_schema import SCHEMA

    install(show_locals=True, width=None)

    schema = Schema(SCHEMA)
    settings = schema.defaults
    print(settings)

    print(schema.settings_map)

    print(schema.key_to_type)
