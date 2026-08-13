"""Command-line interface for atlasopenmagic.

Installed as both `atlasopenmagic` and `atom`. Wraps the read/query
functions of the Python API (datasets, metadata, URLs, weights) so they
can be used from shell scripts and other non-Python tooling. Output is
JSON on stdout so it composes with tools like `jq`; informational
messages (including the update notice) go to stderr.
"""

import argparse
import json
import os
import sys
import threading
import time
from importlib.metadata import PackageNotFoundError, version

import requests

from . import metadata as _metadata
from . import weights as _weights

_PACKAGE_NAME = "atlasopenmagic"
_PYPI_URL = f"https://pypi.org/pypi/{_PACKAGE_NAME}/json"
_CACHE_PATH = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "atlasopenmagic",
    "update_check.json",
)
_CHECK_INTERVAL_SECONDS = 24 * 3600


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


# --- Output helpers ---


def _emit(data):
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


# --- Command implementations ---


def _cmd_releases(_args):
    _emit(_metadata.RELEASES_DESC)


def _cmd_current_release(_args):
    _emit(_metadata.get_current_release())


def _cmd_datasets(_args):
    _emit(_metadata.available_datasets())


def _cmd_skims(_args):
    _emit(_metadata.available_skims())


def _cmd_keywords(_args):
    _emit(_metadata.available_keywords())


def _cmd_fields(_args):
    _emit(_metadata.get_metadata_fields())


def _cmd_metadata(args):
    if args.full:
        _emit(_metadata.get_all_info(args.key, args.field))
    else:
        _emit(_metadata.get_metadata(args.key, args.field))


def _cmd_urls(args):
    _emit(_metadata.get_urls(args.key, skim=args.skim, protocol=args.protocol, cache=args.cache))


def _cmd_search(args):
    _emit(_metadata.match_metadata(args.field, args.value, float_tolerance=args.tolerance))


def _cmd_weights(args):
    _emit(_weights.get_weights(args.key, e_tag=args.e_tag))


def _cmd_weight_names(args):
    _emit(_weights.get_weight_names(args.key, e_tag=args.e_tag))


def _cmd_all_weights(args):
    _emit(_weights.get_all_weights_for_release(release_name=args.for_release))


# --- Argument parsing ---


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
    parser.add_argument("--release", help="Data release to use for this command (e.g. 2024r-pp)")
    parser.add_argument(
        "--verbosity",
        choices=["error", "warning", "info", "debug"],
        help="Log verbosity for the underlying API calls",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="Skip the PyPI check for a newer atlasopenmagic release",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("releases", help="List available data releases").set_defaults(func=_cmd_releases)
    sub.add_parser("current-release", help="Show the active data release").set_defaults(
        func=_cmd_current_release
    )
    sub.add_parser("datasets", help="List dataset IDs for the active release").set_defaults(func=_cmd_datasets)
    sub.add_parser("skims", help="List available skims for the active release").set_defaults(func=_cmd_skims)
    sub.add_parser("keywords", help="List available keywords for the active release").set_defaults(
        func=_cmd_keywords
    )
    sub.add_parser("fields", help="List available metadata fields for the active release").set_defaults(
        func=_cmd_fields
    )

    p = sub.add_parser("metadata", help="Show metadata for a dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--field", help="Return only this metadata field")
    p.add_argument("--full", action="store_true", help="Include file_list and skims")
    p.set_defaults(func=_cmd_metadata)

    p = sub.add_parser("urls", help="Get file URLs for a dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--skim", default="noskim", help="Skim type (default: noskim)")
    p.add_argument("--protocol", choices=["root", "https", "eos"], default="root")
    cache_group = p.add_mutually_exclusive_group()
    cache_group.add_argument("--cache", dest="cache", action="store_true", default=None)
    cache_group.add_argument("--no-cache", dest="cache", action="store_false")
    p.set_defaults(func=_cmd_urls)

    p = sub.add_parser("search", help="Find datasets by metadata field/value")
    p.add_argument("field", help="Metadata field to search, e.g. process")
    p.add_argument("value", help="Value to match")
    p.add_argument("--tolerance", type=float, default=0.01, help="Fractional tolerance for float fields")
    p.set_defaults(func=_cmd_search)

    p = sub.add_parser("weights", help="Get MC weight metadata for a dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--e-tag", dest="e_tag")
    p.set_defaults(func=_cmd_weights)

    p = sub.add_parser("weight-names", help="List MC weight names for a dataset")
    p.add_argument("key", help="Dataset number or physics_short name")
    p.add_argument("--e-tag", dest="e_tag")
    p.set_defaults(func=_cmd_weight_names)

    p = sub.add_parser("all-weights", help="List weight names for every dataset in a release")
    p.add_argument("--for-release", dest="for_release", help="Defaults to the active release")
    p.set_defaults(func=_cmd_all_weights)

    return parser


def main(argv=None) -> int:
    """Entry point for the `atlasopenmagic` / `atom` console scripts."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    update_check = _start_update_check(args.no_update_check)

    if args.verbosity:
        _metadata.set_verbosity(args.verbosity)
    if args.release:
        _metadata.set_release(args.release)

    try:
        args.func(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 1
    finally:
        _print_update_notice(update_check)

    return 0


if __name__ == "__main__":
    sys.exit(main())
