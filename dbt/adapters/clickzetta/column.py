from dataclasses import dataclass

from dbt.adapters.base.column import Column
from dbt.exceptions import DbtRuntimeError


@dataclass
class ClickZettaColumn(Column):
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

    def is_string(self) -> bool:
        return self.dtype.lower() in [
            "string",
            "varchar",
            "char",
        ]

    def string_size(self) -> int:
        if not self.is_string():
            raise DbtRuntimeError("Called string_size() on non-string field!")

        if self.dtype == "string" or self.char_size is None:
            return 16777216
        else:
            return int(self.char_size)
