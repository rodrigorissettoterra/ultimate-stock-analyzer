from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int


def resolve_run_directory(run_dir: str | Path) -> Path:
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"bootstrap run directory is not a directory: {root}")
    return root


def contained_file_path(root: Path, relative_path: str, *, label: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError(f"{label} path must be relative: {relative_path}")
    candidate = Path(os.path.abspath(root / relative))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes bootstrap run directory: {relative_path}") from exc
    assert_no_symlink_components(root, candidate.parent)
    return candidate


def ensure_contained_directory(root: Path, relative: Path) -> Path:
    if relative.is_absolute():
        raise ValueError(f"bootstrap output directory must be relative: {relative}")
    candidate = Path(os.path.abspath(root / relative))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"bootstrap output directory escapes run directory: {relative}") from exc

    current = root
    for part in candidate.relative_to(root).parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            current.mkdir()
            info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ValueError(
                f"bootstrap output directory contains unsafe path component: {current}"
            )
    return candidate


def assert_no_symlink_components(root: Path, directory: Path) -> None:
    try:
        relative = directory.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes bootstrap run directory: {directory}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"unsafe bootstrap path component: {current}")


def read_regular_file_no_follow(path: Path, *, label: str) -> bytes:
    fd, _identity = open_regular_file_no_follow(path, label=label)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def open_regular_file_no_follow(path: Path, *, label: str) -> tuple[int, FileIdentity]:
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{label} not found: {path}") from exc
    if stat.S_ISLNK(before.st_mode):
        raise ValueError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file: {path}")

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"unable to open {label} without following symlinks: {path}") from exc

    try:
        after = os.fstat(fd)
        if not stat.S_ISREG(after.st_mode):
            raise ValueError(f"{label} must remain a regular file: {path}")
        if before.st_dev != after.st_dev or before.st_ino != after.st_ino:
            raise ValueError(f"{label} changed while being opened: {path}")
        return fd, FileIdentity(device=after.st_dev, inode=after.st_ino)
    except Exception:
        os.close(fd)
        raise


def existing_regular_file_bytes(path: Path, *, label: str) -> bytes | None:
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    return read_regular_file_no_follow(path, label=label)


def write_exclusive_temp_bytes(
    root: Path,
    directory: Path,
    *,
    prefix: str,
    suffix: str,
    content: bytes,
) -> Path:
    fd, raw_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    path = Path(raw_path)
    try:
        resolved_path = path.resolve(strict=True)
        try:
            resolved_path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"staging path escaped bootstrap run directory: {path}") from exc
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"staging path is not a regular file: {path}")
        with os.fdopen(fd, "wb", closefd=True) as file:
            fd = -1
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        return path
    except Exception:
        if fd >= 0:
            os.close(fd)
        unlink_regular_file_if_present(path)
        raise


def file_identity(path: Path, *, label: str) -> FileIdentity:
    fd, identity = open_regular_file_no_follow(path, label=label)
    os.close(fd)
    return identity


def unlink_if_owned(path: Path, *, identity: FileIdentity) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_dev != identity.device
        or info.st_ino != identity.inode
    ):
        return False
    path.unlink()
    return True


def unlink_regular_file_if_present(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode):
        path.unlink(missing_ok=True)
        return
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"refusing to unlink non-regular path: {path}")
    path.unlink(missing_ok=True)


@contextmanager
def exclusive_run_lock(root: Path, *, name: str) -> Iterator[None]:
    if "/" in name or "\\" in name or name in {"", ".", ".."}:
        raise ValueError(f"invalid bootstrap lock name: {name!r}")
    lock_path = root / name

    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    try:
        before = lock_path.lstat()
    except FileNotFoundError:
        before = None
    else:
        if stat.S_ISLNK(before.st_mode):
            raise ValueError(f"bootstrap publication lock must not be a symlink: {lock_path}")
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"bootstrap publication lock must be a regular file: {lock_path}")

    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ValueError(f"unable to open bootstrap publication lock: {lock_path}") from exc

    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError(f"bootstrap publication lock is not a regular file: {lock_path}")
        current = lock_path.lstat()
        if stat.S_ISLNK(current.st_mode) or not stat.S_ISREG(current.st_mode):
            raise ValueError(f"bootstrap publication lock path changed unsafely: {lock_path}")
        if current.st_dev != opened.st_dev or current.st_ino != opened.st_ino:
            raise ValueError(f"bootstrap publication lock changed while opening: {lock_path}")

        _lock_file_descriptor(fd)
        try:
            yield
        finally:
            _unlock_file_descriptor(fd)
    finally:
        os.close(fd)


def _lock_file_descriptor(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
            os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        return

    import fcntl

    fcntl.flock(fd, fcntl.LOCK_EX)


def _unlock_file_descriptor(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)
