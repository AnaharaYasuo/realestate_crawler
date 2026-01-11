import chardet
import aiohttp
import traceback
import lxml.html
from bs4 import BeautifulSoup
import logging

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


class ParserBase(metaclass=ABCMeta):

    @abstractmethod
    def getCharset(self):
        pass

    @abstractmethod
    def createEntity(self)->models.Model:
        return None
        
    @abstractmethod
    def _parsePropertyDetailPage(self, item:models.Model, response:BeautifulSoup)->models.Model:
        return item
    
    async def parsePropertyDetailPage(self, session, url)->models.Model:
        item:models.Model = self.createEntity()
        try:
            item.pageUrl = url
            response:BeautifulSoup = await self.getResponseBs(session, url)
            item = self._parsePropertyDetailPage(item, response)
        except (LoadPropertyPageException, TimeoutError) as e:
            raise e
        except (ReadPropertyNameException) as e:
            raise e
        except Exception as e:
            logging.error('Detail parse error:' + url)
            logging.error(traceback.format_exc())
            raise e
        return item

    async def _parsePageCore(self, response, getXpath , getDestUrl):
        linklist = response.xpath(getXpath())
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
        linklist = response.xpath(getXpath())
        for linkUrl in linklist:
            destUrl = getDestUrl(linkUrl)
            logging.info(destUrl)
            yield destUrl

    async def _get(self, session, url):
        try:
            r = await session.get(url)
        except (asyncio.TimeoutError, TimeoutError, aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ServerDisconnectedError):
            sleep(10)
            r = await session.get(url)
        return r
            
    async def _getContent(self, session, url):
        try:
            r = await self._get(session, url)
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
            return  BeautifulSoup(content, "html.parser", from_encoding=encoding)

        try:
            return await getDocument()
        except(TypeError):
            return await getDocument()
