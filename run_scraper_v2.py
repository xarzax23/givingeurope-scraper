import os
import sys
import requests
import psycopg2
import csv
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from datetime import datetime

load_dotenv()

# Headers para la llamada al API interno de variantes
API_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.givingeurope.com',
    'Referer': 'https://www.givingeurope.com'
}

def create_table_if_not_exists(conn):
    """Creates the products table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_url TEXT,
                model_parent TEXT,
                variant_name TEXT,
                variant_sku TEXT,
                stock_units INTEGER,
                reserved_units INTEGER,
                fecha_extraccion TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (product_url, model_parent, variant_name, variant_sku, stock_units, reserved_units, fecha_extraccion)
            );
        """)
        conn.commit()
        print("Table 'products' is ready.", file=sys.stderr)

def fetch_html(url: str) -> str:
    """Fetches the HTML content of a URL."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

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

def rows_to_tuples(rows):
    """Convierte lista de dicts a lista de tuplas en el orden de columnas para Supabase."""
    return [
        (
            r["product_url"], r["model_parent"], r["variant_name"], r["variant_sku"],
            r["stock_units"], r["reserved_units"], r["fecha_extraccion"],
        ) for r in rows
    ]

def write_to_supabase(conn, rows):
    """Writes the data to the Supabase database."""
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO products (
                    product_url, model_parent, variant_name, variant_sku, stock_units, reserved_units, fecha_extraccion
                ) VALUES %s
                ON CONFLICT (product_url, model_parent, variant_name, variant_sku, stock_units, reserved_units, fecha_extraccion) DO NOTHING;
                """,
                rows_to_tuples(rows),
            )
            conn.commit()
        print(f"✅ {len(rows)} rows inserted/updated in Supabase.", file=sys.stderr)
    except Exception as e:
        print(f"Error writing to Supabase: {e}", file=sys.stderr)

def main():
    db_url = os.environ.get("DATABASE_URL")
    conn = None # Initialize conn to None
    if db_url:
        try:
            conn = psycopg2.connect(db_url)
            create_table_if_not_exists(conn)
        except psycopg2.Error as e:
            print(f"Error connecting to the database: {e}", file=sys.stderr)
            # Continue execution even if DB connection fails

    try:
        with open('referencias_GE.txt', encoding='utf-8') as f:
            urls = [u.strip() for u in f if u.strip()]
    except FileNotFoundError:
        print("Error: falta 'referencias_GE.txt'", file=sys.stderr)
        sys.exit(1)

    all_rows = []
    current_extraction_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for url in urls:
        print(f"Procesando: {url}", file=sys.stderr)
        try:
            html = fetch_html(url)
            pgid = extract_pgid_from_html(html)
            variants = fetch_variants(pgid)
        except Exception as e:
            print(f"  [ERROR] processing {url}: {e}", file=sys.stderr)
            continue

        print(f"  → {len(variants)} variantes", file=sys.stderr)
        for o in variants:
            stock = o.get('stock') or {}
            incs = stock.get('incomingStocks',[])
            if incs:
                next_date = incs[0].get('expectedArrivalDate','').split('T')[0]
                next_qty  = incs[0].get('quantity','')
            else:
                next_date = next_qty = ''

            all_rows.append({
                'product_url':         url,
                'model_parent':        o.get('productCode',''),
                'variant_name':        o.get('name',''),
                'variant_sku':         o.get('variantCode',''),
                'stock_units':         stock.get('quantity', 0),
                'reserved_units':      stock.get('totalOption', 0),
                'next_arrival_date':   next_date,
                'next_arrival_qty':    next_qty,
                'fecha_extraccion':    current_extraction_time
            })

    if not all_rows:
        print("No hay variantes válidas para procesar.", file=sys.stderr)
        sys.exit(0)

    # Write to Supabase if connection was successful
    if conn:
        write_to_supabase(conn, all_rows)
        conn.close()

    # CSV Generation
    headers = [
        'product_url',
        'model_parent',
        'variant_name',
        'variant_sku',
        'stock_units',
        'reserved_units',
        'next_arrival_date',
        'next_arrival_qty',
        'fecha_extraccion'
    ]
    try:
        with open('GE_stock_api.csv', 'w', encoding='utf-8-sig', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_rows)
        print("CSV generado: GE_stock_api.csv", file=sys.stderr)
    except Exception as e:
        print(f"Error generating CSV: {e}", file=sys.stderr)

    print("¡Proceso terminado!", file=sys.stderr)

if __name__ == '__main__':
    main()
