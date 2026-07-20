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

    def __init__(self, msg='Can not read property name'):
        super().__init__(msg)
        logging.info(msg)


class LoadPropertyPageException(Exception):

    def __init__(self, msg='Can not load property page'):
        super().__init__(msg)
        logging.info(msg)


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

    def clean_parsed_item(self, item: models.Model) -> models.Model:
        """
        スクレイピングした物件データの全文字列フィールドに対して：
        1. 前後の余分な空白・改行コードの除去
        2. 全て文字中の複数スペース（二重空白、タブ、改行等含む）を単一スペースに置換
        3. 文字列としての "None" や "none" などの無効値を空文字または None に変換
        """
        import re
        for field in item._meta.fields:
            val = getattr(item, field.name, None)
            if val is None:
                continue
                
            if isinstance(field, (models.CharField, models.TextField)):
                val_str = str(val).strip()
                
                if val_str.lower() in ["none", ""]:
                    if field.null:
                        setattr(item, field.name, None)
                    else:
                        setattr(item, field.name, "")
                    continue
                
                val_cleaned = re.sub(r'\s+', ' ', val_str)
                setattr(item, field.name, val_cleaned)
                
        return item
    
    def save_error_html(self, url, content, reason="Parsing failed"):
        import os
        import hashlib
        import re
        from pathlib import Path
        import datetime
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
            base_filename = hashlib.sha256(url.encode('utf-8')).hexdigest()
            html_filepath = company_dir / (base_filename + ".html")
            meta_filepath = company_dir / (base_filename + "_meta.txt")
            
            with open(html_filepath, "wb") as f:
                f.write(content)
                
            with open(meta_filepath, "w", encoding="utf-8") as f:
                f.write(f"URL: {url}\n")
                f.write(f"Reason: {reason}\n")
                f.write(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
            logging.info(f"Saved error HTML and meta to {company_dir}/{base_filename}")
        except Exception:
            logging.exception("Failed to save error HTML and meta")

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
            item = self.clean_parsed_item(item)
            item._soup = soup
            
            # Centralized validation for "Strict Extraction"
            self.validate_required_fields(item)
            
        except SkipPropertyException as e:
            raise e
        except (LoadPropertyPageException, TimeoutError) as e:
            logging.error(f'Failure loading page: {url} - Reason: {str(e)}')
            raise e
        except (ReadPropertyNameException) as e:
            logging.error(f'Validation or parsing failure for mandatory fields: {url} - Reason: {str(e)}')
            if content: self.save_error_html(url, content, reason=str(e))
            raise e
        except Exception as e:
            logging.error(f'Detail parse error: {url}')
            logging.error(f'Exception type: {type(e).__name__}')
            logging.error(f'Exception message: {str(e)}')
            logging.error(f'Full traceback:')
            logging.error(traceback.format_exc())
            if content: self.save_error_html(url, content, reason=str(e))
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
        
        # 動的ヘッダー（Referer等）の設定
        headers = {}
        if "athome.co.jp" in url:
            headers['Referer'] = 'https://www.google.com/'
            # WAFの負荷制限対策としてクロール前に短い遅延（1秒）を設定
            await asyncio.sleep(1.0)
        elif "homes.co.jp" in url:
            headers['Referer'] = 'https://toushi.homes.co.jp/'
            
        while retry_count <= max_retries:
            try:
                if headers:
                    return await session.get(url, headers=headers)
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
        # アットホームは厳格なWAF規制のため、urllibと本物ブラウザヘッダの組み合わせで接続を偽装して回避
        if "athome.co.jp" in url:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/',
                'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"'
            }
            
            # WAF負荷保護対策としてリクエスト前に短いディレイを置く
            await asyncio.sleep(1.0)
            
            req = urllib.request.Request(url, headers=headers)
            loop = asyncio.get_event_loop()
            
            def run_urllib():
                with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                    return resp.read()
            try:
                content = await loop.run_in_executor(None, run_urllib)
                logging.info(f"urllib fetch success: {len(content)} bytes for URL: {url}")
                return content
            except Exception as e:
                logging.error(f"urllib fetch failed for {url}: {e}")
                raise e

        try:
            r = await self._get(session, url)
            if r is None:
                raise Exception(f"Failed to fetch content from {url} (response is None)")
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
        Also handles tables that use 'td' tags as label headers (e.g., td.table-header or td.label).
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
                
        # Additional Fallback: Search all td elements acting as labels
        for td in response.find_all("td"):
            td_text = td.get_text(strip=True)
            if title == td_text or (partial_match and title in td_text):
                sib = td.find_next_sibling("td")
                if sib:
                    return sib
        
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
        
        # 2. Mitsui Vue.js structure: td.table-header/label + td.table-data/content
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            for i in range(len(tds) - 1):
                t1 = tds[i]
                t2 = tds[i+1]
                t1_class = t1.get("class", [])
                t2_class = t2.get("class", [])
                # クラスリストを平滑化して判定
                t1_class_str = " ".join(t1_class) if isinstance(t1_class, list) else str(t1_class)
                t2_class_str = " ".join(t2_class) if isinstance(t2_class, list) else str(t2_class)
                
                t1_is_header = "table-header" in t1_class_str or "label" in t1_class_str
                t2_is_data = "table-data" in t2_class_str or "content" in t2_class_str
                
                if t1_is_header and t2_is_data:
                    key = t1.get_text(strip=True)
                    if key and key not in data:
                        data[key] = t2
        
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

    def _populateTraffic(self, item, traffic_str_or_list):
        if not traffic_str_or_list:
            return
        if isinstance(traffic_str_or_list, list):
            traffic_str = "  ".join(str(x) for x in traffic_str_or_list if x)
        else:
            traffic_str = str(traffic_str_or_list)
            
        import re
        # 改行、スラッシュ、全角スペースなどのあらゆるセパレータを整理
        s = re.sub(r'[\r\n]+', '  ', traffic_str)
        s = re.sub(r'\s*/\s*', '  ', s)
        s = re.sub(r'\s*／\s*', '  ', s)
        s = re.sub(r'\s*、\s*', '  ', s)
        s = re.sub(r'　', '  ', s)
        # 徒歩/停歩/分/バス乗車等の直後にスペースを強制挿入
        s = re.sub(r'((?:徒歩|停歩|分)\d+分)\s*(?=\S)', r'\1  ', s)
        
        raw_lines = [p.strip() for p in re.split(r'\s{2,}', s) if p.strip()]
        
        # 引き裂かれた要素 (路線名, 駅名, 徒歩分数がばらばらに分割されたもの) をスマートに再結合する
        lines = []
        temp_line = ""
        for p in raw_lines:
            if not temp_line:
                temp_line = p
            else:
                has_walk_temp = any(x in temp_line for x in ["徒歩", "分", "停歩", "バス"])
                is_walk_p = any(x in p for x in ["徒歩", "分", "停歩", "バス"])
                has_station_temp = any(x in temp_line for x in ["駅", "」", "』"])
                is_station_p = any(x in p for x in ["駅", "」", "』"])
                
                # 駅名や徒歩分数が前の要素にまだ含まれていない場合、それは同じ系統の断片であるとみなし結合する
                if (not has_station_temp and is_station_p) or (not has_walk_temp and is_walk_p):
                    temp_line = temp_line + " " + p
                else:
                    lines.append(temp_line)
                    temp_line = p
        if temp_line:
            lines.append(temp_line)
            
        for idx in range(1, 6):
            if idx > len(lines):
                break
            line = lines[idx-1].strip()
            if not line:
                continue
                
            railway = ""
            station = ""
            walk_min = None
            walk_min_str = ""
            bus_min = None
            bus_min_str = ""
            bus_use = 0
            bus_station = ""
            
            # 徒歩分数・バス情報
            if "バス" in line:
                bus_use = 1
                m_bus = re.search(r'バス\s*(\d+)\s*分', line)
                if m_bus:
                    bus_min = int(m_bus.group(1))
                    bus_min_str = str(bus_min)
                m_bus_walk = re.search(r'(?:徒歩|停歩)\s*(\d+)\s*分', line)
                if m_bus_walk:
                    walk_min = int(m_bus_walk.group(1))
                    walk_min_str = str(walk_min)
                bus_station = f"バス乗車{bus_min}分" if bus_min else ""
                
                setattr(item, f"railwayWalkMinute{idx}", None)
                setattr(item, f"railwayWalkMinute{idx}Str", "")
                setattr(item, f"busWalkMinute{idx}", walk_min)
                setattr(item, f"busWalkMinute{idx}Str", walk_min_str)
            else:
                m_walk = re.search(r'(?:徒歩|停歩)\s*(\d+)\s*分', line)
                if m_walk:
                    walk_min = int(m_walk.group(1))
                    walk_min_str = str(walk_min)
                
                setattr(item, f"railwayWalkMinute{idx}", walk_min)
                setattr(item, f"railwayWalkMinute{idx}Str", walk_min_str)
                setattr(item, f"busWalkMinute{idx}", None)
                setattr(item, f"busWalkMinute{idx}Str", "")
                
            # 沿線名と駅名
            m_bracket = re.search(r'^(.*?)\s*[「『（\(]([^」』）\)]+)[」』）\)]', line)
            if m_bracket:
                railway = m_bracket.group(1).strip()
                station = m_bracket.group(2).strip()
            else:
                m_station = re.search(r'^(.*?)\s+(\S+?)駅', line)
                if m_station:
                    railway = m_station.group(1).strip()
                    station = m_station.group(2).strip()
                else:
                    clean_line = re.sub(r'(?:徒歩|停歩|バス).*$', '', line).strip()
                    if "・" in clean_line and "駅" in clean_line:
                        parts = clean_line.split("・")
                    else:
                        parts = re.split(r'\s+', clean_line)
                        
                    if len(parts) >= 2:
                        railway = parts[0].strip()
                        station = parts[1].strip()
                    elif len(parts) == 1:
                        station = parts[0].strip()

            if station.endswith("駅"):
                station = station[:-1]
                
            setattr(item, f"railway{idx}", railway)
            setattr(item, f"station{idx}", station)
            setattr(item, f"busUse{idx}", bus_use)
            setattr(item, f"busStation{idx}", bus_station)
            setattr(item, f"transfer{idx}", line)

    def _parsePropertyName(self, response: BeautifulSoup) -> str:
        """
        物件名（propertyName）を構造的・根本的に取得する共通メソッド。
        各サイトの余計なSEO定型文言（「不動産購入、」「マンション（居住用）」など）が混入するのを防ぐため、
        スペックテーブルやパンくずリストなどの構造化された部分から優先的に抽出します。
        """
        import re
        # 1. サイト個別のカスタムセレクタや汎用クレンジング要素があれば最優先
        custom_selectors = [
            'h1.property-detail-carousel-luxury__building-name',
            'ol.breadcrumb-list li.breadcrumb-list-item:last-child span',
            'ol.breadcrumb-list li:last-child span',
            self.selectors.get('property_name_clean'),
            '#property_name',
            '.property-name-clean',
            '.property-title-clean'
        ]
        for sel in custom_selectors:
            if sel:
                el = response.select_one(sel)
                if el:
                    name = el.get_text(strip=True)
                    if name: return name

        # 2. スペックテーブル (specs) の中のキーから優先取得
        try:
            specs = self._get_specs(response)
        except Exception:
            specs = {}
            
        if specs:
            for key in ["物件名", "名称", "マンション名", "建物名", "アパート名"]:
                if key in specs and specs[key]:
                    val = specs[key].strip()
                    if val and val != "-":
                        return val

        # 3. パンくずリスト (Breadcrumbs) の末尾から2番目（建物名ページへのリンク）または末尾から取得
        breadcrumb_selectors = [
            'ol.breadcrumb-list a[href*="/building/"] span',
            'ol.breadcrumb-list li:nth-last-child(2) span[itemprop="name"]',
            'div.breadcrumb ul li:last-child',
            'ol.breadcrumb li:last-child a',
            'ol.breadcrumb li:last-child span',
            '.breadcrumb a:last-child',
            '.breadcrumb span:last-child'
        ]
        for sel in breadcrumb_selectors:
            el = response.select_one(sel)
            if el:
                val = el.get_text(strip=True)
                if val and val not in ["TOP", "ホーム", "詳細", "物件詳細", "物件概要", "不動産購入"]:
                    if len(val) < 40:
                        return val

        # 4. フォールバック: 各サイトの YAML に定義された title セレクタ、または <h1>
        title_selector = self.selectors.get('title')
        if title_selector:
            el = response.select_one(title_selector)
            if el:
                val = el.get_text(strip=True)
                if val: return val
                
        h1 = response.find("h1")
        if h1:
            return h1.get_text(strip=True)
            
        raise ReadPropertyNameException("Could not find property name through common structures")

    def validateEntity(self, item):
        """
        パース完了後の物件データに対して厳格なバリデーションを実行する。
        スクレイピング誤りやバグによるゴミデータのDB混入を防ぐ防衛機構。
        """
        model_name = item.__class__.__name__
        is_tochi = "tochi" in model_name.lower()
        is_mansion = "mansion" in model_name.lower()
        is_kodate = "kodate" in model_name.lower() or "investment" in model_name.lower()
        
        # 1. 物件名 (propertyName) の検証
        if not item.propertyName:
            raise ValueError(f"[{model_name}] バリデーションエラー: 物件名 (propertyName) が空です。")
        
        # 定型SEO文言の混入検知
        seo_keywords = ["不動産購入、", "の中古マンション", "マンション（居住用）", "の物件情報", "の中古一戸建て"]
        for kw in seo_keywords:
            if kw in item.propertyName:
                raise ValueError(f"[{model_name}] バリデーションエラー: 物件名に定型SEO文言が混入しています: '{item.propertyName}'")
                
        if len(item.propertyName) < 2:
            raise ValueError(f"[{model_name}] バリデーションエラー: 物件名が極端に短いです: '{item.propertyName}'")

        # 2. 価格 (price) の検証
        if not item.price or item.price <= 0:
            raise ValueError(f"[{model_name}] バリデーションエラー: 価格 (price) が空、または0以下です。")
        
        # 万円単位スケールバグの検知 (価格が100万円未満)
        if item.price < 1000000:
            raise ValueError(f"[{model_name}] バリデーションエラー: 価格が100万円未満と異常に低いです (万円スケールバグの疑い): {item.price}円")

        # 3. 住所 (address) の検証
        if not item.address:
            raise ValueError(f"[{model_name}] バリデーションエラー: 所在地 (address) が空です。")
            
        if not getattr(item, "address1", "") or not getattr(item, "address2", ""):
            raise ValueError(f"[{model_name}] バリデーションエラー: 都道府県名 (address1) または市区町村名 (address2) が分割パースされていません。")

        # 4. 交通情報 (railway1 / station1) の検証
        # 交通情報が全くない場合は警告・エラー
        if not getattr(item, "railway1", "") or not getattr(item, "station1", ""):
            raise ValueError(f"[{model_name}] バリデーションエラー: 第1交通（路線名/駅名）が空です。")
            
        # 路線名への余計な文字混入の検知
        r1 = getattr(item, "railway1", "")
        if "徒歩" in r1 or "停歩" in r1 or "駅" in r1 or re.search(r"\d+分", r1) or re.search(r"[０-９]+分", r1):
            raise ValueError(f"[{model_name}] バリデーションエラー: 路線名に『徒歩/分/停歩/駅』などの不要なテキストが混入しています: '{r1}'")
            
        # 駅名への記号・カッコ混入の検知
        s1 = getattr(item, "station1", "")
        if "」" in s1 or "』" in s1 or "）" in s1 or "「" in s1 or "『" in s1:
            raise ValueError(f"[{model_name}] バリデーションエラー: 駅名に『」/』/）/「/『』などのカッコ記号が混入しています: '{s1}'")

        # 路線/駅が空なのに徒歩分数だけある不整合
        if (not r1 or not s1) and getattr(item, "railwayWalkMinute1", None) is not None:
             raise ValueError(f"[{model_name}] バリデーションエラー: 路線名または駅名が空なのに、徒歩分数が入っています。")

        # 5. 面積・専有面積の検証
        if is_mansion:
            menseki = getattr(item, "senyuMenseki", 0)
            if not menseki or float(menseki) <= 0:
                raise ValueError(f"[{model_name}] バリデーションエラー: 専有面積 (senyuMenseki) が空、または0以下です。")
        elif is_tochi or is_kodate:
            menseki = getattr(item, "tochiMenseki", 0)
            if not menseki or float(menseki) <= 0:
                raise ValueError(f"[{model_name}] バリデーションエラー: 土地面積 (tochiMenseki) が空、または0以下です。")

        # 6. 築年月 (chikunengetsuStr) の検証 (土地以外)
        if not is_tochi:
            chikunen_str = getattr(item, "chikunengetsuStr", "")
            if not chikunen_str:
                raise ValueError(f"[{model_name}] バリデーションエラー: 築年月 (chikunengetsuStr) が空です。")
            if "昭和年" in chikunen_str or "平成年" in chikunen_str or "令和年" in chikunen_str:
                raise ValueError(f"[{model_name}] バリデーションエラー: 築年月テキストが不完全です: '{chikunen_str}'")

    def _split_address(self, address: str) -> tuple[str, str, str]:
        """
        住所を都道府県名、市区町村名、町名以降に堅牢に分割する。
        「市原市」「町田市」などの「市」「町」等で始まる地名に対応。
        都道府県名がない場合は、主要市区町村名から都道府県名を自動補完する。
        """
        if not address:
            return "", "", ""
            
        # 1. 都道府県名 (pref) の切り出し
        pref_match = re.match(r'^([^都道府県]+[都道府県])(.*)$', address)
        if not pref_match:
            pref = ""
            rest = address
        else:
            pref = pref_match.group(1)
            rest = pref_match.group(2)
            
        # 2. 政令指定都市の「〇〇市〇〇区」の優先判定 (非貪欲マッチを使用)
        ordinance_match = re.match(r'^(.+?市.+?区)(.*)$', rest)
        if ordinance_match:
            city = ordinance_match.group(1)
            town = ordinance_match.group(2)
        else:
            # 3. 一般市区町村の判定
            city_match = re.match(r'^(.+?(?:市|区|郡[^市区]*?[町村]|町|村))(.*)$', rest)
            if city_match:
                city = city_match.group(1)
                town = city_match.group(2)
            else:
                city = ""
                town = rest
                
        # 4. 都道府県名がない場合の自動補完 (関東一都三県マッピング)
        if not pref and city:
            # 神奈川県の市区町村
            kanagawa_cities = {
                "横浜市", "川崎市", "相模原市", "横須賀市", "平塚市", "鎌倉市", "藤沢市", "小田原市", 
                "茅ヶ崎市", "逗子市", "三浦市", "秦野市", "厚木市", "大和市", "伊勢原市", "海老名市", 
                "座間市", "南足柄市", "綾瀬市", "三浦郡", "高座郡", "中郡", "足柄上郡", "足柄下郡", "愛甲郡"
            }
            # 千葉県の市区町村
            chiba_cities = {
                "千葉市", "銚子市", "市川市", "船橋市", "館山市", "木更津市", "松戸市", "野田市", 
                "茂原市", "成田市", "佐倉市", "東金市", "旭市", "習志野市", "柏市", "勝浦市", 
                "市原市", "流山市", "八千代市", "我孫子市", "鴨川市", "鎌ケ谷市", "君津市", "富津市", 
                "浦安市", "四街道市", "袖ケ浦市", "八街市", "印西市", "白井市", "富里市", "南房総市", 
                "匝瑳市", "香取市", "山武市", "いすみ市", "大網白里市", "印旛郡", "香取郡", "山武郡", 
                "長生郡", "夷隅郡", "安房郡"
            }
            # 埼玉県の市区町村
            saitama_cities = {
                "さいたま市", "川越市", "熊谷市", "川口市", "行田市", "秩父市", "所沢市", "飯能市", 
                "加須市", "本庄市", "東松山市", "春日部市", "狭山市", "羽生市", "鴻巣市", "深谷市", 
                "上尾市", "草加市", "越谷市", "蕨市", "戸田市", "入間市", "朝霞市", "志木市", 
                "和光市", "新座市", "桶川市", "久喜市", "北本市", "八潮市", "富士見市", "三郷市", 
                "蓮田市", "坂戸市", "幸手市", "鶴ヶ島市", "日高市", "吉川市", "ふじみ野市", "白岡市", 
                "北足立郡", "入間郡", "比企郡", "秩父郡", "児玉郡", "大里郡", "南埼玉郡", "北葛飾郡"
            }
            
            if any(city.startswith(c) for c in kanagawa_cities):
                pref = "神奈川県"
            elif any(city.startswith(c) for c in chiba_cities):
                pref = "千葉県"
            elif any(city.startswith(c) for c in saitama_cities):
                pref = "埼玉県"
            else:
                # デフォルトで東京都 (23区、および多摩地域など)
                pref = "東京都"
                
        return pref, city, town


