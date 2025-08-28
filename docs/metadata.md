<!-- markdownlint-disable -->

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metadata`
ATLAS Open Data Magic Client. 

This script provides a user-friendly Python client to interact with the ATLAS Open Magic REST API. It simplifies the process of fetching metadata and file URLs for various datasets and releases from the ATLAS Open Data project. 



**Example:**
 ```
import atlasopenmagic as atom

# Set the desired release
atom.set_release('2025e-13tev-beta')

# Get metadata for a specific dataset
metadata = atom.get_metadata('301204')

# Get the file URLs for the 'exactly4lep' skim of that dataset
urls = atom.get_urls('301204', skim='exactly4lep')
print(urls)
``` 

**Global Variables**
---------------
- **current_release**
- **API_BASE_URL**
- **current_local_path**
- **RELEASES_DESC**
- **AVAILABLE_FIELDS**

---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L193"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `available_releases`

```python
available_releases() → dict[str, tuple[str]]
```

Display a list of all available data releases and their descriptions. 

This function prints directly to the console for easy inspection with clean, aligned formatting. 



**Returns:**
  A dictionary mapping release names to their description tuples. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L213"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_current_release`

```python
get_current_release() → str
```

Return the name of the currently active data release. 



**Returns:**
  The name of the current release (e.g., '2024r-pp'). 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L247"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `set_release`

```python
set_release(release: str, local_path: Optional[str] = None) → None
```

Set the active data release for all subsequent API calls. 

Changing the release will clear the local metadata cache, forcing a re-fetch of data from the API upon the next request. 



**Args:**
 
 - <b>`release`</b>:  The name of the release to set as active. 
 - <b>`local_path`</b>:  A local directory path to use for caching dataset files.  If provided, the client will assume that datasets are available locally  at this path. Provide "eos" as the local_path to access using the native POSIX. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the provided release name is not valid. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L290"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `find_all_files`

```python
find_all_files(local_path: str, warnmissing: bool = False) → None
```

Replace cached remote URLs with corresponding local file paths if files exist locally. 

This function only affects the currently active release, and requires `_metadata` to be populated (it will trigger a fetch automatically). 

Workflow:  1. Walk the given `local_path` once and build a lookup dictionary of available files.  The lookup is keyed only by filename (basename), so this assumes filenames are unique.  2. For every dataset in the current release cache: 
       - Replace each file URL with its local path if the corresponding file exists locally. 
       - For files missing locally, keep the remote URL and optionally emit a warning.  3. This is done both for the main `file_list` and for each skim's `file_list`. 



**Args:**
 
 - <b>`local_path`</b>:  Root directory of your local dataset copy. Can have any internal subdirectory  structure; only filenames are used for matching. 
 - <b>`warnmissing`</b>:  If True, issue a `UserWarning` for every file that is in metadata but  not found locally. 



**Note:**

> - Matching is based on filename only, not relative EOS path. - If you have multiple files with the same name in different datasets, the first one found in `os.walk()` will be used for replacement. - This modifies `_metadata` in place for the current session. - After running this, any `get_urls()` call will return local paths where available, otherwise the original remote URLs. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L388"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_all_info`

```python
get_all_info(key: str, var: Optional[str] = None) → Any
```

Retrieve all the information for a given dataset. 

If the cache is empty for the current release, this function will trigger a fetch from the API to populate it. 



**Args:**
 
 - <b>`key`</b>:  The dataset identifier (e.g., '301204'). 
 - <b>`var`</b>:  A specific metadata field to retrieve.  If None, the entire metadata dictionary is returned.  Supports old and new field names. 



**Returns:**
 The full info dictionary for the dataset, or the value of the single field if 'var' was specified. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the dataset key or the specified variable field is not found. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L438"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_metadata`

```python
get_metadata(key: str, var: Optional[str] = None) → Any
```

Retrieve the metadata (no file lists) for a given dataset. 

Dataset is identified by its number or physics short name. If the cache is empty for the current release, this function will trigger a fetch from the API to populate it. 



**Args:**
 
 - <b>`key`</b>:  The dataset identifier (e.g., '301204'). 
 - <b>`var`</b>:  A specific metadata field to retrieve. If None, the entire  metadata dictionary is returned. Supports old and new field names. 



**Returns:**
 The full metadata dictionary for the dataset, or the value of the single field if 'var' was specified. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the dataset key or the specified variable field is not found. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L463"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_urls`

```python
get_urls(
    key: str,
    skim: str = 'noskim',
    protocol: str = 'root',
    cache: Optional[bool] = None
) → list[str]
```

Retrieve file URLs for a given dataset, with options for skims and protocols. 

This function correctly interprets the structured skim data from the API. 



**Args:**
 
 - <b>`key`</b>:  The dataset identifier. 
 - <b>`skim`</b>:  The desired skim type. Defaults to 'noskim' for the base, 
 - <b>`unfiltered dataset. Other examples`</b>:  'exactly4lep', '3lep'. 
 - <b>`protocol`</b>:  The desired URL protocol. Can be 'root', 'https', or 'eos'.  Defaults to 'root'. 
 - <b>`cache`</b>:  Use the simplecache mechanism of fsspec to locally cache  files instead of streaming them. Default True for https,  False for root protocol. 



**Returns:**
 A list of file URLs matching the criteria. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the requested skim or protocol is not available for the dataset. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L534"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `available_datasets`

```python
available_datasets() → list[str]
```

Return a sorted list of all available dataset numbers for the current release. 



**Returns:**
  A sorted list of dataset numbers as strings. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L549"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_all_metadata`

```python
get_all_metadata() → dict[str, dict]
```

Return the entire metadata dictionary, en mass. 



**Returns:**
  The metadata dictionary. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L562"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `empty_metadata`

```python
empty_metadata() → None
```

Internal helper function to empty the metadata cache and leave it empty. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L574"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `available_keywords`

```python
available_keywords() → list[str]
```

Return a sorted list of available keywords in use in the current release. 



**Returns:**
  A sorted list of keywords as strings. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L594"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `match_metadata`

```python
match_metadata(
    field: str,
    value: Any,
    float_tolerance: float = 0.01
) → list[tuple[str, str]]
```

Return a sorted list of datasets with metadata field matching value. 



**Args:**
 
 - <b>`field`</b>:  The metadata field to search. 
 - <b>`value`</b>:  The value to search for. 
 - <b>`float_tolerance`</b>:  The fractional tolerance for floating point number matches. 



**Returns:**
 A sorted list of matching datasets as tuples of (dataset_id, physics_short). 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L646"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `save_metadata`

```python
save_metadata(file_name: str = 'metadata.json') → None
```

Save the metadata in an output file. 

Attempts to adjust the output based on the file extension, currently supporting txt and json. Loads the metadata if it is currently empty. 



**Args:**
 
 - <b>`file_name`</b>:  The name of the file to save the metadata to, with full path and extension. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the requested file type is not supported. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L691"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `read_metadata`

```python
read_metadata(file_name: str = 'metadata.json', release: str = 'custom') → None
```

Read the metadata from an input file. 

Overwrites existing metadata. 



**Args:**
 
 - <b>`file_name`</b>:  The name of the file to load the metadata from, with full path. 
 - <b>`release`</b>:  The name of the release for this metadata; default 'custom'. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the loaded data is not a dictionary as expected. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/metadata.py#L727"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_urls_data`

```python
get_urls_data(key: str, protocol: str = 'root') → list[str]
```

Retrieve file URLs for the base (unskimmed) dataset. 



**Note:**

> DEPRECATED: Please use get_urls(key, skim='noskim', protocol=protocol, cache=cache) instead. 
>

**Args:**
 
 - <b>`key`</b>:  The dataset identifier. 
 - <b>`protocol`</b>:  The desired URL protocol. 



**Returns:**
 A list of file URLs for the dataset. 




---

_This file was automatically generated via [lazydocs](https://github.com/ml-tooling/lazydocs)._
