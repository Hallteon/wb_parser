import aiohttp
import asyncio
import json
from tqdm import tqdm
from playwright.async_api import async_playwright

async def fetch_products(session, url):
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                content_type = response.headers.get('Content-Type', '')
                response_text = await response.text()

                if 'application/json' in content_type or ('text/plain' in content_type and response_text.strip().startswith('{')):
                    try:
                        data = json.loads(response_text)

                        return data.get('data', {}).get('products', [])

                    except json.JSONDecodeError:
                        print(f"Failed to decode JSON from response: {response_text[:100]}... for URL: {url}")

                        return []
                else:
                    print(f"Unexpected content type: {content_type} for URL: {url}")
                    return []
            else:
                print(f"Non-200 status code: {response.status} for URL: {url}")
                return []
    
    except Exception as e:
        print(f"Error fetching products: {e} for URL: {url}")
    
        return []

async def parse_product(page, product_id, category_name):
    try:
        await page.goto(f'https://www.wildberries.ru/catalog/{product_id}/detail.aspx', timeout=60000)
        await page.wait_for_selector('.product-page__title', timeout=30000)
        prod_name = await page.locator('.product-page__title').first.inner_text()
        await page.locator('.product-page__btn-detail').first.click()
        await page.wait_for_selector('.product-params__cell-decor', timeout=30000)

        info_names = await page.locator('.product-params__cell-decor').all_text_contents()
        info_data = await page.locator('.product-params__cell').all_text_contents()
        price = await page.locator('.price-block__final-price').first.inner_text()

        info = {}
    
        for s in range(0, len(info_names)):
            info[info_names[s]] = info_data[s]

        return {
            'id': product_id,
            'name': prod_name,
            'attributes': info,
            'category': category_name,
            'price': price
        }
    
    except Exception as e:
        print(f"Error parsing product {product_id}: {e}")
        return None

async def main():
    with open('to_parse.json', 'r', encoding='utf-8') as f:
        categories = json.load(f)

    all_products = []
    variants = ['stationery3', 'appliances2', '']

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        )
        page = await context.new_page()

        async with aiohttp.ClientSession() as session:
            for cat in tqdm(categories[16:]):
                i = cat['cat_name']
    
                try:
                    ids = []
    
                    for page_num in range(1, 100):
                        for var in variants:
                            url = f'https://search.wb.ru/exactmatch/ru/common/v9/search?ab_testing=false&appType=1&curr=rub&dest=123586167&lang=ru&page={page_num}&query={i}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false'
                            products = await fetch_products(session, url)
                            if len(products) > 0:
                                ids += [product['id'] for product in products]
                                break

                        if len(ids) >= 100 - cat['count']:
                            break

                    for h in range(min((len(ids), 100 - cat['count']))):
                        product_data = await parse_product(page, ids[h], i)
                        if product_data:
                            all_products.append(product_data)

                    with open('ods_from_wb2.json', 'w', encoding='utf-8') as f:
                        json.dump(all_products, f, ensure_ascii=False, indent=4)

                except Exception as e:
                    print(f"Error processing category {i}: {str(e)}")
                    continue

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
