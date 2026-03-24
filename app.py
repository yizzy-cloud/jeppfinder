import hashlib
import json
import os
import re
import sqlite3
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('DB_PATH', str(BASE_DIR / 'data' / 'renegade_finder.db')))
PORT = int(os.getenv('PORT', '5000'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '25'))
NEW_WINDOW_HOURS = int(os.getenv('NEW_WINDOW_HOURS', '72'))
SCAN_TOKEN = os.getenv('SCAN_TOKEN', '').strip()
AUTOFORCE_TOKEN = os.getenv('AUTOFORCE_TOKEN', '').strip()
AUTOFORCE_API = 'https://api.autodromo.app/v1/used_models'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
}

DEFAULT_FILTERS = {
    'min_price': int(os.getenv('DEFAULT_MIN_PRICE', '90000')),
    'max_price': int(os.getenv('DEFAULT_MAX_PRICE', '113000')),
    'years': [int(x.strip()) for x in os.getenv('DEFAULT_YEARS', '2023,2024,2025').split(',') if x.strip()],
    'version_keywords': [x.strip().lower() for x in os.getenv('DEFAULT_VERSION_KEYWORDS', 'longitude,1.3 turbo').split(',') if x.strip()],
    'only_new': False,
    'strict_keywords': False,
}

DEALERS = [
    {'name': 'Toriba Jeep', 'url': 'https://www.jeeptoriba.com.br/seminovos', 'city': 'São Paulo (Lapa)', 'platform': 'autoforce', 'channel': 2782},
    {'name': 'BEXP Jeep', 'url': 'https://www.bexp.com.br/jeep/seminovos', 'city': 'São Paulo (Morumbi)', 'platform': 'autoforce', 'channel': 336},
    {'name': 'Bicudo Jeep', 'url': 'https://www.jeepbicudo.com.br/seminovos', 'city': 'Itu', 'platform': 'autoforce', 'channel': 1582},
    {'name': 'Marajó Jeep', 'url': 'https://www.jeepmarajo.com.br/seminovos', 'city': 'São José do Rio Preto', 'platform': 'autoforce', 'channel': 2701},
    {'name': 'Soma Jeep', 'url': 'https://www.somajeep.com.br/seminovos', 'city': 'Sorocaba', 'platform': 'autoforce', 'channel': 1219},
    {'name': 'Destaque Jeep', 'url': 'https://www.destaquejeep.com.br/seminovos', 'city': 'Mogi das Cruzes', 'platform': 'autoforce', 'channel': 3254},
    {'name': 'Autostar Jeep', 'url': 'https://www.autostarjeep.com.br/seminovos', 'city': 'São Paulo (Butantã)', 'platform': 'autoforce', 'channel': 2754},
    {'name': 'Jeep Dahruj', 'url': 'https://www.jeepdahruj.com.br/seminovos', 'city': 'São Paulo / Jundiaí / Campinas', 'platform': 'html'},
    {'name': 'Viviani Jeep', 'url': 'https://www.jeepviviani.com.br/seminovos', 'city': 'Piracicaba', 'platform': 'html'},
    {'name': 'Stefanini Jeep', 'url': 'https://www.jeepstefanini.com.br/seminovos', 'city': 'Osasco / Barueri', 'platform': 'html'},
    {'name': 'Divena Jeep', 'url': 'https://www.divenajeep.com.br/seminovos', 'city': 'São Paulo', 'platform': 'html'},
    {'name': 'RP Jeep', 'url': 'https://www.rpjeep.com.br/seminovos', 'city': 'Ribeirão Preto', 'platform': 'html'},
    {'name': 'Osten Jeep', 'url': 'https://jeeposten.com.br/seminovos', 'city': 'São Paulo / São José dos Campos', 'platform': 'html'},
    {'name': 'Way Jeep', 'url': 'https://www.jeepway.com.br/seminovos', 'city': 'Bauru', 'platform': 'html'},
    {'name': 'McLarty Maia Jeep', 'url': 'https://www.jeepmclartymaia.com.br/seminovos', 'city': 'São Paulo', 'platform': 'html'},
    {'name': 'Ravenna Jeep', 'url': 'https://www.jeepravenna.com.br/seminovos', 'city': 'Bragança Paulista', 'platform': 'html'},
    {'name': 'Stecar Jeep', 'url': 'https://stecaramerica.com.br/seminovos?busca=renegade', 'city': 'Ribeirão Preto', 'platform': 'html'},
    {'name': 'Amazonas Jeep', 'url': 'https://jeep.grupoamazonas.com.br/seminovos', 'city': 'São Paulo (ABC)', 'platform': 'html'},
    {'name': 'Sinal Jeep', 'url': 'https://www.gruposinal.com.br/veiculos?filter[new]=false&filter[brand]=Jeep&filter[model]=Renegade', 'city': 'São Paulo / Barueri', 'platform': 'html'},
    {'name': 'Sim Jeep', 'url': 'https://www.jeepsim.com.br/seminovos', 'city': 'Ribeirão Preto', 'platform': 'html'},
    {'name': 'Germânica Jeep', 'url': 'https://www.jeepgermanica.com.br/seminovos', 'city': 'Campinas', 'platform': 'html'},
]


@dataclass
class Listing:
    dealer: str
    dealer_url: str
    city: str
    platform: str
    model: str
    version: str
    year: str
    price: float
    price_label: str
    km: str
    color: str
    url: str
    source: str
    relevance_score: int = 0
    reason_tags: str = ''
    notes: str = ''
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    is_new: bool = False
    fingerprint: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(value: Any, default: int) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except Exception:
        return default


def safe_float_sort(value: Any, default: float = 999999999.0) -> float:
    try:
        if value in (None, '', 'N/I'):
            return default
        return float(value)
    except Exception:
        return default


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS listings (
            fingerprint TEXT PRIMARY KEY,
            dealer TEXT NOT NULL,
            dealer_url TEXT,
            city TEXT,
            platform TEXT,
            model TEXT,
            version TEXT,
            year TEXT,
            price REAL,
            price_label TEXT,
            km TEXT,
            color TEXT,
            url TEXT,
            source TEXT,
            relevance_score INTEGER DEFAULT 0,
            reason_tags TEXT,
            notes TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        '''
    )
    cols = {row['name'] for row in conn.execute("PRAGMA table_info(listings)").fetchall()}
    for col_def in [
        ('relevance_score', 'INTEGER DEFAULT 0'),
        ('reason_tags', 'TEXT'),
        ('notes', 'TEXT'),
    ]:
        if col_def[0] not in cols:
            conn.execute(f'ALTER TABLE listings ADD COLUMN {col_def[0]} {col_def[1]}')
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS scan_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            executed_at TEXT NOT NULL,
            total_raw INTEGER NOT NULL,
            total_filtered INTEGER NOT NULL,
            notes TEXT
        )
        '''
    )
    conn.commit()
    conn.close()


def safe_request(url: str) -> requests.Response | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
    except Exception:
        return None


def parse_price(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r'[^\d,.]', '', str(value))
    if not text:
        return 0.0
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return 0.0


def format_price(value: float) -> str:
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') if value else 'Sob consulta'


def normalize_spaces(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').strip())


def extract_years(value: str) -> list[int]:
    years = [int(x) for x in re.findall(r'20\d{2}', value or '')]
    unique = []
    for year in years:
        if year not in unique:
            unique.append(year)
    return unique


def extract_km(value: str) -> str:
    match = re.search(r'(\d{1,3}(?:[\.\s]\d{3})+|\d{1,6})\s?km', value or '', re.I)
    return normalize_spaces(match.group(0)) if match else 'N/I'


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def build_fingerprint(item: dict[str, Any]) -> str:
    base = '|'.join([
        normalize_spaces(item.get('dealer', '')).lower(),
        normalize_spaces(item.get('url', '')).lower(),
        normalize_spaces(item.get('model', '')).lower(),
        normalize_spaces(item.get('version', '')).lower(),
        normalize_spaces(item.get('year', '')).lower(),
        normalize_spaces(item.get('km', '')).lower(),
        f"{float(item.get('price', 0.0)):.2f}",
    ])
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def looks_like_target_model(text: str) -> bool:
    return 'renegade' in (text or '').lower()


def keyword_hits(text: str, version_keywords: list[str]) -> list[str]:
    haystack = (text or '').lower()
    return [k for k in version_keywords if k and k in haystack]


def score_listing(listing: Listing, filters: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    tags: list[str] = []
    full_text = f'{listing.model} {listing.version} {listing.notes}'.lower()
    years = extract_years(listing.year)
    hits = keyword_hits(full_text, filters['version_keywords'])

    if looks_like_target_model(full_text):
        score += 50
        tags.append('renegade')
    if 'longitude' in full_text:
        score += 25
        tags.append('longitude')
    if '1.3 turbo' in full_text or 't270' in full_text:
        score += 20
        tags.append('1.3 turbo')
    elif 'turbo' in full_text:
        score += 10
        tags.append('turbo')
    if years and any(y in filters['years'] for y in years):
        score += 20
        tags.append('ano_ok')
    if listing.price and filters['min_price'] <= listing.price <= filters['max_price']:
        score += 20
        tags.append('preco_ok')
    if hits:
        score += len(hits) * 5
        tags.extend([f'kw:{x}' for x in hits])
    if listing.url and listing.url != listing.dealer_url:
        score += 5
        tags.append('link_detalhe')
    return score, tags


def matches_filters(listing: Listing, filters: dict[str, Any]) -> bool:
    full_text = f'{listing.model} {listing.version} {listing.notes}'.lower()
    years = extract_years(listing.year)
    hits = keyword_hits(full_text, filters['version_keywords'])

    if not looks_like_target_model(full_text):
        return False
    if filters['years'] and years and not any(y in filters['years'] for y in years):
        return False
    if listing.price and listing.price < filters['min_price']:
        return False
    if listing.price and listing.price > filters['max_price']:
        return False
    if filters.get('strict_keywords'):
        return all(k in full_text for k in filters['version_keywords']) if filters['version_keywords'] else True
    if filters['version_keywords']:
        return bool(hits)
    return True


def row_to_listing(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        first_seen = datetime.fromisoformat(data['first_seen_at'])
    except Exception:
        first_seen = None
    data['is_new'] = bool(first_seen and first_seen >= datetime.now(timezone.utc) - timedelta(hours=NEW_WINDOW_HOURS))
    data['reason_tags'] = [x for x in (data.get('reason_tags') or '').split(',') if x]
    return data


def upsert_listing(listing: Listing) -> Listing:
    conn = get_db()
    fp = listing.fingerprint or build_fingerprint(asdict(listing))
    listing.fingerprint = fp
    existing = conn.execute('SELECT first_seen_at FROM listings WHERE fingerprint = ?', (fp,)).fetchone()
    current_ts = now_iso()

    if existing:
        listing.first_seen_at = existing['first_seen_at']
        listing.last_seen_at = current_ts
        listing.is_new = False
        conn.execute(
            '''
            UPDATE listings
            SET dealer=?, dealer_url=?, city=?, platform=?, model=?, version=?, year=?,
                price=?, price_label=?, km=?, color=?, url=?, source=?, relevance_score=?,
                reason_tags=?, notes=?, last_seen_at=?
            WHERE fingerprint=?
            ''',
            (
                listing.dealer, listing.dealer_url, listing.city, listing.platform, listing.model,
                listing.version, listing.year, listing.price, listing.price_label, listing.km,
                listing.color, listing.url, listing.source, listing.relevance_score,
                listing.reason_tags, listing.notes, listing.last_seen_at, fp,
            ),
        )
    else:
        listing.first_seen_at = current_ts
        listing.last_seen_at = current_ts
        listing.is_new = True
        conn.execute(
            '''
            INSERT INTO listings (
                fingerprint, dealer, dealer_url, city, platform, model, version, year, price,
                price_label, km, color, url, source, relevance_score, reason_tags, notes,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                fp, listing.dealer, listing.dealer_url, listing.city, listing.platform, listing.model,
                listing.version, listing.year, listing.price, listing.price_label, listing.km,
                listing.color, listing.url, listing.source, listing.relevance_score,
                listing.reason_tags, listing.notes, listing.first_seen_at, listing.last_seen_at,
            ),
        )
    conn.commit()
    conn.close()
    return listing


def record_scan_run(total_raw: int, total_filtered: int, notes: str = '') -> None:
    conn = get_db()
    conn.execute(
        'INSERT INTO scan_runs (executed_at, total_raw, total_filtered, notes) VALUES (?, ?, ?, ?)',
        (now_iso(), total_raw, total_filtered, notes),
    )
    conn.commit()
    conn.close()


def fetch_autoforce(dealer: dict[str, Any]) -> list[Listing]:
    if not AUTOFORCE_TOKEN:
        return []
    try:
        response = requests.get(
            AUTOFORCE_API,
            params={'page': 1, 'per_page': 200, 'channel_id': dealer['channel']},
            headers={**HEADERS, 'Authorization': f'Token {AUTOFORCE_TOKEN}'},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    items: list[Listing] = []
    base_domain = dealer['url'].split('/seminovos')[0]
    for entry in payload.get('entries', []):
        try:
            model = normalize_spaces(entry.get('name') or entry.get('model') or '')
            brand = normalize_spaces(entry.get('brand') or '')
            full_model = normalize_spaces(f'{brand} {model}')
            if not looks_like_target_model(full_model):
                continue
            version = normalize_spaces(entry.get('version') or model)
            price = parse_price(entry.get('price_value') or entry.get('price'))
            fabrication_year = str(entry.get('fabrication_year') or '').strip()
            model_year = str(entry.get('model_year') or '').strip()
            year = '/'.join([x for x in [fabrication_year, model_year] if x]) or 'N/I'
            km = str(entry.get('km') or 'N/I')
            color = normalize_spaces(entry.get('color') or 'N/I')
            slug = normalize_spaces(entry.get('slug') or '')
            url = f'{base_domain}/seminovos/{slug}' if slug else dealer['url']
            notes = normalize_spaces(' '.join([
                str(entry.get('fuel') or ''),
                str(entry.get('transmission') or ''),
                str(entry.get('description') or ''),
            ]))
            items.append(Listing(
                dealer=dealer['name'], dealer_url=dealer['url'], city=dealer['city'], platform=dealer['platform'],
                model=full_model, version=version, year=year, price=price, price_label=format_price(price),
                km=km, color=color, url=url, source='autoforce', notes=notes,
            ))
        except Exception:
            continue
    return items


def pick_anchor_context(anchor) -> str:
    blocks = [anchor.get_text(' ', strip=True)]
    parent = anchor.parent
    if parent:
        blocks.append(parent.get_text(' ', strip=True))
        grandparent = parent.parent
        if grandparent:
            blocks.append(grandparent.get_text(' ', strip=True))
    return normalize_spaces(' '.join(blocks))


def infer_version(text: str) -> str:
    lower = (text or '').lower()
    pieces = []
    if 'longitude' in lower:
        pieces.append('Longitude')
    if 't270' in lower:
        pieces.append('T270')
    if '1.3 turbo' in lower:
        pieces.append('1.3 Turbo')
    elif 'turbo' in lower:
        pieces.append('Turbo')
    return ' '.join(pieces) or 'Renegade'


def fetch_detail_page(detail_url: str) -> dict[str, str]:
    response = safe_request(detail_url)
    if not response:
        return {}
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    full_text = normalize_spaces(soup.get_text(' ', strip=True))
    title = normalize_spaces((soup.title.string if soup.title and soup.title.string else ''))
    price_match = re.search(r'R\$\s?[\d\.,]+', full_text, re.I)
    price_label = normalize_spaces(price_match.group(0)) if price_match else ''
    return {
        'title': title,
        'full_text': full_text,
        'price_label': price_label,
        'km': extract_km(full_text),
        'version': infer_version(full_text),
        'year': '/'.join(str(y) for y in extract_years(full_text)[:2]) or 'N/I',
    }


def fetch_html_fallback(dealer: dict[str, Any]) -> list[Listing]:
    response = safe_request(dealer['url'])
    if not response:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    results: list[Listing] = []
    seen_urls: set[str] = set()

    for anchor in soup.select('a[href]'):
        try:
            href = normalize_spaces(anchor.get('href') or '')
            if not href or href.startswith('javascript:') or href.startswith('#'):
                continue
            full_url = absolute_url(dealer['url'], href)
            if full_url in seen_urls:
                continue
            context = pick_anchor_context(anchor)
            combined = f'{href} {context}'.lower()
            if 'renegade' not in combined:
                continue
            seen_urls.add(full_url)

            detail = fetch_detail_page(full_url) if full_url != dealer['url'] else {}
            merged = normalize_spaces(' '.join([context, detail.get('title', ''), detail.get('full_text', '')]))
            if 'renegade' not in merged.lower():
                merged = context
            years = extract_years(merged)
            year_label = '/'.join(str(y) for y in years[:2]) if years else 'N/I'
            price_match = re.search(r'R\$\s?[\d\.,]+', merged, re.I)
            price = parse_price(price_match.group(0)) if price_match else parse_price(detail.get('price_label'))
            km = extract_km(merged)
            version = infer_version(merged)
            notes = normalize_spaces(merged[:500])

            results.append(Listing(
                dealer=dealer['name'], dealer_url=dealer['url'], city=dealer['city'], platform=dealer['platform'],
                model='Jeep Renegade', version=detail.get('version') or version, year=detail.get('year') or year_label,
                price=price, price_label=format_price(price), km=detail.get('km') or km, color='N/I',
                url=full_url, source='html-fallback', notes=notes,
            ))
        except Exception:
            continue

    return results


def normalize_filters(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    years = payload.get('years', DEFAULT_FILTERS['years'])
    if isinstance(years, str):
        years = [safe_int(x.strip(), 0) for x in years.split(',') if x.strip()]
        years = [x for x in years if x > 0]

    version_keywords = payload.get('version_keywords', DEFAULT_FILTERS['version_keywords'])
    if isinstance(version_keywords, str):
        version_keywords = [x.strip().lower() for x in version_keywords.split(',') if x.strip()]

    return {
        'min_price': safe_int(payload.get('min_price', DEFAULT_FILTERS['min_price']), DEFAULT_FILTERS['min_price']),
        'max_price': safe_int(payload.get('max_price', DEFAULT_FILTERS['max_price']), DEFAULT_FILTERS['max_price']),
        'years': years,
        'version_keywords': version_keywords,
        'only_new': bool(payload.get('only_new', DEFAULT_FILTERS['only_new'])),
        'strict_keywords': bool(payload.get('strict_keywords', DEFAULT_FILTERS['strict_keywords'])),
    }


def dedupe_listings(items: list[Listing]) -> list[Listing]:
    best_by_fp: dict[str, Listing] = {}
    for item in items:
        fp = build_fingerprint(asdict(item))
        item.fingerprint = fp
        current = best_by_fp.get(fp)
        if current is None or len(item.notes) > len(current.notes) or item.url != item.dealer_url:
            best_by_fp[fp] = item
    return list(best_by_fp.values())


def run_scan(filters: dict[str, Any]) -> dict[str, Any]:
    raw_items: list[Listing] = []
    dealer_stats: list[dict[str, Any]] = []
    messages: list[str] = []

    for dealer in DEALERS:
        items: list[Listing] = []
        dealer_error = None

        try:
            items = fetch_autoforce(dealer) if dealer['platform'] == 'autoforce' else fetch_html_fallback(dealer)

            if dealer['platform'] == 'autoforce' and not items:
                html_attempt = fetch_html_fallback(dealer)
                if html_attempt:
                    items = html_attempt
                    messages.append(f'{dealer["name"]}: fallback HTML usado por ausência de retorno AutoForce.')
        except Exception as e:
            dealer_error = str(e)
            traceback.print_exc()
            items = []

        safe_items: list[Listing] = []
        for item in items:
            try:
                score, tags = score_listing(item, filters)
                item.relevance_score = score
                item.reason_tags = ','.join(tags)
                safe_items.append(item)
            except Exception:
                traceback.print_exc()
                continue

        raw_items.extend(safe_items)
        dealer_stats.append({
            'dealer': dealer['name'],
            'city': dealer['city'],
            'platform': dealer['platform'],
            'found_raw': len(safe_items),
            'dealer_url': dealer['url'],
            'error': dealer_error,
        })

        if dealer_error:
            messages.append(f'{dealer["name"]}: erro na varredura ({dealer_error}).')

    raw_items = dedupe_listings(raw_items)
    filtered: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for item in raw_items:
        try:
            stored = upsert_listing(item)
            row = asdict(stored)
            row['reason_tags'] = [x for x in item.reason_tags.split(',') if x]
            row['relevance_score'] = item.relevance_score

            if matches_filters(item, filters):
                if filters.get('only_new') and not row.get('is_new'):
                    continue
                filtered.append(row)
            else:
                candidates.append(row)
        except Exception:
            traceback.print_exc()
            continue

    filtered.sort(
        key=lambda x: (
            not x.get('is_new', False),
            -safe_int(x.get('relevance_score', 0), 0),
            safe_float_sort(x.get('price', 999999999)),
            x.get('dealer', '')
        )
    )
    candidates.sort(
        key=lambda x: (
            -safe_int(x.get('relevance_score', 0), 0),
            safe_float_sort(x.get('price', 999999999)),
            x.get('dealer', '')
        )
    )

    record_scan_run(len(raw_items), len(filtered), notes=json.dumps(filters, ensure_ascii=False))
    return {
        'executed_at': now_iso(),
        'filters': filters,
        'total_raw': len(raw_items),
        'total_filtered': len(filtered),
        'total_candidates': len(candidates),
        'dealer_stats': sorted(dealer_stats, key=lambda x: (-x['found_raw'], x['dealer'])),
        'results': filtered,
        'candidates': candidates[:50],
        'messages': messages + [
            'Se o resultado filtrado vier zerado, veja abaixo os candidatos próximos do filtro.',
            'Anúncios marcados como NOVO são os que surgiram dentro da janela configurada.',
        ],
    }


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me')
init_db()


@app.get('/')
def index():
    return render_template(
        'index.html',
        default_filters=DEFAULT_FILTERS,
        dealers=DEALERS,
        new_window_hours=NEW_WINDOW_HOURS
    )


@app.post('/api/scan')
def api_scan():
    try:
        filters = normalize_filters(request.get_json(silent=True))
        return jsonify(run_scan(filters)), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'error': f'Erro interno em /api/scan: {str(e)}',
            'trace_hint': 'Verifique os logs do Render para o traceback completo.'
        }), 500


@app.post('/api/scan-secret')
def api_scan_secret():
    try:
        token = request.headers.get('X-Scan-Token', '')
        if not SCAN_TOKEN or token != SCAN_TOKEN:
            return jsonify({'error': 'unauthorized'}), 401

        filters = normalize_filters(request.get_json(silent=True))
        return jsonify(run_scan(filters)), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'error': f'Erro interno em /api/scan-secret: {str(e)}',
            'trace_hint': 'Verifique os logs do Render para o traceback completo.'
        }), 500


@app.get('/api/listings')
def api_listings():
    try:
        only_new = request.args.get('only_new', 'false').lower() == 'true'
        conn = get_db()
        rows = conn.execute('SELECT * FROM listings ORDER BY last_seen_at DESC, relevance_score DESC, price ASC').fetchall()
        conn.close()
        items = [row_to_listing(row) for row in rows]
        if only_new:
            items = [item for item in items if item['is_new']]
        return jsonify({'total': len(items), 'results': items}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Erro interno em /api/listings: {str(e)}'}), 500


@app.get('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'time': now_iso(), 'db_path': str(DB_PATH)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
