# Critical Fixes Checklist - DO THESE FIRST

**Created**: 2026-01-09
**Priority**: URGENT - Fix before any other work
**Total Critical Issues**: 8
**Estimated Time**: 4-6 hours

---

## 🚨 SECURITY CRITICAL (Fix in next 1 hour)

### ✅ Issue #1: Installation Blocker - Dependency Typo

**Status**: [x] Fixed
**Severity**: 🔴 CRITICAL - BLOCKS ALL INSTALLATION
**Time to Fix**: 30 seconds

**Problem**:

```text
requirements.txt:8 has "quartc>=0.10.0" (typo)
Should be "quart>=0.10.0"
```

**Impact**: `pip install -r requirements.txt` fails completely

**Fix**:

```bash
# Open requirements.txt and change line 8:
# FROM: quartc>=0.10.0
# TO:   quart>=0.10.0
```

**Copilot Command**:

```text
@workspace Fix the typo in requirements.txt line 8: change quartc to quart
```

**Verification**:

```bash
./.venv/bin/python -m pip install -r requirements.txt
# Should complete without errors
```

**Reference**: CRITICAL_ISSUES_FOUND.md #1, IMPLEMENTATION_TASKS.md Task 1.1

---

### ✅ Issue #2: Path Traversal Vulnerability (CVE-WORTHY)

**Status**: [x] Fixed
**Severity**: 🔴 CRITICAL SECURITY - Arbitrary file deletion
**Time to Fix**: 5 minutes

**Problem**:

```python
# modules/llm/manager.py:463 - VULNERABLE CODE
if not any(str(fp).startswith(str(p)) for p in allowed_parents):
    return {"ok": False, "error": "Path not in allowed model directories"}
```

**Attack Vector**:

```python
# Attacker creates symlink:
# ln -s /etc/passwd ~/.beast/models/llm/evil_link
# Then calls: delete_local_model("~/.beast/models/llm/evil_link")
# String check passes, but unlink() deletes /etc/passwd!
```

**Fix**:

```python
# Implemented in modules/llm/manager.py (LLMManager.delete_local_model):

def delete_local_model(self, path: str) -> dict:
    """Delete a local model file."""
    try:
        fp = Path(path).resolve(strict=True)  # Resolve symlinks & verify exists
    except (OSError, RuntimeError) as e:
        return {"ok": False, "error": f"Invalid path: {e}"}

    # Safety check: only delete from known model directories
    allowed_parents = [
        self.llm_models_dir.resolve(),
        self.models_dir.resolve(),
        self.heavy_dir.resolve()
    ]

    if not any(fp.is_relative_to(p) for p in allowed_parents):
        return {"ok": False, "error": "Path not in allowed model directories"}

    try:
        fp.unlink()
        self._model_cache.pop(str(fp), None)
        self._cache_time = 0
        return {"ok": True, "path": str(fp)}
    except OSError as e:
        return {"ok": False, "error": str(e)}
```

**Copilot Command**:

```text
@workspace Implement Task 1.4 from IMPLEMENTATION_TASKS.md - fix the path traversal vulnerability in modules/llm/manager.py line 463. Use Path.resolve(strict=True) and is_relative_to() for proper security.
```

**Verification**:

```bash
./.venv/bin/python -m pytest -q tests/test_llm_manager_security.py
```

**Reference**: CRITICAL_ISSUES_FOUND.md #2, IMPLEMENTATION_TASKS.md Task 1.4

---

### ✅ Issue #3: SSRF Vulnerability - No URL Validation

**Status**: [x] Fixed
**Severity**: 🔴 CRITICAL SECURITY - Can attack internal services
**Time to Fix**: 10 minutes

**Problem**:

```python
# modules/llm/manager.py:368 - NO VALIDATION
req = urllib.request.Request(url)  # Accepts ANY URL!
with urllib.request.urlopen(req, timeout=60) as resp:
    # Downloads from any URL including localhost, internal IPs
```

**Attack Vector**:

```python
# Attacker can:
download_from_url("http://169.254.169.254/latest/meta-data")  # AWS secrets
download_from_url("http://localhost:11434/admin/delete")      # Internal APIs
download_from_url("http://192.168.1.1/admin")                 # Internal network
download_from_url("file:///etc/passwd")                       # File protocol
```

**Fix**:

Implemented `_validate_download_url()` and enforced it in `download_from_url()`.

Key protections:

- Only `http`/`https`
- Blocks localhost / internal IP ranges (including via DNS resolution)
- Blocks common metadata endpoints
- Rejects embedded credentials in URLs

**Copilot Command**:

```text
@workspace Implement Task 1.5 from IMPLEMENTATION_TASKS.md - add URL validation to modules/llm/manager.py download_from_url() to prevent SSRF attacks. Block localhost, private IPs, and non-http schemes.
```

**Verification**:

```python
# Test URL validation
from modules.llm.manager import LLMManager

mgr = LLMManager()

# Should block localhost
result = mgr.download_from_url("http://localhost:8080/model.gguf")
assert not result["ok"]
assert "localhost" in result["error"].lower()

# Should block private IPs
result = mgr.download_from_url("http://192.168.1.1/model.gguf")
assert not result["ok"]
assert "private" in result["error"].lower()

# Should block AWS metadata
result = mgr.download_from_url("http://169.254.169.254/latest/meta-data")
assert not result["ok"]

# Should allow public URLs
result = mgr.download_from_url("https://huggingface.co/model.gguf")
# This will fail to download but URL validation should pass

print("✓ SSRF protection working")
```

**Reference**: CRITICAL_ISSUES_FOUND.md #3, IMPLEMENTATION_TASKS.md Task 1.5

---

## ⚠️ HIGH PRIORITY (Fix in next 2 hours)

### ✅ Issue #4: Python Version Mismatch

**Status**: [x] Fixed
**Severity**: ⚠️ HIGH - Causes false negatives in linting
**Time to Fix**: 2 minutes

**Problem**:

```toml
# pyproject.toml
requires-python = ">=3.12"        # Line 12 - Requires Python 3.12
target-version = "py312"          # Line 36 - Lint target matches requirement
```

**Impact**: Ruff won't catch Python 3.12-specific syntax errors

**Fix**:

```bash
# Edit pyproject.toml line 36:
# FROM: target-version = "py311"
# TO:   target-version = "py312"
```

**Copilot Command**:

```text
@workspace Fix pyproject.toml line 36: change target-version from py311 to py312 to match the requires-python setting
```

**Verification**:

```bash
grep 'target-version' pyproject.toml
# Should show: target-version = "py312"
```

**Reference**: CRITICAL_ISSUES_FOUND.md #4, IMPLEMENTATION_TASKS.md Task 1.2

---

### ✅ Issue #5: Makefile Uses Wrong Python Command

**Status**: [x] Fixed
**Severity**: ⚠️ HIGH - Build fails on macOS/Linux
**Time to Fix**: 2 minutes

**Problem**:

```makefile
# Makefile uses "python" which points to Python 2.7 on many systems
verify:
    python scripts/00_verify_stack.py --verbose    # Line 52
lint:
    python -m ruff check .                         # Line 61
fmt:
    python -m ruff format .                        # Line 65
test:
    python -m pytest -q                            # Line 68
```

**Fix**:
Makefile now prefers repo-local `./.venv/bin/python` when present, else falls back to `python3`.

**Copilot Command**:

```text
@workspace Update Makefile to prefer repo-local ./.venv/bin/python when present (fallback python3) and use that interpreter for verify/lint/fmt/test/install.
```

**Manual Fix**:

```bash
# Make sure Makefile defines PY and uses it consistently:
# PY := $(shell if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)
# lint: ; $(PY) -m ruff check .
```

**Verification**:

```bash
make lint
# Should work without errors
```

**Reference**: CRITICAL_ISSUES_FOUND.md #5, IMPLEMENTATION_TASKS.md Task 1.3

---

## 🔐 SECURITY AUDIT REQUIRED (Next 2-4 hours)

### ✅ Issue #6: Shell Injection in Multiple Scripts

**Status**: [ ] Not Audited
**Severity**: 🔴 HIGH - Potential RCE
**Time to Fix**: 2-4 hours (audit + fixes)

**Problem**:
Audit scripts for unsafe `eval` usage and command construction from user input.

Note: `exec` used as `exec "$tool" "$@"` is typically safe; `eval` is the primary red-flag.

**Affected Files**:

1. `scripts/17_agent_verify.sh`
2. `scripts/25_compose_generate.sh`
3. `scripts/41_smoke_tests.sh`
4. `scripts/60_restore.sh`
5. `scripts/93_state.sh`
6. `scripts/94_graph.sh`
7. `scripts/96_speech.sh`
8. `scripts/lib/backup.sh`
9. `scripts/lib/deps.sh`

**Attack Example**:

```bash
#!/bin/bash
# If user input flows into eval:
user_input="'; rm -rf / #"
eval "echo $user_input"  # Executes: echo ''; rm -rf / #
```

**Fix Process**:

1. Audit each file manually
2. Find all `eval` and `exec` usages
3. Determine if input is user-controlled
4. Replace with safer alternatives:
   - Use parameter expansion instead of eval
   - Use arrays for command building
   - Validate/sanitize input first
   - Quote variables properly

**Copilot Command** (for each file):

```text
@workspace Audit scripts/17_agent_verify.sh for shell injection vulnerabilities. Find all uses of eval/exec and replace with safer alternatives. Ensure all variables are properly quoted.
```

**Manual Audit Steps**:

```bash
# For each file, search for dangerous patterns:
grep -n 'eval\|exec\|\$(' scripts/17_agent_verify.sh

# Common fixes:
# BAD:  eval "command $var"
# GOOD: command "$var"

# BAD:  exec $(some_command)
# GOOD: some_command  # Just call directly

# BAD:  file=$(cat $path)
# GOOD: file=$(cat "$path")
```

**Reference**: CRITICAL_ISSUES_FOUND.md #6, IMPLEMENTATION_TASKS.md Task 1.6

---

## 📋 Quick Reference Summary

| Issue | Severity | File | Time | Fixed |
| ------- | -------- | ------ | ------ | ------- |
| #1 Dependency typo | 🔴 BLOCKER | requirements.txt | 30s | [x] |
| #2 Path traversal | 🔴 SECURITY | modules/llm/manager.py | 5m | [x] |
| #3 SSRF vulnerability | 🔴 SECURITY | modules/llm/manager.py | 10m | [x] |
| #4 Python version | ⚠️ HIGH | pyproject.toml | 2m | [x] |
| #5 Makefile python | ⚠️ HIGH | Makefile | 2m | [x] |
| #6 Shell injection | 🔴 SECURITY | 9 shell scripts | 2-4h | [ ] |

**Total Time**: ~4-6 hours for all critical fixes

---

## 🎯 Recommended Fix Order

1. **FIRST** (15 minutes):
    - [x] Fix dependency typo (#1) - 30 seconds
    - [x] Fix path traversal (#2) - 5 minutes
    - [x] Add URL validation (#3) - 10 minutes

2. **NEXT** (5 minutes):
    - [x] Fix Python version (#4) - 2 minutes
    - [x] Fix Makefile (#5) - 2 minutes

3. **THEN** (2-4 hours):
   - [ ] Audit shell scripts (#6) - 2-4 hours

**After these fixes, install and verify**:

```bash
# Test installation
./.venv/bin/python -m pip install -r requirements.txt

# Run tests
make test

# Verify security fixes
./.venv/bin/python -m pytest -q tests/test_llm_manager_security.py
```

---

## 🔗 Full Documentation References

- **CRITICAL_ISSUES_FOUND.md** - Complete analysis of all 36 issues
- **IMPLEMENTATION_TASKS.md** - Detailed fixes for Phase 1-5
- **IMPLEMENTATION_CHECKLIST.md** - Full tracking of all 40 tasks
- **docs/instructions.md** - Development guidelines

---

## ✅ Completion Checklist

Once all critical fixes are done:

- [ ] All 6 critical issues fixed
- [ ] `pip install -r requirements.txt` works
- [ ] `make check` passes
- [ ] Security tests pass
- [ ] No shell injection vulnerabilities
- [ ] Ready to proceed with Phase 2 (Testing & Quality)

**Next Steps After Critical Fixes**:
Proceed to IMPLEMENTATION_CHECKLIST.md Phase 2 (Testing & Quality)
