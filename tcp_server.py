import ssl
from aiohttp import web
import os

ROOT = "www"

async def handler(request):
    path = request.path if request.path != "/" else "/index.html"
    filepath = os.path.join(ROOT, path.lstrip("/"))
    if os.path.isfile(filepath):
        return web.FileResponse(filepath)
    return web.Response(status=404, text="Not Found")

async def init_app():
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    return app

if __name__ == "__main__":
    sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sslctx.load_cert_chain("certs/cert.pem", "certs/key.pem")

    web.run_app(
        init_app(),
        host="0.0.0.0",
        port=8443,
        ssl_context=sslctx
    )
