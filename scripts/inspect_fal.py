
import fal_client
import inspect

print("Dir of fal_client:")
for item in dir(fal_client):
    if not item.startswith("_"):
        print(item)
