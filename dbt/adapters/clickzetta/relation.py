from dataclasses import dataclass, field
from dbt.adapters.base.relation import BaseRelation, Policy


@dataclass
class ClickZettaQuotePolicy(Policy):
    database: bool = False
    schema: bool = False
    identifier: bool = False


@dataclass(frozen=True, eq=False, repr=False)
class ClickZettaRelation(BaseRelation):
    quote_policy: ClickZettaQuotePolicy = field(default_factory=lambda: ClickZettaQuotePolicy())
