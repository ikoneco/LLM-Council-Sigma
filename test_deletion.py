
import urllib.request
import json
import os
import time

API_BASE = "http://localhost:8001"

def test_delete():
    # 1. Create a conversation
    print("Creating conversation...")
    req = urllib.request.Request(f"{API_BASE}/api/conversations", data=b'{}', method='POST')
    req.add_header('Content-Type', 'application/json')
    
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        conv_id = data["id"]
        print(f"Created: {conv_id}")

    # 2. Check if file exists
    file_path = f"data/conversations/{conv_id}.json"
    # Need absolute path to be sure
    abs_path = os.path.abspath(file_path)
    print(f"Checking path: {abs_path}")
    
    if os.path.exists(abs_path):
        print("File exists locally.")
    else:
        print("File NOT found locally initially.")
        # Sometimes it takes a split second to write?
        time.sleep(0.5)
        if os.path.exists(abs_path):
            print("File found after delay.")
        else:
             print("STILL NOT FOUND. CHECKING DATA_DIR...")
             return

    # 3. Delete via API
    print(f"Deleting via API: {conv_id}")
    del_req = urllib.request.Request(f"{API_BASE}/api/conversations/{conv_id}", method='DELETE')
    with urllib.request.urlopen(del_req) as resp:
        print(f"Status: {resp.status}")
        print(f"Response: {resp.read().decode()}")

    # 4. Check if file still exists
    time.sleep(0.5) # Give it a moment
    if os.path.exists(abs_path):
        print("FAIL: File still exists!")
    else:
        print("SUCCESS: File deleted.")

if __name__ == "__main__":
    test_delete()
