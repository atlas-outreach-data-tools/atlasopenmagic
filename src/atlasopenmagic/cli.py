"""Command-line interface for atlasopenmagic.

Installed as both `atlasopenmagic` and `atom`. Exposes the package's public
API as `atom <group> <command> [arguments] [options]`, so ATLAS Open Data can
be queried from shell scripts and other non-Python tooling. Output is JSON on
stdout so it composes with tools like `jq`; informational messages (including
the update notice) go to stderr.

Unlike a Python session, each CLI invocation is a fresh process, so the
library's in-memory release selection and metadata cache do not survive
between commands. Two pieces of on-disk state make up for that:

* a config file holding the release chosen with `atom release set`, and
* a per-release metadata cache, so repeated commands don't refetch the
  whole release from the API every time.

Deprecated library functions (`get_urls_data`, `build_mc_dataset`,
`build_data_dataset`) are deliberately not exposed here; their replacements
are `dataset urls` and `dataset build`.
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from importlib.metadata import PackageNotFoundError, version

import requests

from . import metadata as _metadata
from . import utils as _utils
from . import weights as _weights

_PACKAGE_NAME = "atlasopenmagic"
_PYPI_URL = f"https://pypi.org/pypi/{_PACKAGE_NAME}/json"

# Disposable state: safe to delete at any time, rebuilt from the API on demand.
_CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "atlasopenmagic",
)
_CACHE_PATH = os.path.join(_CACHE_DIR, "update_check.json")

# Durable state: records what the user explicitly asked for.
_CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "atlasopenmagic",
    "config.json",
)

_CHECK_INTERVAL_SECONDS = 24 * 3600

# Published releases are effectively immutable, so this can be generous; it
# exists to eventually pick up datasets or skims added to an existing release.
_METADATA_CACHE_TTL_SECONDS = 7 * 24 * 3600

# Release names become filenames, so keep them to something obviously safe.
_SAFE_RELEASE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


# --- Update notification (CLI only; never runs on `import atlasopenmagic`) ---


def _installed_version():
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return None


def _version_tuple(v):
    """Loose numeric-prefix comparison, good enough for this package's plain X.Y.Z versions."""
    parts = []
    for chunk in v.split("."):
        digits = ""
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _read_cache():
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_cache(data):
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass  # Caching is a nice-to-have; never fail the command over it.


def _fetch_latest_version():
    try:
        resp = requests.get(_PYPI_URL, timeout=2)
        resp.raise_for_status()
        return resp.json()["info"]["version"]
    except (requests.exceptions.RequestException, ValueError, KeyError):
        return None


def _check_for_update(result: dict):
    """Populate result['notice'] if a newer release is available. Runs in a background thread."""
    installed = _installed_version()
    if not installed:
        return

    cache = _read_cache()
    now = time.time()
    if now - cache.get("checked_at", 0) < _CHECK_INTERVAL_SECONDS:
        latest = cache.get("latest_version")
    else:
        latest = _fetch_latest_version()
        if latest:
            _write_cache({"checked_at": now, "latest_version": latest})

    if latest and _version_tuple(latest) > _version_tuple(installed):
        result["notice"] = (
            f"A new version of atlasopenmagic is available: {installed} -> {latest}\n"
            "Upgrade with: pip install --upgrade atlasopenmagic"
        )


def _start_update_check(disabled: bool):
    result = {}
    if disabled or os.environ.get("ATLASOPENMAGIC_NO_UPDATE_CHECK"):
        return None
    thread = threading.Thread(target=_check_for_update, args=(result,), daemon=True)
    thread.start()
    return thread, result


def _print_update_notice(check):
    if check is None:
        return
    thread, result = check
    thread.join(timeout=2)
    if result.get("notice"):
        print(f"\n{result['notice']}", file=sys.stderr)


# --- Persistent configuration ---


def _read_config() -> dict:
    """Read the CLI config file, treating any unreadable or malformed file as empty."""
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_config(data: dict) -> None:
    """Write the CLI config file.

    Unlike the metadata cache, failures here are not swallowed: the user asked
    for this to be remembered, so they need to know when it wasn't.
    """
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --- Release selection ---


def _metadata_cache_path(release: str) -> str:
    if not _SAFE_RELEASE_RE.match(release):
        raise ValueError(f"Invalid release name: '{release}'.")
    return os.path.join(_CACHE_DIR, f"metadata-{release}.json")


def _known_releases() -> list[str]:
    """Releases that may be selected: the published ones plus any imported locally."""
    known = list(_metadata.RELEASES_DESC)
    try:
        cached = os.listdir(_CACHE_DIR)
    except OSError:
        cached = []
    for name in cached:
        if name.startswith("metadata-") and name.endswith(".json"):
            release = name[len("metadata-") : -len(".json")]
            if release not in known:
                known.append(release)
    return known


def _validate_release(release: str) -> None:
    """Raise ValueError if `release` is neither published nor present in the local cache."""
    if release not in _known_releases():
        raise ValueError(f"Invalid release '{release}'. Use one of: {', '.join(_known_releases())}")


def _resolve_release(cli_release):
    """Resolve the release to use, returning (release, source).

    Precedence follows the usual CLI convention: an explicit flag beats the
    environment, which beats saved config, which beats the library default.
    """
    if cli_release:
        return cli_release, "--release"
    env_release = os.environ.get("ATLAS_RELEASE")
    if env_release:
        return env_release, "ATLAS_RELEASE"
    configured = _read_config().get("release")
    if configured:
        return configured, "config"
    return _metadata.get_current_release(), "default"


# --- Metadata cache ---


def _cache_age(path: str):
    """Age of `path` in seconds, or None if it doesn't exist."""
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return None


def _save_metadata_cache(cache_file: str) -> None:
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        _metadata.save_metadata(cache_file)
    except OSError:
        pass  # Same as the update cache: never fail a command over a cache write.


def _apply_release(release: str, refresh: bool, needs_full: bool) -> None:
    """Point the library at `release`, loading metadata from cache where possible."""
    _validate_release(release)
    cache_file = _metadata_cache_path(release)

    age = None if refresh else _cache_age(cache_file)
    if age is not None and age < _METADATA_CACHE_TTL_SECONDS:
        try:
            _metadata.read_metadata(cache_file, release=release)
            return
        except (OSError, ValueError):
            pass  # Corrupt or truncated cache: fall through and refetch.

    if not needs_full:
        # Single-dataset lookups hit the per-dataset API endpoint, which is far
        # cheaper than pulling a whole release just to read one field. Set the
        # release directly rather than via set_release(), which always fetches.
        _metadata.current_release = release
        return

    _metadata.set_release(release)
    _save_metadata_cache(cache_file)


# --- Output helpers ---


def _emit(data):
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def _read_json_file(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --- release ---


def _cmd_release_list(_args):
    _emit(_metadata.RELEASES_DESC)


def _cmd_release_show(args):
    release, source = _resolve_release(args.release)
    _emit({"release": release, "source": source})


def _cmd_release_set(args):
    _validate_release(args.name)
    config = _read_config()
    config["release"] = args.name
    _write_config(config)
    _emit({"release": args.name, "config_file": _CONFIG_PATH})


def _cmd_release_unset(_args):
    config = _read_config()
    config.pop("release", None)
    _write_config(config)
    _emit({"release": None, "config_file": _CONFIG_PATH})


# --- dataset ---


def _cmd_dataset_list(_args):
    _emit(_metadata.available_datasets())


def _cmd_dataset_show(args):
    if args.full:
        _emit(_metadata.get_all_info(args.key, args.field))
    else:
        _emit(_metadata.get_metadata(args.key, args.field))


def _cmd_dataset_urls(args):
    _emit(_metadata.get_urls(args.key, skim=args.skim, protocol=args.protocol, cache=args.cache))


def _cmd_dataset_search(args):
    _emit(_metadata.match_metadata(args.field, args.value, float_tolerance=args.tolerance))


def _cmd_dataset_build(args):
    samples_defs = _read_json_file(args.definitions)
    if not isinstance(samples_defs, dict):
        raise ValueError(f"{args.definitions} must contain a JSON object mapping sample names to definitions.")
    _emit(
        _utils.build_dataset(
            samples_defs,
            skim=args.skim,
            protocol=args.protocol,
            cache=args.cache,
        )
    )


# --- metadata ---


def _cmd_metadata_fields(_args):
    _emit(_metadata.get_metadata_fields())


def _cmd_metadata_keywords(_args):
    _emit(_metadata.available_keywords())


def _cmd_metadata_skims(_args):
    _emit(_metadata.available_skims())


def _cmd_metadata_dump(_args):
    _emit(_metadata.get_all_metadata())


def _cmd_metadata_export(args):
    _metadata.save_metadata(args.file)
    _emit({"exported": args.file, "release": _metadata.get_current_release()})


def _cmd_metadata_import(args):
    _metadata.read_metadata(args.file, release=args.as_release)
    # Persist into the cache so subsequent commands can select this release.
    _save_metadata_cache(_metadata_cache_path(args.as_release))
    _emit({"imported": args.file, "release": args.as_release})


# --- weights ---


def _cmd_weights_show(args):
    _emit(_weights.get_weights(args.key, e_tag=args.e_tag))


def _cmd_weights_names(args):
    _emit(_weights.get_weight_names(args.key, e_tag=args.e_tag))


def _cmd_weights_list(args):
    _emit(_weights.get_all_weights_for_release(release_name=args.for_release))


# --- cache ---


def _cmd_cache_info(_args):
    entries = []
    for release in sorted(_known_releases()):
        path = _metadata_cache_path(release)
        age = _cache_age(path)
        if age is None:
            continue
        entries.append(
            {
                "release": release,
                "path": path,
                "age_seconds": int(age),
                "stale": age >= _METADATA_CACHE_TTL_SECONDS,
            }
        )
    _emit({"cache_dir": _CACHE_DIR, "entries": entries})


def _cmd_cache_clear(_args):
    removed = []
    # Only ever remove files we know we wrote, never a blind glob of the directory.
    for release in sorted(_known_releases()):
        path = _metadata_cache_path(release)
        try:
            os.remove(path)
        except OSError:
            continue
        removed.append(path)
    _emit({"removed": removed})


def _cmd_cache_localize(args):
    _metadata.find_all_files(args.path, warnmissing=args.warn_missing)
    release = _metadata.get_current_release()
    _save_metadata_cache(_metadata_cache_path(release))
    _emit({"localized": args.path, "release": release})


# --- env ---


def _cmd_env_install(args):
    _utils.install_from_environment(*args.packages, environment_file=args.environment_file)
    _emit({"installed": list(args.packages) or "all", "environment_file": args.environment_file})


# --- Argument parsing ---


def _add_release_commands(sub):
    """`release` manages which release other commands act on. Local config only."""
    parser = sub.add_parser("release", help="Inspect or set the release used by default")
    parser.set_defaults(loads_metadata=False)
    group = parser.add_subparsers(dest="release_command", required=True)

    group.add_parser("list", help="List available data releases").set_defaults(func=_cmd_release_list)
    group.add_parser("show", help="Show the release in effect and where it came from").set_defaults(
        func=_cmd_release_show
    )
    p = group.add_parser("set", help="Save a release to use for future commands")
    p.add_argument("name", help="Release name, e.g. 2024r-pp")
    p.set_defaults(func=_cmd_release_set)
    group.add_parser("unset", help="Forget the saved release").set_defaults(func=_cmd_release_unset)


def _add_dataset_commands(sub):
    """`dataset` covers discovery and per-dataset lookups."""
    parser = sub.add_parser("dataset", help="Find datasets and get their metadata or file URLs")
    group = parser.add_subparsers(dest="dataset_command", required=True)

    group.add_parser("list", help="List dataset IDs in the active release").set_defaults(
        func=_cmd_dataset_list, needs_full=True
    )

    p = group.add_parser("show", help="Show metadata for one dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--field", help="Return only this metadata field")
    p.add_argument("--full", action="store_true", help="Include file_list and skims")
    p.set_defaults(func=_cmd_dataset_show)

    p = group.add_parser("urls", help="Get file URLs for one dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--skim", default="noskim", help="Skim type (default: noskim)")
    p.add_argument("--protocol", choices=["root", "https", "eos"], default="root")
    cache_group = p.add_mutually_exclusive_group()
    cache_group.add_argument("--cache", dest="cache", action="store_true", default=None)
    cache_group.add_argument("--no-cache", dest="cache", action="store_false")
    p.set_defaults(func=_cmd_dataset_urls)

    p = group.add_parser("search", help="Find datasets whose metadata field matches a value")
    p.add_argument("field", help="Metadata field to search, e.g. process")
    p.add_argument("value", help="Value to match")
    p.add_argument("--tolerance", type=float, default=0.01, help="Fractional tolerance for float fields")
    p.set_defaults(func=_cmd_dataset_search, needs_full=True)

    p = group.add_parser("build", help="Build a sample->URLs mapping from a JSON definitions file")
    p.add_argument("definitions", help="JSON file mapping sample names to {'dids': [...], 'color': ...}")
    p.add_argument("--skim", default="noskim", help="Skim type (default: noskim)")
    p.add_argument("--protocol", choices=["root", "https", "eos"], default="https")
    cache_group = p.add_mutually_exclusive_group()
    cache_group.add_argument("--cache", dest="cache", action="store_true", default=False)
    cache_group.add_argument("--no-cache", dest="cache", action="store_false")
    p.set_defaults(func=_cmd_dataset_build)


def _add_metadata_commands(sub):
    """`metadata` covers release-wide vocabularies and bulk import/export."""
    parser = sub.add_parser("metadata", help="Release-wide metadata vocabularies and bulk transfer")
    group = parser.add_subparsers(dest="metadata_command", required=True)

    group.add_parser("fields", help="List available metadata fields").set_defaults(
        func=_cmd_metadata_fields, needs_full=True
    )
    group.add_parser("keywords", help="List keywords used in the active release").set_defaults(
        func=_cmd_metadata_keywords, needs_full=True
    )
    group.add_parser("skims", help="List skims available in the active release").set_defaults(
        func=_cmd_metadata_skims, needs_full=True
    )
    group.add_parser("dump", help="Print the whole metadata dictionary").set_defaults(
        func=_cmd_metadata_dump, needs_full=True
    )

    p = group.add_parser("export", help="Write the active release's metadata to a .json or .txt file")
    p.add_argument("file", help="Destination file; extension selects the format")
    p.set_defaults(func=_cmd_metadata_export, needs_full=True)

    p = group.add_parser("import", help="Load metadata from a file into the local cache")
    p.add_argument("file", help="JSON file previously written by `metadata export`")
    p.add_argument("--as-release", dest="as_release", default="custom", help="Name to store it under")
    p.set_defaults(func=_cmd_metadata_import, loads_metadata=False)


def _add_weights_commands(sub):
    """`weights` covers Monte Carlo weight metadata."""
    parser = sub.add_parser("weights", help="Query Monte Carlo weight metadata")
    group = parser.add_subparsers(dest="weights_command", required=True)

    p = group.add_parser("show", help="Show weight metadata for one dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--e-tag", dest="e_tag")
    p.set_defaults(func=_cmd_weights_show)

    p = group.add_parser("names", help="List weight names for one dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--e-tag", dest="e_tag")
    p.set_defaults(func=_cmd_weights_names)

    p = group.add_parser("list", help="List weight names for every dataset in a release")
    p.add_argument("--for-release", dest="for_release", help="Defaults to the active release")
    p.set_defaults(func=_cmd_weights_list)


def _add_cache_commands(sub):
    """`cache` manages the on-disk metadata cache."""
    parser = sub.add_parser("cache", help="Inspect, clear, or localize the metadata cache")
    parser.set_defaults(loads_metadata=False)
    group = parser.add_subparsers(dest="cache_command", required=True)

    group.add_parser("info", help="Show which releases are cached locally").set_defaults(func=_cmd_cache_info)
    group.add_parser("clear", help="Delete all cached release metadata").set_defaults(func=_cmd_cache_clear)

    p = group.add_parser("localize", help="Rewrite cached URLs to point at a local copy of the files")
    p.add_argument("path", help="Root directory holding your local copy of the data")
    p.add_argument("--warn-missing", action="store_true", help="Warn about files not found locally")
    # Needs the release loaded so the rewritten metadata can be saved back.
    p.set_defaults(func=_cmd_cache_localize, loads_metadata=True, needs_full=True)


def _add_env_commands(sub):
    """`env` covers environment setup helpers."""
    parser = sub.add_parser("env", help="Environment setup helpers")
    parser.set_defaults(loads_metadata=False)
    group = parser.add_subparsers(dest="env_command", required=True)

    p = group.add_parser("install", help="Install packages pinned in an environment.yml")
    p.add_argument("packages", nargs="*", help="Packages to install; omit to install all")
    p.add_argument("--environment-file", dest="environment_file", help="Path or URL to environment.yml")
    p.set_defaults(func=_cmd_env_install)


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="atlasopenmagic",
        description="Query ATLAS Open Data metadata, file URLs, and MC weights.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_installed_version() or 'unknown'}",
    )
    parser.add_argument("--release", help="Release to use for this command, overriding any saved setting")
    parser.add_argument(
        "--verbosity",
        choices=["error", "warning", "info", "debug"],
        help="Log verbosity for the underlying API calls",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore cached metadata and refetch from the API",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="Skip the PyPI check for a newer atlasopenmagic release",
    )

    # Most commands only read one dataset; those needing the whole release
    # loaded opt in with needs_full=True, and purely local ones with
    # loads_metadata=False.
    parser.set_defaults(loads_metadata=True, needs_full=False)

    sub = parser.add_subparsers(dest="command", required=True)

    _add_release_commands(sub)
    _add_dataset_commands(sub)
    _add_metadata_commands(sub)
    _add_weights_commands(sub)
    _add_cache_commands(sub)
    _add_env_commands(sub)

    return parser


def main(argv=None) -> int:
    """Entry point for the `atlasopenmagic` / `atom` console scripts."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    update_check = _start_update_check(args.no_update_check)

    # Quiet by default, the way a CLI is expected to behave: the library
    # defaults to INFO, which narrates every cache load on stderr.
    _metadata.set_verbosity(args.verbosity or "warning")

    try:
        if args.loads_metadata:
            release, _ = _resolve_release(args.release)
            _apply_release(release, args.refresh, args.needs_full)
        args.func(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    # RequestException subclasses OSError, so it has to be caught first.
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        _print_update_notice(update_check)

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
