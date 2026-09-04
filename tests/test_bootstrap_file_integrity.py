from __future__ import annotations

import threading
from pathlib import Path

from ultimate_stock_analyzer.bootstrap.file_integrity import (
    exclusive_run_lock,
    file_identity,
    unlink_if_owned,
)


def test_exclusive_run_lock_serializes_publishers(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def _first() -> None:
        with exclusive_run_lock(root, name=".test-publication.lock"):
            first_entered.set()
            assert release_first.wait(5)

    def _second() -> None:
        assert first_entered.wait(5)
        with exclusive_run_lock(root, name=".test-publication.lock"):
            second_entered.set()

    first = threading.Thread(target=_first)
    second = threading.Thread(target=_second)
    first.start()
    second.start()
    assert first_entered.wait(5)
    assert not second_entered.wait(0.1)

    release_first.set()
    first.join(5)
    second.join(5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert second_entered.is_set()


def test_owned_rollback_never_unlinks_replacement_inode(tmp_path: Path) -> None:
    path = tmp_path / "route.jsonl.gz"
    path.write_bytes(b"owned")
    owned_identity = file_identity(path, label="owned test output")

    path.unlink()
    path.write_bytes(b"replacement")

    assert not unlink_if_owned(path, identity=owned_identity)
    assert path.read_bytes() == b"replacement"
