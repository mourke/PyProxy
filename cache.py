from typing import Optional, NamedTuple
import datetime


class CacheResult(NamedTuple):
    data: bytes
    cached_date: datetime.datetime # the date on which the entry was cached
    expiration: datetime.datetime


cache: dict[str, CacheResult] = {}
cache_max_size = 200


def http_header_datestring_to_date(date_str: str) -> datetime.datetime:
    # %a = Day abbreviated. E.g. Sat
    # %d = Day number. E.g. 13
    # %b = Month abbreviated. E.g. Mar
    # %Y = Year full. E.g. 2021
    # %H = Hour padded in 24 hour time. E.g. 01 or 15
    # %M = Minute padded. E.g. 01 or 15
    # %S = Second padded. E.g. 01 or 15
    # %Z = Timezone. E.g. GMT
    return datetime.datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')


def cache_url(url: str, data: bytes, date_str: str, expiration_str: str):
    date = http_header_datestring_to_date(date_str)
    expiration = http_header_datestring_to_date(expiration_str)

    if is_cache_full():
        if not remove_expired_cache_entries(): # no entries expired so cache is still full
            remove_oldest_cache_entry()
    cache[url] = CacheResult(data, date, expiration)


def remove_oldest_cache_entry():
    oldest_entry: (str, datetime.datetime) = None
    for url, cache_result in cache.items():
        if (not oldest_entry) or cache_result.cached_date < oldest_entry[1]:
            oldest_entry = (url, cache_result.cached_date)

    if oldest_entry:
        del cache[oldest_entry[0]]


def remove_expired_cache_entries() -> bool:
    has_anything_changed = False
    now = datetime.datetime.now() # set now once before the loop so as to be fair in the comparison
    for url, cache_result in cache.items():
        if cache_result.expiration <= now:
            has_anything_changed = True
            del cache[url]

    return has_anything_changed


def is_cache_full():
    return len(cache) == cache_max_size


def data_for_url(url: str) -> Optional[bytes]:
    if url in cache:
        cache_result = cache[url]
        if cache_result.expiration > datetime.datetime.now():
            return cache_result.data
        else: # might as well remove from cache since it's expired
            del cache[url]
    return None
