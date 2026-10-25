from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging
import httpx

logger = logging.getLogger(__name__)

FUELHH_URL = 'https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream'
WINDFOR_URL = 'https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream'

# In-memory cache for fetched raw datasets to avoid redundant external network calls
# Key: (dataset_name, start_date, end_date) -> {'data': list, 'fetched_at': datetime, 'latency_ms': float}
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes


def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
    """Normalizes API payload into a list of row dicts."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ('data', 'items', 'results', 'response'):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return []


async def fetch_fuelhh_raw(start_date: str, end_date: str, client: Optional[httpx.AsyncClient] = None, force_refresh: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetches FUELHH actual generation for fuelType=WIND from Elexon BMRS stream.
    """
    cache_key = f'fuelhh:{start_date}:{end_date}'
    now = datetime.now(timezone.utc)
    if not force_refresh and cache_key in _cache:
        entry = _cache[cache_key]
        if (now - entry['fetched_at']).total_seconds() < CACHE_TTL_SECONDS:
            return entry['data'], entry['meta']

    params = {
        'settlementDateFrom': start_date,
        'settlementDateTo': end_date,
        'fuelType': 'WIND'
    }

    t0 = datetime.now(timezone.utc)
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=35.0)
        close_client = True

    try:
        response = await client.get(FUELHH_URL, params=params)
        latency = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        response.raise_for_status()
        rows = _extract_rows(response.json())
        meta = {
            'status': 'ok',
            'status_code': response.status_code,
            'latency_ms': round(latency, 1),
            'fetched_at': now.isoformat(),
            'record_count': len(rows),
            'endpoint': FUELHH_URL
        }
        _cache[cache_key] = {'data': rows, 'meta': meta, 'fetched_at': now}
        return rows, meta
    except Exception as exc:
        logger.error(f"Failed to fetch FUELHH from Elexon: {exc}")
        meta = {
            'status': 'error',
            'error_message': str(exc),
            'latency_ms': (datetime.now(timezone.utc) - t0).total_seconds() * 1000,
            'fetched_at': now.isoformat(),
            'record_count': 0,
            'endpoint': FUELHH_URL
        }
        raise
    finally:
        if close_client:
            await client.aclose()


async def fetch_windfor_raw(start_date: str, end_date: str, client: Optional[httpx.AsyncClient] = None, force_refresh: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetches WINDFOR forecast generation from Elexon BMRS stream.
    To ensure Day-Ahead vintages published prior to cutoff (e.g. D-1 or earlier) are retrieved
    for the start_date, the publishDateTimeFrom query window extends back 3 days before start_date.
    """
    cache_key = f'windfor:{start_date}:{end_date}'
    now = datetime.now(timezone.utc)
    if not force_refresh and cache_key in _cache:
        entry = _cache[cache_key]
        if (now - entry['fetched_at']).total_seconds() < CACHE_TTL_SECONDS:
            return entry['data'], entry['meta']

    # Query window: start 3 days prior to cover D-1 and earlier vintages for delivery on start_date
    start_dt = datetime.fromisoformat(start_date)
    query_start = (start_dt - timedelta(days=3)).strftime('%Y-%m-%d')
    params = {
        'publishDateTimeFrom': f'{query_start}T00:00:00Z',
        'publishDateTimeTo': f'{end_date}T23:59:59Z'
    }

    t0 = datetime.now(timezone.utc)
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=45.0)
        close_client = True

    try:
        response = await client.get(WINDFOR_URL, params=params)
        latency = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        response.raise_for_status()
        rows = _extract_rows(response.json())
        meta = {
            'status': 'ok',
            'status_code': response.status_code,
            'latency_ms': round(latency, 1),
            'fetched_at': now.isoformat(),
            'record_count': len(rows),
            'endpoint': WINDFOR_URL,
            'query_publish_window': f"{params['publishDateTimeFrom']} to {params['publishDateTimeTo']}"
        }
        _cache[cache_key] = {'data': rows, 'meta': meta, 'fetched_at': now}
        return rows, meta
    except Exception as exc:
        logger.error(f"Failed to fetch WINDFOR from Elexon: {exc}")
        meta = {
            'status': 'error',
            'error_message': str(exc),
            'latency_ms': (datetime.now(timezone.utc) - t0).total_seconds() * 1000,
            'fetched_at': now.isoformat(),
            'record_count': 0,
            'endpoint': WINDFOR_URL
        }
        raise
    finally:
        if close_client:
            await client.aclose()


def get_cached_metadata() -> Dict[str, Any]:
    """Returns cached upstream connectivity and freshness metadata."""
    return {
        key: entry.get('meta') for key, entry in _cache.items()
    }


def clear_cache():
    """Clears raw API cache."""
    _cache.clear()
