import asyncio, ssl, time
from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3Connection, H3_ALPN
from aioquic.h3.events import HeadersReceived, DataReceived

class H3StressClient(QuicConnectionProtocol):
    def __init__(self, *a, request_paths=None, **kw):
        super().__init__(*a, **kw)
        self.paths = request_paths or []
        self.h3 = None
        self.responses = {p: 0 for p in self.paths}
        self.latencies = {}
        self.pending = len(self.paths)
        self._done = asyncio.Event()

    def quic_event_received(self, event):
        if self.h3 is None and self._quic._handshake_complete:
            self.h3 = H3Connection(self._quic)
            for path in self.paths:
                sid = self._quic.get_next_available_stream_id()
                self.latencies[path] = time.perf_counter()
                self.h3.send_headers(
                    sid,
                    [(b":method", b"GET"), (b":scheme", b"https"),
                     (b":authority", b"localhost"), (b":path", path.encode())],
                )
                self.h3.send_data(sid, b"", end_stream=True)
            print(f"📤 Sent {len(self.paths)} concurrent GET requests")
            self.transmit()

        if self.h3:
            for ev in self.h3.handle_event(event):
                if isinstance(ev, HeadersReceived):
                    pass
                elif isinstance(ev, DataReceived):
                    self.responses.setdefault(ev.stream_id, 0)
                    self.responses[ev.stream_id] += len(ev.data)
                    if ev.stream_ended:
                        self.pending -= 1
                        if self.pending == 0:
                            self._done.set()
        self.transmit()

async def main():
    paths = [f"/files/file{i}.bin" for i in range(1, 51)]
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    cfg.verify_mode = ssl.CERT_NONE
    start = time.perf_counter()
    async with connect(
        "localhost", 4433, configuration=cfg,
        create_protocol=lambda *a, **kw: H3StressClient(*a, request_paths=paths, **kw)
    ) as proto:
        await proto._done.wait()
    total = time.perf_counter() - start
    print(f"✅ Completed 50 streams in {total:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
