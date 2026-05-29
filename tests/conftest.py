import pytest
import os

# Import the functional fixtures as a plugin
# Note: fixtures with session scope need to be local

pytest_plugins = ["dbt.tests.fixtures.project"]


# The profile dictionary, used to write out profiles.yml
@pytest.fixture(scope="class")
def dbt_profile_target():
    return {
        "type": "clickzetta",
        "service": os.getenv("CLICKZETTA_TEST_SERVICE"),
        "instance": os.getenv("CLICKZETTA_TEST_INSTANCE"),
        "workspace": os.getenv("CLICKZETTA_TEST_WORKSPACE"),
        "username": os.getenv("CLICKZETTA_TEST_USERNAME"),
        "password": os.getenv("CLICKZETTA_TEST_PASSWORD"),
        "vcluster": os.getenv("CLICKZETTA_TEST_VCLUSTER", "default_ap"),
        "schema": os.getenv("CLICKZETTA_TEST_SCHEMA", "dbt_test"),
    }
