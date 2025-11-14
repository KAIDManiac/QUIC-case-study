import asyncio
import time

from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived


class H3ClientProtocol(QuicConnectionProtocol):

    def __init__(self, *args, request_paths=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_paths = request_paths or ["/index.html"]
        self.responses = {}
        self.h3 = None
        self.pending_streams = len(self.request_paths)
        self.stream_map = {}   # ✅ stream_id → path mapping
        self.latencies = {}
        self._all_done = asyncio.Event()

    def quic_event_received(self, event):
        try:
            # ✅ Initialize HTTP/3 after handshake
            if self.h3 is None and self._quic._handshake_complete:
                self.h3 = H3Connection(self._quic)

                # Send all GET requests concurrently
                for path in self.request_paths:
                    sid = self._quic.get_next_available_stream_id()
                    self.stream_map[sid] = path   # ✅ map stream ID to path
                    self.latencies[path] = time.perf_counter()
                    self.responses[path] = b""

                    self.h3.send_headers(
                        sid,
                        [
                            (b":method", b"GET"),
                            (b":scheme", b"https"),
                            (b":authority", b"localhost"),
                            (b":path", path.encode()),
                        ],
                    )

                    print(f"📤 Sent GET {path} on stream {sid}")

                self.transmit()

            # ✅ Process data
            if self.h3:
                for ev in self.h3.handle_event(event):

                    if isinstance(ev, HeadersReceived):
                        print(f"📥 Response headers for stream {ev.stream_id}: {ev.headers}")

                    elif isinstance(ev, DataReceived):
                        sid = ev.stream_id
                        path = self.stream_map[sid]  # ✅ use correct mapping
                        self.responses[path] += ev.data

                        if ev.stream_ended:
                            latency = time.perf_counter() - self.latencies[path]
                            print(f"✅ Completed {path} in {latency:.4f}s")
                            self.pending_streams -= 1

                            if self.pending_streams == 0:
                                self._all_done.set()

            self.transmit()

        except Exception as e:
            print("🔥 Client Error:", e)


async def main():
    config = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    config.verify_mode = False

    paths = ["/index.html", "/index.html", "/index.html"]

    async with connect(
        "localhost",
        4433,
        configuration=config,
        create_protocol=lambda *a, **kw: H3ClientProtocol(*a, request_paths=paths, **kw)
    ) as protocol:

        await protocol._all_done.wait()

        print("\n✅ ALL RESPONSES RECEIVED:")
        for p, data in protocol.responses.items():
            print(f"\n🔹 {p} ({len(data)} bytes):")
            print(data.decode())

        protocol.close()


if __name__ == "__main__":
    asyncio.run(main())
