from dataclasses import dataclass
from typing import Mapping, Any, Optional, List, Union, Dict

import agate
import dbt.exceptions

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
from dbt.contracts.relation import RelationType
from dbt.exceptions import CompilationError, DbtDatabaseError, DbtRuntimeError
from dbt.adapters.base import BaseRelation
from dbt.clients.agate_helper import DEFAULT_TYPE_TESTER
from dbt.contracts.connection import AdapterResponse
from dbt.contracts.graph.nodes import ConstraintType
from dbt.contracts.relation import RelationType
from dbt.events import AdapterLogger
from dbt.utils import executor, AttrDict

GET_COLUMNS_IN_RELATION_RAW_MACRO_NAME = "get_columns_in_relation_raw"
LIST_SCHEMAS_MACRO_NAME = "list_schemas"
LIST_RELATIONS_MACRO_NAME = "list_relations_without_caching"
LIST_RELATIONS_SHOW_TABLES_MACRO_NAME = "list_relations_show_tables_without_caching"
DESCRIBE_TABLE_EXTENDED_MACRO_NAME = "describe_table_extended_without_caching"
DROP_RELATION_MACRO_NAME = "drop_relation"

TABLE_OR_VIEW_NOT_FOUND_MESSAGES = (
    "[TABLE_OR_VIEW_NOT_FOUND]",
    "Table or view not found",
    "NoSuchTableException",
)


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
        return "current_timestamp()"

    @classmethod
    def _catalog_filter_table(cls, table: agate.Table, manifest: Manifest) -> agate.Table:
        lowered = table.rename(column_names=[c.lower() for c in table.column_names])
        return super()._catalog_filter_table(lowered, manifest)

    @classmethod
    def convert_text_type(cls, agate_table, col_idx):
        return "string"

    @classmethod
    def convert_number_type(cls, agate_table, col_idx):
        decimals = agate_table.aggregate(agate.MaxPrecision(col_idx))
        return "double" if decimals else "bigint"

    @classmethod
    def convert_date_type(cls, agate_table, col_idx):
        return "date"

    @classmethod
    def convert_time_type(cls, agate_table, col_idx):
        return "time"

    @classmethod
    def convert_datetime_type(cls, agate_table, col_idx):
        return "timestamp"

    def quote(self, identifier):
        return "`{}`".format(identifier)

    def parse_describe_extended(
            self, relation: BaseRelation, raw_rows: AttrDict
    ) -> List[ClickZettaColumn]:
        # Convert the Row to a dict
        dict_rows = [dict(zip(row._keys, row._values)) for row in raw_rows]

        rows = [row for row in dict_rows if not row["column_name"].startswith("#")]

        return [
            ClickZettaColumn(
                table_database=None,
                table_schema=relation.schema,
                table_name=relation.name,
                column=column["column_name"],
                dtype=column["data_type"],
            )
            for idx, column in enumerate(rows)
        ]

    def get_columns_in_relation(self, relation: BaseRelation) -> List[ClickZettaColumn]:
        columns = []
        try:
            rows: AttrDict = self.execute_macro(
                GET_COLUMNS_IN_RELATION_RAW_MACRO_NAME, kwargs={"relation": relation}
            )
            columns = self.parse_describe_extended(relation, rows)
        except dbt.exceptions.DbtRuntimeError as e:
            errmsg = getattr(e, "msg", "")
            found_msgs = (msg in errmsg for msg in TABLE_OR_VIEW_NOT_FOUND_MESSAGES)
            if any(found_msgs):
                pass
            else:
                raise e

        columns = [x for x in columns]
        return columns

    def check_schema_exists(self, database, schema):
        results = self.execute_macro(LIST_SCHEMAS_MACRO_NAME, kwargs={"database": database})

        exists = True if schema in [row[0] for row in results] else False
        return exists

    def list_relations_without_caching(self, schema_relation: ClickZettaRelation) \
            -> List[ClickZettaRelation]:  # type: ignore
        kwargs = {"schema_relation": schema_relation}
        try:
            results = self.execute_macro(LIST_RELATIONS_MACRO_NAME, kwargs=kwargs)
        except DbtDatabaseError as exc:
            if "Object does not exist" in str(exc):
                return []
            raise

        relations = []
        quote_policy = {"database": False, "schema": True, "identifier": True}
        for row in results:
            _schema, _identifier, _is_view, _is_materialized_view = row
            try:
                if _is_view == 'true':
                    _type = RelationType.View
                elif _is_materialized_view == 'true':
                    _type = RelationType.MaterializedView
                else:
                    _type = RelationType.Table
            except ValueError:
                _type = self.Relation.External
            relations.append(
                self.Relation.create(
                    database=None,
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
