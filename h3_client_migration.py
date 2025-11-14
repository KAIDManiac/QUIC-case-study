import asyncio
import ssl
import time
from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived


class H3MigrationClient(QuicConnectionProtocol):
    def __init__(self, *args, request_path="/bigfile.bin", **kwargs):
        super().__init__(*args, **kwargs)
        self.request_path = request_path
        self.h3 = None
        self.start_time = None
        self.done = asyncio.Event()
        self.bytes_received = 0
        self.migrated = False

    def quic_event_received(self, event):
        if self.h3 is None and self._quic._handshake_complete:
            # initialize HTTP/3
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
            print(f"📤 Started GET {self.request_path} (stream {self.stream_id})")

        if self.h3:
            for ev in self.h3.handle_event(event):
                if isinstance(ev, HeadersReceived):
                    print("📥 Headers received:", ev.headers)
                elif isinstance(ev, DataReceived) and ev.stream_id == self.stream_id:
                    self.bytes_received += len(ev.data)
                    if not self.migrated and self.bytes_received > 2_000_000:
                        # trigger migration once ~2 MB downloaded
                        asyncio.create_task(self.trigger_migration())
                        self.migrated = True
                    if ev.stream_ended:
                        elapsed = time.perf_counter() - self.start_time
                        print(f"✅ Download complete — {self.bytes_received/1e6:.2f} MB in {elapsed:.2f}s")
                        self.done.set()
        self.transmit()

    async def trigger_migration(self):
        print("\n🌐 Simulating network change... requesting new CID migration.")
        try:
            # this changes the Connection ID (simulated new path)
            self._quic.change_connection_id()
            print("🔁 QUIC path migration triggered.")
        except Exception as e:
            print("⚠️ Migration error:", e)


async def main():
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    cfg.verify_mode = ssl.CERT_NONE
    cfg.server_name = "localhost"

    async with connect(
        "localhost",
        4433,
        configuration=cfg,
        create_protocol=lambda *a, **kw: H3MigrationClient(*a, request_path="/bigfile.bin", **kw),
    ) as protocol:
        await protocol.done.wait()
        print("🏁 Connection closed gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
