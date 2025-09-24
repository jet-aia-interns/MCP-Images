import requests
import sseclient
import sys

BASE_URL = "https://image-mcp-server-fhf0bzdxdnced7fj.australiaeast-01.azurewebsites.net"

def check_root():
    url = f"{BASE_URL}/"
    print(f"\n[1] Checking {url}")
    r = requests.get(url)
    print("Status:", r.status_code)
    print("Body:", r.text[:200])

def check_health():
    url = f"{BASE_URL}/health"
    print(f"\n[2] Checking {url}")
    r = requests.get(url)
    print("Status:", r.status_code)
    print("Body:", r.text.strip())

def check_manifest():
    url = f"{BASE_URL}/mcp/manifest.json"
    print(f"\n[3] Checking {url}")
    r = requests.get(url)
    print("Status:", r.status_code)
    body = r.text.strip()
    print("Body:", body[:300])  # print first 300 chars only
    if r.status_code == 200:
        try:
            manifest = r.json()
            print("Parsed manifest keys:", list(manifest.keys()))
            # Validate required fields
            if "endpoints" not in manifest:
                print("❌ ERROR: Manifest missing 'endpoints'")
            else:
                if "sse" not in manifest["endpoints"]:
                    print("❌ ERROR: Manifest missing 'endpoints.sse'")
                else:
                    print("✅ Manifest includes SSE endpoint:", manifest["endpoints"]["sse"])
            return manifest
        except Exception as e:
            print("❌ Manifest is not valid JSON:", e)
    return None

def check_sse(manifest):
    if not manifest or "endpoints" not in manifest or "sse" not in manifest["endpoints"]:
        print("\n[4] Skipping SSE check (manifest invalid)")
        return
    url = manifest["endpoints"]["sse"]
    print(f"\n[4] Testing SSE connection to {url}")
    try:
        # Open streaming request
        r = requests.get(url, stream=True, timeout=10)
        if r.status_code != 200:
            print(f"❌ SSE connection failed with status {r.status_code}")
            return
        client = sseclient.SSEClient(r)
        for event in client.events():
            print("✅ SSE Event received:", event.event, event.data[:100])
            break
    except Exception as e:
        print("❌ SSE connection failed:", e)

if __name__ == "__main__":
    check_root()
    check_health()
    manifest = check_manifest()
    check_sse(manifest)
