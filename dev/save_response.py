#!/usr/bin/env python3
import sys
import json
import os
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover - requests may not be installed
    print("The 'requests' library is required. Install with 'pip install requests'.")
    raise


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
    resp = requests.get(url)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        data = resp.text
    os.makedirs("dev", exist_ok=True)
    path = os.path.join("dev", "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2) if isinstance(data, dict) or isinstance(data, list) else f.write(str(data))
    print(f"API response from {url} saved to {path}")


if __name__ == "__main__":
    main()
