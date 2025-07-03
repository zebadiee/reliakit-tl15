# ReliaKit Usage Guide

## Basic Commands

```bash
# Seed database
docker run -it reliakit-loop --seed

# Run agent
docker run -it reliakit-loop --execute "AgentName" --input "data"

# Launch GUI
docker run -it -e DISPLAY=host.docker.internal:0 -v /tmp/.X11-unix:/tmp/.X11-unix reliakit-loop

# Run evolution loop
docker run -it reliakit-loop --loop
```

## Configuration

Place agent configs in:
`generated_configs/reliakit_codex_gpts.jsonl`

## Volumes

Persist these directories:
- `./generated_configs`
- `./memory.db`