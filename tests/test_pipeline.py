import pytest

from server.pipeline import Pipeline

# ---------------------------------------------------------------------------
# test of load_module
# ---------------------------------------------------------------------------
def test_load_module_import_error_leaves_module_none(fake_connection):
    pipeline = Pipeline(fake_connection, app_config="does_not_exist", app_directory="app")
    assert pipeline.module is None

