import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DigestBuilder:
    @staticmethod
    def queue_for_digest(gap: Dict[str, Any]):
        # Stub for queuing routine/documentation gaps for a daily digest
        ward_id = gap.get("ward_id")
        severity = gap.get("severity")
        logger.info(f"[DIGEST QUEUE] Added {severity} gap for {ward_id} to daily digest.")
        print(f"[DIGEST QUEUE] Added {severity} gap for {ward_id} to daily digest.")
