from dataclasses import dataclass
from typing import Any, Dict, Optional, TypeVar, Union

from dbt.adapters.base.column import Column
from dbt.exceptions import DbtRuntimeError
from dbt_common.dataclass_schema import dbtClassMixin

JsonDict = Dict[str, Any]


@dataclass
class ClickZettaColumn(dbtClassMixin, Column):  # type: ignore
    table_database: Optional[str] = None
    table_schema: Optional[str] = None
    table_name: Optional[str] = None

    # Maps PostgreSQL/MySQL/generic aliases to ClickZetta canonical type names.
    # Applied at column construction time so all downstream code sees canonical names.
    _ALIAS_MAP = {
        # PostgreSQL numeric aliases
        "float8": "double",
        "float4": "float",
        "int2": "smallint",
        "int4": "int",
        "int8": "bigint",
        "integer": "int",
        "serial": "int",
        "bigserial": "bigint",
        # PostgreSQL string aliases
        "text": "string",
        "character varying": "varchar",
        "character": "char",
        # PostgreSQL boolean alias
        "bool": "boolean",
        # PostgreSQL/generic numeric alias
        "numeric": "decimal",
        "real": "float",
        # PostgreSQL timestamp aliases
        "timestamptz": "timestamp",
        "timestamp with time zone": "timestamp",
        "timestamp without time zone": "timestamp_ntz",
        # MySQL aliases
        "datetime": "timestamp_ntz",
        "tinyint(1)": "boolean",
        "long": "bigint",
        "short": "smallint",
        "byte": "tinyint",
    }

    @classmethod
    def translate_type(cls, dtype: str) -> str:
        # Normalize to lowercase for lookup, preserve original casing for unknown types
        normalized = dtype.strip().lower()
        # Strip length/precision suffix for alias lookup (e.g. "varchar(255)" -> "varchar")
        base = normalized.split("(")[0].strip()
        if base in cls._ALIAS_MAP:
            return cls._ALIAS_MAP[base]
        if normalized in cls._ALIAS_MAP:
            return cls._ALIAS_MAP[normalized]
        return dtype

    def is_integer(self) -> bool:
        return self.dtype.lower() in [
            "int8",
            "int16",
            "int32",
            "int64",
        ]

    def is_float(self):
        return self.dtype.lower() in [
            "float32",
            "float64",
            # TODO(hanmiao.li): decimal is a subclass of float, but we don't want to treat it
            # "decimal",
        ]

    @property
    def quoted(self) -> str:
        return "`{}`".format(self.column)

    @property
    def data_type(self) -> str:
        return self.dtype

    def is_string(self) -> bool:
        return self.dtype.lower() in [
            "string",
            "varchar",
            "char",
        ]

    def to_column_dict(self, omit_none: bool = True, validate: bool = False) -> JsonDict:
        original_dict = self.to_dict(omit_none=omit_none)
        return original_dict
