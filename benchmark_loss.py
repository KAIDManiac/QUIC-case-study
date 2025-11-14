import asyncio
import subprocess
import ssl
import time
import csv
import requests
import matplotlib.pyplot as plt
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3Connection, H3_ALPN
from aioquic.h3.events import DataReceived, HeadersReceived


# -----------------------------------------------------------
# Custom QUIC Protocol (same as your stable one)
# -----------------------------------------------------------
class H3LossProtocol(QuicConnectionProtocol):
    def __init__(self, *args, request_path="/index.html", **kwargs):
        super().__init__(*args, **kwargs)
        self.request_path = request_path
        self.h3 = None
        self.buffer = bytearray()
        self.start_time = None
        self.elapsed = None
        self.done = asyncio.Event()

    def quic_event_received(self, event):
        try:
            if self.h3 is None and self._quic._handshake_complete:
                self.h3 = H3Connection(self._quic)
                self.stream_id = self._quic.get_next_available_stream_id()
                self.start_time = time.perf_counter()
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
# Run one QUIC HTTP/3 request
# -----------------------------------------------------------
async def quic_request(path="/index.html"):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    cfg.verify_mode = ssl.CERT_NONE
    cfg.server_name = "localhost"  # ✅ aioquic 1.2.0-compatible

    async with connect(
        "localhost",
        4433,
        configuration=cfg,
        create_protocol=lambda *a, **k: H3LossProtocol(*a, request_path=path, **k)
    ) as protocol:
        try:
            await asyncio.wait_for(protocol.done.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            print("QUIC timeout")
            return 0, float("inf")

        return len(protocol.buffer), protocol.elapsed or float("inf")


# -----------------------------------------------------------
# TCP/HTTPS (HTTP/1.1)
# -----------------------------------------------------------
def tcp_request(path="/index.html"):
    url = f"https://localhost:8443{path}"
    start = time.perf_counter()
    r = requests.get(url, verify=False, timeout=10.0)
    elapsed = time.perf_counter() - start
    return len(r.content), elapsed


# -----------------------------------------------------------
# Apply and remove packet loss/delay
# -----------------------------------------------------------
def set_netem(loss=0, delay=0):
    # clear old rules
    subprocess.run(["sudo", "tc", "qdisc", "del", "dev", "lo", "root"], stderr=subprocess.DEVNULL)
    # add new ones
    if loss > 0 or delay > 0:
        cmd = ["sudo", "tc", "qdisc", "add", "dev", "lo", "root", "netem"]
        if delay > 0:
            cmd += ["delay", f"{delay}ms"]
        if loss > 0:
            cmd += ["loss", f"{loss}%"]
        subprocess.run(cmd)


# -----------------------------------------------------------
# Benchmark under multiple loss levels
# -----------------------------------------------------------
async def run_loss_tests():
    loss_levels = [0, 1, 5, 10]
    trials = 5
    results = []

    for loss in loss_levels:
        print(f"\n🌐 Testing with {loss}% packet loss ...")
        set_netem(loss, delay=50)  # baseline delay
        quic_times, tcp_times = [], []

        for i in range(trials):
            size_q, t_q = await quic_request()
            size_t, t_t = tcp_request()
            quic_times.append(t_q)
            tcp_times.append(t_t)
            print(f"Run {i+1}: QUIC={t_q:.4f}s, TCP={t_t:.4f}s")

        results.append({
            "loss": loss,
            "quic_avg": sum(quic_times) / len(quic_times),
            "tcp_avg": sum(tcp_times) / len(tcp_times)
        })

    # restore normal network
    set_netem(0, 0)

    # save results
    with open("loss_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["loss", "quic_avg", "tcp_avg"])
        writer.writeheader()
        writer.writerows(results)
    print("✅ Results saved to loss_results.csv")

    # plot
    plt.figure(figsize=(8, 5))
    plt.plot([r["loss"] for r in results], [r["quic_avg"] for r in results], "-o", label="QUIC (HTTP/3)")
    plt.plot([r["loss"] for r in results], [r["tcp_avg"] for r in results], "-o", label="TCP (HTTP/1.1)")
    plt.xlabel("Packet Loss (%)")
    plt.ylabel("Average Latency (s)")
    plt.title("Impact of Packet Loss on QUIC vs TCP")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig("loss_impact.png")
    print("✅ Graph saved as loss_impact.png")

if __name__ == "__main__":
    asyncio.run(run_loss_tests())
