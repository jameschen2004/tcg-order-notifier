from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def get_order_details(order_id):
    async with async_playwright() as p:
        # Optimized for e2-micro (Low RAM)
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox"]
        )
        context = await browser.new_context(storage_state="tcg_state.json")
        page = await context.new_page()
        page.set_default_timeout(120000)
        await Stealth().apply_stealth_async(page)

        print(f"🔍 Scraping Order: {order_id}...", flush=True)
        try:
            await page.goto(f"https://sellerportal.tcgplayer.com/orders/{order_id}", wait_until="domcontentloaded")
            await page.wait_for_selector("tbody tr", state="attached", timeout=60000)

            # Extract Buyer
            buyer_locator = page.locator("div:has-text('Buyer')").locator("strong").first
            buyer_name = await buyer_locator.inner_text()

            # Extract Items
            items = []
            product_rows = page.locator("tbody tr").filter(has=page.locator("a[href*='product']"))
            count = await product_rows.count()
            for i in range(count):
                row = product_rows.nth(i)
                cells = row.locator("td")
                if await cells.count() >= 4:
                    name = await cells.nth(0).inner_text()
                    qty = await cells.nth(2).inner_text()
                    price = await cells.nth(3).inner_text()
                    items.append({"name": name.strip(), "qty": qty.strip(), "price": price.strip()})

            # Deduplicate
            unique_items = []
            seen = set()
            for item in items:
                if item['name'] not in seen:
                    unique_items.append(item)
                    seen.add(item['name'])

            print(f"✨ Scraper finished extracting {len(unique_items)} items.", flush=True)
            return {"buyer": buyer_name.strip(), "items": unique_items}
        except Exception as e:
            print(f"❌ Scraper Error: {e}", flush=True)
            return None
        finally:
            await browser.close()