from __future__ import annotations


def pytest_addoption(parser):
    parser.addoption(
        "--cspyserver2",
        action="store",
        default="",
        help="Absolute path to CSpyServer2 executable for live tests.",
    )
    parser.addoption(
        "--launch-json",
        action="store",
        default="",
        help="Optional launch.json path override for live tests.",
    )
