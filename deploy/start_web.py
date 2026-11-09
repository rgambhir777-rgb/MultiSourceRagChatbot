"""Start-up script for the single-container deployment (Modal, or `docker run` to test it locally).

It runs inside the image built by docker/modal.Dockerfile and starts two programs:

1. the API (uvicorn) on 127.0.0.1:8000, reachable only from inside the container;
2. nginx on 0.0.0.0:8080: serves the React app, forwards /api to the API, asks for a password.

Steps:
- write nginx's password file from APP_USERNAME / APP_PASSWORD (env vars from a Modal Secret).
  It refuses to start without a password, so the app can never go online unprotected;
- start the API and wait until /health answers, so the first visitors don't get "502 Bad Gateway";
- start nginx, then wait. If either program stops, stop the other one too and exit, so Modal
  replaces the container instead of serving a half-working app.

This is deployment tooling, not app code, so it reads its own two env vars directly; the API
itself still reads all of its configuration through app/config.py.
"""

import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HTPASSWD = Path("/etc/nginx/ragbot.htpasswd")
# Full paths, so a planted program earlier on PATH can't be started instead.
UVICORN = "/usr/local/bin/uvicorn"
NGINX = "/usr/sbin/nginx"
OPENSSL = "/usr/bin/openssl"
API_HEALTH_URL = "http://127.0.0.1:8000/health"
API_START_TIMEOUT_S = 180  # first start loads the embedding models
MIN_PASSWORD_LENGTH = 12

logging.basicConfig(level=logging.INFO, format="start_web: %(message)s", stream=sys.stdout)
log = logging.getLogger("start_web")


def write_password_file() -> None:
    """Write nginx's password file: the password salted and hashed (SHA-512 crypt), not as text."""
    username = os.environ.get("APP_USERNAME", "ragbot")
    password = os.environ.get("APP_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"APP_PASSWORD must be set and at least {MIN_PASSWORD_LENGTH} characters long")
    # The password goes in through stdin, never as an argument (others could see arguments).
    hashed = subprocess.run(  # noqa: S603 - fixed program and arguments
        [OPENSSL, "passwd", "-6", "-stdin"],
        input=password.encode(),
        capture_output=True,
        check=True,
    ).stdout.decode()
    HTPASSWD.write_text(f"{username}:{hashed.strip()}\n")
    # Readable by nginx's worker user (www-data) and root only.
    os.chown(HTPASSWD, 0, _www_data_gid())
    HTPASSWD.chmod(0o640)
    log.info("password file written for user %s", username)


def _www_data_gid() -> int:
    import grp  # Linux-only module, so imported here, where it is used

    return grp.getgrnam("www-data").gr_gid


def start_api() -> subprocess.Popen[bytes]:
    """Start uvicorn (one worker, like the compose setup) and wait until it is alive."""
    api = subprocess.Popen(  # noqa: S603 - fixed program and arguments
        [UVICORN, "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000"],
        cwd="/app",
    )
    deadline = time.monotonic() + API_START_TIMEOUT_S
    while time.monotonic() < deadline:
        if api.poll() is not None:
            sys.exit(f"the API stopped during start-up (exit code {api.returncode})")
        try:
            with urllib.request.urlopen(API_HEALTH_URL, timeout=2):
                log.info("API is up")
                return api
        except OSError:
            time.sleep(1)
    api.terminate()
    sys.exit(f"the API did not answer {API_HEALTH_URL} within {API_START_TIMEOUT_S} s")


def main() -> None:
    """Start both programs and exit as soon as either one stops."""
    write_password_file()
    api = start_api()
    nginx = subprocess.Popen([NGINX, "-g", "daemon off;"])  # noqa: S603 - fixed arguments
    log.info("nginx started on port 8080")
    while api.poll() is None and nginx.poll() is None:
        time.sleep(2)
    stopped = "API" if api.returncode is not None else "nginx"
    for proc in (api, nginx):
        if proc.poll() is None:
            proc.terminate()
    sys.exit(f"the {stopped} stopped; shutting the container down")


if __name__ == "__main__":
    main()
