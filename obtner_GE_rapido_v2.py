#!/usr/bin/env python3
import requests
import csv
import re
import sys
from bs4 import BeautifulSoup

# Cabeceras para la petición HTML de la página de producto
HTML_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://www.givingeurope.com/'
}

# Cabeceras para las llamadas al API JSON
API_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.givingeurope.com',
    'Referer': 'https://www.givingeurope.com'
}

def extract_pgid_from_html(html: str) -> str:
    """
    Parsear el HTML y extraer el atributo `product` de <fg-configurator>.
    """
    soup = BeautifulSoup(html, 'html.parser')
    cfg = soup.find('fg-configurator')
    if cfg and cfg.has_attr('product'):
        return cfg['product']
    raise ValueError("No encontré <fg-configurator product='...'>")

def fetch_variants(pgid: str) -> list:
    """
    Llamar al endpoint /configurator para obtener las variantes
    y su stock/incomingStocks.
    """
    url = f'https://components.givingeurope.com/api/v1/products/{pgid}/configurator'
    params = {
        'locale': 'es_ES',
        'layout': 'wholesale',
        'country': 'ES',
        'color': ''
    }
    resp = requests.get(url, params=params, headers=API_HEADERS, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    for step in data.get('steps', []):
        if step.get('type') == 'quantity_per_variant':
            return step.get('options', [])
    return []

def main():
    # Leer las primeras 10 URLs de referencias_GE.txt
    try:
        with open('referencias_GE.txt', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()][:10]
    except FileNotFoundError:
        print("Error: no encontré 'referencias_GE.txt'", file=sys.stderr)
        sys.exit(1)

    rows = []
    for url in urls:
        print(f"Procesando URL: {url}", file=sys.stderr)
        try:
            resp = requests.get(url, headers=HTML_HEADERS, timeout=5)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [ERROR] Falló la petición HTML: {e}", file=sys.stderr)
            continue

        try:
            pgid = extract_pgid_from_html(resp.text)
        except ValueError as ve:
            print(f"  [ERROR] No pude extraer pgid: {ve}", file=sys.stderr)
            # Opcional: imprimir un poco de HTML para depuración:
            print(f"  [DEBUG] HTML recibido (primeros 300 car.): {resp.text[:300]!r}", file=sys.stderr)
            continue

        try:
            opts = fetch_variants(pgid)
        except Exception as e:
            print(f"  [ERROR] Falló fetch_variants: {e}", file=sys.stderr)
            continue

        print(f"  → {len(opts)} variantes encontradas", file=sys.stderr)
        for o in opts:
            stock_info = o.get('stock') or {}
            incs = stock_info.get('incomingStocks', [])
            rows.append({
                'product_url':     url,
                'model_parent':    o.get('productCode', ''),
                'variant_name':    o.get('name', ''),
                'variant_sku':     o.get('variantCode', ''),
                'stock_units':     stock_info.get('quantity', ''),
                'reserved_units':  stock_info.get('totalOption', 0),
                'incomingStocks':  incs
            })

    if not rows:
        print("No se descargó ninguna variante válida.", file=sys.stderr)
        sys.exit(0)

    # Calcular cuántas llegadas máximas hay
    max_arrivals = max((len(r['incomingStocks']) for r in rows), default=0)

    # Header base y dinámico de llegadas
    base_headers = [
        'product_url', 'model_parent',
        'variant_name', 'variant_sku',
        'stock_units', 'reserved_units'
    ]
    arrival_headers = []
    for i in range(1, max_arrivals + 1):
        arrival_headers += [f'arrival_date_{i}', f'arrival_qty_{i}']

    all_headers = base_headers + arrival_headers

    # Escribir CSV a stdout (o redirige a un archivo)
    writer = csv.DictWriter(sys.stdout, fieldnames=all_headers, lineterminator='\n')
    writer.writeheader()
    for r in rows:
        row = {h: r.get(h, '') for h in base_headers}
        for idx in range(max_arrivals):
            date_key = f'arrival_date_{idx+1}'
            qty_key  = f'arrival_qty_{idx+1}'
            if idx < len(r['incomingStocks']):
                entry = r['incomingStocks'][idx]
                row[date_key] = entry.get('expectedArrivalDate', '').split('T')[0]
                row[qty_key]  = entry.get('quantity', '')
            else:
                row[date_key] = ''
                row[qty_key]  = ''
        writer.writerow(row)

    print("Proceso completado.", file=sys.stderr)

if __name__ == '__main__':
    main()
