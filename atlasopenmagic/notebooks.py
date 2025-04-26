import yaml
import subprocess
import sys
from pathlib import Path

def install_from_environment(*packages, environment_file=None):
    """
    Install specific packages listed in an environment.yml file via pip.

    Args:
        *packages: Package names to install (e.g., 'coffea', 'dask').
        environment_file: Path to the environment.yml file. If None, defaults to "../../binder/environment.yml".
    """
    if environment_file is None:
        environment_file = "../../binder/environment.yml"

    environment_file = Path(environment_file)

    if not environment_file.exists():
        raise FileNotFoundError(f"Environment file not found at {environment_file}")

    with environment_file.open('r') as file:
        environment_data = yaml.safe_load(file)

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

    for dep in dependencies:
        if isinstance(dep, str):
            for pkg in packages:
                if dep.startswith(pkg):
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

    all_packages = conda_packages + pip_packages

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
