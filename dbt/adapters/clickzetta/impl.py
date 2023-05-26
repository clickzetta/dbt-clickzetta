from dataclasses import dataclass
from typing import Mapping, Any, Optional, List, Union, Dict

import agate

from dbt.adapters.base.impl import AdapterConfig, ConstraintSupport  # type: ignore
from dbt.adapters.sql import SQLAdapter  # type: ignore
from dbt.adapters.sql.impl import (
    LIST_SCHEMAS_MACRO_NAME,
    LIST_RELATIONS_MACRO_NAME,
)

from dbt.adapters.clickzetta import ClickZettaConnectionManager
from dbt.adapters.clickzetta import ClickZettaRelation
from dbt.adapters.clickzetta import ClickZettaColumn
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ConstraintType
from dbt.exceptions import CompilationError, DbtDatabaseError, DbtRuntimeError


@dataclass
class ClickZettaConfig(AdapterConfig):
    pass


class ClickZettaAdapter(SQLAdapter):
    Relation = ClickZettaRelation
    Column = ClickZettaColumn
    ConnectionManager = ClickZettaConnectionManager

    AdapterSpecificConfigs = ClickZettaConfig

    CONSTRAINT_SUPPORT = {
        ConstraintType.check: ConstraintSupport.NOT_SUPPORTED,
        ConstraintType.not_null: ConstraintSupport.ENFORCED,
        ConstraintType.unique: ConstraintSupport.NOT_ENFORCED,
        ConstraintType.primary_key: ConstraintSupport.NOT_ENFORCED,
        ConstraintType.foreign_key: ConstraintSupport.NOT_SUPPORTED,
    }

    @classmethod
    def date_function(cls):
        return "CURRENT_TIMESTAMP()"

    @classmethod
    def _catalog_filter_table(cls, table: agate.Table, manifest: Manifest) -> agate.Table:
        lowered = table.rename(column_names=[c.lower() for c in table.column_names])
        return super()._catalog_filter_table(lowered, manifest)

    @classmethod
    def convert_number_type(cls, agate_table: agate.Table, col_idx: int) -> str:
        decimals = agate_table.aggregate(agate.MaxPrecision(col_idx))
        return 'FLOAT' if decimals else 'INT'

    @classmethod
    def convert_datetime_type(cls, agate_table: agate.Table, col_idx: int) -> str:
        return 'DATE'

    def list_schemas(self, database: str) -> List[str]:
        try:
            results = self.execute_macro(LIST_SCHEMAS_MACRO_NAME, kwargs={"database": database})
        except DbtDatabaseError as exc:
            msg = f"Database error while listing schemas in database " f'"{database}"\n{exc}'
            raise DbtRuntimeError(msg)

        return [row["name"] for row in results]

    def get_columns_in_relation(self, relation):
        try:
            return super().get_columns_in_relation(relation)
        except DbtDatabaseError as exc:
            if "does not exist or not authorized" in str(exc):
                return []
            else:
                raise

    def list_relations_without_caching(self, schema_relation: ClickZettaRelation) -> List[
        ClickZettaRelation]:  # type: ignore
        kwargs = {"schema_relation": schema_relation}
        try:
            results = self.execute_macro(LIST_RELATIONS_MACRO_NAME, kwargs=kwargs)
        except DbtDatabaseError as exc:
            if "Object does not exist" in str(exc):
                return []
            raise

        relations = []
        quote_policy = {"database": True, "schema": True, "identifier": True}

        columns = ["database_name", "schema_name", "name", "kind"]
        for _database, _schema, _identifier, _type in results.select(columns):  # type: ignore
            try:
                _type = self.Relation.get_relation_type(_type.lower())
            except ValueError:
                _type = self.Relation.External
            relations.append(
                self.Relation.create(
                    database=_database,
                    schema=_schema,
                    identifier=_identifier,
                    quote_policy=quote_policy,
                    type=_type,
                )
            )

        return relations

    def quote_seed_column(self, column: str, quote_config: Optional[bool]) -> str:
        quote_columns: bool = False
        if isinstance(quote_config, bool):
            quote_columns = quote_config
        elif quote_config is None:
            pass
        else:
            msg = (
                f'The seed configuration value of "quote_columns" has an '
                f"invalid type {type(quote_config)}"
            )
            raise CompilationError(msg)

        if quote_columns:
            return self.quote(column)
        else:
            return column

    def timestamp_add_sql(self, add_to: str, number: int = 1, interval: str = "hour") -> str:
        return f"DATEADD({interval}, {number}, {add_to})"

    def valid_incremental_strategies(self):
        return ["append", "merge", "insert_overwrite"]
