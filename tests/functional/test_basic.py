import pytest

from dbt.tests.adapter.basic.test_base import BaseSimpleMaterializations
from dbt.tests.adapter.basic.test_incremental import BaseIncremental
from dbt.tests.adapter.basic.test_generic_tests import BaseGenericTests
from dbt.tests.adapter.basic.test_singular_tests import BaseSingularTests
from dbt.tests.adapter.basic.test_ephemeral import BaseEphemeral
from dbt.tests.adapter.basic.test_empty import BaseEmpty
from dbt.tests.adapter.basic.test_snapshot_timestamp import BaseSnapshotTimestamp
from dbt.tests.adapter.basic.test_snapshot_check_cols import BaseSnapshotCheckCols
from dbt.tests.adapter.basic.test_adapter_methods import BaseAdapterMethod


class TestSimpleMaterializations(BaseSimpleMaterializations):
    pass


class TestIncremental(BaseIncremental):
    pass


class TestIncrementalAppend(BaseIncremental):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "name": "incremental_append",
            "models": {"+incremental_strategy": "append"},
        }


class TestIncrementalInsertOverwrite(BaseIncremental):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "name": "incremental_insert_overwrite",
            "models": {"+incremental_strategy": "insert_overwrite"},
        }


class TestGenericTests(BaseGenericTests):
    pass


class TestSingularTests(BaseSingularTests):
    pass


class TestEphemeral(BaseEphemeral):
    pass


class TestEmpty(BaseEmpty):
    pass


class TestSnapshotTimestamp(BaseSnapshotTimestamp):
    pass


class TestSnapshotCheckCols(BaseSnapshotCheckCols):
    pass


class TestAdapterMethods(BaseAdapterMethod):
    pass
