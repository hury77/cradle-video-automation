import os
from pathlib import Path

path = "/Users/hubert.rycaj/Downloads/1004853"
if os.path.exists(path):
    files = os.listdir(path)
    print(f"Files in {path}:")
    for f in files:
        print(f"  {repr(f)} (suffix: {repr(Path(f).suffix)})")
else:
    print(f"Path {path} does not exist")
