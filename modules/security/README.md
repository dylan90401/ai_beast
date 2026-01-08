# Security Module

Provides security scanning, validation, and enforcement for AI Beast.

## Features

- File hash computation and verification
- Secret scanning in files
- Permission validation
- Trust enforcement helpers

## Usage

```python
from modules.security import compute_sha256, verify_file_hash, scan_for_secrets
from pathlib import Path

# Compute hash
hash_val = compute_sha256(Path("/path/to/model.safetensors"))
print(f"SHA256: {hash_val}")

# Verify hash
is_valid = verify_file_hash(
    Path("/path/to/model.safetensors"),
    "abc123..."
)

# Scan for secrets
with open("config.yaml") as f:
    findings = scan_for_secrets(f.read())
    for finding in findings:
        print(f"Found {finding['type']} at position {finding['position']}")
```

## TODO(KRYPTOS)

- Add ClamAV integration for virus scanning
- Add SBOM (Software Bill of Materials) generation
- Add CVE checking for dependencies
- Add compliance checks (PCI, HIPAA, etc.)
