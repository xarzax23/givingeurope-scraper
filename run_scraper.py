import os
import sys
import requests
import psycopg2
from bs4 import BeautifulSoup
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Credenciales Oxylabs Realtime API
OXY_USER = 'xarzax23_ZvmVl'
OXY_PASS = 'xarzax23A_12'

# Oxylabs: Headers y URL
OXY_URL = 'https://realtime.oxylabs.io/v1/queries'
OXY_HEADERS = {'Content-Type': 'application/json'}

# Headers para la llamada al API interno de variantes
API_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.givingeurope.com',
    'Referer': 'https://www.givingeurope.com'
}

def create_table_if_not_exists():
    """Connects to the database and creates the products table if it does not exist."""
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            host=os.environ.get("DB_HOST"),
            port=os.environ.get("DB_PORT")
        )
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                product_url TEXT,
                model_parent TEXT,
                variant_name TEXT,
                variant_sku TEXT UNIQUE,
                stock_units INTEGER,
                reserved_units INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Table 'products' is ready.", file=sys.stderr)
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}", file=sys.stderr)
        sys.exit(1)

def fetch_html_via_oxylabs(url: str) -> str:
    payload = {
        "source": "universal",
        "url": url,
        "render": True
    }
    resp = requests.post(
        'https://realtime.oxylabs.io/v1/queries',
        auth=(OXY_USER, OXY_PASS),
        headers={'Content-Type': 'application/json'},
        json=payload,
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json().get('results', [])
    if not data or 'content' not in data[0]:
        raise ValueError("Oxylabs: no devolvió 'content'")
    return data[0]['content']

def extract_pgid_from_html(html: str) -> str:
    """
    Parsear el HTML renderizado y extraer <fg-configurator product="...">
    """
    soup = BeautifulSoup(html, 'html.parser')
    cfg = soup.find('fg-configurator')
    if not cfg or not cfg.has_attr('product'):
        raise ValueError("No encontré <fg-configurator product='...'>")
    return cfg['product']

def fetch_variants(pgid: str) -> list:
    """
    Llamar al endpoint configurator para obtener las variantes.
    """
    api = f'https://components.givingeurope.com/api/v1/products/{pgid}/configurator'
    params = {'locale':'es_ES','layout':'wholesale','country':'ES','color':''}
    r = requests.get(api, params=params, headers=API_HEADERS, timeout=10)
    r.raise_for_status()
    for step in r.json().get('steps', []):
        if step.get('type') == 'quantity_per_variant':
            return step.get('options', [])
    return []

def main():
    create_table_if_not_exists()

    try:
        with open('referencias_GE.txt', encoding='utf-8') as f:
            urls = [u.strip() for u in f if u.strip()][:10]
    except FileNotFoundError:
        print("Error: falta 'referencias_GE.txt'", file=sys.stderr)
        sys.exit(1)

    rows = []
    for url in urls:
        print(f"Procesando: {url}", file=sys.stderr)
        try:
            html = fetch_html_via_oxylabs(url)
        except Exception as e:
            print(f"  [ERROR] Oxylabs fetch: {e}", file=sys.stderr)
            continue

        try:
            pgid = extract_pgid_from_html(html)
        except ValueError as ve:
            print(f"  [ERROR] pgid: {ve}", file=sys.stderr)
            continue

        try:
            opts = fetch_variants(pgid)
        except Exception as e:
            print(f"  [ERROR] fetch_variants: {e}", file=sys.stderr)
            continue

        print(f"  → {len(opts)} variantes", file=sys.stderr)
        for o in opts:
            stock = o.get('stock') or {}
            incs  = stock.get('incomingStocks', [])
            rows.append({
                'product_url':     url,
                'model_parent':    o.get('productCode',''),
                'variant_name':    o.get('name',''),
                'variant_sku':     o.get('variantCode',''),
                'stock_units':     stock.get('quantity',''),
                'reserved_units':  stock.get('totalOption',0),
                'incomingStocks':  incs
            })

    if not rows:
        print("No hay variantes válidas.", file=sys.stderr)
        sys.exit(0)

    # Supabase connection
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)

    for row in rows:
        # Remove incomingStocks from the row
        row.pop('incomingStocks', None)
        # Upsert data into Supabase
        data, count = supabase.table('products').upsert(row).execute()

    print("¡Terminado!", file=sys.stderr)

if __name__ == '__main__':
    main()