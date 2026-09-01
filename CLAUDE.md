# CLAUDE.md

## Project Summary
This repository hosts a Python MCP server that bridges to IAR C-SPY Thrift services.

Core goal:
- Expose C-SPY debugger/service operations as MCP tools for AI assistants.

Current state:
- Working MCP server implementation with registry-aware service resolution.
- Supports stdio (default) and streamable-http MCP transports.
- Includes auto-registration of a debug event handler service.
- Expanded service coverage: debugger, breakpoints, contextmanager, memory, disassembly, sourcelookup, symbols.

## Key Files
- `mcp_thrift_server/server.py`: MCP tool definitions and orchestration.
- `mcp_thrift_server/thrift_client.py`: Thrift loading, registry resolution, clients, serialization.
- `mcp_thrift_server/config.py`: Environment-driven configuration model.
- `mcp_thrift_server/__main__.py`: Entrypoint and transport selection.
- `README.md`: Setup, env vars, usage, VS Code MCP integration.
- `requirements.txt`: Runtime dependencies (`mcp<2.0.0`, `thriftpy2`).

## Dependency and Compatibility Notes
- `mcp` must stay below 2.0.0 because current server uses `FastMCP` import path/API.
- `thriftpy2` is used for dynamic loading of `cspy.thrift` and dependent IDL files.

## Environment Contract
Common required env vars:
- `THRIFT_FILE`: Absolute path to `cspy.thrift`.
- `THRIFT_INCLUDE_DIRS`: Semicolon-separated include paths containing dependent thrift IDLs (for example `shared.thrift`).
- `THRIFT_REGISTRY_HOST`: Service Registry host.
- `THRIFT_REGISTRY_PORT`: Service Registry port.

Useful optional env vars:
- `MCP_TRANSPORT=stdio|streamable-http`
- `MCP_HOST`, `MCP_PORT`, `MCP_PATH` for network mode.

## Runtime Architecture
1. MCP tool call enters `server.py`.
2. Server uses `thrift_client.py` to resolve service endpoints via Service Registry.
3. Client connects to the resolved service (debugger, breakpoints, etc.).
4. Responses are normalized to plain JSON-safe objects.

Important behavior:
- Registry endpoint is not usually the debugger endpoint itself.
- Session configuration is generally required before most debugger-dependent operations.
- Reconfigure flow uses stop-before-configure best effort to avoid backend state conflicts.

## Implemented Tool Surface (High-Level)
Debugger:
- Configure/start/stop/control/session lifecycle tools.

Breakpoints:
- List/get/set-from-descriptor/set-on-ULE/enable/remove/recently-hit.

Context manager:
- Stack and context helpers.

Memory:
- Memory read and hex write helpers.

Disassembly:
- Range disassembly tool.

Source lookup:
- Source range lookup.

Symbols:
- Visible symbols listing and lookup helpers.

Fallback:
- Generic debugger call tool for unwrapped methods.

## Breakpoint API Guidance (Important)
### `breakpoints_set_on_ule`
Primary API for creating breakpoints/watchpoints.

- Recommended code breakpoint call: `breakpoints_set_on_ule("main", 1)`
- `access_type` common mapping:
  - `1`: execute/fetch code breakpoint
  - `2`: read watchpoint
  - `3`: write watchpoint
  - `4`: read/write watchpoint

ULE format is backend-specific. Try in this order:
1. `main`
2. `file.c:123`
3. `E:/absolute/path/file.c:123`

Notes:
- Some backends reject `main()` while accepting `main`.
- Failures can also be due to backend/session instability, not just ULE syntax.

### `breakpoints_set_from_descriptor`
Do not pass handcrafted descriptor strings.

- Intended workflow:
  1. call `breakpoints_get_all()`
  2. take `descriptor` from returned breakpoint entry
  3. pass that descriptor back to `breakpoints_set_from_descriptor(...)`

Descriptor formats are opaque and backend-version dependent.

## Known Backend Issues Observed
These are external/backend-side, frequently encountered during live testing:
- Connection reset (`WinError 10054`) during/after configure/start.
- Startup failures such as missing frontend service in some launch modes.
- Flash loading failures during start.
- Backend process exiting unexpectedly after some RPC sequences.

Implications:
- Tool failures may be transport/backend lifecycle failures rather than API misuse.
- Fresh backend start and quick validation window are often required.

## Recommended Validation Workflow
1. Start CSpyServer2 in a known-good mode.
2. Export required `THRIFT_*` env vars.
3. Run a minimal sequence:
   - `debugger_get_version_string`
   - `debugger_configure_session`
   - `debugger_start_smp_session` (if target supports)
   - `breakpoints_get_all`
   - `breakpoints_set_on_ule("main", 1)`
4. If failure occurs, capture backend stderr/stdout and retry from fresh server process.

## Useful Local Commands
Compile check:
```powershell
python -m compileall mcp_thrift_server
```

MCP stdio smoke test:
```powershell
python smoke_test_mcp_stdio.py
```

Live end-to-end demo (bundled simulator assets):
```powershell
python examples/run_live_demo.py
```

## Current Priority and Next Work
Highest priority:
- Keep breakpoint behavior clear for AI callers with actionable errors and docs.
- Preserve robust registry/eventhandler behavior across backend restarts.

Good next steps:
- Add a higher-level helper tool that attempts common ULE variants and reports normalized diagnostics.
- Add lightweight retry/backoff around transient transport resets where safe.
- Add a stable integration test harness that can skip tests when backend health is not good.

## Notes for Future Agents
- Do not assume backend stability; validate with short, focused call sequences.
- Treat descriptor inputs as opaque round-trip values only.
- Keep changes small and avoid broad refactors in `server.py` unless necessary.
- Re-run `python -m compileall mcp_thrift_server` after edits.
