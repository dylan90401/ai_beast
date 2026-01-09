# Speech API (STT + TTS)

Runs locally on macOS and is designed to be pack-managed.

## Start
./bin/beast speech up

## Health
curl -s http://127.0.0.1:9977/health | jq

## Transcribe (example)
curl -s -X POST "http://127.0.0.1:9977/transcribe"   -F "file=@/path/to/audio.wav"   -F "backend=auto" | jq

## TTS (macOS)
curl -L -X POST "http://127.0.0.1:9977/tts"   -F "text=hello from ai beast"   -F "fmt=wav" -o tts.wav

### Backends
Default: faster-whisper (downloads model by name, e.g. small/medium/large-v3)
Optional: whisper.cpp
- Build created at: /Users/wolfen/_dev/_AI_Kryptos/ai_beast/apps/whispercpp/whisper.cpp/main
- Put models in: /Volumes/Sunwolf/_LLMS/models/speech/whispercpp/
- Export:
  WHISPER_CPP_BIN="/Users/wolfen/_dev/_AI_Kryptos/ai_beast/apps/whispercpp/whisper.cpp/main"
  WHISPER_CPP_MODEL="/Volumes/Sunwolf/_LLMS/models/speech/whispercpp/<model>"
  SPEECH_BACKEND="whisper_cpp"
