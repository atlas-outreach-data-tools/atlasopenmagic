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
### `set_release(release, local_path)`
Set the release (scope) in which to look for information (research open data, education 8 TeV, et). The `release` passed to the function has to be one of the keys listed by `available_releases()`. If a release has been downloaded locally, it is possible to use `local_path` to point `atlasopenmagic` towards the location of the datasets to use. Files are expected to be in a single directory. Metadata will be still retrieved remotely.

Additionally, if your facility mounts or mirrors [EOS public](https://eos-docs.web.cern.ch/diopside/) as a local filesystem, you can provide "eos" as the local_path. In this case, files will be accessed using the native POSIX path

Args:
- `release`: name of the release to use.
- `local_path`: local directory path to use for downloaded datasets.
            If provided, the client will assume that datasets are available locally
            at this path. If `'eos'` is provided, the original folder structure for the paths is kept.

**Usage (remote storage):**
```python
atom.set_release('2024r-pp')
```

**Usage (local storage):**
```python
atom.set_release('2024r-pp', local_path='/myproject/opendata/2024r-pp')
```
### `get_all_info(key, var)`
Retrieves all the information for a given dataset, identified by its number or physics short name.

Args:
- `key`: The dataset identifier (e.g., '301204').
- `var`: A specific metadata field to retrieve. If None, the entire metadata dictionary is returned.

**Usage:**
You can get a dictionary with all the metadata
```python
metadata = atom.get_metadata('301209')
```
Or a single variable
```python
xsec = atom.get_metadata('301209', 'cross_section')
```
The available variables are: `dataset_number`, `physics_short`, `e_tag`, `cross_section_pb`, `genFiltEff`, `kFactor`, `nEvents`, `sumOfWeights`, `sumOfWeightsSquared`, `process`, `generator`, `keywords`, `file_list`, `description`, `job_path`, `CoMEnergy`, `GenEvents`, `GenTune`, `PDF`, `Release`, `Filters`, `release`, `skims`.

The keys to be used for research data are the Dataset IDs found in the [Monte Carlo Metadata](https://opendata.atlas.cern/docs/data/for_research/metadata)

### `find_all_files(local_path, warnmissing=False)`
Replace cached remote URLs in `_metadata` with corresponding local file paths if those files exist in the given `local_path`.

This function only affects the currently active release, and requires `_metadata` to be populated (it will trigger a fetch automatically).

Args:
- `local_path (str)`: Root directory of your local dataset copy. Can have any internal subdirectory structure; only filenames are used for matching.

- `warnmissing (bool, optional, default=False)`: If True, issue a `UserWarning` for every file that is in metadata but not found locally.

### `get_metadata(key, var)`
Retrieves the metadata (no file lists) for a given MC dataset.

Args:
- `key`: The dataset identifier (e.g., '301204').
- `var`: A specific metadata field to retrieve. If None, the entire metadata dictionary is returned.

**Usage:**
You can get a dictionary with all the metadata
```python
metadata = atom.get_metadata('301209')
```
Or a single variable
```python
xsec = atom.get_metadata('301209', 'cross_section')
```
The available variables are: `dataset_number`, `physics_short`, `e_tag`, `cross_section_pb`, `genFiltEff`, `kFactor`, `nEvents`, `sumOfWeights`, `sumOfWeightsSquared`, `process`, `generator`, `keywords`, `description`, `job_path`, `CoMEnergy`, `GenEvents`, `GenTune`, `PDF`, `Release`, `Filters`, `release`.

The keys to be used for research data are the Dataset IDs found in the [Monte Carlo Metadata](https://opendata.atlas.cern/docs/data/for_research/metadata)

### `get_urls(key, skim, protocol, cache)`
Retrieves the list of URLs corresponding to a given key.

Args:
- `key`: Dataset ID.
- `skim`: Skim for the dataset. This parameter is only taken into account when using the `2025e-13tev-beta` release.
- `protocol`: protocol for the URLs. Options: 'root' and 'https'.
- `cache`: use the `simplecache` mechanism of `fsspec` to locally cache files instead of streaming them.

**Usage:**
```python
urls = atom.get_urls('12345', protocol='root', cache=True)
```
### `available_data()`
Retrieves the list of keys for the data available for a scope/release.

**Usage:**
```python
atom.available_data()
```
### ❗**DEPRECATED** `get_urls_data(data_key, protocol)`
  
*Please use `get_urls(key, skim='noskim', protocol=protocol, cache=False)` instead.*

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

### `build_dataset(samples_defs, skim='noskim', protocol='https', cache=False)`
Build a dict of data and / or MC samples URLs.
    
Args:
- `samples_defs`: Dictionary with DIDs and optional color: `{ sample_name: {'list': [...urls...], 'color': ...}, … }`
- `skim` : The MC skim tag (only meaningful in the 2025e-13tev-beta release)
- `protocol` : Protocol to use for URLs.
- `cache`: use the `simplecache` mechanism of `fsspec` to locally cache files instead of streaming them.

**Usage:**
```python
import atlasopenmagic as atom
atom.set_release('2025e-13tev-beta')
samples_defs = {
    r'Data':                    {'dids': ["data"],                      'color': 'red'},
    r'Background $t\bar t$':    {'dids': [410470],                      'color': 'yellow'},
    r'Background $V+$jets':     {'dids': [700335,700336,700337],        'color': 'orange'},
    r'Background Diboson':      {'dids': [700488,700489,700490,700491],'color': 'green'},
    r'Background $ZZ^{*}$':     {'dids': [700600,700601],               'color': '#ff0000'},
    r'Signal ($m_H$=125 GeV)':  {'dids': [345060,346228],              'color': '#00cdff'},
}

mc_samples = atom.build_dataset(samples_defs, skim='2bjets', protocol='https', cache=True)
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
