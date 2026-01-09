# Utils Module

Common utility functions used across AI Beast modules.

## Features

- Command execution helpers
- Base directory detection
- Config file reading (JSON/YAML)
- File system operations
- Formatting utilities

## Usage

```python
from modules.utils import run_command, get_base_dir, read_config_file, format_bytes
from pathlib import Path

# Run a command
code, out, err = run_command(["ls", "-la"], cwd=Path("/tmp"))
print(f"Exit code: {code}")

# Get base directory
base = get_base_dir()
print(f"Base: {base}")

# Read config
config = read_config_file(base / "config" / "features.yml")
print(config)

# Format bytes
print(format_bytes(1536000))  # "1.5 MB"
```

## TODO(KRYPTOS)

- Add caching utilities
- Add retry logic for commands
- Add progress indicators
- Add temporary file management
