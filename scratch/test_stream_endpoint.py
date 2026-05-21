import http.client
import sys

conn = http.client.HTTPConnection("localhost", 8001)

# Check 869
try:
    conn.request("GET", "/api/v1/files/stream/869")
    resp = conn.getresponse()
    print("File 869 Stream Response:")
    print(f"  Status: {resp.status} {resp.reason}")
    print("  Headers:")
    for h, v in resp.getheaders():
        print(f"    {h}: {v}")
    # Read first 100 bytes
    body = resp.read(100)
    print(f"  First 100 bytes/Error: {body}")
except Exception as e:
    print(f"Error calling 869: {e}")

print("-" * 40)

# Check 870
try:
    conn.request("GET", "/api/v1/files/stream/870")
    resp = conn.getresponse()
    print("File 870 Stream Response:")
    print(f"  Status: {resp.status} {resp.reason}")
    print("  Headers:")
    for h, v in resp.getheaders():
        print(f"    {h}: {v}")
    body = resp.read(100)
    print(f"  First 100 bytes/Error: {body}")
except Exception as e:
    print(f"Error calling 870: {e}")
