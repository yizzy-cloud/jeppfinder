import hashlib
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('DB_PATH', str(BASE_DIR / 'data' / 'renegade_finder.db')))
PORT = int(os.getenv('PORT', '5000'))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
}

AUTOFORCE_API = 'https://api.autodromo.app/v1/used_models'
AUTOFORCE_TOKEN = os.getenv('AUTOFORCE_TOKEN', '').strip()
NEW_WINDOW_HOURS = int(os.getenv('NEW_WINDOW_HOURS', '72'))
SCAN_TOKEN = os.getenv('SCAN_TOKEN', '').strip()

DEFAULT_FILTERS = {
    'min_price': int(os.getenv('DEFAULT_MIN_PRICE', '90000')),
    'max_price': int(os.getenv('DEFAULT_MAX_PRICE', '113000')),
    'years': [int(x.strip()) for x in os.getenv('DEFAULT_YEARS', '2023,2024,2025').split(',') if x.strip()],
    'version_keywords': [x.strip().lower() for x in os.getenv('DEFAULT_VERSION_KEYWORDS', 'longitude,1.3 turbo').split(',') if x.strip()],
    'only_new': False,
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
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    is_new: bool = False
    fingerprint: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        '''
    )
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
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def normalize_spaces(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').strip())


def extract_years(value: str) -> list[int]:
    return [int(x) for x in re.findall(r'20\d{2}', value or '')]


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


def matches_version(text: str, version_keywords: list[str]) -> bool:
    t = (text or '').lower()
    return all(k in t for k in version_keywords)


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
                price=?, price_label=?, km=?, color=?, url=?, source=?, last_seen_at=?
            WHERE fingerprint=?
            ''',
            (
                listing.dealer, listing.dealer_url, listing.city, listing.platform, listing.model,
                listing.version, listing.year, listing.price, listing.price_label, listing.km,
                listing.color, listing.url, listing.source, listing.last_seen_at, fp,
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
                price_label, km, color, url, source, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                fp, listing.dealer, listing.dealer_url, listing.city, listing.platform, listing.model,
                listing.version, listing.year, listing.price, listing.price_label, listing.km,
                listing.color, listing.url, listing.source, listing.first_seen_at, listing.last_seen_at,
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


def row_to_listing(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        first_seen = datetime.fromisoformat(data['first_seen_at'])
    except Exception:
        first_seen = None
    data['is_new'] = bool(first_seen and first_seen >= datetime.now(timezone.utc) - timedelta(hours=NEW_WINDOW_HOURS))
    return data


def fetch_autoforce(dealer: dict[str, Any]) -> list[Listing]:
    if not AUTOFORCE_TOKEN:
        return []
    try:
        response = requests.get(
            AUTOFORCE_API,
            params={'page': 1, 'per_page': 200, 'channel_id': dealer['channel']},
            headers={**HEADERS, 'Authorization': f'Token {AUTOFORCE_TOKEN}'},
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    items: list[Listing] = []
    for entry in payload.get('entries', []):
        model = normalize_spaces(entry.get('name') or entry.get('model') or '')
        brand = normalize_spaces(entry.get('brand') or '')
        full_model = normalize_spaces(f'{brand} {model}')
        if not looks_like_target_model(full_model):
            continue
        version = normalize_spaces(entry.get('version') or model)
        price = parse_price(entry.get('price_value') or entry.get('price'))
        year = f"{entry.get('fabrication_year', '')}/{entry.get('model_year', '')}".strip('/')
        km = str(entry.get('km') or 'N/I')
        color = normalize_spaces(entry.get('color') or 'N/I')
        slug = normalize_spaces(entry.get('slug') or '')
        base_domain = dealer['url'].split('/seminovos')[0]
        url = f'{base_domain}/seminovos/{slug}' if slug else dealer['url']
        if entry.get('sold'):
            continue
        items.append(Listing(
            dealer=dealer['name'], dealer_url=dealer['url'], city=dealer['city'], platform=dealer['platform'],
            model=full_model, version=version, year=year, price=price, price_label=format_price(price),
            km=km, color=color, url=url, source='autoforce'))
    return items


def fetch_html_fallback(dealer: dict[str, Any]) -> list[Listing]:
    try:
        response = requests.get(dealer['url'], headers=HEADERS, timeout=25)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if 'renegade' not in text.lower():
        return []

    results: list[Listing] = []
    candidates = soup.select('a[href]')
    seen_urls: set[str] = set()

    for anchor in candidates:
        href = normalize_spaces(anchor.get('href') or '')
        label = normalize_spaces(anchor.get_text(' ', strip=True))
        combined = f'{label} {href}'.lower()
        if 'renegade' not in combined:
            continue
        full_url = requests.compat.urljoin(dealer['url'], href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        context = normalize_spaces(anchor.parent.get_text(' ', strip=True))
        merged = f'{label} {context}'
        years = extract_years(merged)
        year_label = '/'.join(str(y) for y in years[:2]) if years else 'N/I'
        price_match = re.search(r'R\$\s?[\d\.,]+', merged, re.I)
        price = parse_price(price_match.group(0)) if price_match else 0.0
        km_match = re.search(r'(\d{1,3}(?:\.\d{3})+|\d{1,6})\s?km', merged, re.I)
        km = km_match.group(0) if km_match else 'N/I'
        version = 'Longitude 1.3 Turbo' if 'longitude' in merged.lower() else 'Renegade'
        results.append(Listing(
            dealer=dealer['name'], dealer_url=dealer['url'], city=dealer['city'], platform=dealer['platform'],
            model='Jeep Renegade', version=version, year=year_label, price=price,
            price_label=format_price(price) if price else 'Sob consulta', km=km, color='N/I',
            url=full_url, source='html-fallback'))
    return results


def normalize_filters(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    years = payload.get('years', DEFAULT_FILTERS['years'])
    if isinstance(years, str):
        years = [int(x.strip()) for x in years.split(',') if x.strip()]
    version_keywords = payload.get('version_keywords', DEFAULT_FILTERS['version_keywords'])
    if isinstance(version_keywords, str):
        version_keywords = [x.strip().lower() for x in version_keywords.split(',') if x.strip()]
    return {
        'min_price': int(payload.get('min_price', DEFAULT_FILTERS['min_price'])),
        'max_price': int(payload.get('max_price', DEFAULT_FILTERS['max_price'])),
        'years': years,
        'version_keywords': version_keywords,
        'only_new': bool(payload.get('only_new', DEFAULT_FILTERS['only_new'])),
    }


def run_scan(filters: dict[str, Any]) -> dict[str, Any]:
    raw_items: list[Listing] = []
    dealer_stats: list[dict[str, Any]] = []

    for dealer in DEALERS:
        items = fetch_autoforce(dealer) if dealer['platform'] == 'autoforce' else fetch_html_fallback(dealer)
        raw_items.extend(items)
        dealer_stats.append({
            'dealer': dealer['name'],
            'city': dealer['city'],
            'platform': dealer['platform'],
            'found_raw': len(items),
        })

    filtered: list[dict[str, Any]] = []
    for item in raw_items:
        full_text = f'{item.model} {item.version}'.lower()
        years = extract_years(item.year)
        if not looks_like_target_model(full_text):
            continue
        if filters['version_keywords'] and not matches_version(full_text, filters['version_keywords']):
            continue
        if item.price and item.price < filters['min_price']:
            continue
        if item.price and item.price > filters['max_price']:
            continue
        if filters['years'] and years and not any(y in filters['years'] for y in years):
            continue
        stored = upsert_listing(item)
        row = asdict(stored)
        if filters.get('only_new') and not row.get('is_new'):
            continue
        filtered.append(row)

    filtered.sort(key=lambda x: (not x.get('is_new', False), float(x.get('price', 999999999)), x.get('dealer', '')))
    record_scan_run(len(raw_items), len(filtered), notes=json.dumps(filters, ensure_ascii=False))
    return {
        'executed_at': now_iso(),
        'filters': filters,
        'total_raw': len(raw_items),
        'total_filtered': len(filtered),
        'dealer_stats': dealer_stats,
        'results': filtered,
    }


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me')
init_db()


@app.get('/')
def index():
    return render_template('index.html', default_filters=DEFAULT_FILTERS, dealers=DEALERS, new_window_hours=NEW_WINDOW_HOURS)


@app.post('/api/scan')
def api_scan():
    filters = normalize_filters(request.get_json(silent=True))
    return jsonify(run_scan(filters))


@app.post('/api/scan-secret')
def api_scan_secret():
    token = request.headers.get('X-Scan-Token', '')
    if not SCAN_TOKEN or token != SCAN_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401
    filters = normalize_filters(request.get_json(silent=True))
    return jsonify(run_scan(filters))


@app.get('/api/listings')
def api_listings():
    only_new = request.args.get('only_new', 'false').lower() == 'true'
    conn = get_db()
    rows = conn.execute('SELECT * FROM listings ORDER BY last_seen_at DESC, price ASC').fetchall()
    conn.close()
    items = [row_to_listing(row) for row in rows]
    if only_new:
        items = [item for item in items if item['is_new']]
    return jsonify({'total': len(items), 'results': items})


@app.get('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'time': now_iso(), 'db_path': str(DB_PATH)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
