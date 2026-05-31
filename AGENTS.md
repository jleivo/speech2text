# AGENTS.md

This file provides guidance to OpenCode agents when working with code in this repository.

## Quick Commands

**Setup:**
```bash
python3 -m venv .venv --prompt speech2text
source .venv/bin/activate
pip install -r requirements.txt
```

**Run:**
```bash
python -m src.main
# or
python src/main.py
```

**Test:**
```bash
# Unit tests only (~4s, no external deps)
pytest tests/ -v --ignore=tests/test_transcribe_integration.py

# Integration tests (requires LiteLLM server)
pytest tests/test_transcribe_integration.py -v
```

**Commit:**
```bash
git add .
git commit -m "<type>: <description>"
git push
```

## Architecture

```
src/
  main.py            # Entry point: loads config, starts watchdog Observer
  config.py          # JSON config + jsonschema validation, defaults injected
  transcribe.py      # LiteLLM API → local Whisper fallback
  router.py          # Magic word matching (case-insensitive), subprocess dispatch
  folder_watcher.py  # File event handler: wait_for_file → transcribe → route → log
  logger.py          # JSON-line transcription logging
config/
  config.json        # Runtime config (folder_to_watch, magic_words, etc)
examples/
  create_note.py     # Sample action script
  append_log.py      # Sample action script
tests/
  test_*.py          # 30 unit tests + 2 integration tests
  audio/             # Test audio files (.m4a)
docs/
  user-guide.md      # Full user documentation
  test-guide.md      # Test suite documentation
  systemd-setup.md   # Production deployment guide
  SECRETS.md         # Secrets management policy
```

## Config Schema

Required fields:
- `folder_to_watch` — directory to monitor
- `magic_words` — map of uppercase trigger words to `script_path`

Optional (with defaults):
- `watched_extensions` — [".wav", ".mp3", ".flac", ".m4a", ".ogg"]
- `delete_after_processing` — false
- `transcription_log` — path to JSON-line log
- `backend` — "litellm" (default) or "local"
- `model` — "whisper-1" (LiteLLM) or "tiny/base/small/medium/large/turbo" (local)
- `default_action` — script for unmatched transcriptions (receives full text)

Config validation: jsonschema enforces required fields, magic word keys must be `^[A-Z]+$`.

## Magic Word Routing

1. First word of transcription matched against `magic_words` keys (case-insensitive)
2. Matching script receives remaining text (magic word stripped)
3. No match + `default_action` configured → default script receives full text
4. No match + no default → silently ignored
5. Scripts called as: `python <script_path> <text>`
6. Exit code 0 = success, non-zero = failure logged

## Transcription Flow

1. LiteLLM backend: calls `litellm.transcription()` with `OPENAI_API_KEY` env var
2. On failure → fallback to local Whisper with `turbo` model
3. Local backend: `whisper.load_model(<model>).transcribe()`
4. File handler waits for file size stability before processing

## Environment Variables

- `OPENAI_API_KEY` — required for LiteLLM backend
- `OPENAI_API_BASE` — optional custom LiteLLM server URL
- `LITELLM_BASE_URL` — integration test override
- `LITELLM_MODEL` — integration test model override

**IMPORTANT:** Never store secrets in text files. See [docs/SECRETS.md](docs/SECRETS.md) for secrets management policy.

## Testing Patterns

- Unit tests use `unittest.mock.patch` for all external deps (litellm, whisper, subprocess)
- Integration tests auto-skip if LiteLLM server unreachable
- Test audio files in `tests/audio/` are Finnish recordings
- Run `pytest tests/test_<module>.py -v` for focused testing

## Gotchas

- Config path relative to working directory (default: `config/config.json`)
- Magic word keys in config must be uppercase letters only
- Scripts must be executable or callable via `python <script> <text>`
- Audio file always kept on error (never deleted on failure)
- Integration tests require LiteLLM server running at configured URL

## Commit Messages

Use conventional commit style:
- `feat:` — new feature
- `fix:` — bug fix
- `test:` — adding or modifying tests
- `docs:` — documentation changes
- `refactor:` — code restructuring without behavior change
- `chore:` — maintenance tasks

Examples:
- `feat: add EMAIL magic word for email notifications`
- `fix: handle empty transcription in router`
- `test: add unit test for config validation`

## Secret management

see docs/SECRETS.md

## CHANGELOG

Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format in `CHANGELOG.md`:

- Every feature, fix, or change goes under `[Unreleased]` as you work
- Use `### Added`, `### Changed`, `### Fixed`, `### Removed`, `### Deprecated`, `### Security`
- When a release is made, rename `[Unreleased]` to the new version with today's date (e.g. `## [1.1.0] - 2026-05-21`) and add a fresh empty `[Unreleased]` section above it
- Version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)