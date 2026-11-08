#!/usr/bin/env python3
"""Verified conditional HTTP cache for approved Trihexoct reference feeds.

This module is intentionally separate from the existing production builder.
It can be integrated into build_filter.py after the maintainer reviews the
integration guide. A stale cache is diagnostic only and is NEVER marked as
fresh evidence for overlap reconciliation.

Only exact HTTPS feed URLs supplied in reference_feeds.json are fetched.
Redirects must remain HTTPS and on the original feed hostname unless that
feed explicitly lists redirect_hosts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

USER_AGENT = "Trihexoct-Guardlux-TRIHEXOMEGA-FeedCache/2.0"
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
FQDN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\.?$", re.I)


class FeedCacheError(RuntimeError):
    pass


class SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]):
        super().__init__()
        self.allowed_hosts = {h.lower().rstrip(".") for h in allowed_hosts}

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or host not in self.allowed_hosts:
            raise FeedCacheError("redirect rejected: destination must be an approved HTTPS host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(value: str) -> str:
    cleaned = NAME_RE.sub("_", value).strip("._-")
    return cleaned[:80] or "feed"


def cache_base(cache_dir: Path, name: str, url: str) -> Path:
    # Include the exact source URL in the cache identity so renaming or changing
    # a feed URL cannot silently reuse another source's validators/content.
    key = hashlib.sha256((name + "\0" + url).encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{safe_name(name)}-{key}"


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            import os
            os.fsync(handle.fileno())
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_bytes(path, data)


def validate_feed_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise FeedCacheError("feed URL must be HTTPS and include a hostname")
    if parsed.username or parsed.password:
        raise FeedCacheError("credentials in feed URLs are prohibited")
    if parsed.port not in (None, 443):
        raise FeedCacheError("non-standard HTTPS ports are not allowed")
    if parsed.fragment:
        raise FeedCacheError("URL fragments are not allowed in feed URLs")
    return parsed.hostname.lower().rstrip(".")


def active_entry_count(text: str, fmt: str) -> int:
    count = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if fmt == "url-indicators":
            if line.startswith(("#", "!", "//")):
                continue
            parsed = urlparse(line)
            if parsed.scheme in {"http", "https"} and parsed.hostname:
                count += 1
            continue
        if fmt == "domains":
            if FQDN_RE.fullmatch(line.rstrip(".")):
                count += 1
            continue
        if line.startswith("!") or line.startswith("["):
            continue
        if line.startswith("#") and not line.startswith(("##", "#@#", "#?#", "#$#", "#@$#")):
            continue
        count += 1
    return count


def validate_bytes(data: bytes, feed: dict[str, Any]) -> tuple[str, int]:
    max_bytes = int(feed.get("max_bytes", 20_000_000))
    if len(data) > max_bytes:
        raise FeedCacheError(f"feed exceeded configured size cap ({max_bytes} bytes)")
    if len(data) < int(feed.get("minimum_bytes", 200)):
        raise FeedCacheError("feed is unexpectedly small")
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise FeedCacheError(f"feed is not valid UTF-8: {exc}") from exc
    if "\x00" in text[:4096]:
        raise FeedCacheError("feed appears to contain binary data")
    prefix = text[:4096].lstrip().lower()
    if "<html" in prefix or "<!doctype html" in prefix:
        raise FeedCacheError("feed endpoint returned HTML rather than feed text")
    fmt = str(feed.get("format", "adblock"))
    count = active_entry_count(text, fmt)
    minimum = int(feed.get("minimum_entries", 10))
    if count < minimum:
        raise FeedCacheError(f"feed has {count} active entries; minimum is {minimum}")
    return text, count


def load_cache(cache_dir: Path, name: str, url: str) -> tuple[bytes | None, dict[str, Any] | None]:
    base = cache_base(cache_dir, name, url)
    body_path = base.with_suffix(".txt")
    state_path = base.with_suffix(".json")
    if not body_path.exists() or not state_path.exists():
        return None, None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        body = body_path.read_bytes()
        if sha256_bytes(body) != state.get("sha256"):
            return None, None
        return body, state
    except (OSError, ValueError, TypeError):
        return None, None



def validate_registry_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    feeds = config.get("feeds") if isinstance(config, dict) else None
    if not isinstance(feeds, list) or not feeds:
        raise FeedCacheError("registry must contain a non-empty feeds array")
    names: set[str] = set()
    urls: set[str] = set()
    allowed_formats = {"adblock", "domains", "url-indicators"}
    known_groups = {"ads", "privacy", "security", "annoyance", "special-category", "compatibility"}
    for index, feed in enumerate(feeds):
        if not isinstance(feed, dict):
            raise FeedCacheError(f"feed entry {index} must be an object")
        for key in ("name", "url", "max_bytes", "format", "groups"):
            if key not in feed:
                raise FeedCacheError(f"feed entry {index} is missing {key}")
        name = str(feed["name"]).strip()
        url = str(feed["url"]).strip()
        if not name or name in names:
            raise FeedCacheError(f"empty or duplicate feed name: {name!r}")
        if not url or url in urls:
            raise FeedCacheError(f"empty or duplicate feed URL: {url!r}")
        validate_feed_url(url)
        if feed["format"] not in allowed_formats:
            raise FeedCacheError(f"unsupported feed format for {name}: {feed['format']!r}")
        if not isinstance(feed["max_bytes"], int) or not 200 <= feed["max_bytes"] <= 100_000_000:
            raise FeedCacheError(f"invalid max_bytes for {name}")
        if not isinstance(feed["groups"], list) or not set(feed["groups"]).issubset(known_groups):
            raise FeedCacheError(f"invalid groups for {name}")
        if "redirect_hosts" in feed and not isinstance(feed["redirect_hosts"], list):
            raise FeedCacheError(f"redirect_hosts must be an array for {name}")
        if "publisher_id" in feed and not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", str(feed["publisher_id"])):
            raise FeedCacheError(f"publisher_id must be a stable lowercase identifier for {name}")
        names.add(name)
        urls.add(url)
    required_groups = config.get("required_groups", {})
    if not isinstance(required_groups, dict) or not set(required_groups).issubset(known_groups):
        raise FeedCacheError("required_groups contains unsupported categories")
    return feeds


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, min(60.0, float(value)))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
            return max(0.0, min(60.0, (dt - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return None


def fetch_one(feed: dict[str, Any], cache_dir: Path, retries: int = 2, timeout: int = 25) -> dict[str, Any]:
    name = str(feed.get("name", "unnamed-feed"))
    url = str(feed.get("url", ""))
    host = validate_feed_url(url)
    redirects = {host}
    for item in feed.get("redirect_hosts", []):
        redirects.add(str(item).lower().rstrip("."))
    if not all(re.fullmatch(r"[a-z0-9.-]+", h) for h in redirects):
        raise FeedCacheError(f"{name}: invalid redirect host allowlist")

    cached_body, cached_state = load_cache(cache_dir, name, url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/plain, application/octet-stream;q=0.9, */*;q=0.1",
    }
    if cached_state:
        if cached_state.get("etag"):
            headers["If-None-Match"] = str(cached_state["etag"])
        if cached_state.get("last_modified"):
            headers["If-Modified-Since"] = str(cached_state["last_modified"])

    started = time.monotonic()
    attempts = max(0, min(int(retries), 4)) + 1
    last_error = "unknown fetch error"
    for attempt in range(1, attempts + 1):
        req = Request(url, headers=headers, method="GET")
        opener = build_opener(SafeRedirectHandler(redirects))
        try:
            with opener.open(req, timeout=max(3, min(int(timeout), 60))) as response:
                status = int(getattr(response, "status", 200))
                if status != 200:
                    raise FeedCacheError(f"unexpected HTTP status {status}")
                final_url = response.geturl()
                final_host = validate_feed_url(final_url)
                if final_host not in redirects:
                    raise FeedCacheError("final response host is not approved")
                length = response.headers.get("Content-Length")
                max_bytes = int(feed.get("max_bytes", 20_000_000))
                if length and length.isdigit() and int(length) > max_bytes:
                    raise FeedCacheError("Content-Length exceeds configured cap")
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise FeedCacheError("response exceeded configured cap")
                text, count = validate_bytes(data, feed)
                etag = response.headers.get("ETag")
                modified = response.headers.get("Last-Modified")
                digest = sha256_bytes(data)
                state = {
                    "schema_version": 1,
                    "name": name,
                    "url": url,
                    "final_url": final_url,
                    "sha256": digest,
                    "etag": etag,
                    "last_modified": modified,
                    "content_type": response.headers.get("Content-Type", ""),
                    "byte_count": len(data),
                    "active_entries": count,
                    "validated_at_utc": utc_now(),
                }
                base = cache_base(cache_dir, name, url)
                atomic_bytes(base.with_suffix(".txt"), data)
                atomic_json(base.with_suffix(".json"), state)
                return {
                    "name": name, "ok": True, "cache_status": "refreshed",
                    "coverage_eligible": True, "stale": False,
                    "active_entries": count, "byte_count": len(data), "sha256": digest,
                    "etag_present": bool(etag), "last_modified_present": bool(modified),
                    "final_url": final_url, "content_type": state["content_type"],
                    "etag": etag, "last_modified": modified,
                    "_validated_lines": text.splitlines(),
                    "attempts": attempt, "duration_seconds": round(time.monotonic() - started, 3),
                }
        except HTTPError as exc:
            if exc.code == 304:
                if cached_body is None or cached_state is None:
                    last_error = "server returned 304 but no verified local cache exists"
                    break
                try:
                    _, count = validate_bytes(cached_body, feed)
                except FeedCacheError as validation_error:
                    last_error = f"cached content failed validation after 304: {validation_error}"
                    break
                cached_state["last_confirmed_utc"] = utc_now()
                atomic_json(cache_base(cache_dir, name, url).with_suffix(".json"), cached_state)
                return {
                    "name": name, "ok": True, "cache_status": "not_modified_304",
                    "coverage_eligible": True, "stale": False,
                    "active_entries": count, "byte_count": len(cached_body),
                    "sha256": cached_state["sha256"], "etag_present": bool(cached_state.get("etag")),
                    "last_modified_present": bool(cached_state.get("last_modified")),
                    "final_url": cached_state.get("final_url", url),
                    "content_type": cached_state.get("content_type", ""),
                    "etag": cached_state.get("etag"), "last_modified": cached_state.get("last_modified"),
                    "_validated_lines": cached_body.decode("utf-8-sig").splitlines(),
                    "attempts": attempt, "duration_seconds": round(time.monotonic() - started, 3),
                }
            last_error = f"HTTP {exc.code}"
            retry_after = parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)
            if exc.code not in RETRYABLE_STATUS or attempt >= attempts:
                break
            time.sleep(retry_after if retry_after is not None else min(8.0, (2 ** (attempt - 1)) + random.uniform(0.05, 0.4)))
        except FeedCacheError as exc:
            # Content, redirect, and policy failures are deterministic; do not
            # retry invalid payloads or unsafe destinations.
            last_error = f"{type(exc).__name__}: {exc}"
            break
        except (URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, URLError) and isinstance(getattr(exc, "reason", None), FeedCacheError):
                break
            if attempt >= attempts:
                break
            time.sleep(min(8.0, (2 ** (attempt - 1)) + random.uniform(0.05, 0.4)))

    stale_available = cached_body is not None and cached_state is not None
    return {
        "name": name, "ok": False, "cache_status": "stale_diagnostic_only" if stale_available else "unavailable",
        "coverage_eligible": False, "stale": stale_available,
        "cached_sha256": cached_state.get("sha256") if stale_available else None,
        "last_validated_utc": cached_state.get("validated_at_utc") if stale_available else None,
        "attempts": attempts, "duration_seconds": round(time.monotonic() - started, 3),
        "error": last_error,
    }



def fetch_feed_compatible(feed: dict[str, Any], retries: int | None = None):
    """Adapter matching tools/build_filter.py's existing fetch_feed return shape.

    It is designed for an explicitly reviewed patch to the existing builder.
    Stale cache contents are never returned as coverage evidence.
    """
    cache_dir = Path(os.environ.get("TRIHEXOMEGA_FEED_CACHE_DIR", "reports/feed-cache"))
    result = fetch_one(feed, cache_dir, retries=feed.get("retries", 2) if retries is None else retries,
                       timeout=int(feed.get("timeout_seconds", 30)))
    lines = result.pop("_validated_lines", None)
    status = {
        "name": result.get("name", feed.get("name", "unnamed-feed")),
        "ok": bool(result.get("ok")),
        "format": feed.get("format", "adblock"),
        "coverage_mode": ("health-only; URL indicators are never treated as domain-wide coverage"
                          if feed.get("format") == "url-indicators" or feed.get("health_only")
                          else "coverage-index only; feed rules are never copied into output"),
        "bytes": result.get("byte_count", 0),
        "lines": len(lines) if lines is not None else 0,
        "active_lines": result.get("active_entries", 0),
        "sha256": result.get("sha256"),
        "final_url": result.get("final_url"),
        "content_type": result.get("content_type", ""),
        "etag": result.get("etag"),
        "last_modified": result.get("last_modified"),
        "attempts": result.get("attempts", 0),
        "duration_seconds": result.get("duration_seconds", 0.0),
        "cache_status": result.get("cache_status"),
        "coverage_eligible": bool(result.get("coverage_eligible")),
    }
    if not status["ok"]:
        status["error"] = result.get("error", "feed unavailable; stale cache excluded from coverage")
    return lines, status


def select_adaptive_workers(requested: int, history_path: Path, feed_count: int) -> tuple[int, dict[str, Any]]:
    """A conservative controller: back off on trouble; increase only after a healthy streak."""
    requested = max(1, min(int(requested), 8, max(1, feed_count)))
    state = {"last_workers": requested, "healthy_streak": 0, "schema_version": 1}
    if history_path.exists():
        try:
            loaded = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("schema_version") == 1:
                state.update({k: loaded[k] for k in ("last_workers", "healthy_streak") if k in loaded})
        except (OSError, ValueError, TypeError):
            pass
    previous_workers = max(1, min(int(state.get("last_workers", requested)), 8, max(1, feed_count)))
    streak = max(0, min(int(state.get("healthy_streak", 0)), 10))
    # Failures/throttling are recorded by the previous run. The controller
    # deliberately lowers concurrency faster than it raises it.
    previous_report = history_path.with_name(history_path.stem + "-last-report.json")
    degraded = False
    if previous_report.exists():
        try:
            previous = json.loads(previous_report.read_text(encoding="utf-8"))
            rows = previous.get("feeds", [])
            degraded = any((not row.get("ok")) or row.get("attempts", 1) > 1 or "429" in str(row.get("error", "")) for row in rows)
        except (OSError, ValueError, TypeError):
            degraded = True
    if degraded:
        chosen = max(2, previous_workers - 2)
        streak = 0
        reason = "backoff_after_previous_failures_or_retries"
    elif streak >= 2:
        chosen = min(requested, previous_workers + 1)
        streak += 1
        reason = "gradual_increase_after_healthy_streak"
    else:
        chosen = min(requested, previous_workers)
        streak += 1
        reason = "conservative_warmup"
    chosen = max(1, min(chosen, requested, 8, max(1, feed_count)))
    return chosen, {"schema_version": 1, "last_workers": chosen, "healthy_streak": streak,
                    "selection_reason": reason}


def run_registry(registry_path: Path, cache_dir: Path, report_path: Path, workers: int, history_path: Path | None = None) -> dict[str, Any]:
    config = json.loads(registry_path.read_text(encoding="utf-8"))
    feeds = validate_registry_config(config)
    names = [str(f.get("name", "")) for f in feeds]
    if len(names) != len(set(names)):
        raise FeedCacheError("feed names must be unique for cache isolation")
    history_path = history_path or report_path.with_name("feed-cache-controller.json")
    max_workers, controller_state = select_adaptive_workers(workers, history_path, len(feeds))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_one, feed, cache_dir): feed for feed in feeds}
        for future in as_completed(futures):
            feed = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # isolate one feed failure from the rest
                results.append({"name": feed.get("name", "unnamed-feed"), "ok": False,
                                "coverage_eligible": False, "cache_status": "error",
                                "error": f"{type(exc).__name__}: {exc}"})
    results.sort(key=lambda row: row["name"].casefold())
    # Never place full reference-feed contents into a machine-readable report.
    for row in results:
        row.pop("_validated_lines", None)
    by_name = {str(f["name"]): f for f in feeds}
    successful = sum(bool(x.get("ok")) and bool(x.get("coverage_eligible")) for x in results)
    required_failures = [x["name"] for x in results if by_name.get(x["name"], {}).get("required") and not x.get("ok")]
    report = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "mode": "conditional-cache-preflight",
        "selected_workers": max_workers,
        "concurrency_controller": controller_state,
        "feed_count": len(feeds),
        "validated_fresh_or_304_count": successful,
        "failed_or_stale_count": len(feeds) - successful,
        "required_failures": required_failures,
        "coverage_credit_policy": "Only fresh HTTP 200 or verified HTTP 304 results are coverage-eligible. Stale cache is diagnostic only.",
        "feeds": results,
    }
    atomic_json(report_path, report)
    atomic_json(history_path, controller_state)
    # Keep a compact last-run report for the next controller decision.
    atomic_json(history_path.with_name(history_path.stem + "-last-report.json"), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("config/reference_feeds.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("reports/feed-cache"))
    parser.add_argument("--report", type=Path, default=Path("reports/feed-cache-report.json"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--controller-state", type=Path, default=Path("reports/feed-cache-controller.json"))
    args = parser.parse_args()
    try:
        report = run_registry(args.registry, args.cache_dir, args.report, args.workers, args.controller_state)
    except (OSError, ValueError, FeedCacheError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: report[k] for k in ("mode", "feed_count", "validated_fresh_or_304_count", "failed_or_stale_count", "required_failures")}, indent=2))
    return 0 if not report["required_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
