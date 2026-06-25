from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Iterable, List, Optional

from config import settings
from pipeline import process_content_item


ProgressCallback = Optional[Callable[[int, int, Dict[str, Any]], None]]


def process_batch(
    items: Iterable[Dict[str, Any]],
    campaign_brief: Optional[Dict[str, Any]] = None,
    max_workers: int = 4,
    progress_callback: ProgressCallback = None,
) -> List[Dict[str, Any]]:
    item_list = list(items)
    if not item_list:
        return []

    worker_count = max(1, min(max_workers, len(item_list), settings.DEFAULT_BATCH_SIZE))
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(process_content_item, item, campaign_brief) for item in item_list]
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            if progress_callback:
                progress_callback(completed, len(item_list), result)

    return results
