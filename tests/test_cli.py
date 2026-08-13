"""Tests for the atlasopenmagic CLI (the `atlasopenmagic` / `atom` console scripts).

These tests never touch the network: PyPI lookups and the underlying
metadata/weights functions are mocked throughout.
"""

import json

import pytest

from atlasopenmagic import cli


# --- Version comparison ---


@pytest.mark.parametrize(
    "latest,installed,expected",
    [
        ("1.10.0", "1.9.1", True),
        ("1.9.1", "1.9.1", False),
        ("1.9.0", "1.9.1", False),
        ("2.0.0", "1.9.1", True),
    ],
)
def test_version_tuple_ordering(latest, installed, expected):
    assert (cli._version_tuple(latest) > cli._version_tuple(installed)) is expected


# --- Command dispatch ---


def test_metadata_command_emits_json(capsys, monkeypatch):
    monkeypatch.setattr(cli._metadata, "get_metadata", lambda key, var: {"cross_section_pb": 0.0017})
    assert cli.main(["--no-update-check", "metadata", "301204"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"cross_section_pb": 0.0017}


def test_urls_command_passes_options_through(capsys, monkeypatch):
    captured = {}

    def fake_get_urls(key, skim, protocol, cache):
        captured.update(key=key, skim=skim, protocol=protocol, cache=cache)
        return ["root://example/file.root"]

    monkeypatch.setattr(cli._metadata, "get_urls", fake_get_urls)
    rc = cli.main(["--no-update-check", "urls", "301204", "--skim", "exactly4lep", "--protocol", "https"])
    assert rc == 0
    assert captured == {"key": "301204", "skim": "exactly4lep", "protocol": "https", "cache": None}
    assert json.loads(capsys.readouterr().out) == ["root://example/file.root"]


def test_unknown_dataset_returns_exit_code_1(capsys, monkeypatch):
    def raise_value_error(key, var):
        raise ValueError(f"Dataset '{key}' not found")

    monkeypatch.setattr(cli._metadata, "get_metadata", raise_value_error)
    rc = cli.main(["--no-update-check", "metadata", "does-not-exist"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_release_flag_calls_set_release(monkeypatch):
    calls = []
    monkeypatch.setattr(cli._metadata, "set_release", lambda release: calls.append(release))
    monkeypatch.setattr(cli._metadata, "available_datasets", lambda: [])
    cli.main(["--no-update-check", "--release", "2024r-pp", "datasets"])
    assert calls == ["2024r-pp"]


# --- Update notification ---


def test_no_update_check_flag_skips_pypi_lookup(monkeypatch):
    called = []
    monkeypatch.setattr(cli, "_fetch_latest_version", lambda: called.append(True))
    monkeypatch.setattr(cli._metadata, "available_datasets", lambda: [])
    cli.main(["--no-update-check", "datasets"])
    assert called == []


def test_update_check_env_var_skips_pypi_lookup(monkeypatch):
    called = []
    monkeypatch.setattr(cli, "_fetch_latest_version", lambda: called.append(True))
    monkeypatch.setenv("ATLASOPENMAGIC_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(cli._metadata, "available_datasets", lambda: [])
    cli.main(["datasets"])
    assert called == []


def test_check_for_update_sets_notice_for_newer_release(monkeypatch):
    monkeypatch.setattr(cli, "_installed_version", lambda: "1.0.0")
    monkeypatch.setattr(cli, "_read_cache", dict)
    monkeypatch.setattr(cli, "_write_cache", lambda data: None)
    monkeypatch.setattr(cli, "_fetch_latest_version", lambda: "2.0.0")
    result = {}
    cli._check_for_update(result)
    assert "1.0.0 -> 2.0.0" in result["notice"]


def test_check_for_update_no_notice_when_up_to_date(monkeypatch):
    monkeypatch.setattr(cli, "_installed_version", lambda: "1.0.0")
    monkeypatch.setattr(cli, "_read_cache", dict)
    monkeypatch.setattr(cli, "_write_cache", lambda data: None)
    monkeypatch.setattr(cli, "_fetch_latest_version", lambda: "1.0.0")
    result = {}
    cli._check_for_update(result)
    assert "notice" not in result
