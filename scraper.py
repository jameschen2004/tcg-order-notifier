from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def get_order_details(order_id):
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        # Load your saved TCGplayer session
        context = await browser.new_context(storage_state="tcg_state.json")
        page = await context.new_page()
        
        # Apply Stealth
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        print(f"🔍 Scraping Order: {order_id}...")
        await page.goto(f"https://sellerportal.tcgplayer.com/orders/{order_id}")
        await page.wait_for_load_state("networkidle")

        try:
            # 1. Extract Buyer Name
            buyer_locator = page.locator("div:has-text('Buyer')").locator("strong").first
            buyer_name = await buyer_locator.inner_text()
            
            # 2. Extract Product Details (Name, Qty, Price)
            items = []
            # Filter for table rows that contain product links
            product_rows = page.locator("tbody tr").filter(has=page.locator("a[href*='product']"))
            
            all_rows = await product_rows.all()
            for row in all_rows:
                # Get all table cells in this specific row
                cells = row.locator("td")
                cell_count = await cells.count()
                
                # Standard TCGplayer rows have 4-5 cells. 
                # Hidden/Mobile rows usually have fewer or are empty.
                if cell_count >= 4:
                    name = await cells.nth(0).inner_text()
                    qty = await cells.nth(2).inner_text()
                    price = await cells.nth(3).inner_text()
                    
                    # Prevent adding empty or "Ghost" rows
                    if name.strip():
                        items.append({
                            "name": name.strip(), 
                            "qty": qty.strip(), 
                            "price": price.strip()
                        })
                        
            unique_items = []
            seen_names = set()
            for item in items:
                if item['name'] not in seen_names:
                    unique_items.append(item)
                    seen_names.add(item['name'])

            return {"buyer": buyer_name.strip(), "items": unique_items}
        except Exception as e:
            print(f"❌ Scraper failed for {order_id}: {e}")
            return None
        finally:
            await browser.close()