import asyncio
import os

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived

ROOT = "www"


class H3ServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.h3 = H3Connection(self._quic)

    def quic_event_received(self, event):
        try:
            for http_event in self.h3.handle_event(event):

                # ✅ Handle GET requests
                if isinstance(http_event, HeadersReceived):
                    headers = dict(http_event.headers)
                    path = headers.get(b":path", b"/").decode()
                    stream_id = http_event.stream_id

                    print(f"📥 Request from client: {path}")

                    file_path = os.path.join(ROOT, path.lstrip("/"))

                    if os.path.isfile(file_path):
                        with open(file_path, "rb") as f:
                            data = f.read()

                        try:
                            self.h3.send_headers(stream_id, [
                                (b":status", b"200"),
                                (b"content-length", str(len(data)).encode()),
                            ])
                            self.h3.send_data(stream_id, data, end_stream=True)
                        except Exception as e:
                            # ✅ Prevent crash if stream already closed (FIN)
                            print(f"🔥 Server write error on stream {stream_id}: {e}")

                    else:
                        try:
                            self.h3.send_headers(stream_id, [(b":status", b"404")], end_stream=True)
                        except Exception as e:
                            print(f"🔥 Server write error on stream {stream_id}: {e}")

                # ✅ Echo body if POST or streamed data
                elif isinstance(http_event, DataReceived):
                    try:
                        self.h3.send_data(http_event.stream_id, http_event.data, end_stream=True)
                    except Exception as e:
                        print(f"🔥 Server write error on stream {http_event.stream_id}: {e}")

            self.transmit()

        except Exception as e:
            print("🔥 Server error:", e)


async def main():
    config = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN)
    config.load_cert_chain("certs/cert.pem", "certs/key.pem")

    print("✅ HTTP/3 QUIC Server running on port 4433...")

    await serve(
        host="0.0.0.0",
        port=4433,
        configuration=config,
        create_protocol=H3ServerProtocol,
    )

    await asyncio.Future()  # keep server alive


if __name__ == "__main__":
    asyncio.run(main())
