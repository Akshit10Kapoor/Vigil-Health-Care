import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.append(str(Path(__file__).resolve().parents[2]))

from backend.config.settings import settings
from backend.event_store.integrity import record_verification, verify_chain


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the Vigil clinical event hash chain."
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Persist the verification result in chain_verification_logs.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit a single-line JSON result.",
    )
    args = parser.parse_args()

    url = (
        os.getenv("MIGRATION_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
        or settings.DATABASE_URL
    )
    engine = create_engine(url, pool_pre_ping=True)
    session = Session(bind=engine)
    try:
        result = verify_chain(session)
        if args.record:
            record_verification(session, result)
        payload = result.as_dict()
        print(
            json.dumps(payload, indent=None if args.compact else 2, sort_keys=True)
        )
        return 0 if result.valid else 1
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
