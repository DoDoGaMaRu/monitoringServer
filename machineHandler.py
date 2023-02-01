from typing import Callable, Awaitable
from socketio import AsyncNamespace


class MachineHandler(AsyncNamespace):
    def __init__(self,
                 namespace,
                 callback: Callable[[str, dict], Awaitable[None]]):
        super().__init__(namespace=namespace)
        self.name = namespace[1:]
        self.callback = callback

    def on_connect(self, sid, environ):
        print(self.name, 'connect')

    def on_disconnect(self, sid):
        print(self.name, 'disconnect')

    async def on_vib(self, sid, data):
        await self.callback('vib', data)

    async def on_temp(self, sid, data):
        await self.callback('temp', data)


class MyCustomNamespace(AsyncNamespace):
    def on_connect(self, sid, environ):
        pass

    def on_disconnect(self, sid):
        pass

    async def on_vib(self, sid, data):
        print('vib', data)

    async def on_temp(self, sid, data):
        print('temp', data)
