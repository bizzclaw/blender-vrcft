"""OSC capture logger. Writes one line per inbound message to a file."""
import os
import threading
from datetime import datetime, timezone

DEFAULT_MAX_BYTES = 50 * 1024 * 1024


class CaptureWriter:
    def __init__(self, path, max_bytes=DEFAULT_MAX_BYTES):
        self.path = path
        self.max_bytes = max_bytes
        self.bytes_written = 0
        self._f = None
        self._lock = threading.Lock()
        self.truncated = False

    def open(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
        self._f = open(self.path, "a", encoding="utf-8", buffering=1)
        header = (
            f"# vrcft capture started "
            f"{datetime.now(timezone.utc).isoformat()}\n"
            f"# columns: iso8601_utc\\taddress\\ttype_tags\\tvalues\n"
        )
        self._f.write(header)
        self.bytes_written += len(header)

    def write(self, address, args):
        with self._lock:
            if self._f is None:
                return
            if self.bytes_written >= self.max_bytes:
                if not self.truncated:
                    self._f.write("# capture truncated: max_bytes reached\n")
                    self.truncated = True
                return
            ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            type_tags = ",".join(type(a).__name__ for a in args) or "-"
            values = " ".join(_fmt(a) for a in args) if args else "-"
            line = f"{ts}\t{address}\t{type_tags}\t{values}\n"
            try:
                self._f.write(line)
                self.bytes_written += len(line)
            except OSError:
                pass

    def close(self):
        with self._lock:
            if self._f is not None:
                try:
                    self._f.write(
                        f"# vrcft capture ended "
                        f"{datetime.now(timezone.utc).isoformat()} "
                        f"({self.bytes_written} bytes)\n"
                    )
                    self._f.close()
                except OSError:
                    pass
                self._f = None


def _fmt(value):
    if isinstance(value, float):
        return f"{value:.6f}"
    return repr(value)
