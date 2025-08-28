<!-- markdownlint-disable -->

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/utils.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `utils`
This module provides utility functions for the atlasopenmagic package. 

It includes functions to install packages from an environment file and to build datasets from sample definitions. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/utils.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `install_from_environment`

```python
install_from_environment(
    *packages: Optional[str],
    environment_file: Optional[str] = None
) → None
```

Install specific packages listed in an environment.yml file via pip. 



**Args:**
 
 - <b>`*packages`</b>:  Package names to install (e.g., 'coffea', 'dask').  If empty, all packages in the environment.yml will be installed. 
 - <b>`environment_file`</b>:  Path to the environment.yml file.  If None, defaults to the environment.yml file contained in our notebooks repository. 



**Raises:**
 
 - <b>`FileNotFoundError`</b>:  If the environment file is not found at the specified path. 
 - <b>`ValueError`</b>:  If the environment file cannot be fetched from URL or has malformed structure. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/utils.py#L150"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_dataset`

```python
build_dataset(
    samples_defs: dict[str, dict],
    skim: str = 'noskim',
    protocol: str = 'https',
    cache: Optional[bool] = False
) → dict[str, dict]
```

Build a dict of MC samples URLs. 



**Args:**
 
 - <b>`samples_defs`</b>:  The datasets to be built up with their definitions and  colors. See examples for more info. 
 - <b>`skim`</b>:  The desired skim type. Defaults to 'noskim' for the base, 
 - <b>`unfiltered dataset. Other examples`</b>:  'exactly4lep', '3lep'. 
 - <b>`protocol`</b>:  The desired URL protocol. Can be 'root', 'https', or 'eos'.  Defaults to 'https'. 
 - <b>`cache`</b>:  Use the simplecache mechanism of fsspec to locally cache  files instead of streaming them. Default False means let  atlasopenmagic decide what to do for that protocol. 



**Returns:**
 A dictionary containing sample names as keys and dictionaries with 'list' of URLs and optional 'color' as values. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/utils.py#L185"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_data_dataset`

```python
build_data_dataset(
    data_keys: list[str],
    name: str = 'Data',
    color: Optional[str] = None,
    protocol: str = 'https',
    cache: Optional[bool] = None
) → dict[str, dict]
```

Build a dataset for data samples. 



**Note:**

> This function is deprecated and will be removed in future versions. Use build_dataset with the appropriate data definitions instead. 
>

**Args:**
 
 - <b>`data_keys`</b>:  List of data keys to be included in the dataset. 
 - <b>`name`</b>:  Name of the dataset. Defaults to "Data". 
 - <b>`color`</b>:  Color associated with the dataset. Defaults to None. 
 - <b>`protocol`</b>:  Protocol for the URLs. Defaults to "https". 
 - <b>`cache`</b>:  Use caching for file access. Default None means let  atlasopenmagic decide what to do for that protocol. 



**Returns:**
 A dictionary containing the dataset with URLs and optional color information. 


---

<a href="https://github.com/atlas-outreach-data-tools/atlasopenmagic/tree/main/src/atlasopenmagic/utils.py#L223"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_mc_dataset`

```python
build_mc_dataset(
    mc_defs: dict[str, dict],
    skim: str = 'noskim',
    protocol: str = 'https',
    cache: Optional[bool] = None
) → dict[str, dict]
```

Build a dict of MC samples URLs. 



**Note:**

> This function is deprecated and will be removed in future versions. Use build_dataset with the appropriate MC definitions instead. 
>

**Args:**
 
 - <b>`mc_defs`</b>:  The MC datasets to be built up with their definitions and colors.  See examples for more info. 
 - <b>`skim`</b>:  The desired skim type. Defaults to 'noskim' for the base, 
 - <b>`unfiltered dataset. Other examples`</b>:  'exactly4lep', '3lep'. 
 - <b>`protocol`</b>:  The desired URL protocol. Can be 'root', 'https', or 'eos'.  Defaults to 'https'. 
 - <b>`cache`</b>:  Use the simplecache mechanism of fsspec to locally cache  files instead of streaming them. Default None means let  atlasopenmagic decide what to do for that protocol. 



**Returns:**
 A dictionary containing MC sample names as keys and dictionaries with 'list' of URLs and optional 'color' as values. 




---

_This file was automatically generated via [lazydocs](https://github.com/ml-tooling/lazydocs)._
