import pytest
import os

# Import the fuctional fixtures as a plugin
# Note: fixtures with session scope need to be local

pytest_plugins = ["dbt.tests.fixtures.project"]


# The profile dictionary, used to write out profiles.yml
@pytest.fixture(scope="class")
def dbt_profile_target():
    return {
        "type": "clickzetta",
        "base_url": os.getenv("CLICKZETTA_TEST_BASE_URL"),
        "workspace": os.getenv("CLICKZETTA_TEST_WORKSPACE"),
        "instance_name": os.getenv("CLICKZETTA_TEST_INSTANCE_NAME"),
        "password": os.getenv("CLICKZETTA_TEST_PASSWORD"),
        "vc_name": os.getenv("CLICKZETTA_TEST_VC_NAME"),
        "user_name": os.getenv("CLICKZETTA_TEST_USER_NAME"),
        "schema": os.getenv("CLICKZETTA_TEST_SCHEMA"),
    }
