"""Uruchamiaj pytest także na Windows z zależnościami Home Assistant."""

from __future__ import annotations

from contextlib import suppress
import sys
from pathlib import Path
import socket
from types import ModuleType

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


def _install_windows_posix_stubs() -> None:
    """Uzupełnij uniksowe importy używane tylko przez runner testowego HA."""
    if sys.platform != "win32":
        return
    if "fcntl" not in sys.modules:
        fcntl = ModuleType("fcntl")
        fcntl.LOCK_EX = 2
        fcntl.LOCK_NB = 4
        fcntl.LOCK_UN = 8
        fcntl.flock = lambda _descriptor, _operation: None
        sys.modules["fcntl"] = fcntl
    if "resource" not in sys.modules:
        resource = ModuleType("resource")
        resource.RLIMIT_NOFILE = 7
        resource.getrlimit = lambda _resource: (2048, 2048)
        resource.setrlimit = lambda _resource, _limits: None
        sys.modules["resource"] = resource


def _install_windows_socketpair() -> None:
    """Pozwól pętli asyncio utworzyć lokalną parę mimo blokady sieci testów."""
    if sys.platform != "win32":
        return
    original_socket = socket.socket

    def socketpair(
        family: int = socket.AF_INET,
        kind: int = socket.SOCK_STREAM,
        protocol: int = 0,
    ) -> tuple[socket.socket, socket.socket]:
        listener = original_socket(family, kind, protocol)
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            address, port = listener.getsockname()[:2]
            client = original_socket(family, kind, protocol)
            try:
                client.setblocking(False)
                with suppress(BlockingIOError, InterruptedError):
                    client.connect((address, port))
                client.setblocking(True)
                descriptor, _ = listener._accept()
                server = original_socket(
                    family,
                    kind,
                    protocol,
                    fileno=descriptor,
                )
            except BaseException:
                client.close()
                raise
        finally:
            listener.close()
        return server, client

    socket.socketpair = socketpair


_install_windows_posix_stubs()
_install_windows_socketpair()

import pytest  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
