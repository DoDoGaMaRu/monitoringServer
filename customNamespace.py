from typing import Callable, Awaitable
from socketio import AsyncNamespace


class CustomNamespace(AsyncNamespace):
    def __init__(self,
                 logger,
                 namespace):
        super().__init__(namespace=namespace)
        self.logger = logger
        self.name = namespace[1:]

    def on_connect(self, sid, environ):
        client = 'ip: ' + str(environ['asgi.scope']['client'][0]) + ', sid: ' + sid + ''
        self.logger.info(self.name + ' connected    \t- ' + client)

    def on_disconnect(self, sid):
        client = 'sid: ' + sid
        self.logger.info(self.name + ' disconnected \t- ' + client)


class MachineHandler(CustomNamespace):
    def __init__(self,
                 logger,
                 namespace,
                 callback: Callable[[str, dict], Awaitable[None]]):
        super().__init__(logger, namespace)
        self.logger = logger
        self.name = namespace[1:]
        self.callback = callback

    async def on_vib(self, sid, data):
        await self.callback('vib', data)

    async def on_temp(self, sid, data):
        await self.callback('temp', data)
