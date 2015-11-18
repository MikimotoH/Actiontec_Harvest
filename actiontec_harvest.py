#!/usr/bin/env python3
# coding: utf-8
import harvest_utils
from harvest_utils import waitClickable, waitVisible, waitText, getElems, \
        getElemText,getFirefox,driver,dumpSnapshot,\
        getText,getNumElem,waitTextChanged,waitElem,\
        waitUntil,clickElem,getElemAttr,hasElem,waitUntilStable,\
        waitUntilA,mouseClickE,waitTextA,UntilTextChanged,mouseOver,elemWithText,\
        goToUrl,isReadyState
from selenium.common.exceptions import NoSuchElementException, \
        TimeoutException, StaleElementReferenceException, \
        WebDriverException, ElementNotVisibleException
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
from my_utils import uprint,ulog,getFuncName
from contextlib import suppress

driver,conn=None,None
startTrail=[]
prevTrail=[]

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

def getTextA(elm:WebElement)->str:
    waitUntil(lambda: elm.is_displayed() and elm.text,30,1)
    return elm.text

def retryA(statement, timeOut:float=6.2, pollFreq:float=0.3):
    timeElap=0
    while timeElap<timeOut:
        timeBegin=time.time()
        try:
            return statement()
        except (StaleElementReferenceException,NoSuchElementException, StopIteration, ElementNotVisibleException ):
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
    m = re.search(r'\d{4}-\d{2}-\d{2}', txt)
    if not m:
        return None
    return datetime.strptime(m.group(0), '%Y-%m-%d')

def guessVersion(txt:str)->str:
    """ 'Firmware Upgrade - GT784WN NCS01-1.0.13' """
    try:
        return txt.splitlines()[0].split()[-1]
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()

def fileWalker():
    global driver,prevTrail
    try:
        waitUntil(isReadyState)
        prodName=waitText('#prodname')
        ulog('prodName="%s"'%prodName)
        modelName = waitText('#prodmodel')
        ulog('modelName="%s"'%modelName)
        # click "Support"
        retryA(lambda: elemWithText('li.tab-link', 'Support').click())
        # expand "Downloads"
        waitClickable('div.accordion-section:nth-child(2) a').click()
        pageUrl=driver.current_url

        # select  tables
        try:
            tables = getElems('table.supp',9,1)
        except TimeoutException:
            tables=None
        if not tables:
            ulog('no firmware download for "%s"'%modelName)
            trailStr=str(prevTrail)
            sql("INSERT OR REPLACE INTO TFiles (model,product_name,"
                "page_url,tree_trail) VALUES"
                "(:modelName, :prodName,"
                ":pageUrl,:trailStr)",glocals())
            ulog('UPSERT "%(modelName)s", "%(prodName)s", '%glocals())
            driver.back()
            return
        files = getElems('table.supp tr')
        startIdx = getStartIdx()
        numFiles=len(files)
        ulog('numFiles=%s'%numFiles)
        bUpserted=False
        for idx in range(startIdx, numFiles):
            try:
                col=files[idx].find_element_by_css_selector('td:nth-child(1)')
            except NoSuchElementException:
                ulog('bypass idx=%s'%idx)
                continue
            fwDate=guessDate(col.text)
            if not fwDate:
                ulog('bypass idx=%s'%idx)
                continue
            desc=files[idx].find_element_by_css_selector('td:nth-child(2)')
            fwDesc=desc.text
            fileName=desc.find_element_by_css_selector('a')
            ulog('fileName.text="%s"'%fileName.text)
            if 'firmware' not in fileName.text.lower():
                ulog('bypass idx=%s'%idx)
                continue
            fwVer = guessVersion(fileName.text)
            fileUrl=fileName.get_attribute('href')

            fwDesc=desc.text.strip()
            trailStr=str(prevTrail+[idx])
            ulog('trail=%s'%trailStr)
            sql("INSERT OR REPLACE INTO TFiles (model,product_name,"
                "fw_date, fw_ver, fw_desc, "
                "page_url,file_url,tree_trail) VALUES"
                "(:modelName, :prodName,"
                ":fwDate,:fwVer,:fwDesc,"
                ":pageUrl,:fileUrl,:trailStr)",glocals())
            ulog('UPSERT "%(modelName)s", "%(prodName)s", "%(fwDate)s", '
                ' "%(fwVer)s", %(fileUrl)s'%glocals())
            bUpserted=True

        if not bUpserted:
            trailStr=str(prevTrail)
            sql("INSERT OR REPLACE INTO TFiles (model,product_name,"
                "page_url,tree_trail) VALUES"
                "(:modelName, :prodName,"
                ":pageUrl,:trailStr)",glocals())
            ulog('UPSERT "%(modelName)s", "%(prodName)s", '%glocals())

        driver.back()
        return
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        driver.save_screenshot(getScriptName()+'_'+getFuncName()+'_exc.png')


mkts = ['#myHeader1','#myHeader2','#myHeader3','#myHeader4']
def modelWalker():
    global driver,prevTrail
    CSS=driver.find_element_by_css_selector
    CSSs=driver.find_elements_by_css_selector
    try:
        retryA(lambda:CSS(mkts[prevTrail[-1]]).click())
        models = CSSs('#newboxes%d a'%(prevTrail[-1]+1))
        numModels=len(models)
        ulog('numModels=%s'%numModels) 
        startIdx = getStartIdx()
        for idx in range(startIdx,numModels):
            waitUntil(lambda: models[idx].is_displayed(),5)
            if not models[idx].text:
                ulog('bypass idx=%s'%idx)
                continue
            ulog('enter %s,"%s"'%(idx,models[idx].text))
            prevTrail+=[idx]
            retryA(lambda: models[idx].click())
            fileWalker()
            prevTrail.pop()
            waitUntil(isReadyState)
            retryA(lambda:CSS(mkts[prevTrail[-1]]).click())
            models = CSSs('#newboxes%d a'%(prevTrail[-1]+1))
            assert numModels == len(models)
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        driver.save_screenshot(getScriptName()+'_'+getFuncName()+'_exc.png')

def marketWalker():
    global driver,prevTrail
    CSS=driver.find_element_by_css_selector
    try:
        startIdx=getStartIdx()
        numCats = len(mkts)
        for idx in range(startIdx, numCats):
            ulog('select %s'%idx)
            prevTrail+=[idx]
            modelWalker()
            prevTrail.pop()
    except Exception as ex:
        ipdb.set_trace()
        traceback.print_exc()
        driver.save_screenshot(getScriptName()+'_'+getFuncName()+'_exc.png')


def main():
    global startTrail,prevTrail, driver,conn
    rootUrl='http://www.actiontec.com/support/'
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
        goToUrl(rootUrl)
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

