#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"
mkdir -p "$DATA_DIR/media/audio" "$DATA_DIR/media/video" "$DATA_DIR/media/images" "$DATA_DIR/media/transcripts"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[pack:media_synth] DRYRUN would create media dirs under $DATA_DIR/media"
  exit 0
fi
cat > "$DATA_DIR/media/README.txt" <<EOF
Media pack:
- ComfyUI outputs can go to: $OUTPUT_DIR
- Transcripts: $DATA_DIR/media/transcripts
Example transcription (pack venv):
  $BASE_DIR/.venv_packs/media_synth/bin/whisper <file> --model small --output_dir "$DATA_DIR/media/transcripts"
EOF
