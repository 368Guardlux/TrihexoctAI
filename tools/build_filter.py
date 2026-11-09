#!/usr/bin/env python3
"""Build the Trihexoct supplementary Brave list with conservative feed reconciliation.

Downloaded feeds are treated as untrusted UTF-8 text. The builder never executes them
or republishes their full contents; it only indexes simple coverage for de-duplication.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / 'src' / 'modules'
FEED_CONFIG = ROOT / 'config' / 'reference_feeds.json'
BASELINE_PATH = ROOT / 'reports' / 'reference-feed-baseline.json'
PROJECT_VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
UA = 'Trihexoct-Guardlux-Filter-Builder/2.0 (+https://github.com/368Guardlux/Trihexoct)'
OVERLAP_POLICY_VERSION = '2.1'
META_PATH = ROOT / 'Trihexoct.meta.json'
DELTA_PATH = ROOT / 'reports' / 'rule-delta.json'
BANNED = (
    '##+js(', '#@#+js(', '$csp=', ':xpath(', ':has-text(', '$websocket', '$webtransport',
    '$important', 'window-open-defuser', 'abort-on-property-read', 'set-constant, navigator.',
    'set-cookie,', 'set-local-storage-item,', 'prevent-addEventListener',
)
DANGEROUS_PARAMS = {
    'session','sessionid','session_id','user','user_id','visitor','visitor_id','device','device_id',
    'token','access_token','refresh_token','auth','code','state','redirect','redirect_uri','return',
    'return_url','next','continue','destination','deep_link','deeplink','app_link','source','ref',
    'ref_url','referrer','referer'
}
KNOWN_PARAM_REGEX = {
    '/^utm_/', '/^utm_/i', '/^utm_(source|medium|campaign|term|content|id|referrer|name)$/i',
    '/^(_ga|_gl)$/i', '/^(fbclid|fb_action_ids|fb_ref|fb_source)$/i',
    '/^(gclid|gclsrc|dclid|wbraid|gbraid|msclkid|yclid|twclid|ttclid)$/i',
    '/^(soc_src|soc_trk)$/i', '/^gad_(campaignid|groupid|source)$/i'
}
RISKY_UI = ('paywall','premium-content','subscribe-overlay','cookie-consent','cookie-banner','cookiebot',
            'onetrust','didomi','usercentrics','newsletter','exit-intent','modal','overlay','disqus','comment',
            'social','instagram-media','twitter-tweet','twitter-timeline','reddit-embed','floating-video',
            'sticky-video','video-pip','video-player','sticky-player','sticky-header','app-install','smart-banner',
            'onesignal-popover','onesignal-slidedown','gdpr','consent','push-notification','open-in-app','checkout','login')
RESOURCE_TYPES = {'script','image','stylesheet','font','media','object','subdocument','xmlhttprequest','ping','websocket','other','document'}
DOMAIN_RE = re.compile(r'^\|\|(?P<host>[a-z0-9.-]+)\^(?:\$(?P<opts>[^\s]+))?$', re.I)
PARAM_RE = re.compile(r'^\*?\$removeparam=(?P<param>[a-z0-9_.-]+)$', re.I)
PARAM_PREFIX_RE = re.compile(r'^\*?\$removeparam=/\^(?P<prefix>[a-z0-9_]+)', re.I)
FQDN_RE = re.compile(r'^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\.?$', re.I)
CORE_HOSTS = {
    'google.com','googleapis.com','gstatic.com','facebook.com','facebook.net','connect.facebook.net',
    'instagram.com','whatsapp.com','youtube.com','discord.com','github.com','paypal.com','stripe.com',
    'recaptcha.net','hcaptcha.com','challenges.cloudflare.com','cloudflare.com','firebaseio.com',
    'firebaseapp.com','amazonaws.com','cloudfront.net','akamaihd.net','akamai.net','intercom.com',
    'intercom.io','hubspot.com','hubspot.net','onesignal.com','braze.com','appboy.com','perimeterx.net',
    'humansecurity.com','datadome.co','riskified.com','forter.com','threatmetrix.com','sift.com',
    'siftscience.com','arkoselabs.com'
}


def active(line: str) -> bool:
    s=line.strip()
    return bool(s) and not s.startswith('!')


def rule_category(line: str) -> str:
    """Return the project's stable category name for one active filter rule."""
    s=line.strip(); low=s.lower()
    if '$removeparam=' in low:
        return 'url_parameter'
    if '##' in s:
        return 'cosmetic'
    if s.startswith('||'):
        return 'network'
    if s.startswith(('/', '*/')):
        return 'path_or_regex'
    return 'other'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_rule(line: str) -> str | None:
    s=line.strip(); low=s.lower()
    if not s or s.startswith('!'): return None
    for token in BANNED:
        if token.lower() in low: return f'prohibited or non-portable behavior: {token}'
    if low.startswith('@@'): return 'allow rules are not included in the supplementary deny list'
    if re.search(r'(?:\$|,)\s*important(?:,|$)', low): return 'important override is excluded'
    if re.match(r'^\|\|(?:\d{1,3}\.){3}\d{1,3}',s) or re.match(r'^\|\|\[[0-9a-f:]+\]',s,re.I): return 'raw IP-address blocking is excluded'
    if '$removeparam=' in low:
        value=s.split('$removeparam=',1)[1].split(',',1)[0].strip()
        if value.startswith('/') and value.lower() not in KNOWN_PARAM_REGEX:
            return 'unreviewed parameter regex is excluded'
        if not value: return 'empty removeparam value'
        if not value.startswith('/') and value.lower() in DANGEROUS_PARAMS: return 'credential/session/routing parameter removal is excluded'
    if '##' in s:
        selector=s.split('##',1)[1].lower()
        if not selector: return 'empty cosmetic selector'
        if any(term in selector for term in RISKY_UI): return 'consent, paywall, login, comments, or video UI hiding is excluded'
        if any(term in selector for term in (':xpath(',':has-text(',':upward(',':style(',':remove(',':remove-attr(')):
            return 'extended or behavior-changing cosmetic syntax is excluded'
        if selector.strip() in ('.modal','.overlay','[class*=modal]','[class*=overlay]','[class*="modal"]','[class*="overlay"]'):
            return 'generic modal or overlay hiding is excluded'
    # Keep generic path filters scoped to third-party requests; this avoids disabling
    # first-party application endpoints whose paths happen to contain words like 'track'.
    if s.startswith('*/') and '$' in s:
        opts=s.split('$',1)[1].split(',')
        if not any(o.strip().lower() in ('third-party','3p') for o in opts):
            return 'path-based network rules must be third-party scoped'
    # Slash-delimited regex filters can match URLs on many unrelated hosts. Require
    # explicit third-party scope even when the pattern is path-oriented.
    if s.startswith('/') and '/$' in s:
        opts=s.rsplit('/$',1)[1].split(',')
        if not any(o.strip().lower() in ('third-party','3p') for o in opts):
            return 'regex network rules must be third-party scoped'
    # Reject speculative regexes that match many unrelated hosts/endpoints.
    if s.startswith('/') and 'https?' in low and ('.*' in low or '[^' in low):
        return 'unbounded cross-site URL regex is excluded; use a named host or explicit path'
    if s.startswith('||'):
        head=s[2:].split('$',1)[0]
        host=head.split('/',1)[0].removesuffix('^')
        if '*' in host: return 'wildcard hostnames are excluded'
        if not re.fullmatch(r'[a-z0-9.-]+',host,re.I) or host.count('.')<1: return 'malformed or too-broad hostname rule'
        if host.lower().rstrip('.') in CORE_HOSTS and '/' not in head: return 'whole-domain block of a common functional service is excluded'
        # Ensure block is third-party scoped. Host/path may be specific; the build normalizes known simple rules.
        opts=s.split('$',1)[1].split(',') if '$' in s else []
        if not any(o.strip().lower() in ('third-party','3p') for o in opts):
            return 'network deny rule must be third-party scoped'
    return None


def normalize_rule(line: str) -> str:
    """Normalize only safe, deterministic syntax; do not rewrite semantics broadly."""
    s = line.strip()
    if not s or s.startswith('!'):
        return s
    # Case-fold literal query parameter names: those names are case-insensitive in URLs.
    if '$removeparam=' in s.lower():
        prefix, value = s.split('$removeparam=', 1)
        value = value.strip()
        if value and not value.startswith('/'):
            value = value.lower()
        s = prefix + '$removeparam=' + value
        if s.startswith('$removeparam='):
            s = '*' + s
        return s
    # Host-based network rules are always third-party scoped in this supplement.
    if s.startswith('||'):
        if '$' not in s:
            s += '$third-party'
        else:
            base, opt_text = s.split('$', 1)
            options = [o.strip() for o in opt_text.split(',') if o.strip()]
            if not any(o.lower() in ('third-party', '3p') for o in options):
                options.append('third-party')
            options = ['third-party' if o.lower() == '3p' else o for o in options]
            s = base + '$' + ','.join(dict.fromkeys(options))
        return s
    # Broad path patterns must be third-party only as well. Do not add a domain-wide
    # pattern or a global API override to compensate for unsupported syntax.
    if s.startswith('*/'):
        if '$' not in s:
            s += '$third-party'
        else:
            base, opt_text = s.split('$', 1)
            options = [o.strip() for o in opt_text.split(',') if o.strip()]
            if not any(o.lower() in ('third-party', '3p') for o in options):
                options.append('third-party')
            options = ['third-party' if o.lower() == '3p' else o for o in options]
            s = base + '$' + ','.join(dict.fromkeys(options))
    return s


def simple_host_rule(line: str):
    m=DOMAIN_RE.match(line.strip())
    if not m: return None
    host=m.group('host').lower().rstrip('.')
    if '*' in host or not FQDN_RE.fullmatch(host): return None
    opts=set()
    if m.group('opts'):
        for x in m.group('opts').split(','):
            x=x.strip().lower()
            if x in ('3p','third-party'): x='third-party'
            if x in ('1p','first-party'): x='first-party'
            if x=='xhr': x='xmlhttprequest'
            opts.add(x)
    if any(x.startswith(('redirect=','removeparam=','csp=','permissions=','denyallow=','method=')) for x in opts): return None
    if any(x not in RESOURCE_TYPES|{'third-party','first-party','match-case'} and not x.startswith('domain=') for x in opts): return None
    return host,opts


def domain_covers(source_rule: str, target_rule: str) -> bool:
    src=simple_host_rule(source_rule); dst=simple_host_rule(target_rule)
    if not src or not dst: return False
    sh,so=src; th,to=dst
    if not (th==sh or th.endswith('.'+sh)): return False
    if any(x.startswith('domain=') for x in so): return False
    src_first='first-party' in so; src_third='third-party' in so
    dst_first='first-party' in to; dst_third='third-party' in to
    if src_first and not dst_first: return False
    if src_third and not dst_third: return False
    src_types=so&RESOURCE_TYPES; dst_types=to&RESOURCE_TYPES
    if src_types and (not dst_types or not dst_types.issubset(src_types)): return False
    return True


def param_name(line: str):
    m=PARAM_RE.match(line.strip())
    return m.group('param').lower() if m else None


def param_prefix(line: str):
    m=PARAM_PREFIX_RE.match(line.strip())
    return m.group('prefix').lower() if m else None


def feed_entry_active(line: str, fmt: str) -> bool:
    """Count actual feed entries by declared format, not headings/comments/HTML."""
    s=line.strip()
    if not s or s.startswith('!'):
        return False
    if fmt == 'domains':
        return FQDN_RE.fullmatch(s.rstrip('.')) is not None
    if fmt == 'url-indicators':
        parsed=urlparse(s)
        return parsed.scheme in ('http','https') and bool(parsed.hostname)
    if s.startswith('['):
        return False
    if s.startswith('#') and not s.startswith(('##','#@#','#?#','#$#','#@$#')):
        return False
    return True


def fetch_feed(feed: dict, retries: int | None = None):
    """Fetch one approved reference feed with bounded retries and strict content checks.

    Feed text is untrusted data. It is never evaluated and never copied wholesale to output.
    Retry transient network/server errors, but do not retry a feed that returned invalid content.
    """
    url = feed['url']
    parsed = urlparse(url)
    started = time.monotonic()
    if parsed.scheme != 'https' or not parsed.hostname:
        return None, {'name': feed['name'], 'ok': False, 'attempts': 0, 'error': 'feed URL must use HTTPS'}
    attempts_allowed = int(feed.get('retries', 2) if retries is None else retries)
    attempts_allowed = max(0, min(attempts_allowed, 5))
    max_bytes = int(feed.get('max_bytes', 20_000_000))
    last_error = 'unknown fetch error'
    for attempt in range(1, attempts_allowed + 2):
        try:
            req = Request(url, headers={
                'User-Agent': UA,
                'Accept': 'text/plain,application/octet-stream;q=0.8,*/*;q=0.2',
                'Cache-Control': 'no-cache'
            })
            with urlopen(req, timeout=int(feed.get('timeout_seconds', 30))) as response:
                status_code = getattr(response, 'status', 200)
                if status_code != 200:
                    raise RuntimeError(f'HTTP {status_code}')
                final_url = response.geturl()
                if urlparse(final_url).scheme != 'https':
                    raise RuntimeError('redirected away from HTTPS')
                content_type = response.headers.get('Content-Type', '')
                content_length = response.headers.get('Content-Length')
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise RuntimeError(f'feed Content-Length exceeds byte cap ({max_bytes} bytes)')
                data = response.read(max_bytes + 1)
                etag = response.headers.get('ETag')
                last_modified = response.headers.get('Last-Modified')
            if len(data) > max_bytes:
                raise RuntimeError(f'feed exceeded size cap ({max_bytes} bytes)')
            if len(data) < 200:
                raise RuntimeError('feed was unexpectedly small')
            try:
                text = data.decode('utf-8-sig', errors='strict')
            except UnicodeDecodeError as exc:
                raise RuntimeError(f'feed is not valid UTF-8 text: {exc}') from exc
            if '\x00' in text[:1000]:
                raise RuntimeError('feed appears binary')
            prefix = text[:4000].lstrip().lower()
            if '<html' in prefix or '<!doctype html' in prefix:
                raise RuntimeError('endpoint returned HTML instead of the declared feed format')
            lines = text.splitlines()
            fmt = feed.get('format', 'adblock')
            count = sum(feed_entry_active(x, fmt) for x in lines)
            if count < int(feed.get('minimum_entries', 10)):
                raise RuntimeError(f'feed has too few valid entries for format {fmt!r} ({count})')
            mode = ('health-only; URL indicators are never treated as domain-wide coverage'
                    if fmt == 'url-indicators' or feed.get('health_only')
                    else 'coverage-index only; feed rules are never copied into output')
            return lines, {
                'name': feed['name'], 'ok': True, 'format': fmt, 'coverage_mode': mode,
                'bytes': len(data), 'lines': len(lines), 'active_lines': count,
                'sha256': sha256(data), 'final_url': final_url,
                'content_type': content_type, 'etag': etag, 'last_modified': last_modified,
                'attempts': attempt, 'duration_seconds': round(time.monotonic() - started, 3)
            }
        except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = f'{type(exc).__name__}: {exc}'
            retryable = not isinstance(exc, HTTPError) or exc.code == 429 or 500 <= exc.code < 600
            if attempt <= attempts_allowed and retryable:
                time.sleep(min(0.5 * (2 ** (attempt - 1)), 4.0))
                continue
            break
        except Exception as exc:
            last_error = f'{type(exc).__name__}: {exc}'
            break
    return None, {
        'name': feed['name'], 'ok': False, 'error': last_error,
        'attempts': attempt, 'duration_seconds': round(time.monotonic() - started, 3)
    }


def validate_feed_config(config: dict) -> None:
    """Reject ambiguous or unsafe feed registries before making network requests."""
    feeds = config.get('feeds')
    if not isinstance(feeds, list) or not feeds:
        raise RuntimeError('reference feed registry must contain a non-empty feeds array')
    names, urls = set(), set()
    allowed_formats = {'adblock', 'domains', 'url-indicators'}
    known_groups = {'ads', 'privacy', 'security', 'annoyance', 'special-category', 'compatibility'}
    for feed in feeds:
        for key in ('name', 'url', 'max_bytes', 'format', 'groups'):
            if key not in feed:
                raise RuntimeError(f'reference feed is missing required field {key!r}: {feed!r}')
        name, url = feed['name'].strip(), feed['url'].strip()
        parsed = urlparse(url)
        if not name or name in names:
            raise RuntimeError(f'duplicate or empty reference feed name: {name!r}')
        if url in urls:
            raise RuntimeError(f'duplicate reference feed URL: {url!r}')
        if parsed.scheme != 'https' or not parsed.hostname:
            raise RuntimeError(f'reference feed must use an HTTPS URL: {name}')
        if feed['format'] not in allowed_formats:
            raise RuntimeError(f'unsupported reference-feed format for {name}: {feed["format"]!r}')
        if not isinstance(feed['max_bytes'], int) or not 200 <= feed['max_bytes'] <= 100_000_000:
            raise RuntimeError(f'invalid feed max_bytes for {name}')
        if not isinstance(feed['groups'], list) or not set(feed['groups']).issubset(known_groups):
            raise RuntimeError(f'invalid reference-feed groups for {name}')
        names.add(name); urls.add(url)
    required_groups = config.get('required_groups', {})
    if not isinstance(required_groups, dict) or not set(required_groups).issubset(known_groups):
        raise RuntimeError('required_groups contains unknown categories')


def fetch_feeds_concurrently(feeds: list[dict], max_workers: int = 8, retries: int = 2):
    """Fetch feeds concurrently, but return results in the stable registry order."""
    if not feeds:
        return []
    workers = max(1, min(int(max_workers), len(feeds), 12))
    indexed = {}
    results = [None] * len(feeds)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='trihexoct-feed') as pool:
        for index, feed in enumerate(feeds):
            indexed[pool.submit(fetch_feed, feed, retries)] = index
        for future in as_completed(indexed):
            index = indexed[future]
            try:
                results[index] = future.result()
            except Exception as exc:  # Defensive: worker should convert failures into status reports.
                results[index] = (None, {'name': feeds[index].get('name', f'feed-{index}'), 'ok': False,
                                         'error': f'unhandled worker exception: {type(exc).__name__}: {exc}'})
    return results


def build_coverage_index(feed_lines, fmt, candidates, target_hosts):
    exact=set(); hosts={}; params=set(); prefixes=set()
    # URL-indicator feeds (for example, a phishing URL feed) are monitored for
    # source health and hashes only. A single bad URL does NOT prove its entire
    # hostname is malicious, so never infer domain-wide overlap from those entries.
    if fmt == 'url-indicators':
        return exact,hosts,params,prefixes
    for raw in feed_lines:
        line=raw.strip()
        if not line or line.startswith(('!','[')): continue
        if line.startswith('#') and not line.startswith(('##','#@#','#?#','#$#','#@$#')): continue
        if fmt=='domains':
            candidate=line.rstrip('.')
            if not FQDN_RE.fullmatch(candidate): continue
            line=f'||{candidate.lower()}^'
        if line in candidates: exact.add(line)
        parsed=simple_host_rule(line)
        if parsed and parsed[0] in target_hosts:
            hosts.setdefault(parsed[0],[]).append(line)
        name=param_name(line)
        if name: params.add(name)
        prefix=param_prefix(line)
        if prefix: prefixes.add(prefix)
    return exact,hosts,params,prefixes


def feed_groups(statuses, config):
    by_name={f['name']:f for f in config['feeds']}; out={}
    for status in statuses:
        if status.get('ok'):
            for group in by_name.get(status['name'],{}).get('groups',[]): out[group]=out.get(group,0)+1
    return out


def check_anomalies(statuses, baseline, lower=0.45, upper=2.5, history_samples=7):
    """Compare current counts against a rolling median, backward-compatible with v1 baselines."""
    anomalies = []
    for status in statuses:
        if not status.get('ok'):
            continue
        entry = baseline.get(status['name'], {})
        history = entry.get('history', []) if isinstance(entry, dict) else []
        counts = [x.get('active_lines') for x in history if isinstance(x, dict) and isinstance(x.get('active_lines'), int)]
        if not counts and isinstance(entry, dict) and isinstance(entry.get('active_lines'), int):
            counts = [entry['active_lines']]
        counts = counts[-max(1, int(history_samples)):]
        if not counts:
            continue
        reference = int(median(counts))
        current = int(status.get('active_lines', 0))
        if reference >= 50 and current > 0:
            ratio = current / reference
            if ratio < lower or ratio > upper:
                anomalies.append({
                    'name': status['name'], 'previous_active_lines': reference,
                    'history_counts': counts, 'current_active_lines': current,
                    'ratio': round(ratio, 3), 'lower_limit': lower, 'upper_limit': upper
                })
    return anomalies


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a file using a temp file in the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', dir=path.parent,
                                         prefix='.' + path.name + '.', suffix='.tmp', delete=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def atomic_write_json(path: Path, value: dict) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def active_rules_from_text(text: str) -> set[str]:
    """Return unique active lines for deterministic old/new rule comparisons."""
    return {line.strip() for line in text.splitlines() if active(line)}


def calculate_output_delta(previous_text: str | None, candidate_text: str) -> dict:
    """Summarize a candidate list change without counting comments or metadata."""
    old = active_rules_from_text(previous_text or '')
    new = active_rules_from_text(candidate_text)
    added = sorted(new - old)
    removed = sorted(old - new)
    denominator = max(1, len(old))
    return {
        'previous_active_rules': len(old),
        'candidate_active_rules': len(new),
        'added_count': len(added),
        'removed_count': len(removed),
        'changed_count': len(added) + len(removed),
        'changed_ratio': round((len(added) + len(removed)) / denominator, 4),
        'added_examples': added[:100],
        'removed_examples': removed[:100],
    }


def output_delta_gate_passes(delta: dict, threshold: float, gate_applies: bool, override: bool=False) -> bool:
    """A large live rule-set change needs explicit review unless the gate is inapplicable."""
    return (not gate_applies) or float(delta.get('changed_ratio', 0.0)) <= float(threshold) or bool(override)


def compile_list(fetch_refs: bool, require_primary: bool, output: Path, report_path: Path, min_successful: int | None=None, accept_anomaly: bool=False, max_workers: int | None=None, retries: int | None=None, accept_large_output_change: bool=False):
    config=json.loads(FEED_CONFIG.read_text(encoding='utf-8'))
    validate_feed_config(config)
    policy=config.get('policy', {})
    if min_successful is None: min_successful=int(policy.get('minimum_successful_feeds', 8))
    if max_workers is None: max_workers=int(policy.get('max_workers', 8))
    if retries is None: retries=int(policy.get('retries', 2))
    paths=sorted(MODULE_DIR.glob('*.txt'))
    if not paths: raise RuntimeError('no source modules found')
    rules=[]; seen=set(); rejected=[]; duplicate_count=0
    for path in paths:
        for raw in path.read_text(encoding='utf-8-sig').splitlines():
            if not active(raw): continue
            line=normalize_rule(raw)
            issue=validate_rule(line)
            if issue:
                rejected.append({'module':path.name,'rule':line,'issue':issue}); continue
            if line in seen: duplicate_count+=1; continue
            seen.add(line); rules.append(line)
    if rejected:
        raise RuntimeError(f'{len(rejected)} source rules fail policy; examples: '+ '; '.join(x['issue']+': '+x['rule'] for x in rejected[:5]))
    if len(rules)<500: raise RuntimeError(f'candidate list unexpectedly small: {len(rules)} rules')
    candidates=set(rules); target_hosts=set()
    for line in rules:
        parsed=simple_host_rule(line)
        if parsed:
            h=parsed[0].split('.')
            target_hosts.update('.'.join(h[i:]) for i in range(0,len(h)-1) if len(h[i:])>=2)
    statuses=[]; exact_refs=set(); exact_src={}; host_idx={}; ref_params=set(); param_src={}; ref_prefixes=set(); prefix_src={}
    baseline={}
    if BASELINE_PATH.exists():
        try: baseline=json.loads(BASELINE_PATH.read_text(encoding='utf-8')).get('feeds',{})
        except Exception as exc: raise RuntimeError(f'baseline JSON is unreadable: {exc}')
    anomalies=[]; groups={}
    if fetch_refs:
        fetched=fetch_feeds_concurrently(config['feeds'], max_workers=max_workers, retries=retries)
        # Fetching is parallel, but source indexing and reports stay in registry order.
        for feed,(lines,status) in zip(config['feeds'],fetched):
            statuses.append(status)
            if lines is None: continue
            exact,hosts,params,prefixes=build_coverage_index(lines,feed.get('format','adblock'),candidates,target_hosts)
            exact_refs |= exact; ref_params |= params; ref_prefixes |= prefixes
            for r in exact: exact_src.setdefault(r,[]).append(feed['name'])
            for h,covered in hosts.items(): host_idx.setdefault(h,[]).extend((feed['name'],r) for r in covered)
            for p in params: param_src.setdefault(p,[]).append(feed['name'])
            for p in prefixes: prefix_src.setdefault(p,[]).append(feed['name'])
        success=sum(s['ok'] for s in statuses)
        groups=feed_groups(statuses,config)
        failures=[]
        missing=[f['name'] for f in config['feeds'] if f.get('required') and not next((s['ok'] for s in statuses if s['name']==f['name']),False)]
        if require_primary and missing: failures.append('required feeds unavailable: '+', '.join(missing))
        if success<min_successful: failures.append(f'only {success}/{len(statuses)} feeds succeeded; at least {min_successful} required')
        for group,minimum in config.get('required_groups',{}).items():
            if groups.get(group,0)<minimum: failures.append(f'feed group {group} has {groups.get(group,0)} successful feeds; needs {minimum}')
        anomalies=check_anomalies(statuses,baseline, lower=float(policy.get('anomaly_lower_ratio',0.45)), upper=float(policy.get('anomaly_upper_ratio',2.5)), history_samples=int(policy.get('anomaly_history_samples',7)))
        if anomalies and not accept_anomaly: failures.append(f'{len(anomalies)} feed count anomalies; review report, then manually approve only if legitimate')
        if failures:
            report={'schema_version':1,'project_version':PROJECT_VERSION,'build_aborted':True,'generated_at_utc':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'failure_reasons':failures,'source_rule_count':len(rules),'source_duplicate_count':duplicate_count,'successful_feed_count':success,'total_feed_count':len(statuses),'feed_groups':groups,'feed_count_anomalies':anomalies,'feeds':statuses,'reference_coverage_complete':False,'published_file_modified':False}
            atomic_write_json(report_path, report)
            raise RuntimeError('; '.join(failures))
    else:
        statuses=[{'name':'reference feeds','ok':False,'error':'offline bootstrap build; online coverage not checked'}]
    final=[]; removed=[]
    for line in rules:
        if line in exact_refs:
            removed.append({'reason':'exact-filter-match','rule':line,'covered_by':exact_src.get(line,[])}); continue
        name=param_name(line)
        matched=[]
        if name:
            if name in ref_params: matched+=param_src.get(name,[])
            if not matched:
                for pref,srcs in prefix_src.items():
                    if name.startswith(pref): matched+=srcs
        if matched:
            removed.append({'reason':'tracking-parameter-covered','rule':line,'covered_by':sorted(set(matched))}); continue
        parsed=simple_host_rule(line)
        if parsed:
            host=parsed[0]; covered=[]
            labels=host.split('.'); parents=['.'.join(labels[i:]) for i in range(0,len(labels)-1)]
            for parent in parents:
                for feed_name, ref in host_idx.get(parent,[]):
                    if domain_covers(ref,line): covered.append((feed_name,ref))
            if covered:
                removed.append({'reason':'domain-covered','rule':line,'covered_by':sorted({n for n,_ in covered}),'matching_rules':sorted({r for _,r in covered})[:4]}); continue
        final.append(line)
    counts={cat:sum(rule_category(x)==cat for x in final)
            for cat in ('network','url_parameter','cosmetic','path_or_regex')}
    # Rules removed during reconciliation are counted as covered only because the
    # builder found specific evidence in a successfully fetched, supported feed.
    # An offline bootstrap receives no external-coverage credit.
    covered_counts={cat:sum(rule_category(item['rule'])==cat for item in removed)
                    for cat in ('network','url_parameter','cosmetic','path_or_regex')}
    effective_counts={cat:counts[cat] + (covered_counts[cat] if fetch_refs else 0)
                       for cat in counts}
    mins={'network':200,'url_parameter':40,'cosmetic':20,'path_or_regex':5}
    for cat,min_count in mins.items():
        if effective_counts[cat]<min_count:
            raise RuntimeError(
                f'output category regression: {cat} published={counts[cat]}, '
                f'proven-covered={covered_counts[cat] if fetch_refs else 0}, '
                f'effective={effective_counts[cat]}, minimum={min_count}'
            )
    if not fetch_refs:
        build_mode_note='! Build mode: OFFLINE BOOTSTRAP — live reference-feed overlap has not been checked.'
    elif all(x.get('ok') for x in statuses):
        build_mode_note='! Build mode: ONLINE RECONCILIATION — every configured reference feed passed validation.'
    else:
        build_mode_note='! Build mode: PARTIAL ONLINE RECONCILIATION — some optional reference feeds were unavailable; see build report.'
    header=[
      '! Title: Trihexoct Guardlux — TRIHEXΩ v2 Adaptive Supplementary Brave Filter List',
      '! Homepage: https://github.com/368Guardlux/Trihexoct',
      '! Description: TRIHEXΩ v2 alpha supplementary filters for ad delivery, third-party measurement, recognized attribution, cryptojacking indicators, and explicit ad slots.',
      f'! Version: {PROJECT_VERSION}',
      '! Expires: 12 hours',
      '! Release channel: ALPHA integration preview; not a stable production release.',
      '! Compatibility: Brave Shields / adblock-rust; no JavaScript, scriptlets, CSP modifications, or global WebSocket/API tampering.',
      f'! Automation: GitHub Actions is configured to attempt checks for {len(config["feeds"])} approved references every 12 hours with concurrent bounded retries.',
      '! Maintenance: separate read-only TRIHEXOMEGA cycle attempts conditional feed checks, source-health diagnostics, and candidate discovery twice daily.',
      '! Intelligence: optional 16-role staged LLM advisory council (12 analysts, 3 critics, 1 synthesis); not AGI; no production write authority.',
      '! Adaptation: verified conditional cache, discovery-only drift guard, supervised human-feedback diagnostics, adaptive triage, and deterministic evolution planning.',
      '! Scope: network rules are third-party scoped; functional auth/session/redirect/deep-link parameters are not removed.',
      build_mode_note,
      '! Not a malware scanner or guarantee of website compatibility. Keep Brave security features and maintained filters enabled.',
      '! -----------------------------------------------------------------------------',
      '! GENERATED FILE — edit src/modules/*.txt, then run tools/build_filter.py.',
      '! -----------------------------------------------------------------------------',''
    ]
    out=header[:]
    finalset=set(final); emitted=set()
    for path in paths:
        out.append('! ==================== '+path.stem.replace('-',' ').upper()+' ====================')
        for raw in path.read_text(encoding='utf-8-sig').splitlines():
            s=raw.strip()
            if not s: continue
            if s.startswith('!'): out.append(raw.rstrip()); continue
            s=normalize_rule(s)
            if s in finalset and s not in emitted: out.append(s); emitted.add(s)
        out.append('')
    out_text='\n'.join(out).rstrip()+'\n'
    # Validate the exact candidate before touching the last-known-good published file.
    rendered_rules=[x.strip() for x in out_text.splitlines() if active(x)]
    rendered_issues=[(i+1, r, validate_rule(r)) for i,r in enumerate(out_text.splitlines()) if active(r) and validate_rule(r)]
    if rendered_issues:
        raise RuntimeError('rendered list failed internal policy validation: '+ '; '.join(f'line {i}: {issue}: {r}' for i,r,issue in rendered_issues[:5]))
    if len(rendered_rules)!=len(set(rendered_rules)):
        raise RuntimeError('rendered list contains duplicate active rules')
    # Validate all required categories before atomic publication.
    if not any(x.startswith('! Title: Trihexoct Guardlux') for x in out_text.splitlines()[:10]):
        raise RuntimeError('rendered list is missing required title metadata')
    previous_text = None
    if output.exists():
        try:
            previous_text = output.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeDecodeError):
            previous_text = None
    output_delta = calculate_output_delta(previous_text, out_text)
    max_change_ratio = float(policy.get('max_published_rule_change_ratio', 0.40))
    delta_gate_applies = bool(fetch_refs) and output.resolve() == (ROOT / 'Trihexoct.txt').resolve() and previous_text is not None
    output_delta['gate_applied'] = delta_gate_applies
    output_delta['maximum_change_ratio'] = max_change_ratio
    output_delta['manual_override_used'] = bool(accept_large_output_change)
    output_delta['gate_passed'] = output_delta_gate_passes(output_delta, max_change_ratio, delta_gate_applies, accept_large_output_change)
    output_delta['policy_note'] = 'Large live-reconciliation changes require review; override only after inspecting the delta report.'
    atomic_write_json(DELTA_PATH, output_delta)
    if delta_gate_applies and output_delta['changed_ratio'] > max_change_ratio and not accept_large_output_change:
        gate_failures = [f"candidate rule-set changed by {output_delta['changed_ratio']:.1%}, exceeding the {max_change_ratio:.1%} review threshold"]
        gate_report = {
            'schema_version': 1, 'project_version': PROJECT_VERSION,
            'generated_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'build_aborted': True, 'failure_reasons': gate_failures,
            'source_rule_count': len(rules), 'published_active_rules': len(final),
            'successful_feed_count': sum(bool(x.get('ok')) for x in statuses),
            'total_feed_count': len(config['feeds']) if fetch_refs else 0,
            'feed_count_anomalies': anomalies, 'feeds': statuses,
            'reference_coverage_complete': bool(fetch_refs) and all(x.get('ok') for x in statuses),
            'published_file_modified': False, 'output_delta': output_delta,
            'manual_output_delta_override_used': False,
            'note': 'Last-known-good output and feed baseline were not advanced because the output delta gate failed.'
        }
        atomic_write_json(report_path, gate_report)
        raise RuntimeError('; '.join(gate_failures) + '; inspect reports/rule-delta.json, then manually approve only if justified')
    atomic_write_text(output, out_text)
    if fetch_refs:
        newbaseline=dict(baseline)
        history_samples=max(1,min(int(policy.get('anomaly_history_samples',7)),20))
        for status in statuses:
            if not status.get('ok'): continue
            old_entry=newbaseline.get(status['name'],{})
            old_history=old_entry.get('history',[]) if isinstance(old_entry,dict) else []
            if not old_history and isinstance(old_entry,dict) and isinstance(old_entry.get('active_lines'),int):
                old_history=[{'active_lines':old_entry['active_lines'],'sha256':old_entry.get('sha256','legacy')}]
            new_history=list(old_history)+[{'active_lines':status['active_lines'],'sha256':status['sha256'],'observed_at_utc':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}]
            new_history=new_history[-history_samples:]
            newbaseline[status['name']]={'active_lines':status['active_lines'],'sha256':status['sha256'],'history':new_history}
        atomic_write_json(BASELINE_PATH, {'schema_version':2,'project_version':PROJECT_VERSION,'feeds':newbaseline})
    # Stable machine-readable manifest for the published list. Excludes per-run times
    # so it does not create a commit when content and source inputs have not changed.
    if output.resolve() == (ROOT/'Trihexoct.txt').resolve():
        module_hashes={path.name:sha256(path.read_bytes()) for path in paths}
        meta={
            'schema_version':1,'project_version':PROJECT_VERSION,
            'output':'Trihexoct.txt','output_sha256':sha256(out_text.encode('utf-8')),
            'active_rule_count':len(final),'rule_categories':counts,
            'published_rule_categories':counts,
            'covered_rule_categories':covered_counts if fetch_refs else {cat:0 for cat in counts},
            'effective_rule_categories':effective_counts,
            'source_module_count':len(paths),'source_module_sha256':module_hashes,
            'reference_registry_sha256':sha256(FEED_CONFIG.read_bytes()),
            'overlap_policy_version':OVERLAP_POLICY_VERSION,
            'build_mode':('online-reconciliation' if fetch_refs and all(x.get('ok') for x in statuses) else 'partial-online-reconciliation') if fetch_refs else 'offline-bootstrap',
            'successful_feed_count':sum(bool(x.get('ok')) for x in statuses) if fetch_refs else 0,
            'total_feed_count':len(config['feeds']) if fetch_refs else 0,
            'reference_coverage_complete':bool(fetch_refs) and all(x.get('ok') for x in statuses),
            'reference_feed_registry_count':len(config['feeds']),
            'last_output_delta_ratio':output_delta['changed_ratio'],
            'last_output_delta_gate_passed':output_delta['gate_passed'],
            'trihexomega_capabilities': {
                'agent_roster': 16,
                'agent_stages': '12 specialist analyses, 3 critique roles, 1 synthesis guardian; one configured provider/model endpoint per run',
                'adaptive_triage': 'human-feedback-informed review effort ranking only; not threat likelihood and never authorizes blocking',
                'human_feedback_learning': 'hash-chained human outcomes; aggregate diagnostics and bounded review-priority adaptation only',
                'feed_drift_guard': 'discovery-only holds; production feed coverage unchanged',
                'evolution_planner': 'deterministic engineering backlog with recurrence tracking; no automatic code, rule, policy, or publication changes',
                'production_rule_mutations_by_ai': 0,
                'production_publication_by_ai': False,
                'live_feed_validation_at_archive_build': bool(fetch_refs) and all(x.get('ok') for x in statuses),
                'brave_engine_compatibility_at_archive_build': False,
                'self_learning_semantics': 'human-supervised operational diagnostics, not autonomous model training or AGI'
            }
        }
        atomic_write_json(META_PATH, meta)
    report={
      'schema_version':1,'project_version':PROJECT_VERSION,'generated_at_utc':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
      'output':'Trihexoct.txt','output_sha256':sha256(out_text.encode()),'source_module_count':len(paths),
      'source_unique_rules':len(rules),'source_exact_duplicates_removed':duplicate_count,'published_active_rules':len(final),
      'published_rule_categories':counts,'covered_rule_categories':covered_counts if fetch_refs else {cat:0 for cat in counts},
      'effective_rule_categories':effective_counts,
      'removed_exact_and_covered_rules':len(removed),'overlap_removal_examples':removed[:400],
      'reference_feeds':statuses,'reference_coverage_complete':bool(fetch_refs) and all(s.get('ok') for s in statuses),
      'successful_feed_count':sum(bool(s.get('ok')) for s in statuses),'total_feed_count':len(config['feeds']) if fetch_refs else 0,
      'successful_feed_groups':groups,'feed_count_anomalies':anomalies,'manual_anomaly_override_used':accept_anomaly,
      'overlap_policy_version':OVERLAP_POLICY_VERSION,'fetch_workers':max_workers if fetch_refs else 0,'feed_retries':retries if fetch_refs else 0,
      'reference_registry_sha256':sha256(FEED_CONFIG.read_bytes()),
      'output_delta':output_delta,
      'manual_output_delta_override_used':accept_large_output_change,
      'note':('Reference-feed overlap was evaluated using validated feeds; unavailable optional feeds are listed in the report. '
              'Filter syntax lint is not a browser engine parser or live-site test.') if fetch_refs else
             'Offline build does not claim online overlap analysis. Filter syntax lint is not a browser engine parser or live-site test.'
    }
    atomic_write_json(report_path, report)
    print(json.dumps({k:report[k] for k in ('source_unique_rules','source_exact_duplicates_removed','published_active_rules','published_rule_categories','removed_exact_and_covered_rules','reference_coverage_complete')},indent=2))
    if fetch_refs:
        for s in statuses: print(('OK: ' if s.get('ok') else 'WARN: ')+s['name']+(f" ({s.get('active_lines')} active)" if s.get('ok') else ': '+s.get('error','unknown')))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch-references',action='store_true',help='fetch approved HTTPS reference feeds for conservative overlap checks')
    parser.add_argument('--require-primary',action='store_true',help='abort if any required feed is unavailable')
    parser.add_argument('--min-successful-feeds',type=int,default=None,help='override registry minimum; normally taken from reference_feeds.json')
    parser.add_argument('--workers',type=int,default=None,help='concurrent feed workers (capped at 12; registry default is used when omitted)')
    parser.add_argument('--retries',type=int,default=None,help='retry transient feed failures (0-5; registry default is used when omitted)')
    parser.add_argument('--accept-feed-anomaly',action='store_true',help='manual override only after reviewing the anomaly report')
    parser.add_argument('--accept-large-output-change',action='store_true',help='manual override only after reviewing reports/rule-delta.json and confirming a large rule-set change is legitimate')
    parser.add_argument('--output',type=Path,default=ROOT/'Trihexoct.txt')
    parser.add_argument('--report',type=Path,default=ROOT/'reports'/'build-report.json')
    args=parser.parse_args()
    try:
        compile_list(args.fetch_references,args.require_primary,args.output.resolve(),args.report.resolve(),args.min_successful_feeds,args.accept_feed_anomaly,args.workers,args.retries)
    except Exception as exc:
        print('ERROR:',exc,file=sys.stderr); return 2
    return 0

if __name__=='__main__': raise SystemExit(main())
