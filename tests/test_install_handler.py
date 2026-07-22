#!/usr/bin/env python3
# v1.0.0
"""Tests for scripts/install_handler.py — the handler installer.

All subprocess/sudo/systemd calls are mocked; tests never require root
or touch real systemd.  A throwaway handlers/ dir and config.json are
created per-test in a temp directory.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

import pytest

# Make the scripts/ directory importable.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# install_handler lives in scripts/ (added to sys.path above), so pylint
# cannot resolve it statically; the import-error is a false positive.
# redefined-outer-name is the standard pytest fixture-passing idiom.
# pylint: disable=import-error,redefined-outer-name
import install_handler as ih  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


HANDLER_SRC = '''\
MANIFEST = {{
    "description": "{desc}",
    "parameters": {{
        "destination": {{
            "description": "Base directory",
            "required": True,
            "default": "{default}",
            "type": "path",
        }}
    }},
}}
'''

HANDLER_NO_PARAMS_SRC = '''\
MANIFEST = {
    "description": "A handler with no parameters",
    "parameters": {},
}
'''

HANDLER_STRING_PARAM_SRC = '''\
MANIFEST = {
    "description": "A handler with a string param",
    "parameters": {
        "subject": {
            "description": "Email subject",
            "required": True,
            "default": "Note",
            "type": "string",
        }
    },
}
'''

HANDLER_NO_MANIFEST_SRC = '''\
# A handler without a MANIFEST — should be skipped by discovery.
def main():
    pass
'''


@pytest.fixture
def workspace():
    """Create a temp repo layout with handlers/ and config/config.json."""
    tmpdir = tempfile.mkdtemp()
    handlers_dir = os.path.join(tmpdir, "handlers")
    config_dir = os.path.join(tmpdir, "config")
    os.makedirs(handlers_dir)
    os.makedirs(config_dir)

    # Two path-param handlers, one string-param, one without MANIFEST.
    with open(
        os.path.join(handlers_dir, "journal_handler.py"), "w", encoding="utf-8"
    ) as fh:
        fh.write(
            HANDLER_SRC.format(
                desc="Journal handler",
                default="/srv/Obsidian/Archives/dailynotes",
            )
        )
    with open(
        os.path.join(handlers_dir, "note_handler.py"), "w", encoding="utf-8"
    ) as fh:
        fh.write(
            HANDLER_SRC.format(
                desc="Note handler", default="/srv/Obsidian/Inbox"
            )
        )
    with open(
        os.path.join(handlers_dir, "email_handler.py"), "w", encoding="utf-8"
    ) as fh:
        fh.write(HANDLER_STRING_PARAM_SRC)
    with open(
        os.path.join(handlers_dir, "plain_handler.py"), "w", encoding="utf-8"
    ) as fh:
        fh.write(HANDLER_NO_MANIFEST_SRC)
    # A file that should be ignored (underscore prefix).
    with open(
        os.path.join(handlers_dir, "_private.py"), "w", encoding="utf-8"
    ) as fh:
        fh.write(HANDLER_NO_PARAMS_SRC)

    config_path = os.path.join(config_dir, "config.json")
    config = {
        "folder_to_watch": "/srv/speech2text/audio_transfer",
        "magic_words": {
            "NOTE": {
                "script_path": "handlers/note_handler.py",
                "destination": "/srv/Obsidian/Inbox",
            }
        },
    }
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh)

    yield {
        "tmpdir": tmpdir,
        "handlers_dir": handlers_dir,
        "config_path": config_path,
    }

    shutil.rmtree(tmpdir, ignore_errors=True)


def _make_args(workspace, **overrides):
    """Build an argparse.Namespace mimicking parsed CLI args."""
    args = {
        "config": workspace["config_path"],
        "handlers_dir": workspace["handlers_dir"],
        "unit_path": "/etc/systemd/system/speech2text.service",
        "helper_script": os.path.join(
            REPO_ROOT, "deploy", "update_readwrite_paths.sh"
        ),
        "list": False,
        "handler": None,
        "word": None,
        "aliases": "",
        "param": [],
        "yes": False,
        "no_systemd": True,
    }
    args.update(overrides)
    return argparse.Namespace(**args)


import argparse  # noqa: E402  (used by _make_args)


# ---------------------------------------------------------------------------
# MANIFEST discovery
# ---------------------------------------------------------------------------


class TestDiscoverHandlers:
    def test_discovers_manifest_handlers(self, workspace):
        handlers = ih.discover_handlers(workspace["handlers_dir"])
        assert "journal_handler" in handlers
        assert "note_handler" in handlers
        assert "email_handler" in handlers

    def test_skips_handler_without_manifest(self, workspace):
        handlers = ih.discover_handlers(workspace["handlers_dir"])
        assert "plain_handler" not in handlers

    def test_skips_underscore_prefixed_files(self, workspace):
        handlers = ih.discover_handlers(workspace["handlers_dir"])
        assert "_private" not in handlers

    def test_manifest_shape(self, workspace):
        handlers = ih.discover_handlers(workspace["handlers_dir"])
        manifest = handlers["journal_handler"]["manifest"]
        assert "description" in manifest
        assert "parameters" in manifest
        assert manifest["parameters"]["destination"]["type"] == "path"

    def test_repo_relative_path(self, workspace):
        handlers = ih.discover_handlers(workspace["handlers_dir"])
        assert handlers["journal_handler"]["path"] == os.path.join(
            "handlers", "journal_handler.py"
        )

    def test_missing_dir_returns_empty(self):
        assert ih.discover_handlers("/nonexistent/dir") == {}


# ---------------------------------------------------------------------------
# Config diff (installed vs available)
# ---------------------------------------------------------------------------


class TestConfigDiff:
    def test_get_installed_words(self, workspace):
        config = ih.load_raw_config(workspace["config_path"])
        words = ih.get_installed_words(config)
        assert "NOTE" in words

    def test_get_installed_words_includes_aliases(self):
        config = {
            "magic_words": {
                "PÄIVÄKIRJA": {
                    "script_path": "handlers/journal_handler.py",
                    "aliases": ["JOURNAL", "PÄIVÄ"],
                }
            }
        }
        words = ih.get_installed_words(config)
        assert {"PÄIVÄKIRJA", "JOURNAL", "PÄIVÄ"} <= words

    def test_suggest_excludes_installed(self, workspace):
        handlers = ih.discover_handlers(workspace["handlers_dir"])
        config = ih.load_raw_config(workspace["config_path"])
        suggested = ih.suggest_handlers(handlers, config)
        # note_handler is installed -> excluded
        assert "note_handler" not in suggested
        assert "journal_handler" in suggested

    def test_suggest_excludes_default_action(self, workspace):
        handlers = ih.discover_handlers(workspace["handlers_dir"])
        config = ih.load_raw_config(workspace["config_path"])
        config["default_action"] = {
            "script_path": "handlers/journal_handler.py"
        }
        suggested = ih.suggest_handlers(handlers, config)
        assert "journal_handler" not in suggested


# ---------------------------------------------------------------------------
# Building a magic_words entry
# ---------------------------------------------------------------------------


class TestBuildEntry:
    def test_basic_entry(self):
        entry = ih.build_entry(
            "handlers/journal_handler.py",
            {"destination": "/srv/notes"},
        )
        assert entry == {
            "script_path": "handlers/journal_handler.py",
            "destination": "/srv/notes",
        }

    def test_entry_with_aliases(self):
        entry = ih.build_entry(
            "handlers/journal_handler.py",
            {"destination": "/srv/notes"},
            aliases=["JOURNAL", "PÄIVÄ"],
        )
        assert entry["aliases"] == ["JOURNAL", "PÄIVÄ"]

    def test_entry_no_aliases_omits_key(self):
        entry = ih.build_entry("handlers/x.py", {})
        assert "aliases" not in entry


# ---------------------------------------------------------------------------
# resolve_params (defaults, required, unknown, path validation)
# ---------------------------------------------------------------------------


class TestResolveParams:
    def setup_method(self):
        self.manifest = {
            "parameters": {
                "destination": {
                    "required": True,
                    "default": "/srv/default",
                    "type": "path",
                },
                "subject": {
                    "required": False,
                    "default": "Note",
                    "type": "string",
                },
            }
        }

    def test_defaults_applied(self):
        params = ih.resolve_params(self.manifest, {})
        assert params["destination"] == "/srv/default"
        assert params["subject"] == "Note"

    def test_provided_overrides_default(self):
        params = ih.resolve_params(
            self.manifest, {"destination": "/srv/custom"}
        )
        assert params["destination"] == "/srv/custom"

    def test_unknown_param_raises(self):
        with pytest.raises(ih.InstallerError, match="Unknown parameter"):
            ih.resolve_params(self.manifest, {"bogus": "x"})

    def test_relative_path_raises(self):
        with pytest.raises(ih.InstallerError, match="absolute"):
            ih.resolve_params(
                self.manifest, {"destination": "relative/path"}
            )

    def test_missing_required_no_default_raises(self):
        manifest = {
            "parameters": {
                "target": {"required": True, "type": "string"}
            }
        }
        with pytest.raises(ih.InstallerError, match="Required parameter"):
            ih.resolve_params(manifest, {})

    def test_string_param_not_path_validated(self):
        # A relative-looking string param should NOT trigger path validation.
        params = ih.resolve_params(self.manifest, {"subject": "rel/ative"})
        assert params["subject"] == "rel/ative"


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


class TestPathValidation:
    def test_absolute_ok(self):
        ih.validate_path_value("/srv/notes", "destination")  # no raise

    def test_relative_raises(self):
        with pytest.raises(ih.InstallerError, match="absolute"):
            ih.validate_path_value("notes", "destination")

    def test_empty_raises(self):
        with pytest.raises(ih.InstallerError, match="absolute"):
            ih.validate_path_value("", "destination")


# ---------------------------------------------------------------------------
# Word validation
# ---------------------------------------------------------------------------


class TestWordValidation:
    def test_valid_word(self):
        ih.validate_word("JOURNAL")  # no raise

    def test_word_with_underscore(self):
        ih.validate_word("MY_WORD")  # no raise

    def test_empty_raises(self):
        with pytest.raises(ih.InstallerError, match="empty"):
            ih.validate_word("")

    def test_invalid_chars_raise(self):
        with pytest.raises(ih.InstallerError, match="Invalid magic word"):
            ih.validate_word("BAD WORD!")


# ---------------------------------------------------------------------------
# Schema validation of the result
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_valid_config_passes(self, workspace):
        config = ih.load_raw_config(workspace["config_path"])
        config["magic_words"]["JOURNAL"] = {
            "script_path": "handlers/journal_handler.py",
            "destination": "/srv/notes",
        }
        ih.validate_config_dict(config)  # no raise

    def test_invalid_word_key_fails(self, workspace):
        config = ih.load_raw_config(workspace["config_path"])
        config["magic_words"]["BAD KEY"] = {
            "script_path": "handlers/journal_handler.py"
        }
        with pytest.raises(ih.InstallerError, match="validation failed"):
            ih.validate_config_dict(config)

    def test_missing_script_path_fails(self, workspace):
        config = ih.load_raw_config(workspace["config_path"])
        config["magic_words"]["EMPTY"] = {}
        with pytest.raises(ih.InstallerError, match="validation failed"):
            ih.validate_config_dict(config)


# ---------------------------------------------------------------------------
# write_config (atomic, preserves content)
# ---------------------------------------------------------------------------


class TestWriteConfig:
    def test_round_trip_preserves_content(self, workspace):
        config = ih.load_raw_config(workspace["config_path"])
        config["magic_words"]["JOURNAL"] = {
            "script_path": "handlers/journal_handler.py"
        }
        ih.write_config(workspace["config_path"], config)
        reloaded = ih.load_raw_config(workspace["config_path"])
        assert reloaded["magic_words"]["JOURNAL"]["script_path"] == (
            "handlers/journal_handler.py"
        )
        # original NOTE entry preserved
        assert "NOTE" in reloaded["magic_words"]

    def test_no_tmp_file_left_behind(self, workspace):
        config = ih.load_raw_config(workspace["config_path"])
        ih.write_config(workspace["config_path"], config)
        assert not os.path.exists(workspace["config_path"] + ".tmp")


# ---------------------------------------------------------------------------
# load_raw_config error handling
# ---------------------------------------------------------------------------


class TestLoadRawConfig:
    def test_missing_file_raises(self):
        with pytest.raises(ih.InstallerError, match="Config not found"):
            ih.load_raw_config("/nonexistent/config.json")

    def test_invalid_json_raises(self, workspace):
        bad = os.path.join(workspace["tmpdir"], "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{ not valid json")
        with pytest.raises(ih.InstallerError, match="Invalid JSON"):
            ih.load_raw_config(bad)


# ---------------------------------------------------------------------------
# Systemd ReadWritePaths parsing
# ---------------------------------------------------------------------------


class TestReadWritePaths:
    def _write_unit(self, workspace, content):
        unit = os.path.join(workspace["tmpdir"], "speech2text.service")
        with open(unit, "w", encoding="utf-8") as fh:
            fh.write(content)
        return unit

    def test_parse_readwrite_paths(self, workspace):
        unit = self._write_unit(
            workspace,
            "[Service]\nReadWritePaths=/srv/speech2text /srv/Obsidian/Inbox\n",
        )
        paths = ih.read_readwrite_paths(unit)
        assert paths == ["/srv/speech2text", "/srv/Obsidian/Inbox"]

    def test_find_missing_paths(self, workspace):
        unit = self._write_unit(
            workspace,
            "[Service]\nReadWritePaths=/srv/speech2text\n",
        )
        manifest = {
            "parameters": {
                "destination": {"type": "path"}
            }
        }
        missing = ih.find_missing_rw_paths(
            manifest, {"destination": "/srv/Obsidian/Inbox"}, unit
        )
        assert missing == ["/srv/Obsidian/Inbox"]

    def test_no_missing_when_present(self, workspace):
        unit = self._write_unit(
            workspace,
            "[Service]\nReadWritePaths=/srv/speech2text /srv/Obsidian/Inbox\n",
        )
        manifest = {"parameters": {"destination": {"type": "path"}}}
        missing = ih.find_missing_rw_paths(
            manifest, {"destination": "/srv/Obsidian/Inbox"}, unit
        )
        assert missing == []

    def test_string_param_ignored(self, workspace):
        unit = self._write_unit(
            workspace, "[Service]\nReadWritePaths=/srv/speech2text\n"
        )
        manifest = {"parameters": {"subject": {"type": "string"}}}
        missing = ih.find_missing_rw_paths(
            manifest, {"subject": "hello"}, unit
        )
        assert missing == []

    def test_unreadable_unit_returns_empty(self):
        manifest = {"parameters": {"destination": {"type": "path"}}}
        missing = ih.find_missing_rw_paths(
            manifest, {"destination": "/srv/x"}, "/nonexistent/unit"
        )
        assert missing == []


# ---------------------------------------------------------------------------
# run_systemd_update (mocked subprocess)
# ---------------------------------------------------------------------------


class TestRunSystemdUpdate:
    def test_missing_helper_raises(self):
        with pytest.raises(ih.InstallerError, match="Helper script not found"):
            ih.run_systemd_update(
                ["/srv/x"], "/etc/unit", "/nonexistent/helper.sh"
            )

    def test_success_returns_stdout(self, workspace):
        helper = os.path.join(workspace["tmpdir"], "helper.sh")
        with open(helper, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/bash\necho ok\n")
        os.chmod(helper, 0o755)

        with patch("install_handler.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Done.\n"
            mock_run.return_value.stderr = ""
            out = ih.run_systemd_update(
                ["/srv/x"], "/etc/unit", helper
            )
        assert out == "Done.\n"
        # Verify sudo + helper + paths were passed.
        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "sudo"
        assert called_cmd[1] == helper
        assert "/srv/x" in called_cmd

    def test_failure_raises(self, workspace):
        helper = os.path.join(workspace["tmpdir"], "helper.sh")
        with open(helper, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/bash\n")
        os.chmod(helper, 0o755)

        with patch("install_handler.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "boom"
            with pytest.raises(ih.InstallerError, match="Helper failed"):
                ih.run_systemd_update(["/srv/x"], "/etc/unit", helper)


# ---------------------------------------------------------------------------
# Non-interactive mode (end to end, systemd mocked off)
# ---------------------------------------------------------------------------


class TestNonInteractiveFlow:
    def test_install_new_word(self, workspace):
        args = _make_args(
            workspace,
            handler="journal_handler",
            word="JOURNAL",
            aliases="PAIVA,DAY",
            param=["destination=/srv/Obsidian/Archives/dailynotes"],
            yes=True,
            no_systemd=True,
        )
        rc = ih.noninteractive_flow(args)
        assert rc == 0

        config = ih.load_raw_config(workspace["config_path"])
        entry = config["magic_words"]["JOURNAL"]
        assert entry["script_path"] == "handlers/journal_handler.py"
        assert entry["destination"] == "/srv/Obsidian/Archives/dailynotes"
        assert entry["aliases"] == ["PAIVA", "DAY"]

    def test_word_uppercased(self, workspace):
        args = _make_args(
            workspace,
            handler="journal_handler",
            word="journal",
            param=["destination=/srv/notes"],
            yes=True,
            no_systemd=True,
        )
        ih.noninteractive_flow(args)
        config = ih.load_raw_config(workspace["config_path"])
        assert "JOURNAL" in config["magic_words"]

    def test_unknown_handler_raises(self, workspace):
        args = _make_args(
            workspace,
            handler="nonexistent",
            word="X",
            yes=True,
            no_systemd=True,
        )
        with pytest.raises(ih.InstallerError, match="Unknown handler"):
            ih.noninteractive_flow(args)

    def test_relative_path_param_fails(self, workspace):
        args = _make_args(
            workspace,
            handler="journal_handler",
            word="JOURNAL",
            param=["destination=relative/path"],
            yes=True,
            no_systemd=True,
        )
        with pytest.raises(ih.InstallerError, match="absolute"):
            ih.noninteractive_flow(args)

    def test_missing_required_param_fails(self, workspace):
        # email_handler has a required 'subject' string param with a default,
        # so use journal_handler but override default away via a manifest
        # without default. Instead test unknown param here.
        args = _make_args(
            workspace,
            handler="journal_handler",
            word="JOURNAL",
            param=["bogus=value"],
            yes=True,
            no_systemd=True,
        )
        with pytest.raises(ih.InstallerError, match="Unknown parameter"):
            ih.noninteractive_flow(args)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_reinstall_overwrites_with_yes(self, workspace):
        # First install
        args = _make_args(
            workspace,
            handler="journal_handler",
            word="JOURNAL",
            param=["destination=/srv/first"],
            yes=True,
            no_systemd=True,
        )
        ih.noninteractive_flow(args)

        # Re-install with a different destination — should overwrite, not dup
        args2 = _make_args(
            workspace,
            handler="journal_handler",
            word="JOURNAL",
            param=["destination=/srv/second"],
            yes=True,
            no_systemd=True,
        )
        ih.noninteractive_flow(args2)

        config = ih.load_raw_config(workspace["config_path"])
        # Only one JOURNAL key, updated value
        assert config["magic_words"]["JOURNAL"]["destination"] == "/srv/second"
        assert list(config["magic_words"].keys()).count("JOURNAL") == 1

    def test_reinstall_without_yes_non_tty_raises(self, workspace):
        args = _make_args(
            workspace,
            handler="note_handler",
            word="NOTE",  # already installed in fixture config
            param=["destination=/srv/Obsidian/Inbox"],
            yes=False,
            no_systemd=True,
        )
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with pytest.raises(ih.InstallerError, match="already exists"):
                ih.noninteractive_flow(args)


# ---------------------------------------------------------------------------
# parse_param_flags
# ---------------------------------------------------------------------------


class TestParseParamFlags:
    def test_basic(self):
        assert ih.parse_param_flags(["a=1", "b=2"]) == {"a": "1", "b": "2"}

    def test_value_with_equals(self):
        assert ih.parse_param_flags(["url=http://x?a=1"]) == {
            "url": "http://x?a=1"
        }

    def test_missing_equals_raises(self):
        with pytest.raises(ih.InstallerError, match="Invalid --param"):
            ih.parse_param_flags(["noequals"])

    def test_empty_key_raises(self):
        with pytest.raises(ih.InstallerError, match="Empty parameter name"):
            ih.parse_param_flags(["=value"])


# ---------------------------------------------------------------------------
# list handlers
# ---------------------------------------------------------------------------


class TestListHandlers:
    def test_list_returns_zero(self, workspace, capsys):
        args = _make_args(workspace, **{"list": True})
        rc = ih.list_handlers(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "journal_handler" in out
        assert "note_handler" in out
        # installed marker present for note_handler
        assert "installed" in out

    def test_list_missing_config_ok(self, workspace, capsys):
        args = _make_args(
            workspace,
            **{"list": True, "config": "/nonexistent/config.json"}
        )
        rc = ih.list_handlers(args)
        assert rc == 0


# ---------------------------------------------------------------------------
# main() CLI dispatch
# ---------------------------------------------------------------------------


class TestMainDispatch:
    def test_main_list(self, workspace):
        rc = ih.main(
            [
                "--config",
                workspace["config_path"],
                "--handlers-dir",
                workspace["handlers_dir"],
                "--list",
            ]
        )
        assert rc == 0

    def test_main_noninteractive(self, workspace):
        rc = ih.main(
            [
                "--config",
                workspace["config_path"],
                "--handlers-dir",
                workspace["handlers_dir"],
                "--handler",
                "journal_handler",
                "--word",
                "JOURNAL",
                "--param",
                "destination=/srv/notes",
                "--yes",
                "--no-systemd",
            ]
        )
        assert rc == 0

    def test_main_handler_without_word_errors(self, workspace):
        with pytest.raises(SystemExit):
            ih.main(
                [
                    "--config",
                    workspace["config_path"],
                    "--handlers-dir",
                    workspace["handlers_dir"],
                    "--handler",
                    "journal_handler",
                ]
            )

    def test_main_error_returns_one(self, workspace):
        rc = ih.main(
            [
                "--config",
                "/nonexistent/config.json",
                "--handlers-dir",
                workspace["handlers_dir"],
                "--handler",
                "journal_handler",
                "--word",
                "JOURNAL",
                "--yes",
                "--no-systemd",
            ]
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# do_systemd_check (mocked)
# ---------------------------------------------------------------------------


class TestDoSystemdCheck:
    def test_no_systemd_flag_skips(self, workspace, capsys):
        # Unit file exists but is missing the destination path, so the
        # no_systemd branch is actually reached.
        unit = os.path.join(workspace["tmpdir"], "unit.service")
        with open(unit, "w", encoding="utf-8") as fh:
            fh.write("[Service]\nReadWritePaths=/srv/speech2text\n")
        manifest = {"parameters": {"destination": {"type": "path"}}}
        args = _make_args(
            workspace, unit_path=unit, no_systemd=True
        )
        ih.do_systemd_check(
            manifest, {"destination": "/srv/x"}, args
        )
        out = capsys.readouterr().out
        assert "Skipped" in out

    def test_all_paths_present(self, workspace, capsys):
        unit = os.path.join(workspace["tmpdir"], "unit.service")
        with open(unit, "w", encoding="utf-8") as fh:
            fh.write("[Service]\nReadWritePaths=/srv/x\n")
        manifest = {"parameters": {"destination": {"type": "path"}}}
        args = _make_args(
            workspace, unit_path=unit, no_systemd=False, yes=True
        )
        ih.do_systemd_check(
            manifest, {"destination": "/srv/x"}, args
        )
        out = capsys.readouterr().out
        assert "all paths present" in out

    def test_missing_path_triggers_update(self, workspace):
        unit = os.path.join(workspace["tmpdir"], "unit.service")
        with open(unit, "w", encoding="utf-8") as fh:
            fh.write("[Service]\nReadWritePaths=/srv/speech2text\n")
        manifest = {"parameters": {"destination": {"type": "path"}}}
        args = _make_args(
            workspace, unit_path=unit, no_systemd=False, yes=True
        )
        with patch("install_handler.run_systemd_update") as mock_update:
            mock_update.return_value = "Done.\n"
            ih.do_systemd_check(
                manifest, {"destination": "/srv/Obsidian/Inbox"}, args
            )
        mock_update.assert_called_once()
        called_paths = mock_update.call_args[0][0]
        assert "/srv/Obsidian/Inbox" in called_paths
