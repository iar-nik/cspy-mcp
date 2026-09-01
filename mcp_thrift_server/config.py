from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ThriftConfig:
    host: str
    port: int
    timeout_ms: int
    thrift_file: Path
    include_dirs: list[str]
    registry_host: str | None
    registry_port: int | None
    registry_service_name: str
    cspy_mode: str
    cspy_executable: Path | None
    cspy_args: list[str]
    cspy_start_timeout_ms: int
    cspy_restart_on_failure: bool


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _split_include_dirs(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def _default_thrift_file() -> Path:
    # Prefer bundled IDL from repository thrift/ folder when present.
    repo_local = Path(__file__).resolve().parent.parent / "thrift" / "cspy.thrift"
    if repo_local.exists():
        return repo_local
    # Backward-compatible fallback for older repo layouts.
    repo_legacy = Path(__file__).resolve().parent.parent / "cspy.thrift"
    if repo_legacy.exists():
        return repo_legacy
    return Path("./cspy.thrift").expanduser().resolve()


def _split_args(raw: str | None) -> list[str]:
    if not raw:
        return ["-standalone", "-sockets"]
    return [p for p in shlex.split(raw, posix=False) if p]


def load_config() -> ThriftConfig:
    host = os.getenv("THRIFT_HOST", "127.0.0.1")
    port = int(os.getenv("THRIFT_PORT", "9090"))
    timeout_ms = int(os.getenv("THRIFT_TIMEOUT_MS", "15000"))

    thrift_file_raw = os.getenv("THRIFT_FILE")
    thrift_file = (
        Path(thrift_file_raw).expanduser().resolve()
        if thrift_file_raw
        else _default_thrift_file()
    )

    include_dirs = _split_include_dirs(os.getenv("THRIFT_INCLUDE_DIRS"))
    thrift_parent = str(thrift_file.parent)
    if not include_dirs:
        include_dirs = [thrift_parent]
    elif thrift_parent not in include_dirs:
        include_dirs.append(thrift_parent)
    registry_host = os.getenv("THRIFT_REGISTRY_HOST")
    registry_port_raw = os.getenv("THRIFT_REGISTRY_PORT")
    registry_port = int(registry_port_raw) if registry_port_raw else None
    registry_service_name = os.getenv("THRIFT_REGISTRY_SERVICE", "debugger")

    cspy_mode = os.getenv("THRIFT_CSPYSERVER_MODE", "managed").strip().lower()
    if cspy_mode not in {"external", "managed"}:
        cspy_mode = "managed"

    cspy_executable_raw = os.getenv("THRIFT_CSPYSERVER_EXE")
    cspy_executable = Path(cspy_executable_raw).expanduser().resolve() if cspy_executable_raw else None
    cspy_args = _split_args(os.getenv("THRIFT_CSPYSERVER_ARGS"))
    cspy_start_timeout_ms = int(os.getenv("THRIFT_CSPYSERVER_START_TIMEOUT_MS", "20000"))
    cspy_restart_on_failure = _env_bool("THRIFT_CSPYSERVER_RESTART_ON_FAILURE", True)

    return ThriftConfig(
        host=host,
        port=port,
        timeout_ms=timeout_ms,
        thrift_file=thrift_file,
        include_dirs=include_dirs,
        registry_host=registry_host,
        registry_port=registry_port,
        registry_service_name=registry_service_name,
        cspy_mode=cspy_mode,
        cspy_executable=cspy_executable,
        cspy_args=cspy_args,
        cspy_start_timeout_ms=cspy_start_timeout_ms,
        cspy_restart_on_failure=cspy_restart_on_failure,
    )
