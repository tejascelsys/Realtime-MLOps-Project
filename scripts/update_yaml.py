"""Update `storageUri` in inference.yaml with the given Azure Blob URL."""
import re
import sys

if len(sys.argv) != 2:
    print("Usage: python3 update_yaml.py <storage_uri>")
    sys.exit(1)

uri = sys.argv[1]

with open('k8s/inference.yaml', 'r') as f:
    content = f.read()

# Detect if it's the new shell-wrapped format or old storageUri format
if "MODEL_URI=" in content:
    content = re.sub(
        r'(?m)^(\s*MODEL_URI=\s*).*$',
        lambda m: f'{m.group(1)}"{uri}"',
        content,
        count=1,
    )
else:
    content = re.sub(
        r'(?m)^(\s*storageUri:\s*).*$',
        lambda m: f'{m.group(1)}"{uri}"',
        content,
        count=1,
    )

with open('k8s/inference.yaml', 'w') as f:
    f.write(content)

print(f"Updated storageUri to: {uri}")
