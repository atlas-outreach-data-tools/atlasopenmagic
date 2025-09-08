# ATLAS Open Magic 🪄📊
[![Tests](https://github.com/atlas-outreach-data-tools/atlasopenmagic/actions/workflows/test.yml/badge.svg)](https://github.com/atlas-outreach-data-tools/atlasopenmagic/actions/workflows/test.yml)
![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fatlas-outreach-data-tools%2Fatlasopenmagic%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.version&label=pypi)
[![codecov](https://codecov.io/gh/atlas-outreach-data-tools/atlasopenmagic/graph/badge.svg?token=CNTZ8AEHIG)](https://codecov.io/gh/atlas-outreach-data-tools/atlasopenmagic)


**`atlasopenmagic`** is a Python package made to simplify working with ATLAS Open Data by providing utilities to manage metadata and URLs for streaming the data.

### Key Features:
- Simple functions to set the active data release (e.g., `2024r-pp`).
- Efficient local caching of metadata to minimize API calls.
- Helper functions to retrieve specific dataset information, including file URLs for different "skims" (filtered versions of datasets).
- Support for multiple URL protocols (root, https, eos).
- Configuration via environment variables for easy integration into different workflows.

## **Installation**
You can install this package using `pip`.

```bash
pip install atlasopenmagic
```
Alternatively, clone the repository and install locally:
```bash
git clone https://github.com/atlas-outreach-data-tools/atlasopenmagic.git
cd atlasopenmagic
pip install .
```

## Documentation
You can find the full documentation for ATLAS Open Magic in the [ATLAS Open Data website](https://opendata.atlas.cern/docs/atlasopenmagic).

## Quick start
First, import the package:
```python
import atlasopenmagic as atom
```
See the available releases and set to one of the options given by `available_releases()`
```python
atom.available_releases()
set_release('2024r-pp')
```
Check in the [Monte Carlo Metadata](https://opendata.atlas.cern/docs/data/for_research/metadata) which datasets do you want to retrieve and use the 'Dataset ID'. For example, to get the metadata from *Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000*:
```python
all_metadata = atom.get_metadata('301204')
```
If we only want a specific variable:
```python
xsec = atom.get_metadata('301204', 'cross_section')
```
To get the URLs to stream the files for that MC dataset:
```python
all_mc = atom.get_urls('301204')
```
To get some data instead, check the available options:
```python
atom.available_data()
```
And get the URLs for the one that's to be used:
```python
all_mc = atom.get_urls('data')
```


## Contributing
Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature-name`).
5. Create a Pull Request.

Please ensure all tests pass before submitting a pull request (just run `pytest` from the main directory of the package).

Developers can also `pip install` including additional tools required for testing:
```bash
pip install atlasopenmagic[dev]
```
or with a local copy of the repository:
```bash
pip install '.[dev]'
```

### Pre-commit Hooks

We use pre-commit hooks, find below how to use them.

#### Installation

1. Install the `[dev]` dependencies if you haven't already, as shown above.

2. Install the git hook scripts:

```sh
pre-commit install
```

3. (Optional) Run against all files:

```sh
pre-commit run --all-files
```

#### What the hooks do

- **black**: Formats Python code consistently
- **isort**: Sorts imports alphabetically and separates them into sections
- **ruff**: Fast Python linter that catches common errors and style issues
- **codespell**: Checks for common misspellings in code and comments
- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with a newline
- **pydocstyle**: Checks docstring style (Google convention)

The hooks will run automatically on `git commit`.
If any hook fails, the commit will be blocked until the issues are fixed.

## License
This project is licensed under the [Apache 2.0 License](https://github.com/atlas-outreach-data-tools/atlasopenmagic/blob/main/LICENSE)
