from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Type

from dbt.adapters.base.relation import BaseRelation, Policy, classproperty
from dbt.exceptions import DbtRuntimeError
from mashumaro.types import SerializableType


@dataclass
class ClickZettaQuotePolicy(Policy):
    database: bool = False
    schema: bool = False
    identifier: bool = False

@dataclass
class ClickZettaIncludePolicy(Policy):
    database: bool = False
    schema: bool = True
    identifier: bool = True

class StrEnum(str, SerializableType, Enum):
    def __str__(self):
        return self.value

    # https://docs.python.org/3.6/library/enum.html#using-automatic-values
    def _generate_next_value_(name, *_):
        return name

    def _serialize(self) -> str:
        return self.value

    @classmethod
    def _deserialize(cls, value: str):
        return cls(value)


class ClickZettaRelationType(StrEnum):
    Table = "table"
    View = "view"
    MaterializedView = "materializedview"
    DynamicTable = "dynamic_table"


@dataclass(frozen=True, eq=False, repr=False)
class ClickZettaRelation(BaseRelation):
    type: Optional[ClickZettaRelationType] = None
    quote_policy: Policy = field(default_factory=lambda: ClickZettaQuotePolicy())
    include_policy: Policy = field(default_factory=lambda: ClickZettaIncludePolicy())
    quote_character: str = "`"

    def render(self):
        return super().render()

    @property
    def is_dynamic_table(self) -> bool:
        return self.type == ClickZettaRelationType.DynamicTable

    @classproperty
    def DynamicTable(cls) -> str:
        return 'dynamic_table'

    @classproperty
    def get_relation_type(cls) -> Type[ClickZettaRelationType]:
        return ClickZettaRelationType
