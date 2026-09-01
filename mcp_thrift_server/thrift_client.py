from __future__ import annotations

import hashlib
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import thriftpy2
from thriftpy2.rpc import make_client

from .config import ThriftConfig
from .cspy_server_manager import apply_managed_registry_to_config


class ThriftBridgeError(RuntimeError):
    """Raised when the bridge cannot load IDL or invoke backend RPC."""


def _module_name_for(path: Path) -> str:
    digest = hashlib.md5(str(path).encode("utf-8")).hexdigest()
    return f"cspy_{digest}_thrift"


def _find_service_registry_thrift(include_dirs: tuple[str, ...]) -> Path | None:
    for inc in include_dirs:
        candidate = Path(inc) / "ServiceRegistry.thrift"
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=8)
def load_thrift_module(thrift_file: str, include_dirs: tuple[str, ...]):
    path = Path(thrift_file)
    if not path.exists():
        raise ThriftBridgeError(f"Thrift file not found: {path}")

    try:
        return thriftpy2.load(
            str(path),
            module_name=_module_name_for(path),
            include_dirs=list(include_dirs),
        )
    except Exception as exc:  # noqa: BLE001
        raise ThriftBridgeError(
            "Failed to load thrift IDL. Check THRIFT_FILE and THRIFT_INCLUDE_DIRS "
            "(for cspy.thrift, shared.thrift must be resolvable)."
        ) from exc


@lru_cache(maxsize=8)
def load_service_registry_module(include_dirs: tuple[str, ...]):
    registry_thrift = _find_service_registry_thrift(include_dirs)
    if registry_thrift is None:
        raise ThriftBridgeError(
            "ServiceRegistry.thrift not found in THRIFT_INCLUDE_DIRS; cannot resolve service via registry"
        )

    try:
        return thriftpy2.load(
            str(registry_thrift),
            module_name=_module_name_for(registry_thrift),
            include_dirs=list(include_dirs),
        )
    except Exception as exc:  # noqa: BLE001
        raise ThriftBridgeError("Failed to load ServiceRegistry.thrift") from exc


def resolve_service_endpoint(config: ThriftConfig, service_name: str) -> tuple[str, int]:
    try:
        config = apply_managed_registry_to_config(config)
    except Exception as exc:  # noqa: BLE001
        raise ThriftBridgeError(f"Failed to prepare managed CSpyServer2: {exc}") from exc

    if config.registry_port is None:
        if service_name == "debugger":
            return config.host, config.port
        raise ThriftBridgeError(
            f"THRIFT_REGISTRY_PORT is required to resolve service '{service_name}'"
        )

    registry_host = config.registry_host or config.host
    registry_mod = load_service_registry_module(tuple(config.include_dirs))

    try:
        registry = make_client(
            registry_mod.CSpyServiceRegistry,
            registry_host,
            config.registry_port,
            timeout=config.timeout_ms,
        )
        try:
            location = registry.waitForService(service_name, config.timeout_ms)
        finally:
            registry.close()
    except Exception as exc:  # noqa: BLE001
        raise ThriftBridgeError(
            f"Failed to resolve service '{service_name}' via registry "
            f"at {registry_host}:{config.registry_port}: {exc}"
        ) from exc

    transport = getattr(location, "transport", None)
    if int(transport) != 0:
        host = getattr(location, "host", "")
        raise ThriftBridgeError(
            "Registry resolved a non-socket endpoint. "
            f"This bridge currently supports socket endpoints only. Resolved host={host}, transport={transport}."
        )

    return str(location.host), int(location.port)


def resolve_debugger_endpoint(config: ThriftConfig) -> tuple[str, int]:
    return resolve_service_endpoint(config, config.registry_service_name)


def get_debugger_service(config: ThriftConfig):
    mod = load_thrift_module(str(config.thrift_file), tuple(config.include_dirs))
    service = getattr(mod, "Debugger", None)
    if service is None:
        raise ThriftBridgeError("Service 'Debugger' not found in thrift module")
    return service


@contextmanager
def open_debugger_client(config: ThriftConfig) -> Iterator[Any]:
    service = get_debugger_service(config)
    host, port = resolve_debugger_endpoint(config)
    client = make_client(
        service,
        host,
        port,
        timeout=config.timeout_ms,
    )
    try:
        yield client
    except Exception as exc:  # noqa: BLE001
        raise ThriftBridgeError(f"Thrift RPC failed: {exc}") from exc
    finally:
        try:
            client.close()
        except Exception:
            pass


def to_plain(value: Any) -> Any:
    """Convert thrift objects into JSON-serializable plain Python structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if isinstance(value, tuple):
        return [to_plain(v) for v in value]
    if isinstance(value, set):
        return [to_plain(v) for v in sorted(value, key=repr)]
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}

    thrift_spec = getattr(value, "thrift_spec", None)
    if thrift_spec is not None:
        payload = {}
        items = thrift_spec.values() if isinstance(thrift_spec, dict) else thrift_spec
        for item in items:
            if not item:
                continue
            name = None
            if len(item) >= 2 and isinstance(item[1], str):
                name = item[1]
            elif len(item) >= 3 and isinstance(item[2], str):
                name = item[2]
            if not name:
                continue
            payload[name] = to_plain(getattr(value, name, None))
        return payload

    if hasattr(value, "__dict__"):
        return {k: to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}

    return repr(value)
