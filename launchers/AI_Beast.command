#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
./bin/beast menu
