import chardet
import aiohttp
import traceback
import lxml.html
from bs4 import BeautifulSoup
import logging

from abc import ABCMeta, abstractmethod
from builtins import Exception


class ReadPropertyNameException(Exception):

    def __init__(self):
        print('Can not read property name')


class LoadPropertyPageException(Exception):

    def __init__(self):
        print('Can not load property page')


class ParserBase(metaclass=ABCMeta):

    @abstractmethod
    def getCharset(self):
        pass

    async def parsePage(self, session, url, getXpath , getDestUrl):
        response = await self.getResponse(session, url, self.getCharset())
        linklist = response.xpath(getXpath())
        for linkUrl in linklist:
            destUrl = getDestUrl(linkUrl)
            logging.info(destUrl)
            yield destUrl        

    async def parsePageBs(self, session, url, getXpath , getDestUrl):
        response = await self.getResponseBs(session, url, self.getCharset())
        linklist = response.xpath(getXpath())
        for linkUrl in linklist:
            destUrl = getDestUrl(linkUrl)
            logging.info(destUrl)
            yield destUrl
            
    async def _getContent(self, session, url):
        try:
            r = await session.get(url)
            content = await r.content.read()
            return  content
        except aiohttp.ClientError as e:
            print(traceback.format_exc())
            print(e)
            return  None
        except (Exception) as e:
            print(traceback.format_exc())
            print(e)
            
    async def getResponse(self, session, url, charset=None):

        async def getDocument():
            content = await self._getContent(session, url)
            if (charset is None):
                encoding = self.getCharset()
                if(encoding is None):
                    encoding = chardet.detect(content)["encoding"]
            else:
                encoding = charset
            return  lxml.html.fromstring(html=content, parser=lxml.html.HTMLParser(encoding=encoding))

        try:
            return await getDocument()
        except(TypeError):
            return await getDocument()

    async def getResponseBs(self, session, url, charset=None):

        async def getDocument():
            content = await self._getContent(session, url)
            if (charset is None):
                encoding = self.getCharset()
                if(encoding is None):
                    encoding = chardet.detect(content)["encoding"]
            else:
                encoding = charset
            return  BeautifulSoup(content, "html.parser", from_encoding=encoding)

        try:
            return await getDocument()
        except(TypeError):
            return await getDocument()
