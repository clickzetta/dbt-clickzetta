"""
ClickZetta ZettaPark Python model support.

Install with: pip install "dbt-clickzetta[python]"

Usage in a dbt model file (e.g. models/my_model.py):

    def model(dbt, session):
        dbt.config(materialized='table')
        df = session.sql("select 1 as id, 'hello' as msg")
        return df

The returned DataFrame is written to the target relation automatically.

Packages declared in dbt.config(packages=[...]) are installed automatically
before the model runs, in both local and Studio environments.
"""

from typing import Any, Dict

from dbt.adapters.base.impl import PythonJobHelper
from dbt.adapters.contracts.connection import AdapterResponse
from dbt.adapters.events.logging import AdapterLogger

logger = AdapterLogger(__name__)


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
        name = args[-1]
        database = self._parsed_model.get("database", "")
        schema = self._parsed_model.get("schema", "")
        if database and schema:
            return self._session.table(f"{database}.{schema}.{name}")
        elif schema:
            return self._session.table(f"{schema}.{name}")
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


def _collect_config(model_fn: Any, dbt_obj: "DbtZettaPark") -> None:
    """
    Call model() with a mock session to collect dbt.config() settings
    (including packages) without executing any real queries.
    """
    class _MockSession:
        def sql(self, *a, **kw): return self
        def table(self, *a, **kw): return self
        def filter(self, *a, **kw): return self
        def select(self, *a, **kw): return self
        def to_pandas(self, *a, **kw):
            import pandas as pd
            return pd.DataFrame()
        def createDataFrame(self, *a, **kw): return self
        def count(self, *a, **kw): return 0
        def show(self, *a, **kw): pass
        def collect(self, *a, **kw): return []
        @property
        def write(self): return self
        def mode(self, *a, **kw): return self
        def save_as_table(self, *a, **kw): pass

    try:
        model_fn(dbt_obj, _MockSession())
    except Exception:
        pass  # Expected — mock session will fail on real operations


def _install_packages_list(packages: list) -> None:
    """Install a list of Python packages via pip in the current environment."""
    import subprocess
    import sys

    logger.info(f"Installing packages for Python model: {packages}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + packages + ["-q"],
            timeout=300,
        )
        logger.info(f"Packages installed successfully: {packages}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to install packages {packages}. "
            f"Error: {e}. Install them manually with: pip install {' '.join(packages)}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Timeout installing packages {packages}. "
            "Check network connectivity or install them manually."
        )


class ClickZettaPythonJobHelper(PythonJobHelper):
    """
    Executes dbt Python models using ZettaPark.

    The compiled model code is exec()'d in the current process.
    The user's model(dbt, session) function is called with a DbtZettaPark
    object and a ZettaPark Session. The returned DataFrame is written to
    the target relation.

    Packages declared in dbt.config(packages=[...]) are installed automatically
    before the model runs.
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

        # Collect dbt.config() settings (including packages) via a dry-run
        dbt_obj = DbtZettaPark(self._parsed_model, session)
        _collect_config(exec_globals["model"], dbt_obj)

        # Install packages declared in dbt.config(packages=[...])
        packages = dbt_obj._config.get("packages", [])
        if packages:
            _install_packages_list(packages)

        # Reset dbt_obj and run for real
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
