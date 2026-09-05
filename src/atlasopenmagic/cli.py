"""Command-line interface for atlasopenmagic.

Installed as both `atlasopenmagic` and `atom`. Exposes the package's public
API as `atom <group> <command> [arguments] [options]`, so ATLAS Open Data can
be queried from shell scripts and other non-Python tooling. Output is JSON on
stdout so it composes with tools like `jq`; informational messages (including
the update notice) go to stderr.

Unlike a Python session, each CLI invocation is a fresh process, so the
library's in-memory release selection and metadata cache do not survive
between commands. Two pieces of on-disk state make up for that: a config
file holding the release chosen with `atom release set`, and a per-release
metadata cache, so repeated commands don't refetch the whole release from
the API every time.

The module is laid out in the order a command flows through it: update check,
config, release resolution, metadata cache, output helpers, one `_cmd_*`
handler per command, then the parser builders that wire them together.

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
from typing import Any, Optional

import requests

# Absolute imports: lazydocs loads each module without package context, and
# relative imports break its docs generation (see commit 5c7eb09).
from atlasopenmagic import metadata as _metadata
from atlasopenmagic import utils as _utils
from atlasopenmagic import weights as _weights

# argparse's subparser action has no public name, so alias the private one once
# here rather than repeating it in every parser builder's annotation. A `sub`
# argument below is always the object returned by `parser.add_subparsers()`, on
# which `.add_parser(...)` creates one command.
_SubParsers = argparse._SubParsersAction  # pylint: disable=protected-access

# The background update check hands back the thread it started plus the dict
# that thread writes its result into.
_UpdateCheck = Optional[tuple[threading.Thread, dict]]

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

# A search value that opens with a bracket was almost certainly meant to be a
# JSON list or object; see _coerce_search_value for why that matters.
_LOOKS_STRUCTURED_RE = re.compile(r"^\s*[\[{]")

# Sentinel local path meaning "native POSIX EOS access", as set_release() accepts.
_LOCAL_PATH_EOS = "eos"

# Matches the library's own default for set_release(page_size=...).
_DEFAULT_PAGE_SIZE = 1000


# --- Update notification ---
#
# This runs only from the CLI. Importing atlasopenmagic in a script or notebook
# never reaches this module, so no import is ever slowed down or made to touch
# the network by it.


def _installed_version() -> Optional[str]:
    """Version of the installed package, or None if it isn't installed (e.g. run from a source tree)."""
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return None


def _version_tuple(v: str) -> tuple[int, ...]:
    """Loose numeric-prefix comparison, good enough for this package's plain X.Y.Z versions."""
    parts = []
    for chunk in v.split("."):
        # Stop at the first non-digit so a suffix like "1rc2" still compares as 1.
        digits = ""
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _read_cache() -> dict:
    """Read the update-check cache, treating an unreadable or malformed file as empty."""
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_cache(data: dict) -> None:
    """Record when PyPI was last checked, so the next run can skip the network."""
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass  # Caching is a nice-to-have; never fail the command over it.


def _fetch_latest_version() -> Optional[str]:
    """Ask PyPI for the newest published version, or None if that doesn't work out.

    Every failure is deliberately equivalent to "don't know": this is a courtesy
    notice, so being offline or behind a proxy must not disturb the real command.
    """
    try:
        resp = requests.get(_PYPI_URL, timeout=2)
        resp.raise_for_status()
        return resp.json()["info"]["version"]
    except (requests.exceptions.RequestException, ValueError, KeyError):
        return None


def _check_for_update(result: dict) -> None:
    """Populate result['notice'] if a newer release is available. Runs in a background thread."""
    installed = _installed_version()
    if not installed:
        return

    # At most one PyPI request a day; in between, reuse the cached answer.
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


def _start_update_check(disabled: bool) -> _UpdateCheck:
    """Start the update check in the background, or return None if it is switched off.

    It runs concurrently with the actual command so the user never waits on it.
    """
    result: dict = {}
    if disabled or os.environ.get("ATLASOPENMAGIC_NO_UPDATE_CHECK"):
        return None
    thread = threading.Thread(target=_check_for_update, args=(result,), daemon=True)
    thread.start()
    return thread, result


def _print_update_notice(check: _UpdateCheck) -> None:
    """Print the notice if the check found one, waiting only briefly for it.

    The thread is a daemon and the timeout is short, so a hung network request
    delays exit by at most a couple of seconds and never blocks it.
    """
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
    """Cache file for `release`, rejecting names that wouldn't be safe as a filename."""
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
    # A cache file is the only trace an imported release leaves, so the filenames
    # are what make `metadata import --as-release foo` selectable afterwards.
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


def _resolve_release(cli_release: Optional[str]) -> tuple[str, str]:
    """Resolve the release to use, returning (release, source).

    Precedence follows the usual CLI convention: an explicit flag beats the
    environment, which beats saved config, which beats the library default.
    The source is reported by `release show` so the choice is never a mystery.
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


def _cache_age(path: str) -> Optional[float]:
    """Age of `path` in seconds, or None if it doesn't exist."""
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return None


def _save_metadata_cache(cache_file: str) -> None:
    """Write the library's currently loaded metadata to `cache_file`."""
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        _metadata.save_metadata(cache_file)
    except OSError:
        pass  # Same as the update cache: never fail a command over a cache write.


def _resolve_local_path(release: str, cli_local_path: Optional[str]) -> Optional[str]:
    """Resolve the local data path for `release`: flag first, then saved config."""
    if cli_local_path is not None:
        return cli_local_path or None  # An empty --local-path clears it for this run.
    return _read_config().get("local_paths", {}).get(release)


def _apply_local_path(local_path: Optional[str]) -> None:
    """Point the library at a local copy of the data, as set_release(local_path=...) does."""
    # Warn rather than fail: the path may be valid on the machine that will
    # eventually consume the URLs, which isn't necessarily this one.
    if local_path and local_path != _LOCAL_PATH_EOS and not os.path.isdir(local_path):
        print(
            f"Warning: local path '{local_path}' does not exist; URLs will point at it anyway.",
            file=sys.stderr,
        )
    _metadata.current_local_path = local_path


def _load_metadata_for(release: str, refresh: bool, needs_full: bool, page_size: Optional[int]) -> None:
    """Populate the library's metadata cache for `release`, from disk where possible."""
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

    _metadata.set_release(release, page_size=page_size or _DEFAULT_PAGE_SIZE)
    _save_metadata_cache(cache_file)


def _apply_release(
    release: str,
    refresh: bool,
    needs_full: bool,
    local_path: Optional[str] = None,
    page_size: Optional[int] = None,
) -> None:
    """Point the library at `release`, loading metadata from cache where possible."""
    _validate_release(release)
    _load_metadata_for(release, refresh, needs_full, page_size)
    # Applied last: set_release() resets current_local_path, so this has to win.
    _apply_local_path(local_path)


# --- Output helpers ---


def _emit(data: Any) -> None:
    """Print a result as JSON on stdout.

    Sorted keys keep output stable enough to diff between runs; `default=str`
    is a backstop so an unexpected non-serialisable value degrades to its
    string form instead of crashing the command.
    """
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def _read_json_file(path: str) -> Any:
    """Load a JSON file, letting OSError and ValueError reach main()'s handlers."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _coerce_search_value(value: str, raw: bool) -> Any:
    """Turn a command-line search value into the type match_metadata expects.

    A shell can only hand over strings, but match_metadata compares some fields
    by identity: searching an integer field for "20000" silently matches nothing
    where 20000 matches. Reading the value as JSON recovers ints, floats, lists
    (which match_metadata treats as AND-matching) and null, while anything that
    isn't valid JSON stays the plain string it already was.
    """
    if raw:
        return value
    try:
        return json.loads(value)
    except ValueError:
        # Falling back to text is right for values like `pp>Zprime>ee`, but a
        # value that opens like a JSON list usually means the shell stripped the
        # quotes: bash turns an unquoted ["a","b"] into [a,b], which would then
        # be searched for as literal text and quietly match nothing.
        if _LOOKS_STRUCTURED_RE.match(value):
            print(
                f"Warning: '{value}' is not valid JSON, so it is being searched for as text. "
                "If you meant a list, quote it so the shell keeps it intact: "
                '\'["2electron","BSM"]\'. Pass --raw to silence this.',
                file=sys.stderr,
            )
        return value


def _validate_samples_defs(samples_defs: Any, path: str) -> None:
    """Check a `dataset build` definitions file before handing it to the library.

    build_dataset() iterates `info["dids"]` directly, so a missing key raises a
    bare KeyError and a string is iterated character by character. Both are easy
    mistakes to make in a hand-written file, so catch them with a message that
    names the offending sample.
    """
    if not isinstance(samples_defs, dict):
        raise ValueError(f"{path} must contain a JSON object mapping sample names to definitions.")
    for name, info in samples_defs.items():
        if not isinstance(info, dict):
            raise ValueError(f"{path}: sample '{name}' must be an object with a 'dids' list.")
        if "dids" not in info:
            raise ValueError(f"{path}: sample '{name}' is missing 'dids'.")
        if not isinstance(info["dids"], list):
            raise ValueError(
                f"{path}: sample '{name}' has 'dids' as {type(info['dids']).__name__}; "
                'it must be a list, e.g. "dids": ["301204"].'
            )
        if not info["dids"]:
            raise ValueError(f"{path}: sample '{name}' has an empty 'dids' list.")


def _format_age(seconds: float) -> str:
    """Render a cache age the way a person would say it."""
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            value = int(seconds // size)
            return f"{value} {unit}{'s' if value != 1 else ''} old"
    return "just now"


def _describe_cache(release: str) -> str:
    """One-word cache state for `release`, for human-readable output."""
    age = _cache_age(_metadata_cache_path(release))
    if age is None:
        return "not cached"
    state = "stale" if age >= _METADATA_CACHE_TTL_SECONDS else "fresh"
    return f"{state}, {_format_age(age)}"


# --- Command handlers ---
#
# Every _cmd_* function takes the parsed argparse.Namespace and returns None:
# they print and are the last thing a command does, so there is nothing to hand
# back. The early `return`s below are just bail-outs after emitting JSON.
# Handlers named `_args` ignore their argument entirely.


# --- release ---


def _release_catalogue() -> dict[str, str]:
    """Every selectable release: the published ones, plus anything imported locally."""
    catalogue = dict(_metadata.RELEASES_DESC)
    for name in _known_releases():
        if name not in catalogue:
            catalogue[name] = "Imported locally with `metadata import`."
    return catalogue


def _cmd_release_list(args: argparse.Namespace) -> None:
    """List every selectable release, marking the active one with `*`."""
    catalogue = _release_catalogue()
    if args.json:
        _emit(catalogue)
        return
    active, _ = _resolve_release(args.release)
    width = max(len(name) for name in catalogue)
    for name, description in catalogue.items():
        marker = "*" if name == active else " "
        print(f"{marker} {name.ljust(width)}  {description}")


def _cmd_release_show(args: argparse.Namespace) -> None:
    """Report the release in effect, where it came from, and its cache state."""
    release, source = _resolve_release(args.release)
    local_path = _resolve_local_path(release, args.local_path)
    if args.json:
        _emit(
            {
                "release": release,
                "source": source,
                "cache": _describe_cache(release),
                "local_path": local_path,
            }
        )
        return
    print(f"Release: {release}")
    print(f"Source:  {source}")
    print(f"Cache:   {_describe_cache(release)}")
    print(f"Data:    {local_path or 'remote'}")


def _cmd_release_set(args: argparse.Namespace) -> None:
    """Save a release for future commands and, unless told not to, cache it now."""
    _validate_release(args.name)
    config = _read_config()
    config["release"] = args.name

    # The local path is per-release state, so it is stored per release rather
    # than as a single global setting. `release set --local-path` wins over a
    # global --local-path given before the subcommand.
    chosen_local_path = args.set_local_path if args.set_local_path is not None else args.local_path
    if chosen_local_path is not None:
        local_paths = config.setdefault("local_paths", {})
        if chosen_local_path:
            local_paths[args.name] = chosen_local_path
        else:
            local_paths.pop(args.name, None)
    _write_config(config)

    local_path = _resolve_local_path(args.name, chosen_local_path)

    # Warm the cache now, so the cost of fetching a release is paid here where
    # the user asked for it, rather than ambushing whichever query comes first.
    cached = None
    if not args.no_fetch:
        _apply_release(
            args.name,
            refresh=args.refresh,
            needs_full=True,
            local_path=local_path,
            page_size=args.page_size,
        )
        cached = len(_metadata.available_datasets())

    if args.json:
        _emit(
            {
                "release": args.name,
                "config_file": _CONFIG_PATH,
                "datasets_cached": cached,
                "local_path": local_path,
            }
        )
        return
    print(f"Release set to {args.name} ({_CONFIG_PATH}).")
    if local_path:
        print(f"Data path: {local_path}")
    if cached is not None:
        print(f"Cached {cached} datasets.")


def _cmd_release_unset(args: argparse.Namespace) -> None:
    """Forget the saved release, then report what the fallback now is."""
    config = _read_config()
    config.pop("release", None)
    _write_config(config)
    if args.json:
        _emit({"release": None, "config_file": _CONFIG_PATH})
        return
    fallback, source = _resolve_release(None)
    print(f"Saved release cleared. Now using {fallback} (source: {source}).")


# --- dataset ---


def _cmd_dataset_list(_args: argparse.Namespace) -> None:
    """List the dataset IDs available in the active release."""
    _emit(_metadata.available_datasets())


def _cmd_dataset_show(args: argparse.Namespace) -> None:
    """Show one dataset's metadata, or a single field of it."""
    if args.full:
        _emit(_metadata.get_all_info(args.key, args.field))
    else:
        _emit(_metadata.get_metadata(args.key, args.field))


def _cmd_dataset_urls(args: argparse.Namespace) -> None:
    """Print the file URLs for one dataset."""
    _emit(_metadata.get_urls(args.key, skim=args.skim, protocol=args.protocol, cache=args.cache))


def _cmd_dataset_search(args: argparse.Namespace) -> None:
    """Find datasets whose metadata field matches a value."""
    value = _coerce_search_value(args.value, args.raw)
    _emit(_metadata.match_metadata(args.field, value, float_tolerance=args.tolerance))


def _cmd_dataset_build(args: argparse.Namespace) -> None:
    """Turn a JSON definitions file into a sample-name -> URLs mapping."""
    samples_defs = _read_json_file(args.definitions)
    _validate_samples_defs(samples_defs, args.definitions)
    _emit(
        _utils.build_dataset(
            samples_defs,
            skim=args.skim,
            protocol=args.protocol,
            cache=args.cache,
        )
    )


# --- metadata ---


def _cmd_metadata_fields(_args: argparse.Namespace) -> None:
    """List the metadata fields available in the active release."""
    _emit(_metadata.get_metadata_fields())


def _cmd_metadata_keywords(_args: argparse.Namespace) -> None:
    """List the keywords used in the active release."""
    _emit(_metadata.available_keywords())


def _cmd_metadata_skims(_args: argparse.Namespace) -> None:
    """List the skims available in the active release."""
    _emit(_metadata.available_skims())


def _cmd_metadata_dump(_args: argparse.Namespace) -> None:
    """Print the whole metadata dictionary for the active release."""
    _emit(_metadata.get_all_metadata())


def _cmd_metadata_export(args: argparse.Namespace) -> None:
    """Write the active release's metadata to a file."""
    _metadata.save_metadata(args.file)
    _emit({"exported": args.file, "release": _metadata.get_current_release()})


def _cmd_metadata_import(args: argparse.Namespace) -> None:
    """Load metadata from a file and register it under a release name."""
    _metadata.read_metadata(args.file, release=args.as_release)
    # Persist into the cache so subsequent commands can select this release.
    _save_metadata_cache(_metadata_cache_path(args.as_release))
    _emit({"imported": args.file, "release": args.as_release})


# --- weights ---


def _cmd_weights_show(args: argparse.Namespace) -> None:
    """Show the Monte Carlo weight metadata for one dataset."""
    _emit(_weights.get_weights(args.key, e_tag=args.e_tag))


def _cmd_weights_names(args: argparse.Namespace) -> None:
    """List the weight names for one dataset."""
    _emit(_weights.get_weight_names(args.key, e_tag=args.e_tag))


def _cmd_weights_list(_args: argparse.Namespace) -> None:
    """List the weight names for every dataset in the active release."""
    # Always the active release: the library only supports the current one, so
    # the global --release (which is validated) is the single way to choose it.
    _emit(_weights.get_all_weights_for_release())


# --- cache ---


def _cmd_cache_info(args: argparse.Namespace) -> None:
    """Report which releases are cached on disk, and how old each entry is."""
    entries = []
    for release in sorted(_known_releases()):
        path = _metadata_cache_path(release)
        age = _cache_age(path)
        if age is None:
            continue  # Known release, but nothing cached for it yet.
        entries.append(
            {
                "release": release,
                "path": path,
                "age_seconds": int(age),
                "stale": age >= _METADATA_CACHE_TTL_SECONDS,
            }
        )

    if args.json:
        _emit({"cache_dir": _CACHE_DIR, "entries": entries})
        return
    print(f"Cache directory: {_CACHE_DIR}")
    if not entries:
        print("No releases cached.")
        return
    width = max(len(e["release"]) for e in entries)
    for entry in entries:
        state = "stale" if entry["stale"] else "fresh"
        print(f"  {entry['release'].ljust(width)}  {state}, {_format_age(entry['age_seconds'])}")


def _cmd_cache_clear(args: argparse.Namespace) -> None:
    """Delete every cached release, which only ever costs a refetch."""
    removed = []
    # Only ever remove files we know we wrote, never a blind glob of the directory.
    for release in sorted(_known_releases()):
        path = _metadata_cache_path(release)
        try:
            os.remove(path)
        except OSError:
            continue  # Not cached, or already gone: nothing to report.
        removed.append(path)
    if args.json:
        _emit({"removed": removed})
        return
    print(f"Cleared {len(removed)} cached release{'s' if len(removed) != 1 else ''}.")


def _cmd_cache_localize(args: argparse.Namespace) -> None:
    """Rewrite cached URLs to point at local files, for the ones that exist.

    Unlike --local-path, which mirrors the EOS directory structure under the
    given root regardless of what's actually on disk, this keeps files it
    can't find as remote URLs, so a partial local copy still works.
    """
    _metadata.find_all_files(args.path, warnmissing=args.warn_missing)
    release = _metadata.get_current_release()
    _save_metadata_cache(_metadata_cache_path(release))
    if args.json:
        _emit({"localized": args.path, "release": release})
        return
    print(f"Cached metadata for {release} now points at {args.path}.")


# --- env ---


def _cmd_env_install(args: argparse.Namespace) -> None:
    """Install packages at the versions pinned in an environment.yml."""
    _utils.install_from_environment(*args.packages, environment_file=args.environment_file)
    _emit({"installed": list(args.packages) or "all", "environment_file": args.environment_file})


# --- Argument parsing ---
#
# One builder per command group, each taking the shared subparsers object and
# attaching its commands to it. Two flags set via set_defaults() control what
# main() does before dispatching: `loads_metadata` (False for commands that
# touch only local state) and `needs_full` (True for commands that need the
# whole release rather than a single dataset lookup).


def _add_release_commands(sub: _SubParsers) -> None:
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
    p.add_argument(
        "--no-fetch",
        action="store_true",
        help="Save the setting without downloading the release's metadata",
    )
    # A separate dest from the global --local-path: sharing one would let this
    # subparser's default clobber a value given before the subcommand.
    p.add_argument(
        "--local-path",
        dest="set_local_path",
        help=(
            "Remember a local data directory for this release, "
            f"or '{_LOCAL_PATH_EOS}' for native POSIX EOS paths. Pass '' to forget it."
        ),
    )
    p.set_defaults(func=_cmd_release_set)
    group.add_parser("unset", help="Forget the saved release").set_defaults(func=_cmd_release_unset)


def _add_dataset_commands(sub: _SubParsers) -> None:
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
    # default=None, not False: the library distinguishes "caller said no cache"
    # from "caller expressed no preference".
    cache_group = p.add_mutually_exclusive_group()
    cache_group.add_argument("--cache", dest="cache", action="store_true", default=None)
    cache_group.add_argument("--no-cache", dest="cache", action="store_false")
    p.set_defaults(func=_cmd_dataset_urls)

    p = group.add_parser("search", help="Find datasets whose metadata field matches a value")
    p.add_argument("field", help="Metadata field to search, e.g. process")
    p.add_argument(
        "value",
        help=(
            "Value to match, read as JSON where possible: 20000 matches a number, "
            '\'["top","Alternative"]\' requires both, null finds empty fields, '
            "anything else is treated as text. Quote lists so the shell keeps them intact"
        ),
    )
    p.add_argument("--raw", action="store_true", help="Treat the value as plain text, never as JSON")
    p.add_argument("--tolerance", type=float, default=0.01, help="Fractional tolerance for float fields")
    p.set_defaults(func=_cmd_dataset_search, needs_full=True)

    p = group.add_parser("build", help="Build a sample->URLs mapping from a JSON definitions file")
    p.add_argument("definitions", help="JSON file mapping sample names to {'dids': [...], 'color': ...}")
    p.add_argument("--skim", default="noskim", help="Skim type (default: noskim)")
    p.add_argument("--protocol", choices=["root", "https", "eos"], default="https")
    # Here the library's own default is False, so mirror it rather than None.
    cache_group = p.add_mutually_exclusive_group()
    cache_group.add_argument("--cache", dest="cache", action="store_true", default=False)
    cache_group.add_argument("--no-cache", dest="cache", action="store_false")
    p.set_defaults(func=_cmd_dataset_build)


def _add_metadata_commands(sub: _SubParsers) -> None:
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

    # Imports read from a file rather than the API, so no release is loaded first.
    p = group.add_parser("import", help="Load metadata from a file into the local cache")
    p.add_argument("file", help="JSON file previously written by `metadata export`")
    p.add_argument("--as-release", dest="as_release", default="custom", help="Name to store it under")
    p.set_defaults(func=_cmd_metadata_import, loads_metadata=False)


def _add_weights_commands(sub: _SubParsers) -> None:
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

    # Needs the whole release loaded: the library walks available_datasets().
    group.add_parser("list", help="List weight names for every dataset in the active release").set_defaults(
        func=_cmd_weights_list, needs_full=True
    )


def _add_cache_commands(sub: _SubParsers) -> None:
    """`cache` manages the on-disk metadata cache."""
    parser = sub.add_parser("cache", help="Inspect, clear, or localize the metadata cache")
    parser.set_defaults(loads_metadata=False)
    group = parser.add_subparsers(dest="cache_command", required=True)

    group.add_parser("info", help="Show which releases are cached locally").set_defaults(func=_cmd_cache_info)
    group.add_parser("clear", help="Delete all cached release metadata").set_defaults(func=_cmd_cache_clear)

    p = group.add_parser("localize", help="Rewrite cached URLs to point at a local copy of the files")
    p.add_argument("path", help="Root directory holding your local copy of the data")
    p.add_argument("--warn-missing", action="store_true", help="Warn about files not found locally")
    # Overrides the group default: needs the release loaded so the rewritten
    # metadata can be saved back to the cache.
    p.set_defaults(func=_cmd_cache_localize, loads_metadata=True, needs_full=True)


def _add_env_commands(sub: _SubParsers) -> None:
    """`env` covers environment setup helpers."""
    parser = sub.add_parser("env", help="Environment setup helpers")
    parser.set_defaults(loads_metadata=False)
    group = parser.add_subparsers(dest="env_command", required=True)

    p = group.add_parser("install", help="Install packages pinned in an environment.yml")
    p.add_argument("packages", nargs="*", help="Packages to install; omit to install all")
    p.add_argument("--environment-file", dest="environment_file", help="Path or URL to environment.yml")
    p.set_defaults(func=_cmd_env_install)


def _build_parser() -> argparse.ArgumentParser:
    """Build the full parser: global options, then one subparser per command group."""
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
        "--local-path",
        dest="local_path",
        help=(
            "Read data from this directory instead of streaming it, "
            f"or '{_LOCAL_PATH_EOS}' for native POSIX EOS paths. Pass '' to ignore a saved path."
        ),
    )
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
        "--page-size",
        dest="page_size",
        type=int,
        help=f"Datasets to request per API call when fetching a release (default {_DEFAULT_PAGE_SIZE})",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="Skip the PyPI check for a newer atlasopenmagic release",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON from `release show`, `release list` and `cache info` too (other commands always do)",
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


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the `atlasopenmagic` / `atom` console scripts.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:] when omitted.

    Returns:
        A process exit code: 0 on success, 1 if the command failed.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    update_check = _start_update_check(args.no_update_check)

    # Quiet by default, the way a CLI is expected to behave: the library
    # defaults to INFO, which narrates every cache load on stderr.
    _metadata.set_verbosity(args.verbosity or "warning")

    try:
        # Commands that only touch local state skip this entirely, so `release
        # show` and `cache info` stay fast and work offline.
        if args.loads_metadata:
            release, _ = _resolve_release(args.release)
            _apply_release(
                release,
                args.refresh,
                args.needs_full,
                local_path=_resolve_local_path(release, args.local_path),
                page_size=args.page_size,
            )
        args.func(args)
    # Errors are reported as a single line rather than a traceback: a stack
    # trace tells a CLI user nothing they can act on.
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
        # In a finally block so the notice still appears when a command fails.
        _print_update_notice(update_check)

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
