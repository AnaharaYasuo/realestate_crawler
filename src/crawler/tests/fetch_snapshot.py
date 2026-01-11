import asyncio
import aiohttp
import ssl
import os
import sys
import argparse
from bs4 import BeautifulSoup
import urllib3
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Config
TARGETS = {
    'misawa': {
        'mansion': {
            'list_url': "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=1",
            'base_url': "https://realestate.misawa.co.jp",
            'output': "data/misawa_mansion_mock.html"
        },
         'kodate': {
            'list_url': "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=2",
            'base_url': "https://realestate.misawa.co.jp",
            'output': "data/misawa_kodate_mock.html"
        },
        'tochi': {
            'list_url': "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=3",
            'base_url': "https://realestate.misawa.co.jp",
            'output': "data/misawa_tochi_mock.html"
        },
        'investment': {
            'list_url': "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=9",
            'base_url': "https://realestate.misawa.co.jp",
            'output': "data/misawa_investment_mock.html"
        }
    },
    'mitsui': {
        'mansion': {
            'list_url': "https://www.rehouse.co.jp/buy/mansion/prefecture/13/",
            'base_url': "https://www.rehouse.co.jp",
            'output': "data/mitsui_mansion_mock.html"
        },
        'kodate': {
            'list_url': "https://www.rehouse.co.jp/buy/kodate/prefecture/13/",
            'base_url': "https://www.rehouse.co.jp",
            'output': "data/mitsui_kodate_mock.html"
        },
        'tochi': {
            'list_url': "https://www.rehouse.co.jp/buy/tochi/prefecture/13/",
            'base_url': "https://www.rehouse.co.jp",
            'output': "data/mitsui_tochi_mock.html"
        },
        'investment_mansion': {
            'list_url': "https://www.rehouse.co.jp/buy/tohshi/prefecture-list/13/?buildingTypes=2",
            'base_url': "https://www.rehouse.co.jp",
            'output': "data/mitsui_investment_mansion_mock.html"
        },
         'investment_apartment': {
            'list_url': "https://www.rehouse.co.jp/buy/tohshi/prefecture-list/13/?buildingTypes=4",
            'base_url': "https://www.rehouse.co.jp",
            'output': "data/mitsui_investment_apartment_mock.html"
        },
         'investment_kodate': {
            'list_url': "https://www.rehouse.co.jp/buy/tohshi/prefecture-list/13/?buildingTypes=3",
            'base_url': "https://www.rehouse.co.jp",
            'output': "data/mitsui_investment_kodate_mock.html"
        }
    },
    'sumifu': {
        'mansion': {
            'list_url': "https://www.stepon.co.jp/mansion/",
            'base_url': "https://www.stepon.co.jp",
            'output': "data/sumifu_mansion_mock.html"
        },
         'kodate': {
            'list_url': "https://www.stepon.co.jp/kodate/",
            'base_url': "https://www.stepon.co.jp",
            'output': "data/sumifu_kodate_mock.html"
        },
        'tochi': {
            'list_url': "https://www.stepon.co.jp/tochi/",
            'base_url': "https://www.stepon.co.jp",
            'output': "data/sumifu_tochi_mock.html"
        },
        'investment_mansion': {
            'list_url': "https://www.stepon.co.jp/pro/area_13/list_13_100/?category=tatemono&smk=000100000000",
            'base_url': "https://www.stepon.co.jp",
            'output': "data/sumifu_investment_mansion_mock.html"
        },
        'investment_apartment': {
            'list_url': "https://www.stepon.co.jp/pro/area_13/list_13_100/?category=tatemono&smk=001000000000",
            'base_url': "https://www.stepon.co.jp",
            'output': "data/sumifu_investment_apartment_mock.html"
        },
        'investment_kodate': {
            'list_url': "https://www.stepon.co.jp/pro/area_13/list_13_100/?category=tatemono&smk=000001000000",
            'base_url': "https://www.stepon.co.jp",
            'output': "data/sumifu_investment_kodate_mock.html"
        }
    },
    'tokyu': {
        'mansion': {
            'list_url': "https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/a13121/",
            'base_url': "https://www.livable.co.jp",
            'output': "data/tokyu_mansion_mock.html"
        },
        'kodate': {
            'list_url': "https://www.livable.co.jp/kounyu/chuko-kodate/tokyo/a13121/",
            'base_url': "https://www.livable.co.jp",
            'output': "data/tokyu_kodate_mock.html"
        },
        'tochi': {
            'list_url': "https://www.livable.co.jp/kounyu/tochi/tokyo/a13121/",
            'base_url': "https://www.livable.co.jp",
            'output': "data/tokyu_tochi_mock.html"
        },
         'investment_mansion': {
            'list_url': "https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/conditions-use=mansion-kubun/",
            'base_url': "https://www.livable.co.jp",
            'output': "data/tokyu_investment_mansion_mock.html",
            'target_types': ['/fudosan-toushi/']
        },
         'investment_apartment': {
            'list_url': "https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/conditions-use=apart/",
            'base_url': "https://www.livable.co.jp",
            'output': "data/tokyu_investment_apartment_mock.html",
            'target_types': ['/fudosan-toushi/']
        },
         'investment_kodate': {
            'list_url': "https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/conditions-use=kodate/",
            'base_url': "https://www.livable.co.jp",
            'output': "data/tokyu_investment_kodate_mock.html",
            'target_types': ['/fudosan-toushi/']
        }
    },
    'nomura': {
        'mansion': {
            'list_url': "https://www.nomu.com/mansion/tokyo/",
            'base_url': "https://www.nomu.com",
            'output': "data/nomura_mansion_mock.html"
        },
        'kodate': {
            'list_url': "https://www.nomu.com/house/tokyo/",
            'base_url': "https://www.nomu.com",
            'output': "data/nomura_kodate_mock.html"
        },
        'tochi': {
            'list_url': "https://www.nomu.com/land/tokyo/",
            'base_url': "https://www.nomu.com",
            'output': "data/nomura_tochi_mock.html"
        },
        'investment': {
            'list_url': "https://www.nomu.com/pro/",
            'base_url': "https://www.nomu.com",
            'output': "data/nomura_investment_mock.html"
        }
    }
}


async def fetch_snapshot(target_site, target_type, debug_links=False, use_playwright=True):
    if target_site not in TARGETS:
        print(f"Unknown site: {target_site}")
        return
    if target_type not in TARGETS[target_site]:
         print(f"Unknown type: {target_type} for site {target_site}")
         return

    config = TARGETS[target_site][target_type]
    
    # Delete existing mock if it exists
    if os.path.exists(config['output']):
        print(f"[{target_site}-{target_type}] Deleting existing mock: {config['output']}")
        os.remove(config['output'])

    print(f"[{target_site}-{target_type}] Accessing list page: {config['list_url']}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Custom SSL Context for Misawa or general SSL issue handling
    ssl_context = None
    if target_site == 'misawa':
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        # Security level adjustment for Misawa SSL fix
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            ssl_val = ssl_context if ssl_context else False
            async with session.get(config['list_url'], ssl=ssl_val, timeout=30) as resp:
                if resp.status != 200:
                    print(f"Failed to fetch list page: Status {resp.status}")
                    return
                content = await resp.read()
                html = content.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Failed to fetch list page: {e}")
            return

        soup = BeautifulSoup(html, "html.parser")
        
        if debug_links:
            print(f"--- LINKS FOUND ON {config['list_url']} ---")
            with open("debug_list_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Saved list page to debug_list_page.html")
            for a in soup.find_all("a", href=True):
                print(a['href'])
            print("--- END LINKS ---")
            return
        
        links = []
        
        # Site-specific logic
        if target_site == 'mitsui':
            keyword = "/bkdetail/"
            for a in soup.find_all("a", href=True):
                if keyword in a['href']:
                   links.append(a['href'])
                   
        elif target_site == 'sumifu':
            if 'investment' in target_type:
                keyword = "/pro/detail_"
            else:
                keyword = f"/{target_type}/detail_"
            for a in soup.find_all("a", href=True):
                if keyword in a['href']:
                    links.append(a['href'])
                    
        elif target_site == 'tokyu':
            for a in soup.find_all("a", class_="o-product-list__link"):
                href = a.get('href', '')
                if href: links.append(href)
            if not links:
                patterns = ['/mansion/', '/kodate/', '/tochi/', '/fudosan-toushi/']
                for a in soup.find_all("a", href=True):
                    href = a['href']
                    if any(p in href for p in patterns) and href.count('/') >= 3:
                        if not any(x in href for x in ['area', 'search', 'library', 'select', 'request', 'tokyo', 'new', 'bukken-all']):
                            links.append(href)
                    
        elif target_site == 'nomura':
            segment_map = {'mansion': 'mansion', 'kodate': 'house', 'tochi': 'land'}
            segment = segment_map.get(target_type, target_type)
            keyword = "/pro/bukken_local_id/" if target_type == 'investment' else f"/{segment}/id/"
            for a in soup.find_all("a", href=True):
                if keyword in a['href']:
                    links.append(a['href'])
                    
        elif target_site == 'misawa':
            # Misawa detail links contain /detail/
            for a in soup.find_all("a", href=True):
                 if '/detail/' in a['href']:
                     links.append(a['href'])

        if not links:
            # Generic fallback
            keywords = config.get('target_types', ['/toushi/', '/fudosan-toushi/', '/pro/', 'bukken_id'])
            for a in soup.find_all("a", href=True):
                if any(kw in a['href'] for kw in keywords) and 'list' not in a['href']:
                    links.append(a['href'])

        if not links:
            print("No property links found.")
            return

        target_path = links[1] if len(links) > 1 else links[0]
        full_url = target_path if target_path.startswith("http") else config['base_url'] + target_path
        
        print(f"Found property URL: {full_url}")
        
        # Save to data directory relative to the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        abs_output = os.path.join(script_dir, config['output'])
        os.makedirs(os.path.dirname(abs_output), exist_ok=True)

        if not use_playwright:
            print(f"Fetching detail page with aiohttp (No Playwright)...")
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(full_url, ssl=ssl_val, timeout=30) as resp:
                        if resp.status != 200:
                            print(f"Failed to fetch detail page: Status {resp.status}")
                            return
                        content = await resp.read()
                        detail_html = content.decode('utf-8', errors='replace')
                        
                with open(abs_output, "w", encoding="utf-8") as f:
                    f.write(detail_html)
                print(f"Successfully saved {len(detail_html)} bytes to {abs_output}")
                return
            except Exception as e:
                print(f"Failed to fetch detail page with aiohttp: {e}")
                return

        if not PLAYWRIGHT_AVAILABLE:
            print("Error: Playwright is requested but not installed. Please use --no-playwright or install playwright.")
            return

        print("Fetching detail page with Playwright...")
        
        # Use Playwright to fetch detail page (handles JavaScrasync_playwrightipt-rendered content)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(full_url, wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(2000)  # Wait for JavaScript to render
                
                # Take screenshot for debugging
                screenshot_path = abs_output.replace('.html', '_screenshot.png')
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"Screenshot saved to {screenshot_path}")
                
                detail_html = await page.content()
                
                with open(abs_output, "w", encoding="utf-8") as f:
                    f.write(detail_html)
                print(f"Successfully saved {len(detail_html)} bytes to {abs_output}")
            except Exception as e:
                print(f"Failed to fetch detail page with Playwright: {e}")
            finally:
                await browser.close()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("site", help="Site name (e.g. mitsui, sumifu, misawa)")
    parser.add_argument("type", help="Property type (e.g. mansion, kodate, investment_mansion)")
    parser.add_argument("--debug-links", action="store_true")
    parser.add_argument("--no-playwright", action="store_true", help="Use aiohttp instead of Playwright for detail page")
    args = parser.parse_args()
    
    await fetch_snapshot(args.site, args.type, args.debug_links, use_playwright=not args.no_playwright)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(main())
    else:
        print("Usage: python fetch_snapshot.py <site> <type> [--debug-links]")
