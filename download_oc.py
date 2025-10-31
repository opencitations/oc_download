import argparse
import json
import os
import subprocess
import sys

import web

from src.wl import WebLogger

# Load the configuration file
with open("conf.json") as f:
    c = json.load(f)


# Docker ENV variables
env_config = {
    "base_url": os.getenv("BASE_URL", c["base_url"]),
    "log_dir": os.getenv("LOG_DIR", c["log_dir"]),
    "sync_enabled": os.getenv("SYNC_ENABLED", "false").lower() == "true"
}


active = {
    "corpus": "datasets",
    "index": "datasets",
    "meta": "datasets",
    "coci": "datasets",
    "doci": "datasets",
    "poci": "datasets",
    "croci": "datasets",
    "ccc": "datasets",
    "oci": "tools",
    "intrepid": "tools",
    "api": "querying",
    "sparql": "querying",
    "search": "querying"
}

# URL Mapping
urls = (
    "/", "Main",
    '/favicon.ico', 'Favicon'
)

# Set the web logger
web_logger = WebLogger(env_config["base_url"], env_config["log_dir"], [
    "HTTP_X_FORWARDED_FOR", # The IP address of the client
    "REMOTE_ADDR",          # The IP address of internal balancer
    "HTTP_USER_AGENT",      # The browser type of the visitor
    "HTTP_REFERER",         # The URL of the page that called your program
    "HTTP_HOST",            # The hostname of the page being attempted
    "REQUEST_URI",          # The interpreted pathname of the requested document
                            # or CGI (relative to the document root)
    "HTTP_AUTHORIZATION",   # Access token
    ],
    # comment this line only for test purposes
     {"REMOTE_ADDR": ["130.136.130.1", "130.136.2.47", "127.0.0.1"]}
)

render = web.template.render(c["html"], globals={
    'str': str,
    'isinstance': isinstance,
    'render': lambda *args, **kwargs: render(*args, **kwargs)
})

# App Web.py
app = web.application(urls, globals())

def sync_static_files():
    """
    Function to synchronize static files using sync_static.py
    """
    try:
        print("Starting static files synchronization...")
        subprocess.run([sys.executable, "sync_static.py", "--auto"], check=True)
        print("Static files synchronization completed")
    except subprocess.CalledProcessError as e:
        print(f"Error during static files synchronization: {e}")
    except Exception as e:
        print(f"Unexpected error during synchronization: {e}")


# Process favicon.ico requests
class Favicon:
    def GET(self):
        is_https = (
            web.ctx.env.get('HTTP_X_FORWARDED_PROTO') == 'https' or
            web.ctx.env.get('HTTPS') == 'on' or
            web.ctx.env.get('SERVER_PORT') == '443'
        )
        protocol = 'https' if is_https else 'http'
        raise web.seeother(f"{protocol}://{web.ctx.host}/static/favicon.ico")

class Main:
    def GET(self):
        web_logger.mes()
        current_subdomain = web.ctx.host.split('.')[0].lower()
        return render.download(active="", sp_title="", current_subdomain=current_subdomain, render=render)


# Run the application
if __name__ == "__main__":
    # Add startup log
    print("Starting DOWNLOAD OpenCitations web application...")
    print(f"Configuration: Base URL={env_config['base_url']}")
    print(f"Sync enabled: {env_config['sync_enabled']}")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='DOWNLOAD OpenCitations web application')
    parser.add_argument(
        '--sync-static',
        action='store_true',
        help='synchronize static files at startup (for local testing or development)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='port to run the application on (default: 8080)'
    )
    
    args = parser.parse_args()
    print(f"Starting on port: {args.port}")
    
    if args.sync_static or env_config["sync_enabled"]:
        # Run sync if either --sync-static is provided (local testing) 
        # or SYNC_ENABLED=true (Docker environment)
        print("Static sync is enabled")
        sync_static_files()
    else:
        print("Static sync is disabled")
    
    print("Starting web server...")
    # Set the port for web.py
    web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", args.port))