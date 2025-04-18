# Atlas Open Magic 🪄📊
[![Tests](https://github.com/atlas-outreach-data-tools/atlasopenmagic/actions/workflows/test.yml/badge.svg)](https://github.com/atlas-outreach-data-tools/atlasopenmagic/actions/workflows/test.yml)
![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fatlas-outreach-data-tools%2Fatlasopenmagic%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.version&label=pypi)


**Atlas Open Magic** is a Python package made to simplify working with ATLAS Open Data by providing utilities to manage metadata and URLs for streaming the data.

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
all_mc = atom.get_urls('2016')
```

## Functions description and usage 
### `available_releases()`
Shows the available open data releases keys and descriptions.

**Usage:**
```python
import atlasopenmagic as atom
atom.available_releases()
```
### `get_current_release()`
Retrieves the release that the package is currently set at.

**Usage:**
```python
release = atom.get_current_release()
print(release)
```
### `set_release(release)`
Set the release (scope) in which to look for information (research open data, education 8 TeV, et). The `release` passed to the function has to be one of the keys listed by `available_releases()`.

**Usage:**
```python
atom.set_release('2024r-pp')
```
### `get_metadata(key, *var)`
Get metadata information for MC data.

**Usage:**
You can get a dictionary with all the metadata
```python
metadata = atom.get_metadata('301209')
```
Or a single variable
```python
xsec = atom.get_metadata('301209', 'cross_section')
```
The available variables are: `dataset_id`, `short_name`, `e-tag`, `cross_section`, `filter_efficiency`, `k_factor`, `number_events`, `sum_weights`, `sum_weights_squared`, `process`, `generators`, `keywords`, `description`, `job_link`.

The keys to be used for research data are the Dataset IDs found in the [Monte Carlo Metadata](https://opendata.atlas.cern/docs/data/for_research/metadata)

### `get_urls(key)`
Retrieves the list of URLs corresponding to a given key. This is used for MC data.

**Usage:**
```python
urls = atom.get_urls('12345')
```
### `available_data()`
Retrieves the list of keys for the data available for a scope.

**Usage:**
```python
atom.available_data()
```
### `get_urls_data(data_key)`
Retrieves the list of URLs corresponding to one of the keys listed by `available_data()`.

**Usage:**
```python
data = get_urls_data('2016')
```

## Contributing
Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature-name`).
5. Create a Pull Request.

Please ensure all tests pass before submitting a pull request.

## License
This project is licensed under the [Apache 2.0 License](https://github.com/atlas-outreach-data-tools/atlasopenmagic/blob/main/LICENSE)
