# Copyright 2013 Betterment

# This file is part of The Index Portfolio Whitepaper Engine.

# The Index Portfolio Whitepaper Engine is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# The Index Portfolio Whitepaper Engine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with The Index Portfolio Whitepaper Engine.  If not, see <http://www.gnu.org/licenses/>.

### Data functions ###
### These functions interact with a sqlite database of CRSP data, schema as of 12/31/2012 ###
import os, sys
import sqlite3 as lite
from datetime import date, datetime, time
from cStringIO import StringIO
import numpy as np
import pandas as pd
from settings import config 

def get_fund_styles():
    """ Gets fund styles using CRSP style codes for the purpose of bucketing """
    try:
        print "Getting fund styles from database"
        con=None
        con = lite.connect(config['db_path'])    
        cur = con.cursor()    
        # NEW CRSP style codes
        # get style codes from DB - this query excludes fund that never had a style  
        sql="""select crsp_fundno, crsp_obj_cd, max(begdt) from FUND_STYLE where crsp_obj_cd <> '' group by crsp_fundno;"""
        cur.execute(sql) 
        data = cur.fetchall()
        print "Done getting styles"
        rawdf =  pd.DataFrame(list(data),columns=['FundNo', 'StyleCode', 'BegDt'])
        #reindex by fund number
        rawdf.index = [rawdf['FundNo']]
        del rawdf['FundNo']
        # we actually don't need the date, just had it for purposes of the groupby
        del rawdf['BegDt']
        return rawdf 
    except lite.Error, e:
        print "Error %s:" % e.args[0]
        sys.exit(1)
        
    finally:
        if con:
            con.close()    

def get_fund_fees():
    """ Gets expense ratios for the purpose of filtering criteria """
    try:
        print "Getting fund fees from database"
        con=None
        con = lite.connect(config['db_path'])    
        cur = con.cursor()    
        # sql query to get fee data for each fund. the end date is the time till which the fee is applicable for the fund
        sql="""select crsp_fundno,begdt,enddt,exp_ratio from FUND_FEES order by crsp_fundno, enddt;"""  #
        cur.execute(sql) 
        data = cur.fetchall()
        print "Done getting fees"
        df = pd.DataFrame(list(data),columns=['FundNo', 'StartDate', 'EndDate', 'ExpRatio'])
        return df.groupby('FundNo').last()       
    except lite.Error, e:
        print "Error %s:" % e.args[0]
        sys.exit(1)
        
    finally:
        
        if con:
            con.close()

# leave out variable annuity funds, institutional funds, non-retail funds, 
# target data / balanced funds, and various non-applicable share classes
# NOTE: Some funds were marked non-retail (e.g. ETFs), so we manually change the flag in order to use in analysis
#    e.g. update FUND_HDR set retail_fund='Y' where crsp_fundno in ( 16429 ,31351, 31350, 16413,16432) ;

common_excludes_data_load = """and vau_fund<>"Y"
        and inst_fund <> 'Y' 
        and retail_fund<>'N'
        and fund_name not like '%2010%'
        and fund_name not like '%2015%'
        and fund_name not like '%2020%'
        and fund_name not like '%2025%'
        and fund_name not like '%2030%'
        and fund_name not like '%2035%'
        and fund_name not like '%2040%'
        and fund_name not like '%2045%'
        and fund_name not like '%2050%'
        and fund_name not like '%2055%'
        and fund_name not like '%2060%'
        and fund_name not like '%130/30%'
        and fund_name not like '%120/20%'
        and fund_name not like '%Long/Short%'
        and fund_name not like '%Long-Short%'
        and fund_name not like '%Pacific Life%'
        and fund_name not like '%MassMutual %'
        and fund_name not like '%Transamerica %'
        and fund_name not like '%/Instl' 
        and fund_name not like '%/Y'
        and fund_name not like '%/X' 
        and fund_name not like '%/H' 
        and fund_name not like '%/D' 
        and fund_name not like '%/N' 
        and fund_name not like '%/Z' 
        and fund_name not like '%/Q' 
        and fund_name not like '%/Ist'
        and fund_name not like '%/Inst' 
        and fund_name not like '%/P'
        and fund_name not like '%/E'
        and fund_name not like '%Institutional Class%'
        and fund_name not like '%Institutional Shares%'
        and fund_name not like '%Advisor Shares'
        and fund_name not like '%R Shares'
        and fund_name not like '%T Shares'
        and fund_name not like '%M Shares'
        and fund_name not like '%H Shares'
        and fund_name not like '%I Shares'
        and fund_name not like '%J Shares'
        and fund_name not like '%G Shares'
        and fund_name not like '%K Shares'
        and fund_name not like '%N Shares'
        and fund_name not like '%L Shares'
        and fund_name not like '%P Shares'
        and fund_name not like '%S Shares'
        and fund_name not like '%E Shares'
        and fund_name not like '%Y Shares'
        and fund_name not like '%Z Shares'
        and fund_name not like '%O Shares'
        and fund_name not like '%Q Shares'
        and fund_name not like '%A1 Shares'
        and fund_name not like '%B1 Shares'
        and fund_name not like '%C1 Shares'
        and fund_name not like '%C2 Shares'
        and fund_name not like '%R1 Shares'
        and fund_name not like '%R5 Shares'
        and fund_name not like '%D Shares'
        and fund_name not like '%X Shares'
        and fund_name not like '%529%'"""

# We don't want index funds in regular active fund queries, but we do when loading data to the master set
common_excludes = common_excludes_data_load + """
        and fund_name not like '%Index Fund%'"""

pragmas = """PRAGMA case_sensitive_like = true; """

def get_unique_funds_from_groups():
    """ gets crsp_cl_grp and crsp_portno to remove funds that are of the same root """
    
    # get funds in 4 groups, depending on the data available for them, since we'll 
    # process each differently
    sql_no_grp_no_portno = """select crsp_fundno, crsp_cl_grp, crsp_portno, fund_name From FUND_HDR  
    where crsp_cl_grp = '' 
    and crsp_portno = '' 
    %s 
    order by fund_name, first_offer_dt asc, end_dt desc;""" % common_excludes     
        
    sql_no_grp = """select crsp_fundno, crsp_cl_grp, crsp_portno, fund_name From FUND_HDR 
    where crsp_cl_grp = '' 
    and crsp_portno <> ''
    %s 
    order by crsp_cl_grp, crsp_portno, fund_name asc, first_offer_dt asc, end_dt desc;""" % common_excludes 
    
    sql_no_portno = """
    select crsp_fundno, crsp_cl_grp, crsp_portno, fund_name From FUND_HDR 
    where crsp_cl_grp <> '' 
    and crsp_portno = ''
    %s 
    order by crsp_cl_grp, crsp_portno, fund_name asc, first_offer_dt asc, end_dt desc;""" % common_excludes

    sql_both = """
    select crsp_fundno, crsp_cl_grp, crsp_portno, fund_name From FUND_HDR 
    where crsp_cl_grp <> '' 
    and crsp_portno <> ''
    %s 
    order by crsp_cl_grp, crsp_portno, fund_name asc, first_offer_dt asc, end_dt desc;""" % common_excludes

    try:
        print "Getting fund groups from database"
        con = None
        con = lite.connect(config['db_path'])    
        cur = con.cursor()     
        #setup pragmas
        cur.execute(pragmas)        
        
        # without a portno or grp to use, we resort to parsing names by "/" and drop any with common roots        
        cur.execute(sql_no_grp_no_portno) 
        data = cur.fetchall()
        df_no_grp_no_portno = pd.DataFrame(list(data),columns=['crsp_fundno','crsp_cl_grp', 'crsp_portno', 'fund_name'])
        df_no_grp_no_portno.index=[df_no_grp_no_portno['crsp_fundno']]

        trimmed_names = df_no_grp_no_portno['fund_name'].map(lambda x: x.rsplit('/',1)[0])        
        unique_names = trimmed_names.drop_duplicates()
        
        # drop duplicate portfolios by portno
        cur.execute(sql_no_grp) 
        data = cur.fetchall()
        df_no_grp = pd.DataFrame(list(data),columns=['crsp_fundno','crsp_cl_grp', 'crsp_portno', 'fund_name'])
        df_no_grp.index = [df_no_grp['crsp_fundno']]
        unique_portfs = df_no_grp['crsp_portno'].drop_duplicates()        

        # drop duplicate portfoliios by cl_grp
        cur.execute(sql_no_portno) 
        data = cur.fetchall()
        df_no_portno = pd.DataFrame(list(data),columns=['crsp_fundno','crsp_cl_grp', 'crsp_portno', 'fund_name'])
        df_no_portno.index = [df_no_portno['crsp_fundno']]
        unique_grps = df_no_portno['crsp_cl_grp'].drop_duplicates()        
        
        # if both fields available, drop duplicates by cl_grp
        cur.execute(sql_both) 
        data = cur.fetchall()
        df_both = pd.DataFrame(list(data),columns=['crsp_fundno','crsp_cl_grp', 'crsp_portno', 'fund_name'])
        df_both.index = [df_both['crsp_fundno']]
        unique_both = df_both['crsp_cl_grp'].drop_duplicates()        
        
        # return everything together
        return unique_both.index.append(unique_grps.index.append(unique_portfs.index.append(unique_names.index)))
        
    except lite.Error, e:
        print "Error %s:" % e.args[0]
        sys.exit(1)
        
    finally:
        
        if con:
            con.close()    

def get_pure_index_funds():
    """ gets list of pure index funds to optionally exclude from active fund list """
    try:
        con=None
        con = lite.connect(config['db_path'])    
        cur = con.cursor()      
        sql = """select crsp_fundno from FUND_HDR where index_fund_flag in ('D');"""
        cur.execute(sql) 
        data = cur.fetchall()
        return list(pd.DataFrame(list(data),columns=['crsp_fundno'])['crsp_fundno'])
    except lite.Error, e:
        print "Error %s:" % e.args[0]
        sys.exit(1)
        
    finally:
        
        if con:
            con.close()

def get_all_fund_returns(force_db_read=False, df_file = 'fund_returns_lite_nona_reindex.pandas'):
    """ Reads returns for all funds from the database (excludes some things we aren't interested in """
    # caching to make things faster most of the time
    if not force_db_read and os.path.isfile(df_file):
        print "Loading file from cache:",df_file
        return pd.load(df_file)
    #otherwise read from db
    print "Reading fund returns from the database"
    try:
        con = lite.connect(config['db_path'])   
        cur = con.cursor()      
        
        # run pragmas (case sensivity on)
        cur.execute(pragmas)
        
        sql= """select mr.crsp_fundno, caldt, mret from FUND_HDR fhdr, MONTHLY_RETURNS mr 
        where fhdr.crsp_fundno=mr.crsp_fundno  
        %s
        ;""" % common_excludes_data_load 
        cur.execute(sql)
        data = cur.fetchall()
        
        print 'Parsing database results (those pesky date parses take a little while)'
 
        df = pd.DataFrame(list(data),columns=['FundNo', 'StrCalDate', 'Return'])
        
        # parse the date column (string slicing is faster than datetime.strptime)
        parsed_dates = df['StrCalDate'].map(lambda x: date(int(str(x)[0:4]),int(str(x)[4:6]),int(str(x)[6:8]) ))
        
        # add back to the dataframe
        df['CalDate'] = pd.Series(parsed_dates,index=df.index) 
        
        # remove unneeded column
        del df['StrCalDate']
        # change -99 values to NaN, then drop them
        print 'Drop the -99.0 values'
        df=df.replace({'Return':-99.0}, value=np.nan)
        df=df.dropna(subset=['Return'])
        # add one to all the returns per our convention
        df['Return']=pd.Series(df['Return'],index=df.index) + 1

        print 'Re-index by FundNo and Date'
        df.index = [df['FundNo'],pd.DatetimeIndex(df['CalDate'])]
        
        # now that these are indexes, no need to keep the column data
        del df['CalDate']
        del df['FundNo']
        
        #save the file for next time
        print "Saving returns dataframe for next time as",df_file 
        df.save(df_file)
        
        return df
        
    except lite.Error, e:
        
        print "Error %s:" % e.args[0]
        sys.exit(1)
        
            
def get_fund_info(fundno_list, printout=True):
    """ Gets the supplied fund names and tickers, mostly for logging purposes """
    try:
        con = lite.connect(config['db_path'])   
        cur = con.cursor()    
        
        sql = """select crsp_fundno, fund_name, nasdaq 
        from FUND_HDR hdr where 
        crsp_fundno in (%s);"""   
        
        # get all funds specified, if actually a fund (int) and not an index
        cur.execute(sql % ','.join(str(x) for x in fundno_list if type(x)==int or type(x)==np.int64))   
        
        data = cur.fetchall() 
        if printout:
            for fund in data:
                print '%s - %s (%s)' % (fund[2] if fund[2] else '(Unknown)',fund[1],fund[0])

        return list(data)
        
    except lite.Error, e:
        
        print "Error %s:" % e.args[0]
        sys.exit(1)
        
    finally:
        
        if con:
            con.close()            

def get_all_live_funds():
    """ gets a list of all funds that are not dead """
    try:
        con = lite.connect(config['db_path'])   
        cur = con.cursor()    
        
        sql = """select crsp_fundno 
        from FUND_HDR hdr where 
        dead_flag='N';"""   
        
        cur.execute(sql)   
        data = cur.fetchall() 
        #convert to a list (shortcut..maybe we should use a row_factory)
        return map(list,zip(*data))[0]
        
    except lite.Error, e:
        
        print "Error %s:" % e.args[0]
        sys.exit(1)
        
    finally:
        
        if con:
            con.close()       
       
def get_annual_total_net_assets(force_db_read=False, df_file = 'monthlytna.pandas'):
    """ gets average total net assets per fund per year 
    
    NOTE: This is not used in the current iteration of research    
    """
    # caching to make things faster most of the time
    if not force_db_read and os.path.isfile(df_file):
        print "Loading file from cache:",df_file
        return pd.load(df_file)
    #otherwise read from db    
    try:
        print "Getting Total Net Assets from database"
        con=None
        con = lite.connect(config['db_path'])    
        cur = con.cursor()      
        sql = """select crsp_fundno, substr(caldt,1,4) as year, mtna from MONTHLY_TNA where mtna <> '';"""
        cur.execute(sql) 
        data = cur.fetchall()
        print "Done getting Total Net Assets"
        df = pd.DataFrame(list(data),columns=['FundNo','Year','mtna'],dtype=np.float64) 

        df=df.replace({'mtna':-99.0}, value=np.nan)
        df.dropna(subset=['mtna'])

        grouped = df.groupby(['FundNo','Year'])
        tna_means = grouped.mean()
        print "Saving monthly TNA dataframe for next time as",df_file
        tna_means.save(df_file)
        return tna_means
    except lite.Error, e:
        print "Error %s:" % e.args[0]
        sys.exit(1)

    finally:

        if con:
            con.close()