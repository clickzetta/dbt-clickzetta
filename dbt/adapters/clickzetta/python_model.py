"""
ClickZetta ZettaPark Python model support.

Python models run inside ClickZetta Studio Python Task environments,
where clickzetta-zettapark-python is pre-installed. The package is not
available on PyPI — it is only available in the Studio execution environment.

Usage in a dbt model file (e.g. models/my_model.py):

    def model(dbt, session):
        dbt.config(materialized='table')
        df = session.sql("select 1 as id, 'hello' as msg")
        return df

The returned DataFrame is written to the target relation automatically.
"""

from typing import Any, Dict

from dbt.adapters.base.impl import PythonJobHelper
from dbt.adapters.contracts.connection import AdapterResponse


class DbtZettaPark:
    """
    Minimal dbt object passed to the user's model(dbt, session) function.
    Provides dbt.ref(), dbt.source(), dbt.config() interfaces.
    """

    def __init__(self, parsed_model: Dict, session: Any):
        self._parsed_model = parsed_model
        self._session = session
        self._config = {}

    def config(self, **kwargs):
        self._config.update(kwargs)

    def ref(self, *args):
        # args: (model_name,) or (package_name, model_name)
        if len(args) == 1:
            name = args[0]
        else:
            name = args[1]
        # Resolve via the session's current schema context
        return self._session.table(name)

    def source(self, source_name: str, table_name: str):
        return self._session.table(f"{source_name}.{table_name}")

    def this(self):
        node = self._parsed_model.get("alias") or self._parsed_model.get("name", "")
        schema = self._parsed_model.get("schema", "")
        database = self._parsed_model.get("database", "")
        return self._session.table(f"{database}.{schema}.{node}")


def _build_session(credentials):
    """
    Build a ZettaPark Session from dbt credentials.

    Two paths:
    - Studio Python Task environment: uses clickzetta_dbutils.get_active_lakehouse_engine()
      to obtain a magic_token (pre-injected by the Studio runtime).
    - Local / CI environment: uses service/instance/username/password from profiles.yml.
    """
    try:
        from clickzetta.zettapark.session import Session
    except ImportError:
        raise RuntimeError(
            "Python models require clickzetta-zettapark-python. "
            "Install it with: pip install clickzetta-zettapark-python"
        )

    service = getattr(credentials, "service", None)
    instance = getattr(credentials, "instance", None)
    workspace = getattr(credentials, "workspace", None)
    schema = getattr(credentials, "schema", "public")
    vcluster = getattr(credentials, "vcluster", "default")

    config = {
        "service": service,
        "instance": instance,
        "workspace": workspace,
        "schema": schema,
        "vcluster": vcluster,
    }

    # Try Studio environment first: get magic_token from pre-injected engine
    try:
        import clickzetta_dbutils as dbutils
        from urllib.parse import urlparse, parse_qs
        engine = dbutils.get_active_lakehouse_engine()
        url_str = str(engine.url)
        parsed = urlparse(url_str.replace("clickzetta://", "https://"))
        params = parse_qs(parsed.query)
        magic_token = params.get("magic_token", [None])[0]
        if magic_token:
            full_host = parsed.hostname or ""
            parts = full_host.split(".", 1)
            if len(parts) == 2:
                config["instance"] = parts[0]
                config["service"] = parts[1]
            config["workspace"] = parsed.path.lstrip("/") or workspace
            config["schema"] = params.get("schema", [schema])[0]
            config["vcluster"] = params.get("virtualcluster", [vcluster])[0]
            config["magic_token"] = magic_token
            return Session.builder.configs(config).getOrCreate()
    except Exception:
        pass  # Not in Studio environment, fall through to credentials-based auth

    # Local / CI: use username/password from profiles.yml
    config["username"] = getattr(credentials, "username", None)
    config["password"] = getattr(credentials, "password", None)
    return Session.builder.configs(config).getOrCreate()


class ClickZettaPythonJobHelper(PythonJobHelper):
    """
    Executes dbt Python models using ZettaPark.

    The compiled model code is exec()'d in the current process.
    The user's model(dbt, session) function is called with a DbtZettaPark
    object and a ZettaPark Session. The returned DataFrame is written to
    the target relation.
    """

    def __init__(self, parsed_model: Dict, credentials: Any):
        self._parsed_model = parsed_model
        self._credentials = credentials

    def submit(self, compiled_code: str) -> AdapterResponse:
        session = _build_session(self._credentials)

        # exec the compiled model code to get the model() function
        exec_globals: Dict[str, Any] = {}
        exec(compiled_code, exec_globals)

        if "model" not in exec_globals:
            raise RuntimeError(
                "Python model must define a function named 'model(dbt, session)'. "
                f"Found functions: {[k for k in exec_globals if callable(exec_globals[k])]}"
            )

        dbt_obj = DbtZettaPark(self._parsed_model, session)
        result_df = exec_globals["model"](dbt_obj, session)

        if result_df is None:
            raise RuntimeError(
                "Python model's model() function must return a DataFrame. Got None."
            )

        # Write result to target relation
        node = self._parsed_model
        target = f"{node.get('database', '')}.{node.get('schema', '')}.{node.get('alias') or node.get('name', '')}"
        write_mode = dbt_obj._config.get("write_mode", "overwrite")
        result_df.write.mode(write_mode).save_as_table(target)

        row_count = result_df.count()
        return AdapterResponse(
            _message=f"Python model executed successfully, {row_count} rows written to {target}",
            rows_affected=row_count,
            code="SUCCESS",
        )
