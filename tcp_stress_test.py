import requests
import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://localhost:8443/files/"
FILES = [f"file{i}.bin" for i in range(1, 51)]

print("🌐 Starting TCP (HTTP/1.1) stress test ...")

start = time.perf_counter()
for i, fname in enumerate(FILES, 1):
    url = BASE + fname
    try:
        r = requests.get(url, verify=False, timeout=15)
        print(f"📥 {i:02d}/50 - {fname} ({len(r.content)/1e6:.2f} MB)")
    except Exception as e:
        print(f"❌ {fname} failed: {e}")
elapsed = time.perf_counter() - start

print(f"\n✅ Completed 50 sequential downloads in {elapsed:.2f}s")
