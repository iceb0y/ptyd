from asyncio import get_event_loop, wait, FIRST_COMPLETED
from os import close, execvp, forkpty, path, read, write, waitpid, WNOHANG
from sanic import Sanic
from signal import SIGCHLD
from sys import argv, exit

if not argv[1:]:
    print('Usage: ptyd <command> [<arguments...>]')
    exit(1)

static_dir = path.join(path.dirname(__file__), 'static')
app = Sanic()
app.static('', static_dir)
app.static('', path.join(static_dir, 'app.html'))

def prepare(_, loop):
    loop.add_signal_handler(SIGCHLD, sigchld)

def sigchld():
    while True:
        try:
            waitpid(-1, WNOHANG)
        except ChildProcessError:
            return

@app.websocket('pty')
async def pty(_, ws):
    pid, fd = forkpty()
    if not pid:
        execvp(argv[1], argv[1:])

    loop = get_event_loop()
    fd_to_ws_task = loop.create_task(fd_to_ws(fd, ws))
    ws_to_fd_task = loop.create_task(ws_to_fd(ws, fd))
    try:
        await wait([fd_to_ws_task, ws_to_fd_task], return_when=FIRST_COMPLETED)
    finally:
        if not fd_to_ws_task.done():
            fd_to_ws_task.cancel()
        if not ws_to_fd_task.done():
            ws_to_fd_task.cancel()
        close(fd)

async def fd_to_ws(fd, ws):
    loop = get_event_loop()
    while True:
        data = await loop.run_in_executor(None, read, fd, 256)
        if not data:
            return
        await ws.send(data.decode(errors='replace'))

async def ws_to_fd(ws, fd):
    loop = get_event_loop()
    while True:
        data = (await ws.recv()).encode()
        await loop.run_in_executor(None, write, fd, data)

app.run(before_start=prepare)
