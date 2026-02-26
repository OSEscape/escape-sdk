# CLAUDE.md

## Overview

Bridge is a gRPC bridge between a Python SDK and RuneLite (OSRS client). Linux only.

## Architecture

Python SDK communicates with a Java gRPC server over Unix socket. The server is a RuneLite plugin that uses RuneLite's API to interact with the game client.

```
RuneLite EventBus → BridgePlugin @Subscribe → Handler → SubscribeHandler → gRPC
     ↓                                                                     ↓
EventConsumer (Python) ← ProcessedCache ← Event routing
```

**Key Flow:**
1. Game state changes → RuneLite fires event
2. `@Subscribe` handler in `BridgePlugin.java` receives it
3. Domain handler converts to proto message
4. `SubscribeHandler` broadcasts to Python
5. `EventConsumer` updates `ProcessedCache`
6. Python reads from cache (no RPC)

**RuneLite Plugin Principles:**

- Use RuneLite's plugin API directly. RuneLite's Guice injector provides the `Client` instance, `EventBus` delivers game events.
- Never reflect on the obfuscated OSRS game client. RuneLite handles deobfuscation; we stay above it.
- Never invoke game actions directly (menu actions, etc.) that bypass normal input. Direct invoke is equivalent to injection from an anticheat perspective. Use mouse input simulation instead.

## Build Commands

- `make all` - Build everything
- `make test` - Lint, typecheck, tests
- `make format` - Auto-format Python
- `make kill` - Kill RuneLite

## Adding New RPCs

1. Define messages and service method in `proto/bridge/v1/bridge.proto`
2. Add handler method in Java (auto-discovered by `ReflectiveServiceBuilder`)
3. `make all`
4. Call via `client.stub.RpcName(request)`

Naming convention: RPC `GetFoo` → handler method `getFoo(GetFooRequest req)`

Use `direct=True` on stub calls to skip ClientThread dispatch for RPCs that don't access game state.

## Adding New Events

1. Add message to `ServerMessage` oneof in `proto/bridge/v1/bridge.proto`
2. Create/update handler in `server/src/main/java/bridge/handlers/`
3. Add `@Subscribe` handler in `BridgePlugin.java`, call handler method
4. Process in `escape/_cache/event_processor.py`
5. `make all`

## Boundary Design

Python and Java communicate over gRPC with two patterns: event streaming for state synchronization (Java pushes game state updates and geometry, Python caches them) and request-response RPCs for queries (Python asks Java for data like clickbox tracking). All input simulation (mouse, keyboard) happens in Python via Linux evdev.

1. **Input is Python-side** - Python moves the mouse and clicks via evdev. Java streams clickbox polygons so Python knows where to click. Java never executes input.
2. **Geometry streams from Java** - Clickbox vertices, entity positions, widget bounds flow from Java to Python. Python calculates click targets from this geometry.
3. **Verification via events** - RuneLite's MenuOptionClicked fires after a click lands. Java streams this back so Python can confirm the action succeeded.
4. **Minimal proto fields** - Only include fields Python actually uses. Remove dead fields.
5. **State via streaming** - Use event streaming + `ProcessedCache` for repeated access. Avoid polling RPCs.

Sleeps for input timing (drag duration, typing delay) are intentional human simulation, not state coordination.

## Important Details

- Always use RuneLite API, never game client reflection
- Java server shades all dependencies to avoid classpath conflicts with RuneLite
- SDK package is named `escape`, not `bridge`
- Unix socket path: `$XDG_RUNTIME_DIR/bridge.sock` (default) or `$BRIDGE_SOCKET`

## Testing

### Philosophy

Write tests. Not too many. Mostly integration. Static analysis (ruff, basedpyright) replaces an entire category of tests — don't write a test for something a linter or type checker already catches.

### Test Tiers

1. **Smoke tests** (highest ROI) — connect to live client, verify all snapshot caches populate. One test that validates the full pipeline (Java → gRPC → Python → cache) replaces dozens of narrow unit tests. These live in `test_snapshots.py`.

2. **Unit tests** (pure algorithms only) — behavior trees, distance calculations, anything with complex logic and zero dependencies. Everything else is better tested through integration.

3. **Scenario tests** (critical paths) — scripted workflows that exercise a real game interaction end-to-end. Reserved for features where the smoke test isn't sufficient. Mark with `slow` and `input`.

### Rules

- **Consolidate, don't proliferate.** One test asserting all entity caches populated beats three separate entity tests. Each test must justify its existence.
- **Never test through UI.** Call underlying systems directly. UI-driven tests create false positives and kill trust in automation.
- **Test behavior, not implementation.** If refactoring breaks a test but behavior is unchanged, the test is wrong.
- **Zero flake tolerance.** A flaky test is worse than no test. Fix or remove immediately.
- **No game interaction in smoke tests.** Smoke tests are passive (read cache state). Game interaction (opening tabs, clicking) belongs in scenario tests with explicit `input` marker.

### Running Tests

Environment variables in `.env` configure credentials and world selection for live tests.

Markers: `live` (requires running client), `smoke` (quick validation), `slow` (tests with sleeps), `input` (sends input to game).

Running subsets: `-m "not input"` for read-only, `-m "not slow"` to skip stream tests.
