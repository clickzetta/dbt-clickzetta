from dataclasses import dataclass
from typing import Any, Dict, Optional, TypeVar, Union

from dbt.adapters.base.column import Column
from dbt.exceptions import DbtRuntimeError
from hologram import JsonDict
from dbt.dataclass_schema import dbtClassMixin


@dataclass
class ClickZettaColumn(dbtClassMixin, Column):  # type: ignore
    table_database: Optional[str] = None
    table_schema: Optional[str] = None
    table_name: Optional[str] = None

    @classmethod
    def translate_type(cls, dtype: str) -> str:
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
