"""Async client for JBL MA Series AVR IP control (port 50000).

Implements the protocol described in "IP Control - JBL MA Series AVRs" v1.7.

Frame formats:
  Request : <0x23><CmdID><DataLen><Data...><0x0D>
  Response: <0x02><0x23><CmdID><RspCode><DataLen><Data...><0x0D>

The AVR pushes unsolicited frames whenever state changes (front panel, IR
remote, etc.), so we keep a long-lived connection and dispatch every frame
to the same state handler.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 50000

START_REQ = 0x23
START_RSP1 = 0x02
START_RSP2 = 0x23
END = 0x0D

RSP_OK = 0x00
RSP_BAD_CMD = 0xC1
RSP_BAD_PARAM = 0xC2
RSP_INVALID_TIME = 0xC3
RSP_BAD_LEN = 0xC4

REQ = 0xF0  # "request current value" sentinel

CMD_POWER = 0x00
CMD_DIM = 0x01
CMD_VERSION = 0x02
CMD_IR = 0x04
CMD_SOURCE = 0x05
CMD_VOLUME = 0x06
CMD_MUTE = 0x07
CMD_SURROUND = 0x08
CMD_PARTY = 0x09
CMD_PARTY_VOL = 0x0A
CMD_TREBLE = 0x0B
CMD_BASS = 0x0C
CMD_ROOM_EQ = 0x0D
CMD_DIALOG = 0x0E
CMD_DOLBY = 0x0F
CMD_DRC = 0x10
CMD_STREAM = 0x11
CMD_INIT = 0x50
CMD_HEARTBEAT = 0x51
CMD_REBOOT = 0x52
CMD_FACTORY = 0x53

REFRESH_CMDS = (
    CMD_POWER, CMD_DIM, CMD_SOURCE, CMD_VOLUME, CMD_MUTE, CMD_SURROUND,
    CMD_TREBLE, CMD_BASS, CMD_ROOM_EQ, CMD_DIALOG, CMD_DOLBY, CMD_DRC,
    CMD_PARTY, CMD_PARTY_VOL, CMD_STREAM,
)


class JBLError(Exception):
    """Raised when the AVR rejects a command."""


class JBLClient:
    """Maintains a persistent connection to a JBL MA series AVR."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.state: dict[str, Any] = {}
        self.model: int | None = None
        self.connected = False

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._read_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._supervisor_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._pending: dict[int, asyncio.Future[tuple[int, bytes]]] = {}
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------ public

    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)

        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    async def start(self) -> None:
        self._stop.clear()
        if self._supervisor_task is None or self._supervisor_task.done():
            self._supervisor_task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self._stop.set()
        if self._supervisor_task:
            self._supervisor_task.cancel()
            try:
                await self._supervisor_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self._close()

    async def async_test_connection(self, timeout: float = 5.0) -> int:
        """One-shot connect → init → read model byte → close. For config flow."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=timeout
        )
        try:
            packet = bytes([START_REQ, CMD_INIT, 0x01, REQ, END])
            writer.write(packet)
            await writer.drain()
            buf = bytearray()
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                chunk = await asyncio.wait_for(reader.read(64), timeout=remaining)
                if not chunk:
                    raise ConnectionError("AVR closed connection during init")
                buf.extend(chunk)
                frame = _extract_frame(buf)
                if frame and frame[2] == CMD_INIT and frame[3] == RSP_OK and frame[4] >= 1:
                    return frame[5]
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    # commands -----------------------------------------------------------------

    async def set_power(self, on: bool) -> None:
        await self._request(CMD_POWER, [0x01 if on else 0x00])

    async def set_dim(self, level: int) -> None:
        await self._request(CMD_DIM, [level & 0xFF])

    async def set_source(self, source_id: int) -> None:
        await self._request(CMD_SOURCE, [source_id & 0xFF])

    async def set_volume(self, vol: int) -> None:
        await self._request(CMD_VOLUME, [max(0, min(99, int(vol)))])

    async def set_mute(self, on: bool) -> None:
        await self._request(CMD_MUTE, [0x01 if on else 0x00])

    async def set_surround(self, mode_id: int) -> None:
        await self._request(CMD_SURROUND, [mode_id & 0xFF])

    async def set_party(self, on: bool) -> None:
        await self._request(CMD_PARTY, [0x01 if on else 0x00])

    async def set_party_volume(self, vol: int) -> None:
        await self._request(CMD_PARTY_VOL, [max(0, min(99, int(vol)))])

    async def set_treble(self, db: int) -> None:
        await self._request(CMD_TREBLE, [_encode_signed_db(db)])

    async def set_bass(self, db: int) -> None:
        await self._request(CMD_BASS, [_encode_signed_db(db)])

    async def set_room_eq(self, mode: int) -> None:
        await self._request(CMD_ROOM_EQ, [mode & 0xFF])

    async def set_dialog(self, on: bool) -> None:
        await self._request(CMD_DIALOG, [0x01 if on else 0x00])

    async def set_dolby_mode(self, mode: int) -> None:
        await self._request(CMD_DOLBY, [mode & 0xFF])

    async def set_drc(self, on: bool) -> None:
        await self._request(CMD_DRC, [0x01 if on else 0x00])

    async def send_ir(self, code: int) -> None:
        await self._request(CMD_IR, [(code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF])

    async def reboot(self) -> None:
        await self._request(CMD_REBOOT, [0xAA, 0xAA])

    async def factory_reset(self) -> None:
        await self._request(CMD_FACTORY, [0xAA, 0xAA])

    async def query_version(self, kind: int = REQ) -> None:
        await self._request(CMD_VERSION, [kind])

    # ------------------------------------------------------------ supervision

    async def _supervise(self) -> None:
        """Connect, hold the connection open, reconnect with backoff on failure."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                await self._open_and_run()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("JBL %s: connection error: %s", self.host, exc)
            self.connected = False
            self._notify()
            if self._stop.is_set():
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    async def _open_and_run(self) -> None:
        _LOGGER.debug("JBL %s: connecting", self.host)
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=10
        )
        self.connected = True
        self._read_task = asyncio.create_task(self._read_loop())
        try:
            await self._request(CMD_INIT, [REQ])
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("JBL %s: init failed: %s", self.host, exc)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        await self._refresh_all()
        self._notify()
        # Block until the read loop ends (peer closed or error).
        try:
            await self._read_task
        finally:
            await self._close()

    async def _close(self) -> None:
        for task in (self._heartbeat_task, self._read_task):
            if task and not task.done():
                task.cancel()
        self._heartbeat_task = self._read_task = None
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._reader = self._writer = None
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    # Heartbeat command per spec example: DataLen=0, no data bytes.
                    await self._send_with_response(
                        bytes([START_REQ, CMD_HEARTBEAT, 0x00, END]),
                        CMD_HEARTBEAT,
                        timeout=5.0,
                    )
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.debug("JBL %s: heartbeat failed: %s", self.host, exc)
                    if self._writer:
                        self._writer.close()
                    return
        except asyncio.CancelledError:
            pass

    async def _read_loop(self) -> None:
        assert self._reader is not None
        buf = bytearray()
        try:
            while True:
                chunk = await self._reader.read(1024)
                if not chunk:
                    _LOGGER.debug("JBL %s: peer closed", self.host)
                    return
                buf.extend(chunk)
                while True:
                    frame = _extract_frame(buf)
                    if frame is None:
                        break
                    self._handle_frame(frame)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("JBL %s: read loop ended: %s", self.host, exc)

    def _handle_frame(self, frame: bytes) -> None:
        cmd = frame[2]
        rsp = frame[3]
        datalen = frame[4]
        data = frame[5 : 5 + datalen]
        _LOGGER.debug(
            "JBL %s: rx cmd=%02x rsp=%02x data=%s", self.host, cmd, rsp, data.hex()
        )
        fut = self._pending.pop(cmd, None)
        if fut is not None and not fut.done():
            fut.set_result((rsp, data))
        if rsp == RSP_OK:
            self._update_state(cmd, data)
            self._notify()

    def _update_state(self, cmd: int, data: bytes) -> None:
        if not data:
            return
        if cmd == CMD_POWER:
            self.state["power"] = data[0] == 0x01
        elif cmd == CMD_DIM:
            self.state["dim"] = data[0]
        elif cmd == CMD_SOURCE:
            self.state["source"] = data[0]
        elif cmd == CMD_VOLUME:
            self.state["volume"] = data[0]
        elif cmd == CMD_MUTE:
            self.state["mute"] = data[0] == 0x01
        elif cmd == CMD_SURROUND:
            self.state["surround"] = data[0]
        elif cmd == CMD_PARTY:
            self.state["party"] = data[0] == 0x01
        elif cmd == CMD_PARTY_VOL:
            self.state["party_volume"] = data[0]
        elif cmd == CMD_TREBLE:
            self.state["treble"] = _decode_signed_db(data[0])
        elif cmd == CMD_BASS:
            self.state["bass"] = _decode_signed_db(data[0])
        elif cmd == CMD_ROOM_EQ:
            self.state["room_eq"] = data[0]
        elif cmd == CMD_DIALOG:
            self.state["dialog"] = data[0] == 0x01
        elif cmd == CMD_DOLBY:
            self.state["dolby_mode"] = data[0]
        elif cmd == CMD_DRC:
            self.state["drc"] = data[0] == 0x01
        elif cmd == CMD_STREAM and len(data) >= 2:
            self.state["stream_server"] = data[0]
            self.state["stream_state"] = data[1]
        elif cmd == CMD_INIT:
            self.model = data[0]
            self.state["model"] = data[0]
        elif cmd == CMD_VERSION and len(data) >= 1:
            kind = data[0]
            text = bytes(data[1:]).decode(errors="replace")
            self.state.setdefault("version", {})[kind] = text

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("JBL %s: listener raised", self.host)

    async def _refresh_all(self) -> None:
        for cmd in REFRESH_CMDS:
            try:
                await self._request(cmd, [REQ])
            except JBLError as exc:
                # AVR may legitimately reject e.g. party-mode on MA510.
                _LOGGER.debug("JBL %s: refresh cmd 0x%02x rejected: %s",
                              self.host, cmd, exc)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("JBL %s: refresh cmd 0x%02x failed: %s",
                              self.host, cmd, exc)

    # --------------------------------------------------------------- transport

    async def _request(self, cmd_id: int, data: list[int]) -> tuple[int, bytes]:
        packet = bytes([START_REQ, cmd_id, len(data), *data, END])
        return await self._send_with_response(packet, cmd_id)

    async def _send_with_response(
        self, packet: bytes, cmd_id: int, timeout: float = 10.0
    ) -> tuple[int, bytes]:
        if not self._writer or self._writer.is_closing():
            raise ConnectionError("Not connected to AVR")
        async with self._send_lock:
            loop = asyncio.get_running_loop()
            fut: asyncio.Future[tuple[int, bytes]] = loop.create_future()
            self._pending[cmd_id] = fut
            try:
                self._writer.write(packet)
                await self._writer.drain()
                rsp, data = await asyncio.wait_for(fut, timeout=timeout)
            finally:
                self._pending.pop(cmd_id, None)
            if rsp != RSP_OK:
                raise JBLError(f"AVR rejected cmd 0x{cmd_id:02x} with code 0x{rsp:02x}")
            return rsp, data


# ---------------------------------------------------------------- helpers


def _extract_frame(buf: bytearray) -> bytes | None:
    """Pop one complete response frame from buf, or return None if incomplete.

    Skips garbage and drops one byte at a time on bad framing until either
    a valid frame surfaces or the buffer doesn't yet have enough bytes.
    """
    while True:
        # Scan past anything that doesn't look like the header.
        while len(buf) >= 2:
            if buf[0] == START_RSP1 and buf[1] == START_RSP2:
                break
            del buf[0]
        if len(buf) < 5:
            return None
        datalen = buf[4]
        total = 5 + datalen + 1
        if len(buf) < total:
            return None
        if buf[total - 1] != END:
            # Bad framing; drop one byte and try again.
            del buf[0]
            continue
        frame = bytes(buf[:total])
        del buf[:total]
        return frame


def _encode_signed_db(db: int) -> int:
    db = max(-12, min(12, int(db)))
    return db if db >= 0 else 256 + db


def _decode_signed_db(byte: int) -> int:
    return byte if byte <= 12 else byte - 256
