import pathlib
import pytest

# Setuptools editable installs add a fake PATH_PLACEHOLDER to namespace package
# __path__ lists. HA's custom component scanner calls pathlib.Path(p).iterdir()
# on every entry — which raises FileNotFoundError for the fake path. Strip it.
import custom_components as _cc
_cc.__path__ = [p for p in _cc.__path__ if pathlib.Path(p).is_dir()]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
