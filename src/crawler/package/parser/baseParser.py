import chardet
import aiohttp
import traceback
import lxml.html
from bs4 import BeautifulSoup
import logging
import re

from abc import ABCMeta, abstractmethod
from builtins import Exception
import asyncio
from time import sleep
from django.db import models


class ReadPropertyNameException(Exception):

    def __init__(self):
        logging.info('Can not read property name')


class LoadPropertyPageException(Exception):

    def __init__(self):
        logging.info('Can not load property page')


class SkipPropertyException(Exception):
    """Base exception to skip a property without logging an error."""
    pass


class ListingEndedException(SkipPropertyException):
    """Raised when a property listing has ended."""
    pass


class ServerBusyException(SkipPropertyException):
    """Raised when the server is busy."""
    pass


class ParserBase(metaclass=ABCMeta):

    def __init__(self):
        self._specs_cache = {}

    @abstractmethod
    def getCharset(self):
        pass

    @abstractmethod
    def createEntity(self)->models.Model:
        return None
        
    @abstractmethod
    def _parsePropertyDetailPage(self, item:models.Model, response:BeautifulSoup)->models.Model:
        return item
    
    def save_error_html(self, url, content):
        import os
        import hashlib
        import re
        from pathlib import Path
        try:
            error_dir = Path("docs/error_pages")
            
            # Use model name for directory
            try:
                model_name = self.createEntity().__class__.__name__
                company_type = re.sub(r'(?<!^)(?=[A-Z])', '_', model_name).lower()
                company_dir = error_dir / company_type
            except:
                company_dir = error_dir / "unknown"
                
            company_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename from URL hash
            filename = hashlib.md5(url.encode('utf-8')).hexdigest() + ".html"
            filepath = company_dir / filename
            
            with open(filepath, "wb") as f:
                f.write(content)
            logging.info(f"Saved error HTML to {filepath}")
        except Exception as e:
            logging.error(f"Failed to save error HTML: {e}")

    async def parsePropertyDetailPage(self, session, url)->models.Model:
        item:models.Model = self.createEntity()
        content = None
        try:
            item.pageUrl = url
            # We need content for saving error page, so let's get response first
            # But getResponseBs calls _getContent which reads content.
            # To get raw content, we might need to adjust getResponseBs or retrieve it separately?
            # getResponseBs calls _getContent.
            # We can modify getResponseBs to attach content to response object or just call _getContent here?
            # But getResponseBs does encoding detection which is nice.
            # Let's just catch exception inside getResponseBs? No, exception happens in _parsePropertyDetailPage usually.
            
            # Ideally we want the content that was parsed.
            # Let's allow getResponseBs to return content too or just read it again? No reading stream twice is bad.
            # ParserBase structure is a bit rigid.
            # Let's peek at _getContent... it reads content.
            # lxml/BS parsed it. 
            # If we want to save the EXACT HTML that caused the error, we should probably access it from the response object if possible?
            # BS object doesn't hold raw bytes usually?
            # Actually, `getResponseBs` does `lxml.html.fromstring` or `BeautifulSoup`.
            
            # Refactor: Let's fetch content here first, then parse.
            content = await self._getContent(session, url)
            
            charset = self.getCharset()
            if charset is None:
                encoding = chardet.detect(content)["encoding"]
            else:
                encoding = charset
                
            soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)
            
            # Check for special pages
            title = soup.title.string if soup.title else ""
            if title:
                if "掲載終了物件" in title:
                    logging.info(f"Listing ended for URL: {url}")
                    raise ListingEndedException()
                if "サーバーが混み合っています" in title:
                    logging.info(f"Server busy for URL: {url}")
                    raise ServerBusyException()

            item = self._parsePropertyDetailPage(item, soup)
            
            # Centralized validation for "Strict Extraction"
            self.validate_required_fields(item)
            
        except SkipPropertyException as e:
            raise e
        except (LoadPropertyPageException, TimeoutError) as e:
            logging.error(f'Failure loading page: {url} - Reason: {str(e)}')
            raise e
        except (ReadPropertyNameException) as e:
            logging.error(f'Validation or parsing failure for mandatory fields: {url} - Reason: {str(e)}')
            if content: self.save_error_html(url, content)
            raise e
        except Exception as e:
            logging.error(f'Detail parse error: {url}')
            logging.error(f'Exception type: {type(e).__name__}')
            logging.error(f'Exception message: {str(e)}')
            logging.error(f'Full traceback:')
            logging.error(traceback.format_exc())
            if content: self.save_error_html(url, content)
            raise e
        return item

    async def _parsePageCore(self, response, getXpath , getDestUrl):
        xpath_str = getXpath()
        linklist = response.xpath(xpath_str)
        logging.info(f"XPath: {xpath_str} found {len(linklist) if linklist else 0} elements")
        for linkUrl in linklist:
            destUrl = getDestUrl(linkUrl)
            logging.debug(destUrl)
            yield destUrl

    async def parsePage(self, session, url, getXpath , getDestUrl):
        response = await self.getResponse(session, url, self.getCharset())        
        async for destUrl in self._parsePageCore(response, getXpath, getDestUrl):
            yield destUrl

    async def parsePageBs(self, session, url, getXpath , getDestUrl):
        response = await self.getResponseBs(session, url, self.getCharset())
        # Use CSS selector if it looks like one, otherwise fallback to finding elements
        selector = getXpath()
        if selector.startswith("/") or selector.startswith("("): # Likely XPath
             # BeautifulSoup doesn't naturally support Xpath. 
             # We assume here that if parsePageBs is used, the parser provides CSS selectors.
             # Or we fallback to the lxml-based parsePage.
             pass 
        
        # Standard implementation for BS:
        for link in response.select(selector):
            href = link.get("href")
            if href:
                destUrl = getDestUrl(href)
                yield destUrl

    async def _get(self, session, url):
        max_retries = 3
        retry_count = 0
        while retry_count <= max_retries:
            try:
                return await session.get(url)
            except (asyncio.TimeoutError, TimeoutError, 
                    aiohttp.client_exceptions.ClientConnectorError, 
                    aiohttp.client_exceptions.ServerDisconnectedError) as e:
                retry_count += 1
                if retry_count > max_retries:
                    logging.error(f"Max retries ({max_retries}) exceeded for {url}")
                    raise e
                
                wait_time = 2 ** retry_count
                logging.warning(f"Connection error for {url}, retry {retry_count}/{max_retries} after {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logging.error(f"Unexpected error in _get for {url}: {e}")
                raise e
            
    async def _getContent(self, session, url):
        try:
            r = await self._get(session, url)
            logging.info(f"Response status: {r.status} for URL: {url}")
            # r = await session.get(url)
            content = await r.content.read()
            return  content
        except aiohttp.ClientError as e:
            logging.error(traceback.format_exc())
            raise e
        except (Exception) as e:
            logging.error(traceback.format_exc())
            raise e
            
    async def getResponse(self, session, url, charset=None):

        async def getDocument():
            content = await self._getContent(session, url)
            if (charset is None):
                encoding = self.getCharset()
                if(encoding is None):
                    encoding = chardet.detect(content)["encoding"]
            else:
                encoding = charset
            
            html_text = content[:1000].decode(encoding, errors='ignore')
            logging.info(f"Response snippet for {url}: {html_text}")

            return  lxml.html.fromstring(html=content, parser=lxml.html.HTMLParser(encoding=encoding))

        try:
            return await getDocument()
        except(TypeError):
            return await getDocument()

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:

        async def getDocument():
            content = await self._getContent(session, url)
            if (charset is None):
                encoding = self.getCharset()
                if(encoding is None):
                    encoding = chardet.detect(content)["encoding"]
            else:
                encoding = charset
            
            soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)
            
            # Check for special pages to skip
            title = soup.title.string if soup.title else ""
            if title:
                if "掲載終了物件" in title:
                    logging.info(f"Listing ended for URL: {url}")
                    raise ListingEndedException()
                if "サーバーが混み合っています" in title:
                    logging.info(f"Server busy for URL: {url}")
                    raise ServerBusyException()

            return soup

        try:
            return await getDocument()
        except(TypeError):
            return await getDocument()

    def _getValueFromTable(self, response: BeautifulSoup, title: str, partial_match: bool = False):
        """
        Common extraction logic: Find 'th' containing title, return next 'td'.
        Useful for standard key-value tables in property pages.
        Handles <br> tags in headers by using get_text().
        """
        if not response: return None
        
        # First try exact string match (faster)
        target = response.find("th", string=re.compile(title))
        if target:
            return target.find_next_sibling("td")
        
        # Fallback: search all th elements and check text content
        # This handles cases where <br> tags are present
        for th in response.find_all("th"):
            th_text = th.get_text()
            if title in th_text:
                return th.find_next_sibling("td")
        
        return None

    def _getValueFromDl(self, soup: BeautifulSoup, label: str):
        """
        Search for values in dl/dt/dd structures.
        Useful for 'Point' sections or properties using display lists.
        """
        if not soup: return None
        # Search all dt elements
        dts = soup.select('dt')
        for dt in dts:
            if label in dt.get_text():
                return dt.find_next_sibling('dd')
        return None

    def _getValueByLabel(self, soup: BeautifulSoup, label: str):
        """
        Robustly find a value associated with a label, regardless of structure.
        Checks: th/td, dt/dd, and same-tag mixed content.
        """
        if not soup: return None
        
        # 1. Search in tables (th/td)
        res = self._getValueFromTable(soup, label)
        if res: return res
        
        # 2. Search in definition lists (dt/dd)
        res = self._getValueFromDl(soup, label)
        if res: return res
        
        # 3. Search for tags containing the label (e.g. span, p, div)
        # This handles summary bars where labels and values are just listed together.
        # We look for the tag itself or its immediate parent/sibling.
        regex = re.compile(re.escape(label))
        tags = soup.find_all(string=regex)
        for tag_str in tags:
            parent = tag_str.parent
            if parent:
                # If label is "専有面積" and text is "専有面積87.32m2", return the parent or string itself
                # But usually we want to return a BeautifulSoup Tag to keep compatibility with .get_text()
                # If the string contains more than just the label, it might be the value too.
                full_text = parent.get_text(strip=True)
                if len(full_text) > len(label) + 1: # Value likely included
                     return parent
                
                # Try next sibling if parent text only contained the label
                sibling = parent.find_next_sibling()
                if sibling:
                    return sibling
                    
        return None

    def _scrape_to_dict(self, soup: BeautifulSoup):
        """
        Scrape all standard table (th/td) and definition list (dt/dd) data into a dictionary.
        Keys are labels, values are Tag/NavigableString or text.
        Also handles Mitsui's Vue.js structure: td.table-header + td.table-data
        """
        data = {}
        if not soup: return data

        # 1. th/td (standard) - Handles multiple pairs per row
        for tr in soup.find_all("tr"):
            # Get all th and td children
            cells = tr.find_all(['th', 'td'], recursive=False)
            if not cells:
                continue
                
            # Iterate through cells to find th -> td pairs
            for i in range(len(cells) - 1):
                if cells[i].name == 'th' and cells[i+1].name == 'td':
                    key = cells[i].get_text(strip=True)
                    if key and key not in data:
                        data[key] = cells[i+1]
        
        # 2. Mitsui Vue.js structure: td.table-header + td.table-data
        for tr in soup.find_all("tr", class_="table-row"):
            header_td = tr.find("td", class_=lambda x: x and "table-header" in x)
            data_td = tr.find("td", class_=lambda x: x and "table-data" in x)
            if header_td and data_td:
                key = header_td.get_text(strip=True)
                if key and key not in data:
                    data[key] = data_td
        
        # 3. dt/dd (more robust: finds pairs even if not wrapped in dl)
        # Search for all dt tags and their immediate dd siblings
        for dt in soup.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                key = dt.get_text(strip=True)
                if key and key not in data:
                    data[key] = dd
        
        return data

    def validate_required_fields(self, item: models.Model):
        """
        Validate that mandatory fields (Universal Fields) are correctly extracted.
        Raises ReadPropertyNameException if validation fails.
        """
        issues = []
        
        # 1. Property Name
        name = getattr(item, 'propertyName', None)
        if not name or not str(name).strip():
            issues.append("propertyName")
            
        # 2. Price
        # price can be 0 or None, but for Strict Extraction, missing price is an error.
        # Check if price is set (usually int or Decimal)
        price = getattr(item, 'price', None)
        if price is None or price == 0:
            # Check if priceStr exists as a fallback check
            price_str = getattr(item, 'priceStr', None)
            if not price_str or not str(price_str).strip():
                issues.append("price")
                
        # 3. Address
        address = getattr(item, 'address', None)
        if not address or not str(address).strip() or address == "-":
            issues.append("address")
            
        if issues:
            logging.error(f"Validation failed for mandatory fields: {', '.join(issues)}")
            raise ReadPropertyNameException()
    def _get_specs(self, response: BeautifulSoup):
        """
        Retrieve and cache specifications from the response.
        Uses _scrape_to_dict internally.
        """
        resp_id = id(response)
        if resp_id not in self._specs_cache:
            specs_tags = self._scrape_to_dict(response)
            # Remove trailing colon from keys for consistency
            self._specs_cache[resp_id] = {k.rstrip("："): v.get_text(strip=True) for k, v in specs_tags.items()}
        return self._specs_cache[resp_id]
