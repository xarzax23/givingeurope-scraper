import requests, csv, re, sys
from bs4 import BeautifulSoup

HEADERS = {   
   'Accept': 'application/json, text/plain, */*',
   'Origin': 'https://www.givingeurope.com',
   'Referer': 'https://www.givingeurope.com',
   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'

}

def extract_pgid_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    cfg = soup.find('fg-configurator')
    if cfg and cfg.has_attr('product'):
      return cfg['product']
    raise ValueError("No encontré <fg-configurator product=\"...">")

def fetch_variants(pgid, retry_count=3):
    url = f'https://components.givingeurope.com/api/v1/products/{pgid}/configurator'
    params = {'locale':'es_ES','layout':'wholesale','country':'ES','color':''}
    r = requests.get(url, params=params, headers=HEADERS, timeout=5)
    r.raise_for_status()
    data = r.json()
    for step in data.get('steps', []):
        if step.get('type') == 'quantity_per_variant':
            return step.get('options', [])
    return []

def main():
    with open('referencias_GE.txt', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.strip()][:10]

    rows = []
    for url in urls:
        print(f"Procesando URL: {url}", file=sys.stderr)
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            try:
                pgid = extract_pgid_from_html(resp.text)
            except ValueError as ve:
                print(f"  [ERROR] Could not extract pgid: {ve}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"  [ERROR] An unexpected error occurred while extracting pgid: {e}", file=sys.stderr)
                continue
            opts = fetch_variants(pgid)
            print(f"  → {len(opts)} variantes encontradas", file=sys.stderr)
            for o in opts:
                stock_info = o.get('stock') or {}
                incs = stock_info.get('incomingStocks', [])
                rows.append({
                    'product_url':      url,
                    'model_parent':     o.get('productCode',''),
                    'variant_name':     o.get('name',''),
                    'variant_sku':      o.get('variantCode',''),
                    'stock_units':      stock_info.get('quantity',''),
                    'reserved_units':   stock_info.get('totalOption',0),
                    'incomingStocks':   incs
                })
        except requests.exceptions.RequestException as re:
            print(f"  [ERROR] Request failed: {re}", file=sys.stderr)
        except Exception as e:
            print(f"  [ERROR] {e}", file=sys.stderr)

    if not rows:
        print("No se descargo nada")
        print("No se encontraron datos.", file=sys.stderr)
        return

    # calculamos máximo de llegadas
    max_arrivals = max((len(r['incomingStocks']) for r in rows), default=0)


    base_headers = [
        'product_url','model_parent','variant_name','variant_sku',
        'stock_units','reserved_units'
    ]
    arrival_headers = []
    for i in range(1, max_arrivals+1):
        arrival_headers += [f'arrival_date_{i}', f'arrival_qty_{i}']


    headers = base_headers + arrival_headers

    writer = csv.DictWriter(sys.stdout, fieldnames=headers, lineterminator='\n')
    writer.writeheader()
    for r in rows:
        row = {h: r.get(h, '') for h in base_headers}
        for idx in range(max_arrivals):
            date_key = f'arrival_date_{idx+1}'
            qty_key  = f'arrival_qty_{idx+1}'
            if idx < len(r['incomingStocks']):
                stock_entry = r['incomingStocks'][idx]
                row[date_key] = stock_entry.get('expectedArrivalDate','').split('T')[0]
                row[qty_key]  = stock_entry.get('quantity','')
            else:
                row[date_key] = row[qty_key] = ''
        writer.writerow(row)

    print("Proceso completado.", file=sys.stderr)

if __name__ == '__main__':
    main()
