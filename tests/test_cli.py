"""Tests for the atlasopenmagic CLI (the `atlasopenmagic` / `atom` console scripts).

These tests never touch the network: PyPI lookups and the underlying
metadata/weights functions are mocked throughout.
"""

import json
import threading
import time

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


def test_version_tuple_stops_at_non_digit_suffix():
    assert cli._version_tuple("1.9.1rc2") == (1, 9, 1)


def test_installed_version_returns_none_when_package_not_found(monkeypatch):
    def raise_not_found(_name):
        raise cli.PackageNotFoundError

    monkeypatch.setattr(cli, "version", raise_not_found)
    assert cli._installed_version() is None


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


def test_verbosity_flag_calls_set_verbosity(monkeypatch):
    calls = []
    monkeypatch.setattr(cli._metadata, "set_verbosity", lambda level: calls.append(level))
    monkeypatch.setattr(cli._metadata, "available_datasets", lambda: [])
    cli.main(["--no-update-check", "--verbosity", "debug", "datasets"])
    assert calls == ["debug"]


def test_releases_command_emits_releases_desc(capsys, monkeypatch):
    monkeypatch.setattr(cli._metadata, "RELEASES_DESC", {"2024r-pp": "desc"})
    cli.main(["--no-update-check", "releases"])
    assert json.loads(capsys.readouterr().out) == {"2024r-pp": "desc"}


@pytest.mark.parametrize(
    "argv,target,func_name,fake_return",
    [
        (["current-release"], cli._metadata, "get_current_release", "2024r-pp"),
        (["skims"], cli._metadata, "available_skims", ["noskim"]),
        (["keywords"], cli._metadata, "available_keywords", ["top"]),
        (["fields"], cli._metadata, "get_metadata_fields", ["cross_section_pb"]),
        (["weights", "301204"], cli._weights, "get_weights", {"weights": []}),
        (["weight-names", "301204"], cli._weights, "get_weight_names", ["nominal"]),
        (["all-weights"], cli._weights, "get_all_weights_for_release", {"301204": ["nominal"]}),
    ],
)
def test_simple_commands_emit_underlying_result(capsys, monkeypatch, argv, target, func_name, fake_return):
    monkeypatch.setattr(target, func_name, lambda *a, **kw: fake_return)
    rc = cli.main(["--no-update-check", *argv])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == fake_return


def test_metadata_command_full_flag_uses_get_all_info(capsys, monkeypatch):
    monkeypatch.setattr(cli._metadata, "get_all_info", lambda key, var: {"file_list": ["a.root"]})
    cli.main(["--no-update-check", "metadata", "301204", "--full"])
    assert json.loads(capsys.readouterr().out) == {"file_list": ["a.root"]}


def test_search_command_passes_field_value_tolerance(capsys, monkeypatch):
    captured = {}

    def fake_match(field, value, float_tolerance):
        captured.update(field=field, value=value, float_tolerance=float_tolerance)
        return [["301204", "physics_short"]]

    monkeypatch.setattr(cli._metadata, "match_metadata", fake_match)
    cli.main(["--no-update-check", "search", "process", "pp>Zprime>ee", "--tolerance", "0.1"])
    assert captured == {"field": "process", "value": "pp>Zprime>ee", "float_tolerance": 0.1}
    assert json.loads(capsys.readouterr().out) == [["301204", "physics_short"]]


def test_network_error_returns_exit_code_1(capsys, monkeypatch):
    def raise_request_exception(key, var):
        raise cli.requests.exceptions.RequestException("connection failed")

    monkeypatch.setattr(cli._metadata, "get_metadata", raise_request_exception)
    rc = cli.main(["--no-update-check", "metadata", "301204"])
    assert rc == 1
    assert "Network error" in capsys.readouterr().err


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


def test_check_for_update_skips_when_package_not_installed(monkeypatch):
    monkeypatch.setattr(cli, "_installed_version", lambda: None)
    called = []
    monkeypatch.setattr(cli, "_read_cache", lambda: called.append(True))
    result = {}
    cli._check_for_update(result)
    assert result == {}
    assert called == []


def test_check_for_update_uses_fresh_cache_without_refetching(monkeypatch):
    monkeypatch.setattr(cli, "_installed_version", lambda: "1.0.0")
    monkeypatch.setattr(cli, "_read_cache", lambda: {"checked_at": time.time(), "latest_version": "2.0.0"})
    called = []
    monkeypatch.setattr(cli, "_fetch_latest_version", lambda: called.append(True))
    result = {}
    cli._check_for_update(result)
    assert called == []
    assert "1.0.0 -> 2.0.0" in result["notice"]


def test_read_write_cache_round_trip(tmp_path, monkeypatch):
    cache_path = tmp_path / "atlasopenmagic" / "update_check.json"
    monkeypatch.setattr(cli, "_CACHE_PATH", str(cache_path))
    assert cli._read_cache() == {}  # File doesn't exist yet.
    cli._write_cache({"checked_at": 123.0, "latest_version": "1.2.3"})
    assert cli._read_cache() == {"checked_at": 123.0, "latest_version": "1.2.3"}


def test_read_cache_ignores_corrupt_file(tmp_path, monkeypatch):
    cache_path = tmp_path / "update_check.json"
    cache_path.write_text("not json")
    monkeypatch.setattr(cli, "_CACHE_PATH", str(cache_path))
    assert cli._read_cache() == {}


def test_write_cache_ignores_oserror(monkeypatch):
    def raise_oserror(*a, **kw):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(cli.os, "makedirs", raise_oserror)
    cli._write_cache({"anything": True})  # Should not raise.


def test_fetch_latest_version_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"info": {"version": "3.0.0"}}

    monkeypatch.setattr(cli.requests, "get", lambda *a, **kw: FakeResponse())
    assert cli._fetch_latest_version() == "3.0.0"


def test_fetch_latest_version_returns_none_on_request_error(monkeypatch):
    def raise_connection_error(*a, **kw):
        raise cli.requests.exceptions.RequestException("no network")

    monkeypatch.setattr(cli.requests, "get", raise_connection_error)
    assert cli._fetch_latest_version() is None


def test_start_update_check_runs_target_in_background_thread(monkeypatch):
    monkeypatch.setattr(cli, "_check_for_update", lambda result: result.update(notice="new version!"))
    check = cli._start_update_check(disabled=False)
    assert check is not None
    thread, result = check
    thread.join(timeout=2)
    assert result == {"notice": "new version!"}


def test_print_update_notice_prints_to_stderr(capsys):
    thread = threading.Thread(target=lambda: None)
    thread.start()
    cli._print_update_notice((thread, {"notice": "upgrade me"}))
    assert "upgrade me" in capsys.readouterr().err


def test_print_update_notice_noop_when_check_is_none(capsys):
    cli._print_update_notice(None)
    assert capsys.readouterr().err == ""
