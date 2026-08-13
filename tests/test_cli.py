"""Tests for the atlasopenmagic CLI (the `atlasopenmagic` / `atom` console scripts).

These tests never touch the network or the user's real config/cache
directories: PyPI lookups and the underlying metadata/weights/utils functions
are mocked, and an autouse fixture redirects all on-disk state into tmp_path.
"""

import json
import os
import threading
import time

import pytest

from atlasopenmagic import cli

# `cli._metadata` is the metadata *module*; `cli._metadata._metadata` is the
# release cache dict inside it.
_metadata_mod = cli._metadata


@pytest.fixture(autouse=True)
def isolate_cli_state(tmp_path, monkeypatch):
    """Keep every test off the real ~/.config and ~/.cache, and off each other's state."""
    monkeypatch.setattr(cli, "_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(cli, "_CACHE_PATH", str(tmp_path / "cache" / "update_check.json"))
    monkeypatch.setattr(cli, "_CONFIG_PATH", str(tmp_path / "config" / "config.json"))
    monkeypatch.delenv("ATLAS_RELEASE", raising=False)
    monkeypatch.delenv("ATLASOPENMAGIC_NO_UPDATE_CHECK", raising=False)

    # read_metadata()/set_release() mutate module globals directly, so snapshot
    # and restore them rather than leaking into other test modules.
    saved_release = _metadata_mod.current_release
    saved_metadata = dict(_metadata_mod._metadata)
    saved_fields = list(_metadata_mod.AVAILABLE_FIELDS)
    yield
    _metadata_mod.current_release = saved_release
    _metadata_mod._metadata = saved_metadata
    _metadata_mod.AVAILABLE_FIELDS = saved_fields


@pytest.fixture
def no_metadata_load(monkeypatch):
    """Stub out release/metadata loading for tests that only exercise dispatch."""
    monkeypatch.setattr(cli, "_apply_release", lambda *a, **kw: None)


def _write_cache_file(path, payload=None):
    """Write a minimal but structurally valid metadata cache file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or {"301204": {"dataset_number": "301204", "e_tag": "e3723"}}))


def _run(*argv):
    """Run the CLI with the update check disabled."""
    return cli.main(["--no-update-check", *argv])


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


# --- Config file ---


def test_read_config_returns_empty_when_missing():
    assert cli._read_config() == {}


def test_read_config_ignores_corrupt_file(tmp_path):
    path = tmp_path / "config" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json")
    assert cli._read_config() == {}


def test_read_config_ignores_non_dict_json(tmp_path):
    path = tmp_path / "config" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(["a", "list"]))
    assert cli._read_config() == {}


def test_write_then_read_config_round_trip():
    cli._write_config({"release": "2024r-pp"})
    assert cli._read_config() == {"release": "2024r-pp"}


# --- Release selection ---


def test_validate_release_accepts_published_release():
    cli._validate_release("2024r-pp")  # Should not raise.


def test_validate_release_rejects_unknown_release():
    with pytest.raises(ValueError, match="Invalid release"):
        cli._validate_release("not-a-release")


def test_validate_release_accepts_locally_imported_release(tmp_path):
    _write_cache_file(tmp_path / "cache" / "metadata-custom.json")
    cli._validate_release("custom")  # Should not raise.


def test_metadata_cache_path_rejects_path_traversal():
    with pytest.raises(ValueError, match="Invalid release name"):
        cli._metadata_cache_path("../../etc/passwd")


def test_known_releases_survives_missing_cache_dir():
    assert "2024r-pp" in cli._known_releases()


def test_resolve_release_prefers_cli_flag(monkeypatch):
    monkeypatch.setenv("ATLAS_RELEASE", "2024r-hi")
    cli._write_config({"release": "2020e-13tev"})
    assert cli._resolve_release("2024r-pp") == ("2024r-pp", "--release")


def test_resolve_release_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("ATLAS_RELEASE", "2024r-hi")
    cli._write_config({"release": "2020e-13tev"})
    assert cli._resolve_release(None) == ("2024r-hi", "ATLAS_RELEASE")


def test_resolve_release_falls_back_to_config():
    cli._write_config({"release": "2020e-13tev"})
    assert cli._resolve_release(None) == ("2020e-13tev", "config")


def test_resolve_release_falls_back_to_library_default(monkeypatch):
    monkeypatch.setattr(_metadata_mod, "current_release", "2024r-pp")
    assert cli._resolve_release(None) == ("2024r-pp", "default")


# --- Metadata cache ---


def test_cache_age_returns_none_for_missing_file():
    assert cli._cache_age(cli._metadata_cache_path("2024r-pp")) is None


def test_cache_age_returns_seconds_for_existing_file(tmp_path):
    path = tmp_path / "some-file.json"
    path.write_text("{}")
    age = cli._cache_age(str(path))
    assert age is not None and age < 60


def test_save_metadata_cache_ignores_oserror(monkeypatch):
    def raise_oserror(*a, **kw):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(cli.os, "makedirs", raise_oserror)
    cli._save_metadata_cache(cli._metadata_cache_path("2024r-pp"))  # Should not raise.


def test_apply_release_loads_fresh_cache_without_fetching(monkeypatch, tmp_path):
    _write_cache_file(tmp_path / "cache" / "metadata-2024r-pp.json")

    def fail_if_fetched(*a, **kw):
        raise AssertionError("set_release() should not be called when the cache is fresh")

    monkeypatch.setattr(_metadata_mod, "set_release", fail_if_fetched)
    cli._apply_release("2024r-pp", refresh=False, needs_full=True)
    assert _metadata_mod.get_current_release() == "2024r-pp"
    assert "301204" in _metadata_mod._metadata


def test_apply_release_refetches_when_cache_is_corrupt(monkeypatch, tmp_path):
    cache_file = tmp_path / "cache" / "metadata-2024r-pp.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{ truncated")

    calls = []
    monkeypatch.setattr(_metadata_mod, "set_release", lambda release: calls.append(release))
    monkeypatch.setattr(cli, "_save_metadata_cache", lambda path: None)
    cli._apply_release("2024r-pp", refresh=False, needs_full=True)
    assert calls == ["2024r-pp"]


def test_apply_release_ignores_stale_cache(monkeypatch, tmp_path):
    cache_file = tmp_path / "cache" / "metadata-2024r-pp.json"
    _write_cache_file(cache_file)
    stale = time.time() - (cli._METADATA_CACHE_TTL_SECONDS + 60)
    os.utime(cache_file, (stale, stale))

    calls = []
    monkeypatch.setattr(_metadata_mod, "set_release", lambda release: calls.append(release))
    monkeypatch.setattr(cli, "_save_metadata_cache", lambda path: None)
    cli._apply_release("2024r-pp", refresh=False, needs_full=True)
    assert calls == ["2024r-pp"]


def test_apply_release_refresh_bypasses_fresh_cache(monkeypatch, tmp_path):
    _write_cache_file(tmp_path / "cache" / "metadata-2024r-pp.json")
    calls = []
    monkeypatch.setattr(_metadata_mod, "set_release", lambda release: calls.append(release))
    monkeypatch.setattr(cli, "_save_metadata_cache", lambda path: None)
    cli._apply_release("2024r-pp", refresh=True, needs_full=True)
    assert calls == ["2024r-pp"]


def test_apply_release_is_lazy_when_full_metadata_not_needed(monkeypatch):
    def fail_if_fetched(*a, **kw):
        raise AssertionError("single-dataset commands must not trigger a full release fetch")

    monkeypatch.setattr(_metadata_mod, "set_release", fail_if_fetched)
    cli._apply_release("2024r-hi", refresh=False, needs_full=False)
    assert _metadata_mod.get_current_release() == "2024r-hi"


def test_apply_release_writes_cache_after_fetching(monkeypatch, tmp_path):
    def fake_set_release(release):
        _metadata_mod._metadata = {"301204": {"dataset_number": "301204"}}

    monkeypatch.setattr(_metadata_mod, "set_release", fake_set_release)
    cli._apply_release("2024r-pp", refresh=False, needs_full=True)
    written = tmp_path / "cache" / "metadata-2024r-pp.json"
    assert written.exists()
    assert json.loads(written.read_text())["301204"]["dataset_number"] == "301204"


def test_apply_release_rejects_unknown_release():
    with pytest.raises(ValueError, match="Invalid release"):
        cli._apply_release("bogus", refresh=False, needs_full=False)


# --- release group ---


def test_release_list_json_emits_all_releases(capsys):
    _run("--json", "release", "list")
    assert json.loads(capsys.readouterr().out) == _metadata_mod.RELEASES_DESC


def test_release_list_marks_the_active_release(capsys):
    cli._write_config({"release": "2024r-hi"})
    _run("release", "list")
    lines = capsys.readouterr().out.splitlines()
    active = [line for line in lines if line.startswith("*")]
    assert len(active) == 1
    assert "2024r-hi" in active[0]


def test_release_show_json_reports_release_and_source(capsys):
    cli._write_config({"release": "2020e-13tev"})
    _run("--json", "release", "show")
    out = json.loads(capsys.readouterr().out)
    assert out["release"] == "2020e-13tev"
    assert out["source"] == "config"
    assert out["cache"] == "not cached"


def test_release_show_reports_a_warm_cache(capsys, tmp_path):
    _write_cache_file(tmp_path / "cache" / "metadata-2024r-pp.json")
    cli._write_config({"release": "2024r-pp"})
    _run("release", "show")
    assert "Cache:   fresh, just now" in capsys.readouterr().out


def test_release_show_prints_readable_summary(capsys):
    cli._write_config({"release": "2020e-13tev"})
    _run("release", "show")
    out = capsys.readouterr().out
    assert "Release: 2020e-13tev" in out
    assert "Source:  config" in out
    assert "Cache:   not cached" in out


def test_release_set_persists_choice_and_warms_cache(capsys, monkeypatch):
    applied = []
    monkeypatch.setattr(cli, "_apply_release", lambda release, refresh, needs_full: applied.append(release))
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: ["301204", "410470"])
    assert _run("release", "set", "2024r-hi") == 0
    assert applied == ["2024r-hi"]
    assert "Cached 2 datasets." in capsys.readouterr().out
    assert cli._read_config()["release"] == "2024r-hi"


def test_release_set_no_fetch_skips_the_download(capsys, monkeypatch):
    def fail_if_fetched(*a, **kw):
        raise AssertionError("--no-fetch must not download metadata")

    monkeypatch.setattr(cli, "_apply_release", fail_if_fetched)
    assert _run("release", "set", "2024r-hi", "--no-fetch") == 0
    assert "Cached" not in capsys.readouterr().out
    assert cli._read_config()["release"] == "2024r-hi"


def test_release_set_json_reports_cached_count(capsys, monkeypatch):
    monkeypatch.setattr(cli, "_apply_release", lambda *a, **kw: None)
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: ["301204"])
    _run("--json", "release", "set", "2024r-hi")
    assert json.loads(capsys.readouterr().out)["datasets_cached"] == 1


def test_release_set_rejects_unknown_release(capsys):
    assert _run("release", "set", "not-a-release") == 1
    assert "Invalid release" in capsys.readouterr().err
    assert cli._read_config() == {}


def test_release_unset_forgets_choice(capsys):
    cli._write_config({"release": "2024r-hi"})
    _run("release", "unset")
    assert "Saved release cleared" in capsys.readouterr().out
    assert "release" not in cli._read_config()


def test_release_unset_json_reports_null(capsys):
    cli._write_config({"release": "2024r-hi"})
    _run("--json", "release", "unset")
    assert json.loads(capsys.readouterr().out)["release"] is None


def test_release_set_reports_write_failure(capsys, monkeypatch):
    def raise_oserror(*a, **kw):
        raise OSError("permission denied")

    monkeypatch.setattr(cli.os, "makedirs", raise_oserror)
    assert _run("release", "set", "2024r-pp") == 1
    assert "permission denied" in capsys.readouterr().err


def test_release_commands_never_load_metadata(monkeypatch, capsys):
    def fail_if_loaded(*a, **kw):
        raise AssertionError("release commands must not load metadata")

    monkeypatch.setattr(cli, "_apply_release", fail_if_loaded)
    assert _run("release", "show") == 0
    capsys.readouterr()


# --- dataset group ---


def test_dataset_list_emits_dataset_ids(capsys, monkeypatch, no_metadata_load):
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: ["301204"])
    _run("dataset", "list")
    assert json.loads(capsys.readouterr().out) == ["301204"]


def test_dataset_show_emits_metadata(capsys, monkeypatch, no_metadata_load):
    monkeypatch.setattr(_metadata_mod, "get_metadata", lambda key, var: {"cross_section_pb": 0.0017})
    assert _run("dataset", "show", "301204") == 0
    assert json.loads(capsys.readouterr().out) == {"cross_section_pb": 0.0017}


def test_dataset_show_full_uses_get_all_info(capsys, monkeypatch, no_metadata_load):
    monkeypatch.setattr(_metadata_mod, "get_all_info", lambda key, var: {"file_list": ["a.root"]})
    _run("dataset", "show", "301204", "--full")
    assert json.loads(capsys.readouterr().out) == {"file_list": ["a.root"]}


def test_dataset_urls_passes_options_through(capsys, monkeypatch, no_metadata_load):
    captured = {}

    def fake_get_urls(key, skim, protocol, cache):
        captured.update(key=key, skim=skim, protocol=protocol, cache=cache)
        return ["root://example/file.root"]

    monkeypatch.setattr(_metadata_mod, "get_urls", fake_get_urls)
    rc = _run("dataset", "urls", "301204", "--skim", "exactly4lep", "--protocol", "https")
    assert rc == 0
    assert captured == {"key": "301204", "skim": "exactly4lep", "protocol": "https", "cache": None}
    assert json.loads(capsys.readouterr().out) == ["root://example/file.root"]


def test_dataset_search_passes_field_value_tolerance(capsys, monkeypatch, no_metadata_load):
    captured = {}

    def fake_match(field, value, float_tolerance):
        captured.update(field=field, value=value, float_tolerance=float_tolerance)
        return [["301204", "physics_short"]]

    monkeypatch.setattr(_metadata_mod, "match_metadata", fake_match)
    _run("dataset", "search", "process", "pp>Zprime>ee", "--tolerance", "0.1")
    assert captured == {"field": "process", "value": "pp>Zprime>ee", "float_tolerance": 0.1}
    assert json.loads(capsys.readouterr().out) == [["301204", "physics_short"]]


def test_dataset_build_reads_definitions_and_emits_mapping(capsys, monkeypatch, tmp_path, no_metadata_load):
    defs_file = tmp_path / "samples.json"
    defs_file.write_text(json.dumps({"Signal": {"dids": [301204], "color": "red"}}))
    captured = {}

    def fake_build(samples_defs, skim, protocol, cache):
        captured.update(samples_defs=samples_defs, skim=skim, protocol=protocol, cache=cache)
        return {"Signal": {"list": ["https://example/f.root"], "color": "red"}}

    monkeypatch.setattr(cli._utils, "build_dataset", fake_build)
    assert _run("dataset", "build", str(defs_file)) == 0
    assert captured["samples_defs"] == {"Signal": {"dids": [301204], "color": "red"}}
    assert captured["protocol"] == "https"
    assert json.loads(capsys.readouterr().out)["Signal"]["color"] == "red"


def test_dataset_build_rejects_non_object_definitions(capsys, tmp_path, no_metadata_load):
    defs_file = tmp_path / "samples.json"
    defs_file.write_text(json.dumps(["not", "an", "object"]))
    assert _run("dataset", "build", str(defs_file)) == 1
    assert "must contain a JSON object" in capsys.readouterr().err


def test_dataset_build_reports_missing_file(capsys, tmp_path, no_metadata_load):
    assert _run("dataset", "build", str(tmp_path / "nope.json")) == 1
    assert "Error:" in capsys.readouterr().err


# --- metadata group ---


@pytest.mark.parametrize(
    "argv,func_name,fake_return",
    [
        (["metadata", "fields"], "get_metadata_fields", ["cross_section_pb"]),
        (["metadata", "keywords"], "available_keywords", ["top"]),
        (["metadata", "skims"], "available_skims", ["noskim"]),
        (["metadata", "dump"], "get_all_metadata", {"301204": {}}),
    ],
)
def test_metadata_vocabulary_commands(capsys, monkeypatch, no_metadata_load, argv, func_name, fake_return):
    monkeypatch.setattr(_metadata_mod, func_name, lambda *a, **kw: fake_return)
    assert _run(*argv) == 0
    assert json.loads(capsys.readouterr().out) == fake_return


def test_metadata_export_writes_file(capsys, monkeypatch, tmp_path, no_metadata_load):
    target = tmp_path / "out.json"
    monkeypatch.setattr(_metadata_mod, "save_metadata", lambda file_name: target.write_text("{}"))
    monkeypatch.setattr(_metadata_mod, "get_current_release", lambda: "2024r-pp")
    assert _run("metadata", "export", str(target)) == 0
    assert json.loads(capsys.readouterr().out)["exported"] == str(target)
    assert target.exists()


def test_metadata_import_loads_file_into_cache(capsys, tmp_path):
    source = tmp_path / "in.json"
    source.write_text(json.dumps({"301204": {"dataset_number": "301204"}}))
    assert _run("metadata", "import", str(source), "--as-release", "mycopy") == 0
    assert json.loads(capsys.readouterr().out)["release"] == "mycopy"
    # It must land in the cache so later commands can select it.
    assert (tmp_path / "cache" / "metadata-mycopy.json").exists()
    assert _metadata_mod.get_current_release() == "mycopy"


def test_metadata_import_reports_missing_file(capsys, tmp_path):
    assert _run("metadata", "import", str(tmp_path / "nope.json")) == 1
    assert "Error:" in capsys.readouterr().err


# --- weights group ---


@pytest.mark.parametrize(
    "argv,func_name,fake_return",
    [
        (["weights", "show", "301204"], "get_weights", {"weights": []}),
        (["weights", "names", "301204"], "get_weight_names", ["nominal"]),
        (["weights", "list"], "get_all_weights_for_release", {"301204": ["nominal"]}),
    ],
)
def test_weights_commands(capsys, monkeypatch, no_metadata_load, argv, func_name, fake_return):
    monkeypatch.setattr(cli._weights, func_name, lambda *a, **kw: fake_return)
    assert _run(*argv) == 0
    assert json.loads(capsys.readouterr().out) == fake_return


# --- cache group ---


def test_cache_info_json_lists_cached_releases(capsys, tmp_path):
    _write_cache_file(tmp_path / "cache" / "metadata-2024r-pp.json")
    _run("--json", "cache", "info")
    out = json.loads(capsys.readouterr().out)
    assert [e["release"] for e in out["entries"]] == ["2024r-pp"]
    assert out["entries"][0]["stale"] is False


def test_cache_info_prints_readable_table(capsys, tmp_path):
    _write_cache_file(tmp_path / "cache" / "metadata-2024r-pp.json")
    _run("cache", "info")
    out = capsys.readouterr().out
    assert "Cache directory:" in out
    assert "2024r-pp" in out and "fresh" in out


def test_cache_info_json_is_empty_when_nothing_cached(capsys):
    _run("--json", "cache", "info")
    assert json.loads(capsys.readouterr().out)["entries"] == []


def test_cache_info_says_so_when_nothing_cached(capsys):
    _run("cache", "info")
    assert "No releases cached." in capsys.readouterr().out


def test_cache_info_reports_stale_entries(capsys, tmp_path):
    cached = tmp_path / "cache" / "metadata-2024r-pp.json"
    _write_cache_file(cached)
    stale = time.time() - (cli._METADATA_CACHE_TTL_SECONDS + 86400)
    os.utime(cached, (stale, stale))
    _run("cache", "info")
    assert "stale" in capsys.readouterr().out


def test_cache_clear_removes_cached_releases(capsys, tmp_path):
    cached = tmp_path / "cache" / "metadata-2024r-pp.json"
    _write_cache_file(cached)
    _run("--json", "cache", "clear")
    assert json.loads(capsys.readouterr().out)["removed"] == [str(cached)]
    assert not cached.exists()


def test_cache_clear_prints_count(capsys, tmp_path):
    _write_cache_file(tmp_path / "cache" / "metadata-2024r-pp.json")
    _run("cache", "clear")
    assert "Cleared 1 cached release." in capsys.readouterr().out


def test_cache_clear_is_a_noop_when_nothing_cached(capsys):
    _run("--json", "cache", "clear")
    assert json.loads(capsys.readouterr().out)["removed"] == []


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "just now"),
        (90, "1 minute old"),
        (7200, "2 hours old"),
        (86400, "1 day old"),
        (259200, "3 days old"),
    ],
)
def test_format_age(seconds, expected):
    assert cli._format_age(seconds) == expected


def test_cache_localize_rewrites_and_persists(capsys, monkeypatch, tmp_path, no_metadata_load):
    captured = {}

    def fake_find_all_files(local_path, warnmissing):
        captured.update(local_path=local_path, warnmissing=warnmissing)
        _metadata_mod._metadata = {"301204": {"file_list": ["/local/f.root"]}}

    monkeypatch.setattr(_metadata_mod, "find_all_files", fake_find_all_files)
    monkeypatch.setattr(_metadata_mod, "get_current_release", lambda: "2024r-pp")
    assert _run("--json", "cache", "localize", "/data", "--warn-missing") == 0
    assert captured == {"local_path": "/data", "warnmissing": True}
    assert json.loads(capsys.readouterr().out)["localized"] == "/data"
    assert (tmp_path / "cache" / "metadata-2024r-pp.json").exists()


def test_cache_localize_prints_confirmation(capsys, monkeypatch, no_metadata_load):
    monkeypatch.setattr(_metadata_mod, "find_all_files", lambda local_path, warnmissing: None)
    monkeypatch.setattr(_metadata_mod, "get_current_release", lambda: "2024r-pp")
    _run("cache", "localize", "/data")
    assert "now points at /data" in capsys.readouterr().out


# --- env group ---


def test_env_install_passes_packages_through(capsys, monkeypatch):
    captured = {}

    def fake_install(*packages, environment_file=None):
        captured.update(packages=packages, environment_file=environment_file)

    monkeypatch.setattr(cli._utils, "install_from_environment", fake_install)
    assert _run("env", "install", "coffea", "dask", "--environment-file", "env.yml") == 0
    assert captured == {"packages": ("coffea", "dask"), "environment_file": "env.yml"}
    assert json.loads(capsys.readouterr().out)["installed"] == ["coffea", "dask"]


def test_env_install_with_no_packages_installs_all(capsys, monkeypatch):
    monkeypatch.setattr(cli._utils, "install_from_environment", lambda *a, **kw: None)
    _run("env", "install")
    assert json.loads(capsys.readouterr().out)["installed"] == "all"


# --- Global options and error handling ---


def test_release_flag_overrides_saved_release(monkeypatch):
    cli._write_config({"release": "2020e-13tev"})
    applied = []
    monkeypatch.setattr(cli, "_apply_release", lambda release, refresh, needs_full: applied.append(release))
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: [])
    _run("--release", "2024r-pp", "dataset", "list")
    assert applied == ["2024r-pp"]


def test_refresh_flag_is_passed_to_apply_release(monkeypatch):
    captured = {}

    def fake_apply(release, refresh, needs_full):
        captured.update(release=release, refresh=refresh, needs_full=needs_full)

    monkeypatch.setattr(cli, "_apply_release", fake_apply)
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: [])
    _run("--refresh", "dataset", "list")
    assert captured["refresh"] is True
    assert captured["needs_full"] is True


def test_single_dataset_commands_do_not_request_full_metadata(monkeypatch):
    captured = {}

    def fake_apply(release, refresh, needs_full):
        captured.update(needs_full=needs_full)

    monkeypatch.setattr(cli, "_apply_release", fake_apply)
    monkeypatch.setattr(_metadata_mod, "get_metadata", lambda key, var: {})
    _run("dataset", "show", "301204")
    assert captured["needs_full"] is False


def test_verbosity_flag_calls_set_verbosity(monkeypatch, no_metadata_load):
    calls = []
    monkeypatch.setattr(_metadata_mod, "set_verbosity", lambda level: calls.append(level))
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: [])
    _run("--verbosity", "debug", "dataset", "list")
    assert calls == ["debug"]


def test_cli_is_quiet_by_default(monkeypatch, no_metadata_load):
    calls = []
    monkeypatch.setattr(_metadata_mod, "set_verbosity", lambda level: calls.append(level))
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: [])
    _run("dataset", "list")
    assert calls == ["warning"]


def test_unknown_dataset_returns_exit_code_1(capsys, monkeypatch, no_metadata_load):
    def raise_value_error(key, var):
        raise ValueError(f"Dataset '{key}' not found")

    monkeypatch.setattr(_metadata_mod, "get_metadata", raise_value_error)
    assert _run("dataset", "show", "does-not-exist") == 1
    assert "not found" in capsys.readouterr().err


def test_network_error_returns_exit_code_1(capsys, monkeypatch, no_metadata_load):
    def raise_request_exception(key, var):
        raise cli.requests.exceptions.RequestException("connection failed")

    monkeypatch.setattr(_metadata_mod, "get_metadata", raise_request_exception)
    assert _run("dataset", "show", "301204") == 1
    assert "Network error" in capsys.readouterr().err


# --- Update notification ---


def test_no_update_check_flag_skips_pypi_lookup(monkeypatch, no_metadata_load):
    called = []
    monkeypatch.setattr(cli, "_fetch_latest_version", lambda: called.append(True))
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: [])
    _run("dataset", "list")
    assert called == []


def test_update_check_env_var_skips_pypi_lookup(monkeypatch, no_metadata_load):
    called = []
    monkeypatch.setattr(cli, "_fetch_latest_version", lambda: called.append(True))
    monkeypatch.setenv("ATLASOPENMAGIC_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(_metadata_mod, "available_datasets", lambda: [])
    cli.main(["dataset", "list"])
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


def test_read_write_cache_round_trip():
    assert cli._read_cache() == {}  # File doesn't exist yet.
    cli._write_cache({"checked_at": 123.0, "latest_version": "1.2.3"})
    assert cli._read_cache() == {"checked_at": 123.0, "latest_version": "1.2.3"}


def test_read_cache_ignores_corrupt_file(tmp_path):
    path = tmp_path / "cache" / "update_check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json")
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
