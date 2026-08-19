import asyncio
import json
import logging
import ssl
import threading

from .actions import QolsysAction
from .actions import QolsysActionInfo
from .events import QolsysEvent
from .exceptions import UnknownQolsysEventException
from .exceptions import UnknownQolsysSensorException
from .utils import LoggerCallback


LOGGER = logging.getLogger(__name__)


class QolsysSocket(object):
    def __init__(self, hostname: str, port: int = None, token: str = None,
                 logger=None, callback: callable = None,
                 connected_callback: callable = None,
                 disconnected_callback: callable = None,
                 keep_alive: int = None) -> None:
        self._hostname = hostname
        self._port = port or 12345
        self._token = token or ''

        self._logger = logger or LOGGER
        self._callback = callback or LoggerCallback()
        self._connected_callback = connected_callback or LoggerCallback('Connected callback')
        self._disconnected_callback = disconnected_callback or LoggerCallback('Disconnected callback')
        self._keep_alive = keep_alive or 60 * 4  # 4mn, since the panel generally timeouts at 5mn

        self._writer = None
        self._listen: bool = False

        # Thread isolation — socket I/O runs in its own daemon thread with its
        # own asyncio event loop, completely separate from HA's main loop.
        # This mirrors how AppDaemon isolates the Qolsys socket, and ensures
        # asyncio timers (read timeout, keep-alive sleep) fire reliably
        # regardless of HA's load.
        self._ha_loop: asyncio.AbstractEventLoop | None = None
        self._socket_loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def run_in_thread(self, ha_loop: asyncio.AbstractEventLoop,
                      name: str = 'qolsys_socket') -> None:
        """Start listen + keep_alive in a dedicated daemon thread.

        All socket I/O runs on that thread's own event loop.  Callbacks are
        bridged back to *ha_loop* via run_coroutine_threadsafe so HA state
        updates always happen on the correct loop.
        """
        self._ha_loop = ha_loop
        self._listen = True
        self._thread = threading.Thread(
            target=self._thread_entry,
            name=name,
            daemon=True,
        )
        self._thread.start()

    def _thread_entry(self) -> None:
        """Owned-loop entry point — never share this loop with HA."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._socket_loop = loop
        try:
            loop.run_until_complete(asyncio.gather(
                self.listen(),
                self.keep_alive(),
                return_exceptions=True,
            ))
        finally:
            loop.close()
            self._socket_loop = None

    def stop(self) -> None:
        """Signal the socket thread to shut down."""
        self._listen = False
        loop = self._socket_loop
        if loop and not loop.is_closed():
            for task in asyncio.all_tasks(loop):
                loop.call_soon_threadsafe(task.cancel)

    # ------------------------------------------------------------------
    # Cross-loop callback bridge
    # ------------------------------------------------------------------

    def _dispatch(self, coro) -> None:
        """Schedule a coroutine on HA's event loop from the socket thread."""
        ha_loop = self._ha_loop
        if ha_loop and not ha_loop.is_closed():
            asyncio.run_coroutine_threadsafe(coro, ha_loop)

    # ------------------------------------------------------------------
    # Sending (HA loop → socket loop)
    # ------------------------------------------------------------------

    async def send(self, action: QolsysAction):
        """Send an action to the panel.  Safe to await from HA's event loop."""
        loop = self._socket_loop
        if loop is None or self._writer is None:
            raise Exception('Socket not connected')
        fut = asyncio.run_coroutine_threadsafe(self._do_send(action), loop)
        await asyncio.wrap_future(fut)

    async def _do_send(self, action: QolsysAction) -> None:
        """Write bytes to the panel.  Must run on the socket loop."""
        self._logger.debug(f'Sending: {action.with_token(self._token)}')
        self._writer.write(action.with_token(self._token).encode())
        await self._writer.drain()

    # ------------------------------------------------------------------
    # Socket coroutines (run on socket loop, NOT on HA's loop)
    # ------------------------------------------------------------------

    async def keep_alive(self):
        while self._listen:
            await asyncio.sleep(self._keep_alive)
            if self._writer is not None and self._listen:
                self._logger.debug('Sending keep-alive')
                self._writer.write(b'\n')
                await self._writer.drain()

    async def listen(self):
        # Replace with https://docs.python.org/3/library/ssl.html#ssl.PROTOCOL_TLS_CLIENT ?
        context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        server = (self._hostname, self._port)

        self._listen = True
        delay_reconnect = 0
        while self._listen:
            writer = None
            try:
                self._logger.info('Establishing connection to '
                                  f'{server[0]}:{server[1]}')
                reader, writer = await asyncio.open_connection(
                    *server, ssl=context, server_hostname='')
                self._writer = writer
                await self._do_send(QolsysActionInfo())
                self._dispatch(self._connected_callback())

                delay_reconnect = 0
                # Timeout is keep_alive + 30s grace.  Fires reliably on our own
                # dedicated event loop — the original root cause of missed events
                # was asyncio.wait_for being starved on HA's busy main loop.
                _read_timeout = self._keep_alive + 30
                while self._listen:
                    try:
                        line = await asyncio.wait_for(
                            reader.readline(), timeout=_read_timeout
                        )
                    except asyncio.TimeoutError:
                        self._logger.warning(
                            'Read timeout after %ds — panel silent, reconnecting',
                            _read_timeout,
                        )
                        break

                    if not line:
                        self._logger.info(
                            'Connection closed by the panel, exiting to reset the connection')
                        break

                    line = line.decode().rstrip('\n')
                    self._logger.debug(f'Data received (len: {len(line)}): {line}')

                    if line == 'ACK':
                        # This is an ACK to a command we sent, we can ignore
                        self._logger.debug('ACK - ignoring.')
                        continue

                    try:
                        # We try to parse the event to one of our event classes
                        event = QolsysEvent.from_json(line)
                    except json.decoder.JSONDecodeError:
                        self._logger.debug(f'Data is not JSON: {line}')
                        continue
                    except UnknownQolsysEventException:
                        self._logger.debug(f'Unknown Qolsys event: {line}')
                        continue
                    except UnknownQolsysSensorException:
                        self._logger.debug(f'Unknown sensor in Qolsys event: {line}')
                        continue

                    # Bridge event to HA's event loop without blocking socket I/O
                    self._dispatch(self._callback(event))

            except asyncio.exceptions.CancelledError:
                self._listen = False
                self._logger.info('listening cancelled')
            except:  # noqa: E722
                delay_reconnect = min(delay_reconnect * 2 or 1, 60)
                self._logger.exception('error while listening')
            finally:
                self._dispatch(self._disconnected_callback())

                self._writer = None

                if writer:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except:  # noqa: E722
                        self._logger.exception(
                            'unable to wait for writer to '
                            'be fully closed; this might not be an issue if '
                            'the connection was closed on the other side')

            if self._listen and delay_reconnect:
                self._logger.info(f'sleeping {delay_reconnect} second(s) before reconnecting')
                await asyncio.sleep(delay_reconnect)
