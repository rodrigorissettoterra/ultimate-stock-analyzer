from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime

from ultimate_stock_analyzer.backtesting.raw_price_provenance import (
    bootstrap_raw_price_fingerprint,
    raw_price_fingerprint,
)
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.market.prices import PriceBar

NOW = datetime(2026, 9, 3, tzinfo=UTC)


def test_bootstrap_price_fingerprint_matches_event_price_fingerprint(tmp_path) -> None:
    run_dir = tmp_path / "bootstrap" / "fingerprint-test"
    price_path = run_dir / "normalized/b3/cotahist_2024.jsonl.gz"
    price_path.parent.mkdir(parents=True)

    bars = [
        PriceBar(
            ticker="TEST3",
            trade_date=date(2024, 1, 2),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=1000.0,
            trades=10,
            quantity=100,
            isin="BRTESTACNOR0",
        ),
        PriceBar(
            ticker="TEST3",
            trade_date=date(2024, 1, 3),
            open=10.5,
            high=12.0,
            low=10.0,
            close=11.5,
            volume=1200.0,
            trades=12,
            quantity=110,
            isin="BRTESTACNOR0",
        ),
    ]
    with gzip.open(price_path, "wt", encoding="utf-8") as file:
        for bar in bars:
            payload = asdict(bar)
            payload["trade_date"] = bar.trade_date.isoformat()
            file.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
            file.write("\n")

    content = price_path.read_bytes()
    artifact = BootstrapArtifact(
        name="b3_cotahist",
        source="B3_COTAHIST",
        path="normalized/b3/cotahist_2024.jsonl.gz",
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=len(bars),
        reference_year=2024,
        raw=False,
    )
    manifest = PublicDataBootstrapManifest(
        run_id="fingerprint-test",
        status="COMPLETE",
        started_at=NOW,
        completed_at=NOW,
        start_year=2024,
        end_year=2024,
        requested_tickers=["TEST3"],
        statements=["BPA", "BPP", "DRE"],
        artifacts=[artifact],
    )
    (run_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )

    dataset = BootstrapDataset(run_dir)
    bootstrap_digest = bootstrap_raw_price_fingerprint(
        dataset,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        tickers=["TEST3"],
    )

    assert bootstrap_digest == raw_price_fingerprint(bars)
