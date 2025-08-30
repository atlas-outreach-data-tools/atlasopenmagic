"""This module provides utility functions for the atlasopenmagic package.

It includes functions to install packages from an environment file
and to build datasets from sample definitions.
"""


import io
import re
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any, Optional

import requests
import yaml

from atlasopenmagic.metadata import get_urls


def install_from_environment(
    *packages: Optional[str], environment_file: Optional[str] = None
) -> None:  # pragma: no cover
    """Install specific packages listed in an environment.yml file via pip.

    Args:
        *packages: Package names to install (e.g., 'coffea', 'dask').
            If empty, all packages in the environment.yml will be installed.
        environment_file: Path to the environment.yml file.
            If None, defaults to the environment.yml file contained in our notebooks repository.

    Raises:
        FileNotFoundError: If the environment file is not found at the specified path.
        ValueError: If the environment file cannot be fetched from URL or has malformed structure.
    """
    if environment_file is None:
        environment_file = "https://raw.githubusercontent.com/atlas-outreach-data-tools/notebooks-collection-opendata/refs/heads/master/binder/environment.yml"

    is_url = str(environment_file).startswith("http")
    environment_file = Path(environment_file) if not is_url else environment_file

    if not is_url:
        if not environment_file.exists():
            raise FileNotFoundError(f"Environment file not found at {environment_file}")
        with environment_file.open("r", encoding="utf-8") as file:
            environment_data = yaml.safe_load(file)
    else:
        response = requests.get(environment_file, timeout=100)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch environment file from URL: {environment_file}")
        environment_data = yaml.safe_load(io.StringIO(response.text))

    dependencies = environment_data.get("dependencies", None)

    if dependencies is None:
        raise ValueError(
            f"The environment.yml at {environment_file} is missing a 'dependencies:' section.\n\n"
            "Expected structure:\n"
            "---------------------\n"
            "name: myenv\n"
            "channels:\n"
            "  - conda-forge\n"
            "dependencies:\n"
            "  - python=3.11\n"
            "  - pip:\n"
            "    - mypippackage>=1.0.0\n"
            "---------------------\n"
        )

    conda_packages = []
    pip_packages = []

    if not packages:
        for dep in dependencies:
            if isinstance(dep, str):
                conda_packages.append(dep)
            elif isinstance(dep, dict) and "pip" in dep:
                pip_list = dep["pip"]
                if not isinstance(pip_list, list):
                    raise ValueError(
                        f"Malformed 'pip:' section in {environment_file}.\n\n"
                        "Expected structure:\n"
                        "---------------------\n"
                        "dependencies:\n"
                        "  - pip:\n"
                        "    - package1>=1.0\n"
                        "    - package2>=2.0\n"
                        "---------------------\n"
                    )
                pip_packages.extend(pip_list)
    else:
        for dep in dependencies:
            if isinstance(dep, str):
                for pkg in packages:
                    # Match the package name at the beginning of the string;
                    # this avoids to match two different packages with the same
                    # initial name (e.g. torch, tochvision)
                    base_dep = re.split(r"[=<>]", dep, maxsplit=1)[0]
                    if base_dep == pkg:
                        conda_packages.append(dep)
            elif isinstance(dep, dict):
                if "pip" in dep:
                    pip_list = dep["pip"]
                    if not isinstance(pip_list, list):
                        raise ValueError(
                            f"Malformed 'pip:' section in {environment_file}.\n\n"
                            "Expected structure:\n"
                            "---------------------\n"
                            "dependencies:\n"
                            "  - pip:\n"
                            "    - package1>=1.0\n"
                            "    - package2>=2.0\n"
                            "---------------------\n"
                        )
                    for pip_dep in pip_list:
                        for pkg in packages:
                            if pip_dep.startswith(pkg):
                                pip_packages.append(pip_dep)

    # all_packages = conda_packages + pip_packages
    # Temporarily only install pip packages, to be decided later whether to
    # install conda packages and how
    all_packages = pip_packages

    if all_packages:
        print(f"Installing packages: {all_packages}")

        # Detect if inside a virtualenv and remove the --user flag if so
        in_venv = hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)

        pip_command = [sys.executable, "-m", "pip", "install", "--upgrade"]
        if not in_venv:
            pip_command.append("--user")

        pip_command += all_packages

        subprocess.run(pip_command, check=True)
        print(
            "Installation complete. "
            "You may need to restart your Python environment for changes to take effect."
        )
    else:
        raise ValueError(
            f"No matching packages found for {packages} in {environment_file}.\n\n"
            "Make sure the package names exactly match the beginning of the package entries in the file.\n"
        )


def build_dataset(
    samples_defs: dict[str, dict[str, Any]],
    skim: str = "noskim",
    protocol: str = "https",
    cache: Optional[bool] = False,
) -> dict[str, dict]:
    r"""Build a dict of MC samples URLs.

    Args:
        samples_defs: The datasets to be built up with their definitions and
            colors. See examples for more info.
        skim: The desired skim type. Defaults to 'noskim' for the base,
            unfiltered dataset. Other examples: 'exactly4lep', '3lep'.
        protocol: The desired URL protocol. Can be 'root', 'https', or 'eos'.
            Defaults to 'https'.
        cache: Use the simplecache mechanism of fsspec to locally cache
            files instead of streaming them. Default False means let
            atlasopenmagic decide what to do for that protocol.
    Example:
    ```python
    import atlasopenmagic as atom
    atom.set_release('2025e-13tev-beta')
    samples_defs = {
        r'Data':                    {'dids': ["data"],                      'color': 'red'},
        r'Background $t\bar t$':    {'dids': [410470],                      'color': 'yellow'},
        r'Background $V+$jets':     {'dids': [700335,700336,700337],        'color': 'orange'},
        r'Background Diboson':      {'dids': [700488,700489,700490,700491],'color': 'green'},
        r'Background $ZZ^{*}$':     {'dids': [700600,700601],               'color': '#ff0000'},
        r'Signal ($m_H$=125 GeV)':  {'dids': [345060,346228],              'color': '#00cdff'},
    }
    ```

    Returns:
        A dictionary containing sample names as keys and dictionaries with 'list' of URLs
        and optional 'color' as values.
    """
    out = {}
    for name, info in samples_defs.items():
        urls = []
        for did in info["dids"]:
            urls.extend(get_urls(str(did), skim=skim, protocol=protocol, cache=cache))
        sample = {"list": urls}
        if "color" in info:
            sample["color"] = info["color"]
        out[name] = sample
    return out


def build_data_dataset(
    data_keys: list[str],
    name: str = "Data",
    color: Optional[str] = None,
    protocol: str = "https",
    cache: Optional[bool] = None,
) -> dict[str, dict]:
    """Build a dataset for data samples.

    Note:
        This function is deprecated and will be removed in future versions.
        Use build_dataset with the appropriate data definitions instead.

    Args:
        data_keys: List of data keys to be included in the dataset.
        name: Name of the dataset. Defaults to "Data".
        color: Color associated with the dataset. Defaults to None.
        protocol: Protocol for the URLs. Defaults to "https".
        cache: Use caching for file access. Default None means let
            atlasopenmagic decide what to do for that protocol.

    Returns:
        A dictionary containing the dataset with URLs and optional color information.
    """
    warnings.warn(
        "The build_data_dataset function is deprecated. "
        "Use build_dataset with the appropriate data definitions instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_dataset(
        {name: {"dids": ["data"], "color": color}},
        skim=data_keys,
        protocol=protocol,
        cache=cache,
    )


def build_mc_dataset(
    mc_defs: dict[str, dict],
    skim: str = "noskim",
    protocol: str = "https",
    cache: Optional[bool] = None,
) -> dict[str, dict]:
    """Build a dict of MC samples URLs.

    Note:
        This function is deprecated and will be removed in future versions.
        Use build_dataset with the appropriate MC definitions instead.

    Args:
        mc_defs: The MC datasets to be built up with their definitions and colors.
            See examples for more info.
        skim: The desired skim type. Defaults to 'noskim' for the base,
            unfiltered dataset. Other examples: 'exactly4lep', '3lep'.
        protocol: The desired URL protocol. Can be 'root', 'https', or 'eos'.
            Defaults to 'https'.
        cache: Use the simplecache mechanism of fsspec to locally cache
            files instead of streaming them. Default None means let
            atlasopenmagic decide what to do for that protocol.

    Returns:
        A dictionary containing MC sample names as keys and dictionaries with 'list' of URLs
        and optional 'color' as values.
    """
    warnings.warn(
        "The build_mc_dataset function is deprecated. "
        "Use build_dataset with the appropriate MC definitions instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_dataset(mc_defs, skim=skim, protocol=protocol, cache=cache)
