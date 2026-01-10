#!/usr/bin/env bash
set -euo pipefail

ux_ts() { date +"%Y-%m-%d %H:%M:%S"; }
ux_info() { printf "%s | INFO  | %s\n" "$(ux_ts)" "$*" >&2; }
ux_warn() { printf "%s | WARN  | %s\n" "$(ux_ts)" "$*" >&2; }
ux_err()  { printf "%s | ERROR | %s\n" "$(ux_ts)" "$*" >&2; }
ux_ok()   { printf "%s | OK    | %s\n" "$(ux_ts)" "$*" >&2; }

die() { ux_err "$*"; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }