from asyncio import get_event_loop
from functools import partial
from os import close, kill, execv, forkpty, read
from sanic import Sanic
from sanic.response import text
from signal import SIGTERM

app = Sanic()

@app.route("/")
async def hello(request):
    loop = get_event_loop()
    pid, fd = forkpty()
    if not pid:
        execv('/bin/bash', ['bunny'])
    loop.add_reader(fd, partial(on_read, loop, fd))
    loop.call_later(1, partial(kill, pid, SIGTERM))
    return text("Hello world!")

def on_read(loop, fd):
    try:
        print(read(fd, 4096))
    except Exception as e:
        print(e)
        loop.remove_reader(fd)
        close(fd)

app.run()
