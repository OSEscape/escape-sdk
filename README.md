# Bridge

gRPC bridge between Python SDK and RuneLite. Linux only.

## Quick Start

Requires: Java 17+, GCC, buf, uv

```bash
make all && cd loader && make run
```

## Development

```bash
make all       # Build everything
make test      # Lint + typecheck + tests
make kill      # Kill RuneLite
```
