"""Update storageUri in inference.yaml with the given Azure Blob SAS URL."""
import re
import sys

if len(sys.argv) != 2:
    print("Usage: python3 update_yaml.py <storage_uri>")
    sys.exit(1)

uri = sys.argv[1]

with open('k8s/inference.yaml', 'r') as f:
    content = f.read()

content = re.sub(r'storageUri:.*', f'storageUri: "{uri}"', content)

with open('k8s/inference.yaml', 'w') as f:
    f.write(content)

print(f"Updated storageUri to: {uri}")
