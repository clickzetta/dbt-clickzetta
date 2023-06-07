import base64
import datetime
import pytz
import re
from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from time import sleep
from typing import Optional, Tuple, Union, Any, List

import agate
import dbt.clients.agate_helper
from clickzetta.dbapi.connection import Connection as ClickZettaConnection
from clickzetta.client import Client

from dbt.exceptions import (
    DbtInternalError,
    DbtRuntimeError,
    FailedToConnectError,
    DbtDatabaseError,
    DbtProfileError,
)
from dbt.adapters.base import Credentials  # type: ignore
from dbt.contracts.connection import AdapterResponse, Connection
from dbt.adapters.sql import SQLConnectionManager  # type: ignore
from dbt.events import AdapterLogger  # type: ignore
from dbt.events.functions import warn_or_error
from dbt.events.types import AdapterEventWarning
from dbt.ui import line_wrap_message, warning_tag

logger = AdapterLogger("ClickZetta")
ROW_VALUE_REGEX = re.compile(r"Row Values: \[.*\]")


@dataclass
class ClickZettaAdapterResponse(AdapterResponse):
    query_id: str = ""


@dataclass
class ClickZettaCredentials(Credentials):
    database: Optional[str] = ""  # type: ignore
    workspace: Optional[str] = ""
    instance: Optional[str] = ""
    vcluster: Optional[str] = "default"
    password: Optional[str] = ""
    service: Optional[str] = ""
    username: Optional[str] = ""
    schema: Optional[str] = "public"
    connect_retries: int = 3
    reuse_connections: bool = True

    @classmethod
    def __pre_deserialize__(cls, data):
        data = super().__pre_deserialize__(data)
        if "workspace" not in data:
            raise DbtProfileError(
                "The 'workspace' field is required for ClickZetta connections."
            )
        if "database" not in data:
            data["database"] = data["workspace"]
        return data

    @property
    def type(self):
        return "clickzetta"

    @property
    def unique_field(self):
        return self.username

    def _connection_keys(self):
        return (
            "workspace",
            "instance",
            "vcluster",
            "username",
            "schema",
            "password",
            "service",
            "database",
        )


class ClickZettaConnectionManager(SQLConnectionManager):
    TYPE = "clickzetta"

    @contextmanager
    def exception_handler(self, sql):
        try:
            yield
        except Exception as e:
            logger.warning("Error running SQL: {}", sql)
            logger.warning("Exception {}", e)
            logger.debug("Rolling back transaction.")
            self.rollback_if_open()
            if isinstance(e, DbtRuntimeError):
                # during a sql query, an internal to dbt exception was raised.
                # this sounds a lot like a signal handler and probably has
                # useful information, so raise it without modification.
                raise
            raise DbtRuntimeError(str(e)) from e

    @classmethod
    def open(cls, connection):
        if connection.state == "open":
            logger.debug("Connection is already open, skipping open.")
            return connection

        creds = connection.credentials

        def connect():
            session_parameters = {}
            client = Client(
                username=creds.username,
                password=creds.password,
                instance=creds.instance,
                workspace=creds.workspace,
                vcluster=creds.vcluster,
                schema=creds.schema,
                service=creds.service,
            )
            handle = ClickZettaConnection(client=client)

            return handle

        def exponential_backoff(attempt: int):
            return attempt * attempt

        return cls.retry_connection(
            connection,
            connect=connect,
            logger=logger,
            retry_limit=creds.connect_retries,
            retry_timeout=exponential_backoff,
            retryable_exceptions=[],
        )

    def cancel(self, connection):
        pass

    @classmethod
    def get_response(cls, cursor) -> ClickZettaAdapterResponse:
        code = cursor.rowcount
        logger.info(f"code: {code}")
        if code is not None:
            code = "SUCCESS"

        return ClickZettaAdapterResponse(
            _message="{} {}".format(code, cursor.rowcount),
            rows_affected=cursor.rowcount,
            code=code,
        )  # type: ignore

    def add_begin_query(self, *args, **kwargs):
        pass

    def add_commit_query(self, *args, **kwargs):
        pass

    def begin(self):
        pass

    def commit(self):
        pass

    def clear_transaction(self):
        pass

    @classmethod
    def _split_queries(cls, sql):
        pass

    def execute(
            self, sql: str, auto_begin: bool = False, fetch: bool = False, limit: Optional[int] = None
    ) -> Tuple[AdapterResponse, agate.Table]:
        _, cursor = self.add_query(sql, auto_begin)
        logger.info(f"dbt_execute_sql: {sql}")
        response = self.get_response(cursor)
        if fetch:
            table = self.get_result_from_cursor(cursor)
        else:
            table = dbt.clients.agate_helper.empty_table()
        return response, table

    def add_standard_query(self, sql: str, **kwargs) -> Tuple[Connection, Any]:
        return super().add_query(self._add_query_comment(sql), **kwargs)


    def add_query(
            self,
            sql: str,
            auto_begin: bool = True,
            bindings: Optional[Any] = None,
            abridge_sql_log: bool = False,
    ) -> Tuple[Connection, Any]:  # type: ignore
        # TODO(hanmiao.li): clickzetta cursor is not support pass bingdings, will support later.
        if bindings:
            cast_bindings = []
            for binding in bindings:
                cast_bindings.append(f"'{str(binding)}'")
            sql = sql % tuple(cast_bindings)
            bindings = None

        connection, cursor = self._add_standard_queries(
            [sql],
            auto_begin=auto_begin,
            bindings=bindings,
            abridge_sql_log=abridge_sql_log,
        )

        if cursor is None:
            self._raise_cursor_not_found_error(sql)

        return connection, cursor  # type: ignore

    def _add_standard_queries(self, queries: List[str], **kwargs) -> Tuple[Connection, Any]:
        for query in queries:
            connection, cursor = self.add_standard_query(query, **kwargs)
        return connection, cursor

    def _raise_cursor_not_found_error(self, sql: str):
        conn = self.get_thread_connection()
        try:
            conn_name = conn.name
        except AttributeError:
            conn_name = None

        raise DbtRuntimeError(
            f"""Tried to run an empty query on model '{conn_name or "<None>"}'. If you are """
            f"""conditionally running\nsql, e.g. in a model hook, make """
            f"""sure your `else` clause contains valid sql!\n\n"""
            f"""Provided SQL:\n{sql}"""
        )

    def release(self):
        if self.profile.credentials.reuse_connections:  # type: ignore
            return
        super().release()
