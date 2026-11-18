# OpenCitations DOWNLOAD Service

This repository contains the DOWNLOAD service for OpenCitations.

### Environment Variables

The service requires the following environment variables. These values take precedence over the ones defined in `conf.json`:

- `BASE_URL`: Base URL for the DOWNLOAD endpoint
- `LOG_DIR`: Directory path where log files will be stored
- `SYNC_ENABLED`: Enable/disable static files synchronization (default: false)
- `DATA_DIR`: Directory with the dump descriptions shown on the page (default: `data`, see [Managing the dumps](#managing-the-dumps))

For instance:

```env
BASE_URL=download.opencitations.net
LOG_DIR=/home/dir/log/
SYNC_ENABLED=true
```

> **Note**: When running with Docker, environment variables always override the corresponding values in `conf.json`. If an environment variable is not set, the application will fall back to the values defined in `conf.json`.

## Managing the dumps

The download page is generated from the JSON files in `data/`. Publishing a dump never requires editing the HTML template.

```
data/
├── datasets.json         the datasets (Meta, Index), in the order they appear on the page
├── meta/
│   ├── 2026-06-27.json   one file per dump, named after its release date
│   └── ...
└── index/
    └── ...
```

In each folder the most recent file is shown as the latest dump; the others are listed in the "Dump version" selector of the dataset. Every dump has its own address (for instance `/#meta-2026-01-20`), while `/#meta` and `/#index` always open the latest one.

### Adding a new dump

1. Copy the most recent file of the dataset and name the copy after the release date of the new dump (`YYYY-MM-DD.json`).
2. Update description, statistics, links and sizes in the copy.
3. Check the result with `python3 -m src.dumps`.
4. Bump the version in `pyproject.toml` to release a new Docker image.

The previous dump needs no change: it moves to the version selector by itself. To publish one more file of an existing dump, add an entry to its `files` (or `additional_files`) list.

### Fields of a dump file

```json
{
  "description": "Adds the metadata from the [February 2026 version of Crossref](https://api.crossref.org/snapshots/monthly/2026/02/all.json.tar.gz).",
  "stats": [
    { "value": "147M+", "label": "Bibliographic entities" }
  ],
  "stats_note": "3,673,399 editors and 115,504,540 publishers",
  "files": [
    {
      "name": "Metadata (CSV)",
      "url": "https://doi.org/10.5281/zenodo.20965426",
      "format": "7z",
      "size": "8.4 GB",
      "uncompressed": "56 GB"
    }
  ],
  "additional_files": []
}
```

| Field | Required | Description |
| --- | --- | --- |
| `files` | yes | The files of the dump, shown under "Download files" |
| `additional_files` | no | Same format as `files`, shown under "Additional files" |
| `description` | no | Free text. Links are written as `[label](https://...)`, HTML is not accepted |
| `stats` | no | Key figures: `value` and `label`, plus an optional `detail` (e.g. the exact count) |
| `stats_note` | no | Small note under the statistics |
| `label` | no | Name of the dump; by default month and year of the release date (`June 2026`) |

Each entry of `files` and `additional_files` has:

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | What the file contains, e.g. `Metadata (CSV)` |
| `url` | yes | Link to the archive (DOI) |
| `format` | no | Archive format: `7z`, `zip`, `tar.gz`, ... |
| `size` | no | Size of the download |
| `uncompressed` | no | Size once extracted |
| `badge` | no | Short green label next to the name, e.g. `Kubernetes ready` |
| `note` | no | One line of explanation under the name |
| `repository` | no | Name on the download button; by default taken from the link (Zenodo, Figshare, Internet Archive) |

Columns with no value in a table are hidden, so older dumps can list just names and links.

### Validation

`python3 -m src.dumps` checks every file and reports the first problem with the file name and the field involved (invalid JSON, misspelled or missing fields, wrong file names, links without `https://`). The same check runs in the GitHub workflow and when the service starts: with invalid data the build fails and the service does not start, instead of publishing a broken page.

### Static Files Synchronization

The application can synchronize static files from a GitHub repository. This configuration is managed in `conf.json`:

```json
{
  [...]
  "oc_services_templates": "https://github.com/opencitations/oc_services_templates",
  "sync": {
    "folders": [
      "static",
      "html-template/common"
    ],
    "files": [
      "test.txt"
    ]
  }
}
```

- `oc_services_templates`: The GitHub repository URL to sync files from
- `sync.folders`: List of folders to synchronize
- `sync.files`: List of individual files to synchronize

When static sync is enabled (via `--sync-static` or `SYNC_ENABLED=true`), the application will:
1. Clone the specified repository
2. Copy the specified folders and files
3. Keep the local static files up to date

> **Note**: Make sure the specified folders and files exist in the source repository.

## Running Options


### Local Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

First, install uv package manager and project dependencies:
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
# Install project dependencies
uv sync
```

For local development and testing, the application uses the built-in web.py HTTP server:

Examples:
```bash
# Run with default settings
uv run download_oc.py

# Run with static sync enabled
uv run download_oc.py --sync-static

# Run on custom port
uv run download_oc.py --port 8085

# Run with both options
uv run download_oc.py --sync-static --port 8085
```

The application supports the following command line arguments:

- `--sync-static`: Synchronize static files at startup
- `--port PORT`: Specify the port to run the application on (default: 8080)

### Production Deployment (Docker)

When running in Docker/Kubernetes, the application uses **Gunicorn** as the WSGI HTTP server for better performance and concurrency handling:

- **Server**: Gunicorn with gevent workers
- **Workers**: 4 concurrent worker processes
- **Worker Type**: gevent (async) for handling thousands of simultaneous requests
- **Timeout**: 1200 seconds (to handle long-running SPARQL queries)
- **Connections per worker**: 400 simultaneous connections

The Docker container automatically uses Gunicorn and is configured with static sync enabled by default.

> **Note**: The application code automatically detects the execution environment. When run with `uv run download_oc.py`, it uses the built-in web.py server. When run with Gunicorn (as in Docker), it uses the WSGI interface.
You can customize the Gunicorn server configuration by modifying the `gunicorn.conf.py` file.

### Building the Docker image locally
 
The repository already includes a `Dockerfile`, so there is nothing to write by hand. The image is built from your local checkout: the Dockerfile copies the local source code into the container (`COPY . .`) and installs the dependencies with uv from the lockfile. This means that any changes you make to the code will be included in the image, which is handy to test modifications before pushing them.
 
From the repository root:
 
```bash
docker build -t oc_download:local .
docker run -p 8080:8080 oc_download:local
```
 
The container starts with Gunicorn, exactly as in production. The environment variables (`BASE_URL`, `LOG_DIR`, `SPARQL_ENDPOINT_INDEX`, `SPARQL_ENDPOINT_META`, `SYNC_ENABLED`) have default values defined in the Dockerfile and can be overridden at runtime with `docker run -e VAR=value`