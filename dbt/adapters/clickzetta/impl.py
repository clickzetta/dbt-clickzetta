from dataclasses import dataclass
from typing import Mapping, Any, Optional, List, Union, Dict, Set, Tuple
from concurrent.futures import Future

import agate
import dbt.exceptions

from dbt.adapters.base.impl import AdapterConfig, ConstraintSupport  # type: ignore
from dbt.adapters.sql import SQLAdapter  # type: ignore
from dbt.adapters.sql.impl import (
    LIST_SCHEMAS_MACRO_NAME,
    LIST_RELATIONS_MACRO_NAME,
)
from dbt.adapters.base.impl import catch_as_completed, ConstraintSupport

from dbt.adapters.clickzetta import ClickZettaConnectionManager
from dbt.adapters.clickzetta import ClickZettaRelation
from dbt.adapters.clickzetta import ClickZettaColumn
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ConstraintType
from dbt.adapters.base import BaseRelation, SchemaSearchMap, RelationType
from dbt.exceptions import CompilationError, DbtRuntimeError
from dbt_common.clients.agate_helper import DEFAULT_TYPE_TESTER
from dbt.adapters.contracts.connection import AdapterResponse
from dbt.adapters.events.logging import AdapterLogger
from dbt_common.utils import AttrDict

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
logger = AdapterLogger(__name__)


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

    def _get_catalog_schemas(self, manifest: Manifest) -> SchemaSearchMap:
        candidates = super()._get_catalog_schemas(manifest)
        db_schemas: Dict[str, Set[str]] = {}
        result = SchemaSearchMap()

        for candidate, schemas in candidates.items():
            database = candidate.database
            if database not in db_schemas:
                db_schemas[database] = set(self.list_schemas(database))  # type: ignore[index]
            if candidate.schema in db_schemas[database]:  # type: ignore[index]
                result[candidate] = schemas
            else:
                logger.debug(
                    "Skipping catalog for {}.{} - schema does not exist".format(
                        database, candidate.schema
                    )
                )
        return result

    def get_catalog(self, relation_configs, used_schemas):
        """Build catalog using SHOW TABLES + DESCRIBE TABLE (INFORMATION_SCHEMA not available)."""
        catalog_rows = []
        # used_schemas may contain (None, schema) and (workspace, schema) for the same schema.
        # Collect all unique schemas with their associated databases.
        schema_databases: Dict[str, Set[Optional[str]]] = {}
        for database, schema in used_schemas:
            if schema not in schema_databases:
                schema_databases[schema] = set()
            schema_databases[schema].add(database)

        with self.connection_named("catalog"):
            for schema, databases in schema_databases.items():
                try:
                    _, tables_table = self.execute(f"SHOW TABLES IN {schema}", fetch=True)
                    for tbl_row in tables_table.rows:
                        tbl_name = tbl_row["table_name"]
                        tbl_type = "view" if tbl_row["is_view"] else "table"
                        try:
                            _, desc_table = self.execute(
                                f"DESCRIBE TABLE {schema}.{tbl_name}", fetch=True
                            )
                            # Emit one row per database entry so both nodes (database=None)
                            # and sources (database=workspace) can match the catalog.
                            for database in databases:
                                for idx, col_row in enumerate(desc_table.rows):
                                    catalog_rows.append({
                                        "table_database": database,
                                        "table_schema": schema,
                                        "table_name": tbl_name,
                                        "table_type": tbl_type,
                                        "column_name": col_row["column_name"],
                                        "column_index": idx,
                                        "column_type": col_row["data_type"],
                                        "column_comment": col_row.get("comment", ""),
                                        "stats:row_count:label": None,
                                        "stats:row_count:value": None,
                                        "stats:row_count:description": None,
                                        "stats:row_count:include": False,
                                        "stats:bytes:label": None,
                                        "stats:bytes:value": None,
                                        "stats:bytes:description": None,
                                        "stats:bytes:include": False,
                                        "stats:last_modified:label": None,
                                        "stats:last_modified:value": None,
                                        "stats:last_modified:description": None,
                                        "stats:last_modified:include": False,
                                    })
                        except Exception as e:
                            logger.debug(f"Could not describe {schema}.{tbl_name}: {e}")
                except Exception as e:
                    logger.debug(f"Could not list tables in {schema}: {e}")

        if not catalog_rows:
            catalog_table = agate.Table([], [])
        else:
            col_names = list(catalog_rows[0].keys())
            rows = [[r[c] for c in col_names] for r in catalog_rows]
            catalog_table = agate.Table(rows, col_names)

        return catalog_table, []

    @classmethod
    def convert_text_type(cls, agate_table, col_idx):
        return "string"
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

    def get_relation(self, database: str, schema: str, identifier: str) -> Optional[BaseRelation]:
        if not self.Relation.get_default_include_policy().database:
            database = None
        return super().get_relation(database, schema, identifier)

    def check_schema_exists(self, database, schema):
        results = self.execute_macro(LIST_SCHEMAS_MACRO_NAME, kwargs={"database": database})

        exists = True if schema in [row[0] for row in results] else False
        return exists

    def list_relations_without_caching(self, schema_relation: ClickZettaRelation) \
            -> List[ClickZettaRelation]:  # type: ignore
        # check_schema_exists before querying to avoid connector-level error logs
        # when the schema doesn't exist yet (e.g. snapshot schema before first dbt snapshot run)
        if not self.check_schema_exists(schema_relation.database, schema_relation.schema):
            return []

        kwargs = {"schema_relation": schema_relation}
        try:
            results = self.execute_macro(LIST_RELATIONS_MACRO_NAME, kwargs=kwargs)
        except Exception as exc:
            err = str(exc)
            if "Object does not exist" in err or "NotFound" in err or "not found" in err.lower():
                return []
            raise

        relations = []
        quote_policy = {"database": False, "schema": True, "identifier": True}
        for row in results:
            _schema, _identifier, _is_view, _is_materialized_view, _, _is_dynamic = row
            try:
                if _is_view:
                    _type = RelationType.View
                elif _is_materialized_view:
                    _type = self.Relation.get_relation_type.MaterializedView
                elif _is_dynamic:
                    _type = self.Relation.DynamicTable
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

    def standardize_grants_dict(self, grants_table: agate.Table) -> Dict[str, List[str]]:
        # SHOW GRANTS ON TABLE returns columns:
        #   granted_type, privilege, conditions, granted_on, object_name,
        #   granted_to, grantee_name, grantor_name, grant_option, granted_time
        # privilege values look like "SELECT TABLE", "ALL", "INSERT TABLE" etc.
        # granted_type is "PRIVILEGE" for direct grants, "OBJECT_HIERARCHY" for inherited — skip inherited.
        # grantee_name is prefixed with workspace, e.g. "quick_start.my_role" — strip the prefix.
        col_names = [c.lower() for c in grants_table.column_names]

        if "privilege" not in col_names or "grantee_name" not in col_names:
            return {}

        grants: Dict[str, List[str]] = {}
        for row in grants_table.rows:
            row_dict = dict(zip(col_names, row))

            # only process direct grants, skip inherited hierarchy grants
            if row_dict.get("granted_type", "").upper() != "PRIVILEGE":
                continue

            # normalize "SELECT TABLE" -> "select", "ALL" -> "all"
            raw_priv = row_dict["privilege"].upper()
            privilege = raw_priv.split()[0].lower()

            # strip workspace prefix from grantee: "quick_start.my_role" -> "my_role"
            raw_grantee = row_dict["grantee_name"]
            grantee = raw_grantee.split(".", 1)[-1] if "." in raw_grantee else raw_grantee

            # prefix USER grantees so grant/revoke macros can distinguish ROLE vs USER
            granted_to = row_dict.get("granted_to", "ROLE").upper()
            if granted_to == "USER":
                grantee = f"user:{grantee}"

            grants.setdefault(privilege, []).append(grantee)
        return grants
