import requests, csv, re
from bs4 import BeautifulSoup

HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.givingeurope.com',
    'Referer': 'https://www.givingeurope.com'
}

def extract_pgid_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    cfg = soup.find('fg-configurator')
    if cfg and cfg.has_attr('product'):
        return cfg['product']
    raise ValueError("No encontré <fg-configurator product=\"...\">")

def fetch_variants(pgid):
    url = f'https://components.givingeurope.com/api/v1/products/{pgid}/configurator'
    params = {'locale':'es_ES','layout':'wholesale','country':'ES','color':''}
    r = requests.get(url, params=params, headers=HEADERS, timeout=5)
    r.raise_for_status()
    data = r.json()
    for step in data.get('steps', []):
        if step.get('type')=='quantity_per_variant':
            return step.get('options', [])
    return []

# ... (import y funciones anteriores idénticas) ...

def main():
    with open('referencias_GE.txt', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.strip()][:10]

    rows = []
    for url in urls:
        print(f"Procesando URL: {url}")
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            pgid = extract_pgid_from_html(resp.text)
            opts = fetch_variants(pgid)
            print(f"  → {len(opts)} variantes encontradas")

            for o in opts:
                name          = o.get('name','')
                model_parent  = o.get('productCode','')           # SKU común
                sku           = o.get('variantCode','')
                stock_info    = o.get('stock',{})
                stock         = stock_info.get('quantity','')
                reserved      = stock_info.get('totalOption', 0)  # unidades reservadas
                incs          = stock_info.get('incomingStocks',[])
                if incs:
                    next_date = incs[0].get('expectedArrivalDate','').split('T')[0]
                    next_qty  = incs[0].get('quantity','')
                else:
                    next_date = next_qty = ''

                rows.append({
                    'product_url':         url,
                    'model_parent':        model_parent,
                    'variant_name':        name,
                    'variant_sku':         sku,
                    'stock_units':         stock,
                    'reserved_units':      reserved,
                    'next_arrival_date':   next_date,
                    'next_arrival_qty':    next_qty
                })
        except Exception as e:
            print(f"  [ERROR] {e}")

    # Definimos encabezados incluyendo los nuevos campos
    headers = [
        'product_url',
        'model_parent',
        'variant_name',
        'variant_sku',
        'stock_units',
        'reserved_units',
        'next_arrival_date',
        'next_arrival_qty'
    ]
    with open('GE_stock_api.csv', 'w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print("CSV generado: GE_stock_api.csv")


if __name__=='__main__':
    main()
