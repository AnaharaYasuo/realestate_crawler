from bs4 import BeautifulSoup
from package.parser.misawaParser import MisawaParser
import asyncio
import aiohttp
import logging

class Misawa:
    def __init__(self, limit=None, target_types=None):
        self.limit = limit
        self.base_url = "https://www.misawa-mrd.co.jp/search/"
        # Types: 1:Mansion, 2:Kodate, 3:Tochi, 4:Investment
        if target_types:
            self.target_types = target_types
        else:
            self.target_types = ['1', '2', '3', '4'] 

    async def crawl(self):
        async with aiohttp.ClientSession() as session:
            for p_type in self.target_types:
                logging.info(f"Starting crawl for Misawa Type: {p_type}")
                parser = MisawaParser(p_type)
                
                # Construct search URL
                search_url = f"{self.base_url}?type={p_type}"
                
                # Get Detail URLs (parsePage)
                # MisawaParser.getRootXpath defined
                # Note: This is simplified. Pagination might need handling if not just one page.
                # Assuming baseParser's parsePage handles standard simple navigation or we implement custom here.
                # For now, let's just use the parser's methods manually to control flow.
                
                try:
                    # Fetch Search Page
                    response_bs = await parser.getResponseBs(session, search_url)
                    detail_links = response_bs.select("ul.bukken-list li a")
                    
                    count = 0
                    for link in detail_links:
                        if self.limit and count >= self.limit:
                            break
                        
                        href = link.get('href')
                        detail_url = parser.getRootDestUrl(href)
                        
                        logging.info(f"Processing: {detail_url}")
                        try:
                            item = await parser.parsePropertyDetailPage(session, detail_url)
                            item.save()
                            logging.info(f"Saved: {item.propertyName}")
                            count += 1
                        except Exception as e:
                            logging.error(f"Failed to process {detail_url}: {e}")
                            
                except Exception as e:
                     logging.error(f"Error crawling type {p_type}: {e}")

async def main_crawl(limit=None):
    crawler = Misawa(limit)
    await crawler.crawl()

if __name__ == "__main__":
    # Integration test
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate_crawler.settings')
    django.setup()
    
    asyncio.run(main_crawl(limit=3))
