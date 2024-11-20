# **Atlas Open Magic**

**Atlas Open Magic** is a Python package designed to simplify working with ATLAS Open Data by providing utilities to manage metadata and URL mappings efficiently.

---

## **Features**

- **Metadata Retrieval**:
  - Retrieve metadata for datasets using a user-friendly API.
  - Access specific fields or full metadata entries for datasets.
  
- **URL Mapping**:
  - Map dataset IDs to their corresponding URLs for efficient file access.

---

## **Installation**

You can install this package using `pip`. (Include the installation instructions based on your distribution method.)

```bash
pip install atlasopenmagic
```
Alternatively, clone the repository and install locally:
```bash
git clone https://github.com/yourusername/atlasopenmagic.git
cd atlasopenmagic
pip install .
```
## Usage 
### Retrieving metadata
Use the `get_metadata` function to retrieve metadata for a dataset.

Example:
```python
from atlasopenmagic.metadata import get_metadata

# Retrieve full metadata for a dataset
metadata = get_metadata("301204")
print(metadata)

# Retrieve a specific metadata field
cross_section = get_metadata("301204", "cross_section")
print(f"Cross-section: {cross_section}")
```
### Getting URLs
Use the `get_urls` function to retrieve URLs for a dataset ID.

Example:
```python
from atlasopenmagic.urls import get_urls

# Retrieve URLs for a dataset
urls = get_urls(700200)
print(urls)
```
## Testing 
This project includes a test suite to ensure the correctness of the core functions.
### Run Tests
Run all tests using the following command:
```bash
python -m unittest discover -s tests
```
Example Output:
```bash
.......
----------------------------------------------------------------------
Ran 7 tests in 1.023s

OK
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
This project is licensed under the [Apache 2.0 License](LICENSE)