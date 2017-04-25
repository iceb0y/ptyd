from asyncio import gather, get_event_loop, wait, FIRST_COMPLETED
from os import close, kill, execvp, forkpty, path, read, write, waitpid, WNOHANG
from sanic import Sanic
from sanic.websocket import ConnectionClosed
from signal import SIGCHLD, SIGHUP
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
    try:
        while waitpid(-1, WNOHANG)[0]:
            pass
    except ChildProcessError:
        pass

@app.websocket('pty')
async def pty(_, ws):
    pid, fd = forkpty()
    if not pid:
        execvp(argv[1], argv[1:])

    loop = get_event_loop()
    fd_to_ws_task = loop.create_task(fd_to_ws(fd, ws))
    ws_to_fd_task = loop.create_task(ws_to_fd(ws, fd))
    try:
        done, pending = await wait([fd_to_ws_task, ws_to_fd_task],
                                   return_when=FIRST_COMPLETED)
        await gather(*done)
        for task in pending:
            task.cancel()
    except ConnectionClosed:
        kill(pid, SIGHUP)
    finally:
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
