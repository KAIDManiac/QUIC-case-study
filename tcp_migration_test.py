import requests
import time

url = "https://localhost:8443/bigfile.bin"

print("Starting TCP (HTTP/1.1) download test...")
start = time.perf_counter()

try:
    with requests.get(url, stream=True, verify=False, timeout=5) as r:
        downloaded = 0
        for chunk in r.iter_content(chunk_size=1024*1024):  # 1 MB chunks
            if not chunk:
                break
            downloaded += len(chunk)
            if downloaded >= 2 * 1024 * 1024:  # after ~2MB
                print("\n🌐 Simulating network change (closing socket)...")
                r.raw.close()  # forcibly close connection mid-transfer
                time.sleep(1)
            print(f"Downloaded {downloaded / 1e6:.1f} MB...")
except Exception as e:
    print(f"❌ TCP connection error: {e}")

elapsed = time.perf_counter() - start
print(f"\nFinal downloaded size: {downloaded / 1e6:.2f} MB in {elapsed:.2f}s")
