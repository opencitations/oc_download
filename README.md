# OpenCitations DOWNLOAD Service

This repository contains the DOWNLOAD service for OpenCitations.

### Environment Variables

The service requires the following environment variables. These values take precedence over the ones defined in `conf.json`:

- `BASE_URL`: Base URL for the DOWNLOAD endpoint
- `LOG_DIR`: Directory path where log files will be stored
- `SYNC_ENABLED`: Enable/disable static files synchronization (default: false)

For instance:

```env
BASE_URL=download.opencitations.net
LOG_DIR=/home/dir/log/
SYNC_ENABLED=true
```

> **Note**: When running with Docker, environment variables always override the corresponding values in `conf.json`. If an environment variable is not set, the application will fall back to the values defined in `conf.json`.

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