from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_thrift_server import server
from mcp_thrift_server.cspy_server_manager import shutdown_managed_server
from mcp_thrift_server.thrift_client import ThriftBridgeError


def _require_live_inputs() -> Path:
    default_launch = Path(__file__).resolve().parent / "live_assets" / "launch.json"
    launch_path = os.getenv("MCP_LAUNCH_JSON", "").strip()
    p = Path(launch_path) if launch_path else default_launch
    if not p.exists():
        pytest.skip(f"Launch file does not exist: {p}")
    return p


def _load_launch_config(launch_file: Path) -> str | None:
    """Return configurations[0] as JSON, with relative program/projectPath
    resolved against the launch file's directory."""
    raw = json.loads(launch_file.read_text(encoding="utf-8"))
    if "configurations" not in raw or not raw["configurations"]:
        return None
    cfg = raw["configurations"][0]
    for key in ("program", "projectPath"):
        value = cfg.get(key)
        if value and not Path(value).is_absolute():
            cfg[key] = str((launch_file.parent / value).resolve())
    return json.dumps(cfg)


@pytest.fixture(autouse=True)
def _live_cleanup(request):
    cspy_path = str(request.config.getoption("--cspyserver2") or "").strip()
    launch_json = str(request.config.getoption("--launch-json") or "").strip()

    old_cspy = os.environ.get("THRIFT_CSPYSERVER_EXE")
    old_launch = os.environ.get("MCP_LAUNCH_JSON")

    if cspy_path:
        os.environ["THRIFT_CSPYSERVER_EXE"] = cspy_path
    if launch_json:
        os.environ["MCP_LAUNCH_JSON"] = launch_json

    # Make sure each live test leaves no active debug session/process behind.
    yield
    try:
        server.debugger_stop_session()
    except Exception:
        pass
    try:
        shutdown_managed_server()
    except Exception:
        pass

    if old_cspy is None:
        os.environ.pop("THRIFT_CSPYSERVER_EXE", None)
    else:
        os.environ["THRIFT_CSPYSERVER_EXE"] = old_cspy

    if old_launch is None:
        os.environ.pop("MCP_LAUNCH_JSON", None)
    else:
        os.environ["MCP_LAUNCH_JSON"] = old_launch


@pytest.mark.live
def test_live_configure_start_and_breakpoint_roundtrip():
    try:
        launch_file = _require_live_inputs()
        launch_json = _load_launch_config(launch_file)
        if launch_json is None:
            pytest.skip("launch.json has no configurations[]")

        # Explicit lifecycle: resolve -> configure -> start.
        server.debugger_configure_session(launch_json)
        server.debugger_start_smp_session()

        bp = server.breakpoints_set_on_ule("main", 1)
        assert bp.get("valid") is True
        assert int(bp.get("id", 0)) > 0

        all_bp = server.breakpoints_get_all()
        assert isinstance(all_bp, list)
    except ThriftBridgeError as exc:
        pytest.xfail(f"Backend instability during live test: {exc}")
    finally:
        try:
            server.debugger_stop_session()
        except Exception:
            pass


@pytest.mark.live
def test_live_discovery_and_read_only_calls():
    try:
        launch_file = _require_live_inputs()
        launch_json = _load_launch_config(launch_file)
        if launch_json is None:
            pytest.skip("launch.json has no configurations[]")

        server.debugger_configure_session(launch_json)
        server.debugger_start_smp_session()

        version = server.debugger_get_version()
        assert isinstance(version, str) and version

        online = server.debugger_is_online()
        assert isinstance(online, bool)

        services = server.listwindow_list_services("trace")
        assert isinstance(services, list)

        regs = server.debugger_register_snapshot(limit=4)
        assert "registers" in regs
    except ThriftBridgeError as exc:
        # Backend can reset unexpectedly; mark as xfail to preserve useful signal.
        pytest.xfail(f"Backend instability during live test: {exc}")
    finally:
        try:
            server.debugger_stop_session()
        except Exception:
            pass
