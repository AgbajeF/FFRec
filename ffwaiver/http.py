"""Tiny HTTP helper (standard library only) with retries and an offline fixture mode.

Set FFWAIVER_FIXTURES=/path/to/dir to answer every request from files in that
directory instead of the network. Used by the tests and the offline dry run.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "ff-waiver-site/1.0 (+https://github.com)"


class FetchError(Exception):
    pass


def fixture_name(url, params=None):
    """Map a URL to a stable fixture filename."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    parsed = urllib.parse.urlparse(url)
    key = parsed.netloc + parsed.path
    if parsed.query:
        key += "_" + parsed.query
    return re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("_")


def _fixture_dir():
    return os.environ.get("FFWAIVER_FIXTURES")


def get_bytes(url, params=None, timeout=45, retries=2):
    fx = _fixture_dir()
    if fx:
        name = fixture_name(url, params)
        for candidate in (name, name + ".json", name + ".csv"):
            path = os.path.join(fx, candidate)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read()
        raise FetchError(f"no fixture for {url} ({name})")

    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code != 429:
                break
            time.sleep(2 * (attempt + 1))
    raise FetchError(f"{url}: {last}")


def get_json(url, params=None, timeout=45, retries=2):
    raw = get_bytes(url, params, timeout, retries)
    try:
        return json.loads(raw)
    except ValueError as e:
        raise FetchError(f"{url}: invalid JSON ({e})")


def get_text(url, params=None, timeout=90, retries=2):
    return get_bytes(url, params, timeout, retries).decode("utf-8", errors="replace")
