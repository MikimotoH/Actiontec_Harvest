#!/usr/bin/env python3
# coding: utf-8
import harvest_utils
from harvest_utils import waitClickable, waitVisible, waitText, getElems, \
        getElemText,getFirefox,driver,dumpSnapshot,\
        getText,getNumElem,waitTextChanged,waitElem,\
        waitUntil,clickElem,getElemAttr,hasElem,waitUntilStable,\
        waitUntilA,mouseClickE,waitTextA,UntilTextChanged,mouseOver,elemWithText,\
        goToUrl
from selenium.common.exceptions import NoSuchElementException, \
        TimeoutException, StaleElementReferenceException, \
        WebDriverException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait,Select
from selenium.webdriver.common.action_chains import ActionChains
import sys
import sqlite3
from os import path
import os
import re
import time
from datetime import datetime
import ipdb
import traceback
from my_utils import uprint,ulog
from contextlib import suppress

driver,conn=None,None
startTrail=[]
prevTrail=[]
modelName=''

def glocals()->dict:
    """ globals() + locals()
    """
    import inspect
    outer = dict(inspect.stack()[1][0].f_locals)
    outer.update(globals())
    return outer

def getScriptName():
    from os import path
    return path.splitext(path.basename(__file__))[0]

def retryA(statement, timeOut:float=6.2, pollFreq:float=0.3):
    timeElap=0
    while timeElap<timeOut:
        timeBegin=time.time()
        try:
            return statement()
        except (StaleElementReferenceException,NoSuchElementException, StopIteration):
            pass
        except Exception as ex:
            ulog('raise %s %s'%(type(ex),str(ex)))
            raise ex
        #ulog('sleep %f secs'%pollFreq)
        time.sleep(pollFreq)
        timeElap+=(time.time()-timeBegin)
    raise TimeoutException(getFuncName()+': timeOut=%f'%timeOut)

def getStartIdx():
    global startTrail
    if startTrail:
        return startTrail.pop(0)
    else:
        return 0

def sql(query:str, var=None):
    global conn
    csr=conn.cursor()
    try:
        if var:
            rows = csr.execute(query,var)
        else:
            rows = csr.execute(query)
        if not query.startswith('SELECT'):
            conn.commit()
        if query.startswith('SELECT'):
            return rows.fetchall()
        else:
            return
    except sqlite3.Error as ex:
        print(ex)
        raise ex

def guessDate(txt:str)->datetime:
    """ txt = '2015-08-06' """
    try:
        m = re.search(r'\d{4}-\d{2}-\d{2}', txt)
        return datetime.strptime(m.group(0), '%Y-%m-%d')
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        print('txt=',txt)

def guessVersion(txt:str)->str:
    """ 'Firmware Upgrade - GT784WN NCS01-1.0.13' """
    try:
        return txt.splitlines()[0].split()[-1]
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()

def fileWalker():
    global driver,prevTrail,modelName
    try:
        prodName=waitText('#prodname')
        # click "Support"
        retryA(lambda: elemWithText('li.tab-link', 'Support').click())
        # expand "Downloads"
        waitClickable('div.accordion-section:nth-child(2) a').click()

        # select  tables
        try:
            tables = getElems('table.supp',15,1)
        except TimeoutException:
            tables=None
        if not tables:
            ulog('no firmware download for "%s"'%modelName)
            driver.back()
            return
        relDates = getElems('table.supp tr td:nth-child(1)')
        descs = getElems('table.supp tr td:nth-child(2)')
        assert len(relDates)==len(descs)
        pageUrl=driver.current_url
        startIdx = getStartIdx()
        numFiles=len(relDates)
        ulog('numFiles=%s'%numFiles)
        for idx in range(startIdx, numFiles):
            fwDate=guessDate(relDates[idx].text)
            fileUrl=descs[idx].find_element_by_css_selector('a')
            fwVer = guessVersion(fileUrl.text)
            fileUrl=fileUrl.get_attibute('href')

            fwDesc=descs[idx].text.strip()
            trailStr=str(prevTrail+[idx])
            ulog('trail=%s'%trailStr)
            sql("INSERT OR REPLACE INTO TFiles (model,"
                "fw_date, fw_ver, fw_desc, "
                "page_url,file_url,tree_trail) VALUES"
                "(:modelName,  "
                ":fwDate,:fwVer,:fwDesc,"
                ":pageUrl,:fileUrl,:trailStr)",glocals())
            ulog('UPSERT "%(modelName)s", "%(fwDate)s", '
                ' "%(fwVer)s", %(fileUrl)s'%glocals())
        driver.back()
        return
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        driver.save_screenshot(getScriptName()+'_'+getFuncName()+'_exc.png')
        
def modelWalker():
    global driver,prevTrail,modelName
    try:
        models = getElems('#newboxes1 a')
        numModels=len(models)
        ulog('numModels=%s'%numModels) 
        startIdx = getStartIdx()
        for idx in range(startIdx,numModels):
            modelName = models[idx].text
            ulog('enter %s,"%s"'%(idx,modelName))
            prevTrail+=[idx]
            models[idx].click()
            fileWalker()
            prevTrail.pop()
            cats = getElems('#myHeader1,#myHeader2,#myHeader3')
            cats[prevTrail[-1]].click()
            models = getElems('#newboxes1 a')
            assert numModels == len(models)
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        driver.save_screenshot(getScriptName()+'_'+getFuncName()+'_exc.png')

def marketWalker():
    global driver,prevTrail
    rootUrl='http://www.actiontec.com/support/'
    try:
        goToUrl(rootUrl)
        cats = getElems('#myHeader1,#myHeader2,#myHeader3')
        startIdx=getStartIdx()
        numCats = len(cats)
        for idx in range(startIdx, numCats):
            ulog('select %s'%idx)
            cats[idx].click()
            prevTrail+=[idx]
            modelWalker()
            prevTrail.pop()
            cats = getElems('#myHeader1,#myHeader2,#myHeader3')
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        driver.save_screenshot(getScriptName()+'_'+getFuncName()+'_exc.png')


def main():
    global startTrail,prevTrail, driver,conn
    try:
        startTrail = [int(re.search(r'\d+', _).group(0)) for _ in sys.argv[1:]]
        uprint('startTrail=%s'%startTrail)
        conn=sqlite3.connect('actiontec.sqlite3')
        sql(
            "CREATE TABLE IF NOT EXISTS TFiles("
            "id INTEGER NOT NULL,"
            "model TEXT,"
            "product_name TEXT,"
            "fw_date DATE,"
            "fw_ver TEXT,"
            "fw_desc TEXT,"
            "file_size INTEGER,"
            "page_url TEXT,"
            "file_url TEXT,"
            "tree_trail TEXT,"
            "file_sha1 TEXT,"
            "PRIMARY KEY (id)"
            "UNIQUE(model,fw_date)"
            ");")
        driver=harvest_utils.getFirefox()
        harvest_utils.driver=driver
        prevTrail=[]
        marketWalker()
        driver.quit()
        conn.close()
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        driver.save_screenshot(getScriptName()+'_'+getFuncName()+'_exc.png')

if __name__=='__main__':
    try:
        main()
    except Exception as ex:
        ipdb.set_trace()
        print(ex); traceback.print_exc()
        try:
            driver.save_screenshot(getScriptName()+'_exc.png')
            driver.quit()
        except Exception:
            pass

