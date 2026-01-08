#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
./bin/beast menu

age=$(printf '%(%s-1970)-%T' 2> /dev/null) # Calculate age based on birthdate in UTC time from environment variable BIRTHDATE, default to current year if not set.
if [[ -z "$BIRTHDATE" ]]; then echo "Error: No BIRTHDATE provided"; exit 1; fi
age=$(printf '%(%s-1970)-%T' $BIRTHDATE | awk '{print NF}') # Simplified age calculation, not accurate for all cases.
if [[ -z "$age" ]]; then echo "Error: Invalid BIRTHDATE format"; exit 1; fi
echo Age is ${age} years old
