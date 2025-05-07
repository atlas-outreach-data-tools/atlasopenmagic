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

## Open Data functions description and usage 
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

Args:
- `release`: name of the release to use.

**Usage:**
```python
atom.set_release('2024r-pp')
```
### `get_metadata(key, var)`
Get metadata information for MC data.

Args:
- `key`: Dataset ID.
- `var`: Variable to retrieve.

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

### `get_urls(key, skim, protocol)`
Retrieves the list of URLs corresponding to a given key. This is used for MC data.

Args:
- `key`: Dataset ID.
- `skim`: Skim for the dataset. This parameter is only taken into account when using the `2025e-13tev-beta` release.
- `protocol`: protocol for the URLs. Options: 'root' and 'https'.

**Usage:**
```python
urls = atom.get_urls('12345', protocol='root')
```
### `available_data()`
Retrieves the list of keys for the data available for a scope/release.

**Usage:**
```python
atom.available_data()
```
### `get_urls_data(data_key, protocol)`
Retrieves the list of URLs corresponding to one of the keys listed by `available_data()`.

Args:
- `data_key` : For non-beta releases (e.g. '2015', '2016', etc.), the data key to look up.
- `skim` : Only for the 2025e-13tev-beta release: the skim name to look up.

**Usage:**
```python
data = get_urls_data(data_key='2016', protocol='https')
```
## Notebooks utilities description and usage 
### `install_from_environment(*packages, environment_file)`
Install specific packages listed in an `environment.yml` file via pip.

Args:
- `*packages`: Package names to install (e.g., 'coffea', 'dask').
- `environment_file`: Path to the environment.yml file. If None, defaults to [the environment file for the educational resources](https://github.com/atlas-outreach-data-tools/notebooks-collection-opendata/blob/master/binder/environment.yml).

**Usage:**
```python
import atlasopenmagic as atom
atom.install_from_environment("coffea", "pandas", environment_file="./myfile.yml")
```

### `build_mc_dataset(mc_defs, skim='noskim', protocol='https')`
Build a dict of MC samples URLs.
    
Args:
- `mc_defs`: Dictionary with DIDs and optional color: `{ sample_name: {'list': [...urls...], 'color': ...}, … }`
- `skim` : The MC skim tag (only meaningful in the 2025e-13tev-beta release)
- `protocol` : Protocol to use for URLs.

**Usage:**
```python
import atlasopenmagic as atom
mc_defs = {
    r'Background $t\bar t$':    {'dids': [410470],                      'color': 'yellow'},
    r'Background $V+$jets':     {'dids': [700335,700336,700337],        'color': 'orange'},
    r'Background Diboson':      {'dids': [700488,700489,700490,700491],'color': 'green'},
    r'Background $ZZ^{*}$':     {'dids': [700600,700601],               'color': '#ff0000'},
    r'Signal ($m_H$=125 GeV)':  {'dids': [345060,346228],              'color': '#00cdff'},
}

mc_samples = build_mc_dataset(mc_defs, skim='2bjets', protocol='https')
```

### `build_data_dataset(data_keys, name="Data", color=None, protocol="https")`
Build a dict of Data samples URLS.

Args:
- `data_keys`: The data_key(s) to fetch (e.g. '2015' or ['2015','2016']).
- `name`: The key under which the sample appears in the returned dict.
- `color`: A color string to attach to the sample.
- `protocol` : Protocol to use for URLs.

**Usage:**
```python
import atlasopenmagic as atom

data_samples = build_data_samples("2bjets", name="Data", color="red", protocol="root")
```

## Contributing
Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature-name`).
5. Create a Pull Request.

Please ensure all tests pass before submitting a pull request (just run `pytest` from the main directory of the package).

## License
This project is licensed under the [Apache 2.0 License](https://github.com/atlas-outreach-data-tools/atlasopenmagic/blob/main/LICENSE)
