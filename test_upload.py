import requests
import sys

url = "http://localhost:8002/api/v1/files/upload"
filepath = "/Users/hubert.rycaj/Downloads/961358/118349_961358_E-comm_TASTE_ELXAEG_CZSK_missing_assets_2023934031_Video_16x9_2-18_Slovak_SK.mov"

print(f"Uploading {filepath} to {url}...")
try:
    with open(filepath, "rb") as f:
        response = requests.post(url, files={"file": f})
    
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
