import asyncio
import ssl
import time
import csv
import requests
import matplotlib.pyplot as plt
import urllib3

# disable urllib3 self-signed cert warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3Connection, H3_ALPN
from aioquic.h3.events import DataReceived, HeadersReceived

# -----------------------------------------------------------
# Custom QUIC protocol for one HTTP/3 request
# -----------------------------------------------------------
class H3BenchmarkProtocol(QuicConnectionProtocol):
    def __init__(self, *args, request_path="/index.html", **kwargs):
        super().__init__(*args, **kwargs)
        self.request_path = request_path
        self.h3 = None
        self.stream_id = None
        self.buffer = bytearray()
        self.start_time = None
        self.elapsed = None
        self.done = asyncio.Event()

    def quic_event_received(self, event):
        try:
            # Start HTTP/3 once handshake is complete
            if self.h3 is None and self._quic._handshake_complete:
                self.h3 = H3Connection(self._quic)
                self.stream_id = self._quic.get_next_available_stream_id()
                self.start_time = time.perf_counter()

                # send GET request
                self.h3.send_headers(
                    self.stream_id,
                    [
                        (b":method", b"GET"),
                        (b":scheme", b"https"),
                        (b":authority", b"localhost"),
                        (b":path", self.request_path.encode()),
                    ],
                )
                self.h3.send_data(self.stream_id, b"", end_stream=True)
                self.transmit()

            # Handle HTTP/3 data events
            if self.h3:
                for ev in self.h3.handle_event(event):
                    if isinstance(ev, HeadersReceived):
                        pass
                    elif isinstance(ev, DataReceived) and ev.stream_id == self.stream_id:
                        self.buffer.extend(ev.data)
                        if ev.stream_ended:
                            self.elapsed = time.perf_counter() - self.start_time
                            self.done.set()

        except Exception as e:
            print("Protocol error:", e)

# -----------------------------------------------------------
# Run a single QUIC HTTP/3 GET
# -----------------------------------------------------------
async def quic_request(path="/index.html"):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    cfg.verify_mode = ssl.CERT_NONE

    async with connect(
        "localhost",
        4433,
        configuration=cfg,
        create_protocol=lambda *a, **k: H3BenchmarkProtocol(*a, request_path=path, **k)
    ) as protocol:
        try:
            await asyncio.wait_for(protocol.done.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            print("QUIC request timeout")
            return 0, float("inf")

        return len(protocol.buffer), protocol.elapsed or float("inf")

# -----------------------------------------------------------
# TCP/HTTPS (HTTP/1.1) baseline
# -----------------------------------------------------------
def tcp_request(path="/index.html"):
    url = f"https://localhost:8443{path}"
    start = time.perf_counter()
    r = requests.get(url, verify=False, timeout=10.0)
    elapsed = time.perf_counter() - start
    return len(r.content), elapsed

# -----------------------------------------------------------
# Benchmark loop
# -----------------------------------------------------------
async def benchmark():
    test_path = "/index.html"
    trials = 10

    quic_times = []
    tcp_times = []
    rows = []

    print(f"Running {trials} trials for {test_path}...\n")

    for i in range(trials):
        size_q, t_q = await quic_request(test_path)
        size_t, t_t = tcp_request(test_path)

        print(f"Run {i+1:02d}: QUIC={t_q:.4f}s ({size_q} bytes), TCP={t_t:.4f}s ({size_t} bytes)")

        quic_times.append(t_q)
        tcp_times.append(t_t)
        rows.append({"trial": i+1, "proto": "QUIC", "latency_s": t_q, "bytes": size_q})
        rows.append({"trial": i+1, "proto": "TCP", "latency_s": t_t, "bytes": size_t})

    # Save results to CSV
    csv_name = "benchmark_results.csv"
    with open(csv_name, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["trial", "proto", "latency_s", "bytes"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✅ Results saved to {csv_name}")

    # Plot latency comparison
    plt.figure(figsize=(8, 5))
    plt.boxplot(
        [quic_times, tcp_times],
        tick_labels=["QUIC (HTTP/3)", "TCP (HTTP/1.1)"]
    )
    plt.title("Latency Comparison: QUIC vs TCP")
    plt.ylabel("Seconds")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig("latency_comparison.png")
    print("✅ Graph saved as latency_comparison.png")

    # Average values
    avg_quic = sum(quic_times) / len(quic_times)
    avg_tcp = sum(tcp_times) / len(tcp_times)
    print(f"\nAverage QUIC latency: {avg_quic:.6f} s")
    print(f"Average TCP latency: {avg_tcp:.6f} s")

# -----------------------------------------------------------
# Entry point
# -----------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(benchmark())
