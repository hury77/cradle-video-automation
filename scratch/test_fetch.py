import urllib.request
import json

def fetch_url(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            return status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return None, str(e)

print("Fetching from LIVE (8001):")
status1, body1 = fetch_url("http://localhost:8001/api/v1/compare/548")
print(f"Status: {status1}")
try:
    print(json.loads(body1))
except:
    print(body1[:200])

print("\nFetching from DEV (8002):")
status2, body2 = fetch_url("http://localhost:8002/api/v1/compare/548")
print(f"Status: {status2}")
try:
    print(json.loads(body2))
except:
    print(body2[:200])
