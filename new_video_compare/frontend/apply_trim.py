import json

with open("recovered_args.json", "r") as f:
    args = json.load(f)

chunks = json.loads(args["ReplacementChunks"])
chunks.sort(key=lambda x: x["StartLine"], reverse=True)

with open("src/components/StandalonePlayer.tsx", "r") as f:
    lines = f.readlines()

for chunk in chunks:
    start = chunk["StartLine"] - 1
    end = chunk["EndLine"]
    
    # Simple check if target content matches
    target = chunk["TargetContent"]
    actual = "".join(lines[start:end])
    if target.strip() in actual.strip() or target in actual:
        replacement = chunk["ReplacementContent"]
        if not replacement.endswith("\n"):
            replacement += "\n"
        lines[start:end] = [replacement]
    else:
        print(f"Failed to match chunk at {start+1}")

with open("src/components/StandalonePlayer.tsx", "w") as f:
    f.writelines(lines)

print("Applied chunks.")
