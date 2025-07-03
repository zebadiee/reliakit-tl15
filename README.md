# ReliaKit - Multi-Agent Codex Platform

![ReliaKit Logo](docs/images/logo.png)

ReliaKit is a containerized multi-agent system with autonomous evolution capabilities, memory tracking, and GUI visualization.

## Features

- 12 Core Agents + 4 Visual Agents
- Model arbitration and fallback
- Memory logging and reflection
- Self-evolving agentic loop
- Dockerized deployment

## Quick Start

```bash
# Build container
docker build -t reliakit-loop .

# Run with GUI (requires X11)
xhost + 127.0.0.1
docker run -it -e DISPLAY=host.docker.internal:0 -v /tmp/.X11-unix:/tmp/.X11-unix reliakit-loop

# Run headless
docker run -it reliakit-loop
```

## Documentation

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design and [docs/USAGE.md](docs/USAGE.md) for detailed usage.

## License

MIT