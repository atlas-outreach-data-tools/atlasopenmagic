import yaml
import subprocess
import sys
import requests, io, re
from pathlib import Path
from atlasopenmagic.metadata import get_urls, get_urls_data

def install_from_environment(*packages, environment_file=None):
    """
    Install specific packages listed in an environment.yml file via pip.

    Args:
        *packages: Package names to install (e.g., 'coffea', 'dask'). if empty, all packages in the environment.yml will be installed.
        environment_file: Path to the environment.yml file. If None, defaults to the environment.yml file contained in our notebooks repository.
    """
    if environment_file is None:
        environment_file = "https://raw.githubusercontent.com/atlas-outreach-data-tools/notebooks-collection-opendata/refs/heads/master/binder/environment.yml"

    is_url = str(environment_file).startswith("http")
    environment_file = Path(environment_file) if not is_url else environment_file

    if not is_url:
        if not environment_file.exists():
            raise FileNotFoundError(f"Environment file not found at {environment_file}")
        with environment_file.open('r') as file:
            environment_data = yaml.safe_load(file)
    else:
        response = requests.get(environment_file)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch environment file from URL: {environment_file}")
        environment_data = yaml.safe_load(io.StringIO(response.text))

    dependencies = environment_data.get('dependencies', None)

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
            elif isinstance(dep, dict) and 'pip' in dep:
                pip_list = dep['pip']
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
                    # Match the package name at the beginning of the string; this avoids to match two different packages with the same initial name (e.g. torch, tochvision)
                    base_dep = re.split(r'[=<>]', dep, 1)[0]
                    if base_dep == pkg:
                        conda_packages.append(dep)
            elif isinstance(dep, dict):
                if 'pip' in dep:
                    pip_list = dep['pip']
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
    # Temporarily only install pip packages, to be decided later whether to install conda packages and how
    all_packages = pip_packages

    if all_packages:
        print(f"Installing packages: {all_packages}")

        # Detect if inside a virtualenv and remove the --user flag if so
        in_venv = (
            hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        )

        pip_command = [sys.executable, "-m", "pip", "install", "--upgrade"]
        if not in_venv:
            pip_command.append("--user")

        pip_command += all_packages

        subprocess.run(pip_command, check=True)
    else:
        raise ValueError(
            f"No matching packages found for {packages} in {environment_file}.\n\n"
            "Make sure the package names exactly match the beginning of the package entries in the file.\n"
        )

def build_mc_dataset(mc_defs, skim='noskim', protocol='https'):
    """
    Build a dict of MC samples URLs.
    """
    out = {}
    for name, info in mc_defs.items():
        urls = []
        for did in info['dids']:
            urls.extend(get_urls(str(did), skim=skim, protocol=protocol))
        sample = {'list': urls}
        if 'color' in info:
            sample['color'] = info['color']
        out[name] = sample
    return out

def build_data_dataset(data_keys, name="Data", color=None, protocol="https"):
    """
    Retrieve and group one or more detector data‐keys under a single sample.
    """
    if isinstance(data_keys, str):
        data_keys = [data_keys]

    # Gather all URLs
    urls = []
    for key in data_keys:
        urls.extend(get_urls_data(key, protocol=protocol))

    # Build the single‐sample dict
    sample = {"list": urls}
    if color is not None:
        sample["color"] = color

    return {name: sample}