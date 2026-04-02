import asyncio
import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from playwright.async_api import async_playwright, Page

SOCIAL_MEDIA_DOMAINS = [
    "reddit.com", "quora.com", "instagram.com", "facebook.com", 
    "twitter.com", "x.com", "linkedin.com", "pinterest.com", 
    "tiktok.com", "youtube.com"
]

@dataclass
class LocationData:
    coords: dict  # e.g., {"latitude": 41.8781, "longitude": -87.6298}
    tz: str       # e.g., "America/Chicago"
    locale: str   # e.g., "en-US"

class ProxyManager:
    """Manages rotation of residential proxies."""
    def __init__(self, proxies: List[str]):
        self.proxies = proxies
        self.index = 0

    def get_new_residential_ip(self) -> Optional[dict]:
        if not self.proxies:
            return None
        proxy_url = self.proxies[self.index % len(self.proxies)]
        self.index += 1
        return {"server": proxy_url}

async def type_with_jitter(page: Page, selector: str, text: str, base_delay: int = 100, jitter: int = 50):
    """
    Step 4 Core Mechanic: Types text into an input field with human-like jitter between keystrokes.
    Prevents detection by anti-bot systems looking for perfect machine-like typing.
    """
    await page.wait_for_selector(selector)
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        delay = random.uniform(base_delay - jitter, base_delay + jitter)
        await asyncio.sleep(max(10, delay) / 1000.0)

async def handle_cookie_modals(page: Page):
    """
    Detects and accepts European/Global cookie consent banners which obscure the search box.
    """
    try:
        # Example selector for Google's 'I agree' or 'Accept all' modal
        consent_button = page.locator('#L2AGLb')
        if await consent_button.is_visible(timeout=3000):
            await consent_button.click()
            await asyncio.sleep(1)
            return

        # Fallback to looking for generic "Accept all" text
        accept_all = page.locator('button:has-text("Accept all")')
        if await accept_all.is_visible(timeout=1000):
            await accept_all.click()
            await asyncio.sleep(1)
    except Exception:
        pass # Modal might not exist depending on the region/IP

async def extract_clean_organic_hrefs(page: Page) -> List[str]:
    """
    Step 5 Core Mechanic: Parses the SERP for organic links, avoiding ads, sponsored blocks, and AI overviews.
    """
    organic_links = []
    try:
        # Typically the main organic search results sit within the #rso container
        result_divs = await page.locator('#rso > div').all()
        for div in result_divs:
            text_content = await div.inner_text()
            # Basic filtering to exclude ads and sponsored content
            if "Sponsored" in text_content or "Ad" in text_content:
                continue
                
            # Grab the primary link within the pristine organic result block
            links = await div.locator('a[data-ved], a:has(h3)').element_handles()
            for link in links:
                href = await link.get_attribute('href')
                if href and href.startswith('http') and "google.com" not in href:
                    organic_links.append(href)
                    break # Usually we just evaluate the first main link for the result block
    except Exception as e:
        print(f"Error extracting links: {e}")
        
    return organic_links

async def track_rankings(location_data: LocationData, search_dict: Dict[str, str], proxies: List[str] = None):
    """
    Executes the entire rank tracker lifecycle across a dictionary of keywords and target URLs.
    
    Step 1: Incognito
    Step 2: Geolocation spoofing
    Step 3: Dictionary iteration
    Step 4: Human-like search
    Step 5: Rank matching
    Step 6: Repeat & Teardown
    Step 7: Return final ranks mapping
    """
    results_dict = {}
    proxy_manager = ProxyManager(proxies if proxies else [])

    async with async_playwright() as p:
        # Initiate underlying browser daemon (headless, stealth args)
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        # Step 3/6 Loop: Execute operations for all items in dictionary
        for keyword, target_url in search_dict.items():
            print(f"Tracking keyword: '{keyword}' for URL: '{target_url}'")
            proxy = proxy_manager.get_new_residential_ip()
            
            # Step 1 & 2: Incognito Context + Location Spoofing
            context = await browser.new_context(
                proxy=proxy,
                geolocation=location_data.coords,
                permissions=["geolocation"],
                timezone_id=location_data.tz,
                locale=location_data.locale,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            )
            
            # Stealth payload injection: Nullify the webdriver fingerprint flag entirely
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = await context.new_page()

            try:
                # Step 4: Search on Google securely and naturally
                await page.goto("https://www.google.com")
                await handle_cookie_modals(page)
                
                # Human-like interaction behavior mimicking real user jitter
                await type_with_jitter(page, 'textarea[name="q"], input[name="q"]', keyword)
                await asyncio.sleep(0.5)
                await page.keyboard.press("Enter")

                # Step 5: On the results page, evaluate rank vs target url
                await page.wait_for_selector("#search", timeout=10000)
                
                rank = 0
                current_position = 1
                
                # Extract up to page 5 (depth ~50 results)
                for page_num in range(5): 
                    organic_links = await extract_clean_organic_hrefs(page)
                    
                    link_found = False
                    for link in organic_links:
                        # Normalize trailing slashes for safer match
                        clean_link = link.rstrip('/')
                        target_clean = target_url.rstrip('/')
                        
                        # Ignore social media links completely
                        if any(domain in clean_link for domain in SOCIAL_MEDIA_DOMAINS):
                            continue
                        
                        if target_clean in clean_link:
                            rank = current_position
                            link_found = True
                            print(f" -> Found match at rank {rank}!")
                            break
                        current_position += 1
                        
                    if link_found:
                        break
                        
                    if current_position > 50:
                        break # Exceeded threshold without finding url
                        
                    # Pagination logic
                    try:
                        next_button = page.locator('a#pnnext')
                        if await next_button.is_visible(timeout=3000):
                            await next_button.click()
                        else:
                            # Scroll to trigger continuous load
                            await page.keyboard.press("End")
                            await asyncio.sleep(3)
                            
                        await asyncio.sleep(random.uniform(2, 4))
                    except Exception:
                        break # End of pagination
                        
                results_dict[keyword] = rank
                
            except Exception as e:
                print(f"Failed to process keyword '{keyword}': {e}")
                results_dict[keyword] = None

            # Close context aggressively to wipe session cookies / filter-bubble state
            await context.close()
            
            # Step 6: Anti-bot Cooldown Period (8-15 seconds randomness limit)
            cooldown = random.uniform(8, 15)
            print(f"Waiting {cooldown:.2f} seconds before next keyword processing...\\n")
            await asyncio.sleep(cooldown)

        # Teardown the primary engine
        await browser.close()
        
    # Step 7: Final yield {key: rank}
    return results_dict

if __name__ == "__main__":
    # Blueprint implementation runner validation
    
    locations = LocationData(
        coords={"latitude": 41.8781, "longitude": -87.6298}, # Chicago, IL
        tz="America/Chicago",
        locale="en-US"
    )
    
    my_search_dict = {
        "cybersecurity services": "example.com",
        "network auditing": "example.com/audit"
    }
    
    print("SEO Rank Tracker initialization phase complete.")
    print("Algorithm schema ready to execute via: asyncio.run(track_rankings(locations, my_search_dict))")
