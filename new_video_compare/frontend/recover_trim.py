import json

with open("restore_trim.txt", "r") as f:
    for line in f:
        data = json.loads(line.strip())
        if "tool_calls" in data:
            for call in data["tool_calls"]:
                if call["name"] == "multi_replace_file_content":
                    args = call["args"]
                    with open("recovered_args.json", "w") as out:
                        json.dump(args, out, indent=2)
                    print("Recovered!")
                    exit(0)
