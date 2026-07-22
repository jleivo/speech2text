#!/usr/bin/env python3
# v1.0.0
"""Handler installer for the speech2text project.

Scans handlers/ for MANIFEST-declaring scripts, walks the user through
magic-word configuration (interactive or flag-driven), validates the
result against the config schema, writes config.json, and optionally
updates the systemd unit's ReadWritePaths for path-type parameters.

Interactive:
    python scripts/install_handler.py

Non-interactive:
    python scripts/install_handler.py \
        --handler journal_handler --word PAIVAKIRJA \
        --aliases JOURNAL,PAIVA \
        --param destination=/srv/Obsidian/Archives/dailynotes \
        --yes

List handlers:
    python scripts/install_handler.py --list
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

import jsonschema

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HANDLERS_DIR = os.path.join(REPO_ROOT, "handlers")
DEFAULT_CONFIG_PATH = os.path.join(REPO_ROOT, "config", "config.json")
DEFAULT_UNIT_PATH = "/etc/systemd/system/speech2text.service"
DEFAULT_HELPER_SCRIPT = os.path.join(
    REPO_ROOT, "deploy", "update_readwrite_paths.sh"
)

WORD_RE = re.compile(r"^\w+$")


class InstallerError(Exception):
    """Expected installer error (bad input, validation failure, etc.)."""


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_handlers(handlers_dir):
    """Scan *handlers_dir* for .py files that declare a MANIFEST dict.

    Returns a dict mapping handler name (filename sans .py) to
    ``{"path": <repo-relative path>, "manifest": <MANIFEST dict>}``.
    Files starting with ``_`` and files without a MANIFEST are skipped.
    """
    handlers = {}
    if not os.path.isdir(handlers_dir):
        return handlers

    repo_root = os.path.dirname(os.path.abspath(handlers_dir))

    for filename in sorted(os.listdir(handlers_dir)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        filepath = os.path.join(handlers_dir, filename)
        name = filename[:-3]
        try:
            spec = importlib.util.spec_from_file_location(name, filepath)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except (ImportError, SyntaxError, OSError) as exc:
            print(
                f"Warning: skipping {filename}: {exc}", file=sys.stderr
            )
            continue

        manifest = getattr(module, "MANIFEST", None)
        if not isinstance(manifest, dict):
            continue

        handlers[name] = {
            "path": os.path.relpath(filepath, repo_root),
            "manifest": manifest,
        }
    return handlers


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------


def load_raw_config(config_path):
    """Load config.json as a raw dict (no schema validation, no defaults).

    Raises InstallerError if the file is missing or contains invalid JSON.
    """
    if not os.path.isfile(config_path):
        raise InstallerError(
            f"Config not found: {config_path}\n"
            "Copy config/config.json.example to config/config.json first."
        )
    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise InstallerError(
                f"Invalid JSON in {config_path}: {exc}"
            ) from exc


def get_installed_words(config):
    """Return set of all configured trigger words (keys + aliases), upper."""
    words = set()
    for key, entry in config.get("magic_words", {}).items():
        words.add(key.upper())
        for alias in entry.get("aliases", []):
            words.add(alias.upper())
    return words


def suggest_handlers(handlers, config):
    """Return handlers whose script_path is not yet in any magic_words entry."""
    installed_scripts = {
        entry.get("script_path", "")
        for entry in config.get("magic_words", {}).values()
    }
    default = config.get("default_action", {})
    if default:
        installed_scripts.add(default.get("script_path", ""))

    return {
        name: info
        for name, info in handlers.items()
        if info["path"] not in installed_scripts
    }


def write_config(config_path, config):
    """Write *config* to *config_path* atomically (tmp + rename)."""
    tmp_path = config_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=4, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp_path, config_path)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_word(word):
    """Raise InstallerError if *word* is not a valid magic-word key."""
    if not word:
        raise InstallerError("Magic word cannot be empty")
    if not WORD_RE.match(word):
        raise InstallerError(
            f"Invalid magic word '{word}': must match \\w+ "
            "(letters, digits, underscores)"
        )


def validate_path_value(value, param_name):
    """Raise InstallerError if *value* is not an absolute path."""
    if not os.path.isabs(value):
        raise InstallerError(
            f"Parameter '{param_name}': path must be absolute, "
            f"got '{value}'"
        )


def resolve_params(manifest, provided):
    """Merge *provided* values with MANIFEST defaults and validate.

    Returns the final params dict.  Raises InstallerError for unknown
    parameters, missing required parameters, or invalid path values.
    """
    spec = manifest.get("parameters", {})

    for key in provided:
        if key not in spec:
            raise InstallerError(f"Unknown parameter '{key}'")

    params = {}
    for name, info in spec.items():
        if name in provided:
            value = provided[name]
        elif info.get("default") is not None:
            value = str(info["default"])
        elif info.get("required"):
            raise InstallerError(
                f"Required parameter '{name}' not provided"
            )
        else:
            continue

        if info.get("type") == "path":
            validate_path_value(value, name)
        params[name] = value
    return params


def build_entry(script_path, params, aliases=None):
    """Build a magic_words config entry dict."""
    entry = {"script_path": script_path}
    entry.update(params)
    if aliases:
        entry["aliases"] = list(aliases)
    return entry


def validate_config_dict(config):
    """Validate *config* against the speech2text schema via load_config.

    Writes to a temp file and runs src.config.load_config, which applies
    both jsonschema validation and path-field checks.
    Raises InstallerError on failure.
    """
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    # Imported here so the installer module can be loaded even when src/
    # is not yet on sys.path (e.g. during test collection).
    # pylint: disable-next=import-outside-toplevel,import-error
    from src.config import load_config

    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(config, fh)
        load_config(tmp_path)
    except (jsonschema.ValidationError, ValueError, OSError) as exc:
        raise InstallerError(
            f"Config validation failed: {exc}"
        ) from exc
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Systemd helpers
# ---------------------------------------------------------------------------


def read_readwrite_paths(unit_path):
    """Parse all ReadWritePaths values from a systemd unit file."""
    paths = []
    with open(unit_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith("ReadWritePaths="):
                paths.extend(stripped.split("=", 1)[1].split())
    return paths


def find_missing_rw_paths(manifest, params, unit_path):
    """Return path-type param values absent from the unit's ReadWritePaths.

    Returns an empty list when the unit file cannot be read.
    """
    try:
        current = set(read_readwrite_paths(unit_path))
    except OSError:
        return []

    missing = []
    for pname, pinfo in manifest.get("parameters", {}).items():
        if pinfo.get("type") != "path":
            continue
        value = params.get(pname)
        if value and value not in current:
            missing.append(value)
    return missing


def run_systemd_update(paths, unit_path, helper_script):
    """Run the helper script via sudo to add *paths* to ReadWritePaths.

    Returns the helper's stdout.  Raises InstallerError on failure.
    """
    if not os.path.isfile(helper_script):
        raise InstallerError(
            f"Helper script not found: {helper_script}"
        )

    cmd = ["sudo", helper_script, "--unit-path", unit_path, *paths]
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise InstallerError(
            f"Helper failed (rc={result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------


def prompt_yes_no(question, default=True):
    """Ask a yes/no question; return bool."""
    suffix = " [Y/n] " if default else " [y/N] "
    answer = input(question + suffix).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_handler_choice(handlers):
    """Prompt the user to pick a handler by number or name."""
    names = sorted(handlers)
    while True:
        choice = input(
            f"\nSelect handler (1-{len(names)} or name): "
        ).strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(names):
                return names[idx - 1]
        elif choice in names:
            return choice
        print(f"Enter 1-{len(names)} or a handler name.")


def prompt_word():
    """Prompt for a magic word; validate format; return uppercased."""
    while True:
        word = input("Magic word: ").strip().upper()
        if not word:
            print("Word cannot be empty.")
            continue
        if not WORD_RE.match(word):
            print("Only letters, digits, and underscores allowed.")
            continue
        return word


def prompt_aliases():
    """Prompt for optional comma-separated aliases; return list."""
    raw = input("Aliases (comma-separated, or empty): ").strip()
    if not raw:
        return []
    return [a.strip().upper() for a in raw.split(",") if a.strip()]


def prompt_params(manifest):
    """Prompt for each declared parameter; return dict of provided values."""
    spec = manifest.get("parameters", {})
    if not spec:
        return {}

    print("\nParameters (press Enter to accept default):")
    provided = {}
    for name, info in spec.items():
        desc = info.get("description", "")
        default = info.get("default")
        ptype = info.get("type", "string")
        required = info.get("required", False)

        label = f"  {name}"
        if desc:
            label += f" — {desc}"
        if default is not None:
            label += f" [{default}]"
        elif required:
            label += " (required)"
        label += ": "

        while True:
            value = input(label).strip()
            if not value:
                if required and default is None:
                    print(f"    '{name}' is required.")
                    continue
                break
            if ptype == "path":
                try:
                    validate_path_value(value, name)
                except InstallerError as exc:
                    print(f"    {exc}")
                    continue
            provided[name] = value
            break
    return provided


def handle_existing_word(word, config):
    """Show the existing entry for *word*; ask edit or skip."""
    entry = config.get("magic_words", {}).get(word, {})
    print(f"\n'{word}' is already configured:")
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    if prompt_yes_no("Edit this entry?", default=False):
        return "edit"
    return "skip"


# ---------------------------------------------------------------------------
# Systemd check (shared by both flows)
# ---------------------------------------------------------------------------


def do_systemd_check(manifest, params, args):
    """Check ReadWritePaths and optionally update via the helper script."""
    missing = find_missing_rw_paths(manifest, params, args.unit_path)
    if not missing:
        print("Systemd ReadWritePaths: all paths present.")
        return

    print(f"\nMissing from ReadWritePaths: {', '.join(missing)}")

    if args.no_systemd:
        print("Skipped (--no-systemd). Add them to the unit file manually.")
        return

    if not args.yes and not prompt_yes_no(
        "Add missing paths and restart the service?"
    ):
        print("Skipped. Add them to the unit file manually.")
        return

    try:
        output = run_systemd_update(
            missing, args.unit_path, args.helper_script
        )
        print(output.strip())
    except (InstallerError, OSError) as exc:
        print(f"Warning: systemd update failed: {exc}", file=sys.stderr)
        print(
            "Add the paths to ReadWritePaths in the unit file manually.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------


def _print_handler_list(handlers, config):
    """Print all handlers with their installation status."""
    installed_scripts = {
        entry.get("script_path", "")
        for entry in config.get("magic_words", {}).values()
    }
    print("\nHandlers:")
    for i, name in enumerate(sorted(handlers), 1):
        info = handlers[name]
        desc = info["manifest"].get("description", "")
        tag = " [installed]" if info["path"] in installed_scripts else ""
        print(f"  {i}. {name}{tag} — {desc}")


def interactive_flow(args):
    """Run the interactive installation wizard."""
    handlers = discover_handlers(args.handlers_dir)
    if not handlers:
        raise InstallerError(
            f"No handlers with MANIFEST found in {args.handlers_dir}"
        )

    config = load_raw_config(args.config)
    installed_words = get_installed_words(config)

    print(f"Config: {args.config}")
    print(
        f"Installed words: "
        f"{', '.join(sorted(installed_words)) or '(none)'}"
    )
    _print_handler_list(handlers, config)

    handler_name = prompt_handler_choice(handlers)
    handler = handlers[handler_name]
    manifest = handler["manifest"]

    word = prompt_word()
    editing = word in installed_words
    if editing and handle_existing_word(word, config) == "skip":
        return 0

    aliases = prompt_aliases()
    provided = prompt_params(manifest)
    params = resolve_params(manifest, provided)
    entry = build_entry(handler["path"], params, aliases)

    verb = "Updating" if editing else "Adding"
    print(f"\n{verb} '{word}':")
    print(json.dumps(entry, indent=2, ensure_ascii=False))

    if not prompt_yes_no("Write to config?"):
        print("Aborted.")
        return 1

    config.setdefault("magic_words", {})[word] = entry
    validate_config_dict(config)
    write_config(args.config, config)
    print(f"Written to {args.config}")

    if not args.no_systemd:
        do_systemd_check(manifest, params, args)
    return 0


def parse_param_flags(param_list):
    """Parse ``--param KEY=VALUE`` flags into a dict."""
    provided = {}
    for item in param_list:
        if "=" not in item:
            raise InstallerError(
                f"Invalid --param format: '{item}' (expected KEY=VALUE)"
            )
        key, value = item.split("=", 1)
        if not key:
            raise InstallerError(
                f"Empty parameter name in --param '{item}'"
            )
        provided[key] = value
    return provided


def noninteractive_flow(args):
    """Run a fully flag-driven installation (no prompts with --yes)."""
    handlers = discover_handlers(args.handlers_dir)
    if args.handler not in handlers:
        raise InstallerError(
            f"Unknown handler '{args.handler}'. "
            f"Available: {', '.join(sorted(handlers)) or '(none)'}"
        )

    handler = handlers[args.handler]
    manifest = handler["manifest"]
    config = load_raw_config(args.config)
    installed_words = get_installed_words(config)

    word = args.word.upper()
    validate_word(word)

    aliases = (
        [a.strip().upper() for a in args.aliases.split(",") if a.strip()]
        if args.aliases
        else []
    )

    provided = parse_param_flags(args.param)
    params = resolve_params(manifest, provided)
    entry = build_entry(handler["path"], params, aliases)

    editing = word in installed_words
    if editing and not args.yes:
        if sys.stdin.isatty():
            if handle_existing_word(word, config) == "skip":
                return 0
        else:
            raise InstallerError(
                f"Word '{word}' already exists. Use --yes to overwrite."
            )

    config.setdefault("magic_words", {})[word] = entry
    validate_config_dict(config)
    write_config(args.config, config)

    verb = "Updated" if editing else "Installed"
    print(f"{verb} '{word}' -> {handler['path']}")

    if not args.no_systemd:
        do_systemd_check(manifest, params, args)
    return 0


def list_handlers(args):
    """Print available handlers and installed words, then exit."""
    handlers = discover_handlers(args.handlers_dir)

    if os.path.isfile(args.config):
        config = load_raw_config(args.config)
        installed_words = get_installed_words(config)
        installed_scripts = {
            e.get("script_path", "")
            for e in config.get("magic_words", {}).values()
        }
    else:
        installed_words = set()
        installed_scripts = set()

    if not handlers:
        print("No handlers with MANIFEST found.")
        return 0

    print("Handlers:")
    for name in sorted(handlers):
        info = handlers[name]
        desc = info["manifest"].get("description", "")
        status = (
            "installed"
            if info["path"] in installed_scripts
            else "available"
        )
        print(f"  {name} [{status}] — {desc}")
        for pname, pinfo in info["manifest"].get("parameters", {}).items():
            req = "required" if pinfo.get("required") else "optional"
            ptype = pinfo.get("type", "string")
            default = pinfo.get("default", "—")
            print(f"    {pname}: {ptype}, {req}, default={default}")

    words_str = ", ".join(sorted(installed_words)) or "(none)"
    print(f"\nInstalled words: {words_str}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser():
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Install speech2text handlers into config.json",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.json (default: %(default)s)",
    )
    parser.add_argument(
        "--handlers-dir",
        default=DEFAULT_HANDLERS_DIR,
        help="Directory containing handler scripts (default: %(default)s)",
    )
    parser.add_argument(
        "--unit-path",
        default=DEFAULT_UNIT_PATH,
        help="Path to the systemd unit file (default: %(default)s)",
    )
    parser.add_argument(
        "--helper-script",
        default=DEFAULT_HELPER_SCRIPT,
        help="Path to the ReadWritePaths update helper "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available handlers and installed words, then exit",
    )
    parser.add_argument(
        "--handler",
        help="Handler name (non-interactive mode)",
    )
    parser.add_argument(
        "--word",
        help="Magic word (non-interactive mode)",
    )
    parser.add_argument(
        "--aliases",
        default="",
        help="Comma-separated aliases (non-interactive mode)",
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Parameter value; repeatable (non-interactive mode)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts",
    )
    parser.add_argument(
        "--no-systemd",
        action="store_true",
        help="Skip the systemd ReadWritePaths update",
    )
    return parser


def main(argv=None):
    """CLI entry point.  Returns process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.list:
            return list_handlers(args)
        if args.handler and args.word:
            return noninteractive_flow(args)
        if args.handler or args.word:
            parser.error("--handler and --word must be used together")
        return interactive_flow(args)
    except InstallerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
