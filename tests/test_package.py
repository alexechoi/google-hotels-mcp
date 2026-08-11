"""Package-level smoke tests."""

import ghotels


def test_version_is_exposed():
    assert ghotels.__version__
    assert ghotels.__version__ != "0.0.0.dev0"


def test_all_exports_resolve():
    for name in ghotels.__all__:
        assert getattr(ghotels, name) is not None
