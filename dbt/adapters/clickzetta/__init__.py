from dbt.adapters.clickzetta.column import ClickZettaColumn  # noqa
from dbt.adapters.clickzetta.connections import ClickZettaConnectionManager  # noqa
from dbt.adapters.clickzetta.connections import ClickZettaCredentials
from dbt.adapters.clickzetta.relation import ClickZettaRelation  # noqa
from dbt.adapters.clickzetta.impl import ClickZettaAdapter

from dbt.adapters.base import AdapterPlugin  # type: ignore
from dbt.include import clickzetta  # type: ignore

Plugin = AdapterPlugin(
    adapter=ClickZettaAdapter, credentials=ClickZettaCredentials, include_path=clickzetta.PACKAGE_PATH  # type: ignore
)
