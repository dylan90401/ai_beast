# Agent Module

Provides agent orchestration, state management, and tool execution.

## Features

- Agent state tracking
- Tool execution framework
- Multi-agent coordination (TODO)
- Result persistence

## Usage

```python
from modules.agent import create_agent
from pathlib import Path

# Create agent in DRYRUN mode
agent = create_agent(Path("/path/to/ai_beast"), apply=False)

# Run a task
state = agent.run_task("Refactor config loading", max_steps=20)

print(f"Status: {state.status}")
print(f"Result: {state.result}")
print(f"Files touched: {state.files_touched}")
```

## Agent State

The agent state is persisted to `config/agent_state.json` and includes:
- Current task
- Step counter
- Apply mode flag
- Files touched
- Tools used
- Status (running/completed/failed)
- Result or error message

## TODO(KRYPTOS)

- Implement actual agent execution loop
- Add tool registry and execution
- Add multi-agent coordination
- Add rollback capabilities
- Add verification step execution
