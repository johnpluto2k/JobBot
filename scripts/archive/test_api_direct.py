#!/usr/bin/env python3
"""Test API responses directly."""

import json
import urllib.request
import subprocess
import time
import sys
from pathlib import Path

# Start backend
print("[START] Backend API...")
backend_proc = subprocess.Popen(
    [sys.executable, "-m", "job_bot.api"],
    cwd=str(Path(__file__).parent),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(2)

try:
    # Test /api/companies
    print("[TEST] GET /api/companies")
    response = urllib.request.urlopen('http://127.0.0.1:8000/api/companies', timeout=5)
    data = json.loads(response.read())
    print(f"[OK] Status: {response.status}")
    print(f"[OK] Type: {type(data)}")
    print(f"[OK] Count: {len(data)}")
    if len(data) > 0:
        print(f"[OK] First item keys: {list(data[0].keys())}")
        print(f"[OK] First item: {json.dumps(data[0], indent=2)}")

    # Test /api/summary
    print("\n[TEST] GET /api/summary")
    response = urllib.request.urlopen('http://127.0.0.1:8000/api/summary', timeout=5)
    data = json.loads(response.read())
    print(f"[OK] Status: {response.status}")
    print(f"[OK] Total companies: {data.get('total')}")
    print(f"[OK] By status: {data.get('by_status')}")

    # Test /api/applications
    print("\n[TEST] GET /api/applications")
    response = urllib.request.urlopen('http://127.0.0.1:8000/api/applications', timeout=5)
    data = json.loads(response.read())
    print(f"[OK] Status: {response.status}")
    print(f"[OK] Count: {len(data)}")
    if len(data) > 0:
        print(f"[OK] First application keys: {list(data[0].keys())}")

    print("\n[PASS] All API endpoints working")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

finally:
    backend_proc.terminate()
    try:
        backend_proc.wait(timeout=3)
    except:
        backend_proc.kill()
