# ReliaKit Architecture

## Core Components

### Agent System
- 16 specialized agents (12 core + 4 visual)
- JSONL configuration format
- Model arbitration between Gemini/Ollama/Claude

### Memory System
- SQLite database
- Tracks executions, configurations and relationships
- Supports reflection and evolution

### GUI Interface
- Tkinter-based dashboard
- Multiple visualization tabs
- Real-time monitoring

## Containerization
- Docker-based deployment
- X11 forwarding for GUI
- Persistent storage volumes