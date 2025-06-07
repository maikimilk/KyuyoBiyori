#!/usr/bin/env python3
import sys
import json
import os
import argparse

try:
    import requests
except ImportError:  # pragma: no cover - requests may not be installed
    print("The 'requests' library is required. Install with 'pip install requests'.")
    raise


def main():
    parser = argparse.ArgumentParser(description="Fetch API response and save to dev/result.json")
    parser.add_argument("url", nargs="?", default="http://localhost:8000/", help="Target URL")
    parser.add_argument("file", nargs="?", help="File to upload via POST")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "rb") as fp:
            files = {"file": (os.path.basename(args.file), fp)}
            resp = requests.post(args.url, files=files)
    else:
        resp = requests.get(args.url)

    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        data = resp.text
    os.makedirs("dev", exist_ok=True)
    path = os.path.join("dev", "result.json")
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, (dict, list)):
            json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            f.write(str(data))
    print(f"API response from {args.url} saved to {path}")


if __name__ == "__main__":
    main()
