# -*- coding: utf-8 -*-
import os
import sys
from concurrent.futures.thread import ThreadPoolExecutor
import concurrent.futures
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sumifuDjango.settings')
import importlib
import chardet
importlib.reload(sys)
from bs4 import BeautifulSoup
import logging
from decimal import Decimal
import datetime
import lxml.html
import django
django.setup()
from django.template.defaultfilters import length
from sumifuApp.models import SumifuMansion
import requests

# ssl._create_default_https_context = ssl._create_unverified_context


class GetSumifu(object):

    def __init__(self, params):
        ""

    def parse(self, url):
        response = self.getResponse(url)
        linklist = response.xpath(u'//a[contains(@href,"/mansion/area_")]/@href')
        for linkUrl in linklist:
            areaUrl = 'https://www.stepon.co.jp' + linkUrl
            logging.info(areaUrl)
            print('AreaUrl:' + areaUrl)
            yield areaUrl

    def parseAreaPage(self, url):
        response = self.getResponse(url)
        linklist = response.xpath(u'//a[contains(@href,"/mansion/area_") and contains(@href,"/list_") and contains(text(),"（")]/@href')
        for linkUrl in linklist:
            propListUrl = 'https://www.stepon.co.jp' + linkUrl + "?limit=10000&mode=2"
            logging.info(propListUrl)
            print('propList:' + propListUrl)
            yield propListUrl
        
    def parsePropertyListPage(self, url):
        response = self.getResponse(url)
        linklist = response.xpath(u'//*[@id="searchResultBlock"]//a[contains(@href, "mansion/detail") and contains(text(), "物件詳細")]/@href')
        for propDetailUrl in linklist:
            logging.info(propDetailUrl)
            # print('propDetailUrl:' + propDetailUrl)
            yield propDetailUrl

    def parsePropertyDetailPage(self, url):
        response = self.getResponseBs(url)
        item = SumifuMansion()

        item.pageUrl = url
        item.propertyName = response.find_all("div", id="bukkenNameBlockIcon")[0].find_all("h2")[0].find_all("span")[1].contents[0]
        # item.propertyName = response.xpath('//div[@id="bukkenNameBlockIcon"]/h2/span[2]/text()')[0]
        item.priceStr = response.find_all("dl", id="s_summaryPrice")[0].find_all("dd")[0].find_all("p")[0].find_all("em")[0].contents[0]
        # item.priceStr = response.xpath('//*[@id="s_summaryPrice"]/dd/p[1]/em/text()')[0]
        
        priceWork = item.priceStr.replace(',', '')
        oku = 0
        man = 0
        if u"億" in item.priceStr:
            priceArr = priceWork.split("億")
            oku = int(priceArr[0]) * 10000
            if length(priceArr[1]) != 0:
                man = int(priceArr[1])
        else:
            man = int(priceWork)
        price = oku + man
        item.price = price
        
        item.madori = response.find_all("dl", id="s_summaryMadori")[0].find_all("dd")[0].find_all("em")[0].string
        # item.madori = response.xpath('//*[@id="s_summaryMadori"]/dd/em/text()')[0]
        item.senyuMensekiStr = response.find_all("dl", id="s_summarySenyuMenseki")[0].find_all("dd")[0].contents[0]
        # item.senyuMensekiStr = response.xpath('//*[@id="s_summarySenyuMenseki"]/dd/text()[1]')[0]
        senyuMensekiWork = item.senyuMensekiStr.replace('m', '')
        item.senyuMenseki = Decimal(senyuMensekiWork)
        item.floorType = response.find_all("dl", id="s_summaryFloor")[0].find_all("dd")[0].contents[0]
        # item.floorType = response.xpath('//*[@id="s_summaryFloor"]/dd/text()')[0]
        item.chikunengetsuStr = response.find_all("dl", id="s_summaryChikunengetsu")[0].find_all("dd")[0].contents[0]
        # item.chikunengetsuStr = response.xpath('//*[@id="s_summaryChikunengetsu"]/dd/text()')[0]
        nen = int(item.chikunengetsuStr.split(u"年")[0])
        tsuki = int(item.chikunengetsuStr.split(u"年")[1].split(u"月")[0])
        item.chikunengetsu = datetime.date(nen, tsuki, 1)
        item.address = response.find_all("div", id="bukkenDetailBlock")[0].find_all("div")[1].find_all("dl")[5].find_all("dd")[0].contents[0]
        # item.address = response.xpath('//*[@id="bukkenDetailBlock"]/div[2]/dl[6]/dd/text()')[0]
        transList1 = []
        transList1.append(response.find_all("dd", id="s_summaryTransfer")[0].contents[1])
        transList1.append(response.find_all("dd", id="s_summaryTransfer")[0].contents[3])
        # transList1 = response.xpath('//dd[@id="s_summaryTransfer"]/text()')
        transList2 = []
        transList2.append(response.find_all("dd", id="s_summaryTransfer")[0].contents[0].contents[0])
        transList2.append(response.find_all("dd", id="s_summaryTransfer")[0].contents[2].contents[0])
        # transList2 = response.xpath('//dd[@id="s_summaryTransfer"]/a/text()')

        item.transfer1 = ""
        item.railway1 = ""
        item.station1 = ""
        item.railwayWalkMinute1Str = ""
        item.railwayWalkMinute1 = 0
        item.busStation1 = ""
        item.busWalkMinute1Str = ""
        item.busWalkMinute1 = 0

        item.transfer2 = ""
        item.railway2 = ""
        item.station2 = ""
        item.railwayWalkMinute2Str = ""
        item.railwayWalkMinute2 = 0
        item.busStation2 = ""
        item.busWalkMinute2Str = ""
        item.busWalkMinute2 = 0

        item.transfer3 = ""
        item.railway3 = ""
        item.station3 = ""
        item.railwayWalkMinute3Str = ""
        item.railwayWalkMinute3 = 0
        item.busStation3 = ""
        item.busWalkMinute3Str = ""
        item.busWalkMinute3 = 0

        item.transfer4 = ""
        item.railway4 = ""
        item.station4 = ""
        item.railwayWalkMinute4Str = ""
        item.railwayWalkMinute4 = 0
        item.busStation4 = ""
        item.busWalkMinute4Str = ""
        item.busWalkMinute4 = 0

        item.transfer5 = ""
        item.railway5 = ""
        item.station5 = ""
        item.railwayWalkMinute5Str = ""
        item.railwayWalkMinute5 = 0
        item.busStation5 = ""
        item.busWalkMinute5Str = ""
        item.busWalkMinute5 = 0

        for i in range(len(transList1)):
            if i == 0:
                item.transfer1, item.railway1, item.station1, item.railwayWalkMinute1Str, item.railwayWalkMinute1, item.busStation1, item.busWalkMinute1Str, item.busWalkMinute1 = self.__getPropertyValues(transList1, transList2, i)
            if i == 2:
                item.transfer2, item.railway2, item.station2, item.railwayWalkMinute2Str, item.railwayWalkMinute2, item.busStation2, item.busWalkMinute2Str, item.busWalkMinute2 = self.__getPropertyValues(transList1, transList2, i)
            if i == 4:
                item.transfer3, item.railway3, item.station3, item.railwayWalkMinute3Str, item.railwayWalkMinute3, item.busStation3, item.busWalkMinute3Str, item.busWalkMinute3 = self.__getPropertyValues(transList1, transList2, i)
            if i == 6:
                item.transfer4, item.railway4, item.station4, item.railwayWalkMinute4Str, item.railwayWalkMinute4, item.busStation4, item.busWalkMinute4Str, item.busWalkMinute4 = self.__getPropertyValues(transList1, transList2, i)
            if i == 8:
                item.transfer5, item.railway5, item.station5, item.railwayWalkMinute5Str, item.railwayWalkMinute5, item.busStation5, item.busWalkMinute5Str, item.busWalkMinute5 = self.__getPropertyValues(transList1, transList2, i)
                
        for i, tr in enumerate(response.find_all("div", id="detailBlock")[0].find_all("tr")):
            for j, th in enumerate(tr.find_all("th")):
                thTitle = th.contents[0]
                tdValue = tr.find_all("td")[j].contents[0]
                if thTitle == "バルコニー面積":
                    item.barukoniMenseki = tdValue
                if thTitle == "採光方向":
                    item.saikouKadobeya = tdValue
                    temp = item.saikouKadobeya.split(u"／")
                    if len(temp) == 1:
                        item.saikou = item.saikouKadobeya
                        item.kadobeya = ""
                    else:
                        item.saikou = temp[0]
                        item.kadobeya = temp[1]
                if thTitle == "総戸数":
                    item.soukosuStr = tdValue
                    item.soukosu = int(item.soukosuStr.replace(u"戸", "").strip())
                if thTitle == "管理方式／管理会社":
                    item.kanriKeitaiKaisya = tdValue
                    temp = item.kanriKeitaiKaisya.split(u"／")
                    if len(temp) == 1:
                        item.kanriKeitai = temp[0]
                        item.kanriKaisya = ""
                    else:
                        item.kanriKeitai = temp[0]
                        item.kanriKaisya = temp[1]
                if thTitle == "管理費(月額)":
                    item.kanrihiStr = tdValue            
                    if "-" in item.kanrihiStr:
                        item.kanrihi = 0
                    else:
                        item.kanrihi = int(item.kanrihiStr.replace(",", "").replace(u"円", ""))
                if thTitle == "修繕積立金(月額)":
                    item.syuzenTsumitateStr = tdValue
                    if "-" in item.syuzenTsumitateStr:
                        item.syuzenTsumitate = 0
                    else:
                        item.syuzenTsumitate = int(item.syuzenTsumitateStr.replace(",", "").replace(u"円", ""))
                if thTitle == "引渡時期":
                    item.hikiwatashi = tdValue
                if thTitle == "現況":
                    item.genkyo = tdValue
                if thTitle == "駐車場":
                    item.tyusyajo = tdValue
                if thTitle == "土地権利":
                    item.tochikenri = tdValue
        return item

    def __getTransferText(self, transList1, transList2, i):
        sum_transfer = transList1[i] + self.__getRailwayText(transList2, i) + self.__getRailwayStationText(transList2, i) + transList1[i + 1].replace(' ', '')
        return sum_transfer

    def __getRailwayText(self, transList2, i):
        return transList2[i]

    def __getRailwayStationText(self, transList2, i):
        return transList2[i + 1]

    def __getBusStationText(self, walkStr):
        if u"バス" in walkStr:
            return walkStr[walkStr.find(u"「") + 1:walkStr.rfind(u"」")]
        return ""

    def __getWalkMinute(self, walkStr):
        return walkStr[walkStr.find(u"徒歩") + 2:walkStr.rfind(u"分")].replace(' ', '')

    def __getRailwayWalkText(self, walkStr):
        if u"バス" in walkStr:
            return "0"
        return self.__getWalkMinute(walkStr)

    def __getBusWalkText(self, walkStr):
        if u"バス" in walkStr:
            return self.__getWalkMinute(walkStr)
        return "0"
    
    def __getPropertyValues(self, transList1, transList2, i):
        _transfer1 = self.__getTransferText(transList1, transList2, i)
        _railway1 = self.__getRailwayText(transList2, i)
        _station1 = self.__getRailwayStationText(transList2, i)
        _railwayWalkMinute1Str = self.__getRailwayWalkText(transList1[i + 1])
        if length(_railwayWalkMinute1Str) > 0:
            _railwayWalkMinute1 = int(_railwayWalkMinute1Str)
        _busStation1 = self.__getBusStationText(transList1[i + 1])
        _busWalkMinute1Str = self.__getBusWalkText(transList1[i + 1])
        _busWalkMinute1 = 0
        if length(_busWalkMinute1Str) > 0:
            _busWalkMinute1 = int(_busWalkMinute1Str)
        
        return _transfer1, _railway1, _station1, _railwayWalkMinute1, _railwayWalkMinute1, _busStation1, _busWalkMinute1Str, _busWalkMinute1

    def getResponse(self, url):
        r = requests.get(url)
        return  lxml.html.fromstring(html=r.content, parser=lxml.html.HTMLParser(encoding=chardet.detect(r.content)["encoding"]))

    def getResponseBs(self, url):
        r = requests.get(url)
        return  BeautifulSoup(r.content, "html.parser", from_encoding=chardet.detect(r.content)["encoding"])


def task(areaUrl):
    # currentTime = datetime.datetime.now()
    # currentDay = datetime.date.today()
    sumifu = GetSumifu("params")
    for propListUrl in sumifu.parseAreaPage(areaUrl):
        for propDetailUrl in sumifu.parsePropertyListPage(propListUrl):
            # item = sumifu.parsePropertyDetailPage(url)
            # item.inputDateTime = currentTime
            # item.inputDate = currentDay
            logging.info('save' + propDetailUrl)

            # item.save(False, False, None, None)    


def main():
    _url = "https://www.stepon.co.jp/mansion/tokai/"
    sumifu = GetSumifu("params")
    with ThreadPoolExecutor(max_workers=os.cpu_count(), thread_name_prefix="thread") as executor:
        futures = [executor.submit(task, areaUrl) for areaUrl in sumifu.parse(_url)]
        (done, notdone) = concurrent.futures.wait(futures)
        for future in concurrent.futures.as_completed(futures):
            print(future.result())


def mainBK():
    currentTime = datetime.datetime.now()
    currentDay = datetime.date.today()
    sumifu = GetSumifu("params")
    url = "https://www.stepon.co.jp/mansion/tokai/"
    for url in sumifu.parse(url):
        for url in sumifu.parseAreaPage(url):
            for url in sumifu.parsePropertyListPage(url):
                for item in sumifu.parsePropertyDetailPage(url):
                    item.inputDateTime = currentTime
                    item.inputDate = currentDay

                    item.save(False, False, None, None)

                    
if __name__ == "__main__":
    main()
