# Copyright 2013 Betterment

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

from __future__ import division  #needed so python deals with floats and division properly
import sys, os, types
from datetime import date, datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid.anchored_artists import AnchoredText
import argparse
import math
from settings import config 
from metamappings import *
from crsp_data_wrappers import *
from portfolios import *

con = None

def main():
    parser = argparse.ArgumentParser(description='CRSP Data passive/active engine.')
    parser.add_argument('--portfolio', dest='portfolio_name', default='portfolio_1',
                           help='portfolio name string from portfolio.py')  
    parser.add_argument('--trials', type=int, default=10,
                       help='number of trials to run')
    parser.add_argument('--name', default='figure',
                           help='run name - will be used for output png file name')   
    parser.add_argument('--start_year', type=int, default=1996,
                           help='starting time horizon year')  
    parser.add_argument('--end_year', type=int, default=2012,
                           help='ending time horizon year')  
    parser.add_argument('--start_month', type=int, default=12,
                               help='starting time horizon month')   
    parser.add_argument('--end_month', type=int, default=12,
                                   help='ending time horizon month')   
    parser.add_argument('--fee_quantile', type=float, default=None,
                                       help='fee quantile to filter funds by')
    parser.add_argument('--picks', type=int, dest='active_picks', default=1,
                                           help='number of active funds to pick for each asset class')    
    parser.add_argument('--addbias', action='store_true',
                                               help='removes dead funds, introducing survivorship bias')     
    args = parser.parse_args()

    try:
        comparison_portfolio_def = eval(args.portfolio_name)
    except NameError:
        print 'Portfolio', args.portfolio_name, 'is not defined.  Check portfolios.py'
        return
        
    returns = get_all_fund_returns(force_db_read=False)
    
    # Call the engine
    # NOTE:  We use a day of the month (25) that ensures that end-of-month returns on non-calendar month-end days are not cut off.
    #        This day will be normalized later to actual end of month along with the returns to ensure matches.
    res = engine(comparison_portfolio_def, 
                 returns, 
                 date(args.start_year, args.start_month, 25),
                 date(args.end_year, args.end_month, 31), 
                 bucketing_type='crsp_style', 
                 active_picks=args.active_picks,
                 min_fee_quantile=args.fee_quantile, 
                 survivor_bias=args.addbias,
                 trials=args.trials, name=args.name, pf_name=args.portfolio_name)

def feq(a,b):
    """ Equals function - used in the allocation checks to deal a precision issue """
    if abs(a-b)<0.00000001:
        return 1
    else:
        return 0
    
def check_pf_setup(port_def):
    """ Validates at the chosen allocation and comparison portfolio constituents make sense """
    
    # check if alloc adds to one
    total = 0
    target = 1.0
    for asset_class in port_def.keys():
        total+= port_def[asset_class]['alloc']
    if not feq(total,target):
        print "Allocation doesn't add to 100%:", total*100
        return False
    
    # check if asset classes are all valid
    isect=[a for a in asset_classes if a in port_def.keys()]
    if len(isect) <> len(port_def.keys()): 
        print "Invalid asset class specified in portfolio",port_def.keys()
        return False
    return True

def print_portfolio(port_def):
    """ Pretty prints a portfolio definition with additional info """
    for asset_class in port_def.keys():
        print asset_class, port_def[asset_class]['alloc'] 
        get_fund_info(port_def[asset_class]['funds'])
        print '='*20

def export_fund_list(ids,name=''):
    """ Saves a list of fund names to an output file, given a list of crsp_fundno ids """
    print 'Writing fund list',len(ids),'to file:','fund_list_%s.csv' % name
    f=open('fund_list_%s.csv' % name, 'wb')
    info = get_fund_info(ids, printout=False)
    for fund in info:
        f.write( "\"%s\",\"%s\",\"%s\"\n" % (fund[2] if fund[2] else 'Unknown',fund[1],fund[0]) )
    f.close()

def engine(port_def, all_fund_returns, start_date, end_date, bucketing_type='crsp_style', 
           min_fee_quantile=None, exclude_indexfunds=True, survivor_bias=False, trials=100, name='figure',pf_name='',active_picks=1):
    """ Main routine for choosing random portfolios to compare the passive to active strategy
    
    Works by first calculating the passive portfolio return, then developing the universe of active
    funds to choose from by style and other criteria, then running trials which select funds for each
    asset class and calculate teh returns.  If funds die during the time horizon, the fund is replaced
    with another random fund from the selection universe for the asset class that is active at the time.
    
    Note: we support bucketing by R-squared, but found this to not be a good measure since it tends to keep mostly closet indexers.
    Thus the default method is 'crsp_style'
    
    INPUTS:
    port_def: definition of the target allocation and passive fund to use for each
    all_fund_returns: crsp pandas return object from crsp_data_wrappers
    bucketing_type: R2 or crsp_style - defines the method for choosing funds within the asset class
    min_fee_quantile: for excluding high-fee funds.  0.5 would exclude all but the lowest 1/2 of funds
    exclude_indexfunds: exclude index funds from list of active funds
    trials: how many random active portfolios to pick
    name: name of run, used in graph filename
    pf_name: optional name of portfolio, used in graph
    active_picks: how many active funds to randomly choose for each asset class
    
    OUTPUTS:
    Return differences  between activce and passive (csv)
    Graphs of the passive/active return differences and sharpe ratio differences
    Fund name list by asset class (csv)
    
    """
    if pf_name: print 'Portfolio name:',pf_name
    print_portfolio(port_def)
    print 'Time horizon:',start_date,'to',end_date 
    print 'Active funds from each asset class to pick:',active_picks
    
    if not check_pf_setup(port_def):
        return 

    # Load risk-free rate returns for sharpe ratio calculation, and set to End of Month like the rest of our data
    riskfree_returns = load_benchmark_returns(bmk_list=['TBill-1mo'])[0].resample('M',how='prod')

    ## FIRST: Calculate passive (comparison) portfolio returns
    # get comparison portfolio returns from the returns set or alternate location, 
    # ensure time period is present and calculate fund return over period
    print 'Calculating return and stddev of comparison portfolio'
    comp_pf_return, comp_pf_excessreturn, comp_pf_stddev = get_portfolio_return(port_def, all_fund_returns, riskfree_returns, start_date, end_date)
    comp_pf_sharpe = (comp_pf_excessreturn - 1) / comp_pf_stddev
    
    print 'Comparison portfolio return=',comp_pf_return, 'excess return=', comp_pf_excessreturn, 'stddev=',comp_pf_stddev, 'sharpe=',comp_pf_sharpe
    
    ## NEXT: Calculate active portfolio returns 
    print 'Getting fund buckets for each asset class'
    if bucketing_type=='crsp_style':
        bucket_df = get_style_bucket_funds(all_fund_returns) 
    else:
        bucket_df = get_r2_bucket_funds()

    short_funds = [] #tracks short funds that are not part of our range or have less than certain number of values
    return_diffs = [] # difference of the passive and active trial return - for graphing
    sharpe_diffs = [] # difference of the passive and active trial sharpe ratios -for graphing
    
    print "Getting list of funds open during the time horizon"
    date_bounds = get_fund_date_bounds(all_fund_returns)
    lhs = date_bounds[date_bounds['end_date'] >= start_date]
    rhs = date_bounds[date_bounds['start_date'] <= end_date]
    
    open_funds = list(set(lhs.index).intersection(list(rhs.index)))
    print 'There are',len(open_funds),'which were open during the time horizon'

    # remove non-unique funds
    unique_fund_list = get_unique_funds_from_groups()
    print "Total unique funds that were open:", len(list(set(unique_fund_list).intersection(open_funds)))
    
    if exclude_indexfunds:
        print 'Excluding pure index funds'    
        indexfund_list = get_pure_index_funds()    
    
    if survivor_bias:
        live_funds = get_all_live_funds()

    master_fund_list = {}
    for asset_class in port_def.keys():
        print 'Filtering for',asset_class
        fund_list = list(bucket_df[asset_class].dropna().index)
        
        if exclude_indexfunds:
            fund_list = list(set(fund_list).difference(indexfund_list))        

        all_fund_count = len(fund_list)
        fund_list = list(set(fund_list).intersection(open_funds))     
        print "Excluding %s funds that weren't open during this period for this asset class" % (all_fund_count - len(fund_list))
        
        all_fund_count = len(fund_list)
        fund_list = list(set(fund_list).intersection(unique_fund_list))     
        print 'Removing %s non-unique funds' % (all_fund_count - len(fund_list))
        
        if specific_fund_excludes:
            all_fund_count = len(fund_list)
            fund_list = list(set(fund_list).difference(specific_fund_excludes)) 
            if (all_fund_count - len(fund_list)) > 0:
                print "Funds explicitly excluded: %s" % (all_fund_count - len(fund_list))
                
        # if we are using low fee funds only, take out any that aren't low fee
        # do this last so the quantile is taken from the final list
        if min_fee_quantile:
            lowest_quantile_funds = specific_funds_by_fee(get_fund_fees(), fund_list, min_fee_quantile)
            fund_list = list(set(fund_list).intersection(lowest_quantile_funds))       
                
        if survivor_bias:
            all_fund_count = len(fund_list)
            fund_list = list(set(fund_list).intersection(live_funds)) 
            print "Survivorship bias impact: Excluding %s dead funds for this asset class" % (all_fund_count - len(fund_list))
            
        master_fund_list[asset_class] = fund_list
        print asset_class,'final fund count:',len(fund_list)
        export_fund_list(fund_list, name=asset_class)

    print 'Starting trials... (',trials,')' 
    rs_index = pd.date_range(start_date,end_date,freq='M')
    pcr_index = None
    for trial in range(trials):   
        return_df = pd.DataFrame() # to store the trial returns for each asset class, for later portfolio return calculations
        trial_return = 0
        for asset_class in port_def.keys():
            weight = port_def[asset_class]['alloc'] / active_picks #each pick will be equally weighted
            fund_list = master_fund_list[asset_class]
            
            for pick in range(active_picks):
                combined_returns = pd.Series(None,index=rs_index) # empty return series indexed monthly for date range to start
                combined_funds = []
                # keep drawing funds and combining the series until filled
                while len(combined_returns) <> len(combined_returns.dropna()):
                    
                    # filter fund_list by current open funds (those open at the time the last fund ended)                   
                    next_date = combined_returns[np.isnan(combined_returns)].index[0]
                    lhs = date_bounds[date_bounds['end_date'] >= next_date]
                    rhs = date_bounds[date_bounds['start_date'] <= next_date]
                    current_open_funds = list(set(lhs.index).intersection(list(rhs.index)))
                    open_fund_list = list(set(fund_list).intersection(current_open_funds)) 
                    
                    # draw a random fund
                    random_fund = open_fund_list[np.random.random_integers(len(open_fund_list))-1]
                    
                    #select again if fund is in our list of short_funds, so we don't waste time with ones we know are too short
                    while random_fund in short_funds:
                        random_fund = open_fund_list[np.random.random_integers(len(open_fund_list))-1]
                    fund_pick_returns = all_fund_returns.ix[random_fund]['Return'][start_date:end_date] 
                    
                    # if we didn't get returns or the fund has less than 6 months of history left, don't use it and reloop to redraw
                    if len(fund_pick_returns) == 0:
                        print 'fund out of range',random_fund
                    elif len(fund_pick_returns) < 6:
                        print 'fund too short',random_fund
                        short_funds.append(random_fund)
                    else:
                        # It would be nice to fix this so that we don't do extraneous resampling and splicing if the fund overlaps completely already                                        
                        fund_pick_returns = fund_pick_returns.resample('M', how='prod')  
                        cr_size = len(combined_returns.dropna())
                        combined_returns = splice_returns([combined_returns,fund_pick_returns], resample_base=False)
                        if len(combined_returns.dropna()) > cr_size:
                            combined_funds.append(random_fund)
                            
                # To calculate the portfolio return without rebalancing, we need to convert to dollar values, sum the cumulative
                # values for each time period to get the portfolio value, and then calculate the return.
                # To do this, we add the weight to the start of the return series (like $1 investment) for calculating the portfolio return later 
                
                # First, rebuild index to include one leading value and put into a blank series
                if type(pcr_index) == types.NoneType: # this only needs to be initialized once, so check if it was
                    pcr_index = pd.Index(pd.date_range(combined_returns.index[0] - pd.tseries.offsets.DateOffset(months=1),\
                                                       periods=len(combined_returns.index)+1,freq='M'))
                cr_new = pd.Series(np.empty(len(pcr_index)), index=pcr_index) # create empty series based on this new index
                cr_new[0] = weight   # store the weight
                cr_new[combined_returns.index[0]:combined_returns.index[-1]] = combined_returns  #followed by returns            
                
                # add return series to the result dataframe
                if return_df.empty:
                    return_df = pd.DataFrame(cr_new,columns=[str(random_fund)])
                else:
                    return_df[str(random_fund)] = cr_new
            
                print trial,'asset class=',asset_class,', combined funds=',combined_funds 
                
        # return and stddev calculation at portfolio level
        pf_values = return_df.cumprod().sum(axis=1)
        pf_returns = pf_values / pf_values.shift(1)
        trial_return = calc_annual_return_from_monthly(pf_returns)
        
        # calculate excess return (for sharpe calculation)
        pf_excess_returns = pf_returns.sub(riskfree_returns - 1).dropna()
        pf_trial_excess_return = calc_annual_return_from_monthly(pf_excess_returns)
        
        pf_er_stddev = pf_excess_returns.std() * math.sqrt(12) # annualize stddev
        trial_sharpe = (pf_trial_excess_return - 1) / (pf_er_stddev) 
        sharpe_diffs.append(trial_sharpe - comp_pf_sharpe) # save for graphing
        print 'Trial return=',trial_return,'excess return=',pf_trial_excess_return,'stddev=',pf_er_stddev,'sharpe ratio=',trial_sharpe
        
        return_diffs.append((trial_return - comp_pf_return)*100)
        if comp_pf_return > trial_return:
            print trial, 'Passive wins by',comp_pf_return - trial_return, 'Passive=',comp_pf_return,'Active=',trial_return
        else:
            print trial, 'Active wins by',trial_return - comp_pf_return, 'Passive=',comp_pf_return,'Active=',trial_return
    
    ## LAST: Summarize    
    passive_win_perc = round(sum(map(lambda x: 1 if x<0 else 0, return_diffs)) / (len(return_diffs)) * 100,1)
    print 'Passive wins %s%% of the time' % passive_win_perc
    
    under_median = np.median(filter(lambda x: x<=0, return_diffs))
    print 'Writing return diffs to file...'
    meds = open(name + 'return_diffs.csv','wb')
    for trial_return in return_diffs:
        meds.write('%s\n' % str(round(trial_return,5)))
    meds.close()
    over_median = np.median(filter(lambda x: x>0, return_diffs))
    under_stdev = np.std(filter(lambda x: x<=0, return_diffs))
    over_stdev = np.std(filter(lambda x: x>0, return_diffs))
    print 'Under median=%s, Over median=%s' % (under_median,over_median)
    print 'Under stdev=%s, Over stddev=%s' % (under_stdev, over_stdev)
    
    # Graphs
    return_diffs.sort()  # order diffs

    title = 'Active vs Index Portfolios from %s to %s\n(Indexing wins %s%% of the time)' % \
        (str(int(start_date.strftime("%Y"))+1), end_date.strftime("%Y"), passive_win_perc)
    if min_fee_quantile: title+='\nFilter by lowest %s fee quantile' % min_fee_quantile
    
    figname = name + '_figure_' + pf_name + '_' + start_date.strftime("%Y") + '-' + end_date.strftime("%Y") + '_' + \
        str(trials) + \
        ('_lowfee' if min_fee_quantile else '') + \
        ('_biased' if survivor_bias else '') + \
        '.png'
    save_bar_chart(data = return_diffs, 
                       ylabel = 'Return Difference in % (Active - Index)', 
                       xlabel = 'Sorted Trials', 
                       title = title, 
                       ylimits = [-6,4],
                       under_median = under_median, 
                       over_median = over_median, 
                       figname = figname 
                       )    

    # Graph sharpe diffs
    sharpe_diffs.sort()  # order diffs
    title = 'Sharpe Ratio - Active vs Index Portfolios from %s to %s\n(Indexing wins on risk adjusted basis %s%% of the time)' % \
        (str(int(start_date.strftime("%Y"))+1), end_date.strftime("%Y"), \
         round(sum(map(lambda x: 1 if x<0 else 0, sharpe_diffs)) / (len(sharpe_diffs)) * 100,1))
    if min_fee_quantile: title+='\nFilter by lowest %s fee quantile' % min_fee_quantile
    
    figname = name + '_sharpe_figure_' + pf_name + '_' + start_date.strftime("%Y") + '-' + end_date.strftime("%Y") + '_' + \
        str(trials) + \
        ('_lowfee' if min_fee_quantile else '') + \
        ('_biased' if survivor_bias else '') + \
        '.png'
   
    save_bar_chart(data = sharpe_diffs, 
                   ylabel = 'Sharpe Difference in % (Active - Passive)', 
                   xlabel = 'Sorted Trials', 
                   title = title, 
                   figname = figname
                   )
                   
def save_bar_chart(data, ylabel, xlabel, title, figname, ylimits=None, under_median = None, over_median = None):
    """ Saves a standard bar chart with the specified attributes and file name """
    fig = plt.figure()
    ax = fig.add_subplot(111) # our standard type for this project
    rects = ax.bar(np.arange(len(data)),data, width=1, color='b') #our standard settings
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    if ylimits:
        plt.ylim(ylimits)
    plt.subplots_adjust(top=0.86) #move the title up a bit
    
    if under_median:
        ax.add_artist(AnchoredText("Underperformers:\nmedian:%s%%" % (under_median.round(2)), loc=2, prop=dict(size=12)))   
    if over_median: 
        ax.add_artist(AnchoredText("Outperformers:\nmedian:%s%%" % (over_median.round(2)), loc=4, prop=dict(size=12)))    
    
    print 'Saving figure',figname      
    plt.savefig(figname)    
    

def get_current_open_funds(date_bounds, asof_date):
    """ Returns a list of the current open funds as of a date in a date_bound array """
    
    ## Would like to speed this up - maybe create a method that pre-calculates and caches
    #find the funds open at the next needed date in the series                    
    lhs = date_bounds['end_date'] >= asof_date  
    rhs = date_bounds['start_date'] <= asof_date
    
    return list(set(lhs[lhs==True].index).intersection(list(rhs[rhs==True].index)))

def get_fund_list(df):
    """ takes all fund returns dataframe and returns the unique fund list """
    #fund_list = df.drop_duplicates('FundNo').set_index(['FundNo'])  #prior way
    fund_list = df.groupby(level=0, as_index=False).sum().drop_duplicates('FundNo').set_index(['FundNo']) #now multiindex
    return list(fund_list.index)

def funds_by_fee(df, max_fee=0.01):
    """ Returns an array of crsp_fundno's based on the max fee criteria for a given date in time  """
    cheap_funds = df[df.apply(lambda x: x['ExpRatio'] <= max_fee, axis=1)]
    return list(cheap_funds.index)

def specific_funds_by_fee(df, fund_filter, fee_quantile=0.5):
    """ Returns an array of crsp_fundno's based on the fund filter list, 
    and max fee quantile criteria for a given date in time  """
    print 'Filtering funds by fee quantile',fee_quantile
    df_filtered = df.reindex(fund_filter)
    
    quantile = df_filtered['ExpRatio'].quantile(fee_quantile)
    
    #return those funds with fees below the quantile
    print 'quantile threshold for',len(fund_filter),'funds is',quantile 
    cheap_funds = df_filtered[df_filtered.apply(lambda x: x['ExpRatio'] <= quantile, axis=1)]
    return list(cheap_funds.index)

def get_fund_date_bounds(df):
    fund_list = get_fund_list(df)
    date_df = pd.DataFrame(None,index=fund_list)
    flat_df = df.reset_index(1)
    date_df['start_date'] = flat_df['level_1'].groupby(level=0).first()
    date_df['end_date'] = flat_df['level_1'].groupby(level=0).last()
    return date_df
    
def get_r2_bucket_funds(threshold=0.9, force_bucket=False, r2_file='r2_all_funds.pandas', bucket_file='bucketed_r2.pandas'):
    """ Creates a dataframe of funds that are highly correlated (by threshold) to each asset class"""
    if not force_bucket and os.path.isfile(bucket_file):
        print "Loading bucketed R2 file from cache:",bucket_file
        return pd.load(bucket_file)
    #otherwise create the bucket file
    if not os.path.isfile(r2_file): 
        print "R2 file (%s) does not exist. Run calc_all_fund_r2() first" % r2_file 
        return False 
    else:
        print "Bucketing by R2"
    r2_df = pd.load(r2_file)
    # take only the ones over threshold, and drop any rows with no assets highly correlated
    bucketed_df=r2_df[r2_df.apply(lambda x: x > threshold, axis=1)].dropna(how='all')  

    # save for next time
    bucketed_df.save(bucket_file)
    return bucketed_df

def get_style_bucket_funds(fund_returns, force_bucket=False, bucket_file='bucketed_style.pandas'):
    """ Creates a dataframe of funds that by style mapped to each asset class"""
    if not force_bucket and os.path.isfile(bucket_file):
        print "Loading bucketed style file from cache:",bucket_file
        return pd.load(bucket_file)
    #otherwise create the bucket file
    print "Bucketing by style"
    
    fund_styles = get_fund_styles()
    
    # apply mapping of our asset classes to styles
    # [[put in metamappings.py]]
    asset_style_results = {}
    fund_list = get_fund_list(fund_returns)
    asset_list = asset_classes
    # dataframe to hold our results, index by fund, columns will be asset classes
    style_df=pd.DataFrame(index=fund_list)
    for asset_class in asset_classes:
        print '***** Looking up styles for asset class',asset_class 
        styles = crsp_style_mapping[asset_class] 
        #loop through on the funds we have styles for
        for fund in list(set(fund_list).intersection(list(fund_styles.index))):
            if fund_styles.ix[fund]['StyleCode'] in styles:
                asset_style_results[fund] = 1
        style_df[asset_class] = pd.Series(asset_style_results)
        asset_style_results = {}    
    
    # take only the matching styles, and drop any rows with no assets highly correlated
    bucketed_df=style_df[style_df.apply(lambda x: x == 1, axis=1)].dropna(how='all')  
    
    # save for next time
    bucketed_df.save(bucket_file)
    return bucketed_df 

def calc_all_fund_r2(fund_returns, asset_returns, force_calc=False, df_file='r2_all_funds.pandas'):
    """ Calculates R2 across all funds and asset class benchmarks, returns dataframe of results """
    # caching to make things faster most of the time
    if not force_calc and os.path.isfile(df_file):
        print "Loading R2 file from cache:",df_file
        return pd.load(df_file)
    #otherwise re-calc 
    asset_r2_results = {}
    fund_list = get_fund_list(fund_returns)
    asset_list = asset_classes
    # dataframe to hold our results, index by fund, columns will be asset classes
    r2_df=pd.DataFrame(index=fund_list)
    for asset_series in asset_returns:
        print '***** Calculating R2 for asset class',asset_series.name 
        for fund in fund_list:
            #reindex as datetime so we can resample to EOM dates and join with the benchmark
            f = fund_returns.ix[fund]
            f.index = pd.DatetimeIndex(f.index)
            f = f.resample('M', how='prod') # just to normalize dates, shouldn't change data points
            r2 = calc_r2(f.join(asset_series,how='outer'))
            asset_r2_results[fund] = r2 
            print 'R2(%s, fund %s) = %s' % (asset_series.name,fund,r2)
            
        r2_df[asset_series.name] = pd.Series(asset_r2_results)
        asset_r2_results = {}
    print 'Saving R2 results to',df_file 
    r2_df.save(df_file)
    return r2_df 

def calc_r2(df1,df2):
    """ calculates R2 of the first column of each of two dataframes """
    #df = pd.DataFrame(df1.take([0],1))   #strip out first column
    #df.insert(1,2,df2.take([0],1))       #add first column of second df
    df = pd.DataFrame(df1).insert(1,1,df2)
    return df.corr().ix[0,1]**2

def calc_r2(df):
    """ calculates R2 of the first two columns of a dataframe """
    return df.corr().ix[0,-1]**2

def calc_annual_return_from_monthly(ts):
    """ Calculations the geometric annual return for a monthly return series
    Assumes return values are already R+1 """
    if ts.index.freq == 'M':
        return np.prod(ts)**(12/len(ts))
    else:
        raise('ERROR: This function only works for Monthly return series')

def get_portfolio_return(port_def, crsp_returns, riskfree_returns, start_date, end_date): # iterates over portfolio, splices  
    """ Loads the portfolio, splices funds for each asset class and calculates the returns
    
    Handles portfolio of non-CRSP returns via csv, for example those sourced from xignite """
    comp_pf_return = 0
    return_df = pd.DataFrame()
    
    for asset_class in port_def.keys():
        weight = port_def[asset_class]['alloc']
        tickers = port_def[asset_class]['funds']
        constituent_list = [pd.Series(None,index=pd.date_range(start_date,end_date,freq='M'))]
        for ticker in tickers:
            if type(ticker) == int: #it's a crsp_fundno, get from CRSP data
                constituent_list.append(crsp_returns.ix[ticker]['Return'])
            else:  # get from file-based data (xignite, index, etc)
                constituent_list.append(load_asset_class_returns(asset_list=[ticker])[0])   
                
        spliced_returns = splice_returns(constituent_list, name=asset_class)
        
        spliced_returns = spliced_returns[start_date:end_date]
        spliced_returns.index = pd.DatetimeIndex(spliced_returns.index) #convert to DatetimeIndex
        spliced_returns = spliced_returns.resample('M', how='prod')  # ensure all monthly       
        ann_return = calc_annual_return_from_monthly(spliced_returns)  # calculate annualized return (old way)
        if len(spliced_returns.dropna()) <> len(spliced_returns):
            print 'ERROR: Not enough portfolio returns, try adding an index?',asset_class,\
                  ': need',len(spliced_returns),'got',len(spliced_returns.dropna()) 
            sys.exit()
        print asset_class,'return=',ann_return 
        comp_pf_return += ann_return * weight # old way
        
        # portfolio way
        #add the weight to the start of the return series (like $1 investment) for calculating the portfolio return later 
        # first, rebuild index and put into a blank series
        combined_returns = spliced_returns
        pcr_index = pd.Index(pd.date_range(combined_returns.index[0] - pd.tseries.offsets.DateOffset(months=1),\
                                           periods=len(combined_returns.index)+1,freq='M'))
        cr_new = pd.Series(np.empty(len(pcr_index)), index=pcr_index)
        cr_new[0] = weight   # add the weight
        cr_new[combined_returns.index[0]:combined_returns.index[-1]] = combined_returns  #followed by returns            
        
        # add return series to the result dataframe
        if return_df.empty:
            return_df = pd.DataFrame(cr_new,columns=[asset_class])
        else:
            return_df[asset_class] = cr_new        
    
    # return and stddev calculation at portfolio level
    pf_values = return_df.cumprod().sum(axis=1)
    pf_returns = pf_values / pf_values.shift(1)
    pf_trial_return = calc_annual_return_from_monthly(pf_returns)
    print 'comp_pf_return (old way) =',comp_pf_return
    print 'pf_return=',pf_trial_return
    
    # calculate excess return (for sharpe calculation)
    pf_excess_returns = pf_returns.sub(riskfree_returns - 1).dropna()
    pf_trial_excess_return = calc_annual_return_from_monthly(pf_excess_returns)
    
    # return annual return and annualized standard deviation of returns
    return pf_trial_return, pf_trial_excess_return, pf_excess_returns.std() * math.sqrt(12)

def load_benchmark_returns(bmk_list=['MSCI_EAFE'], fee_adjust=None):
    """ loads the list of benchmark returns from file.  Optionally adjust returns by a fee 
    
    Assumes return is in percentage terms, e.g. 5.5 is 5.5%, so we divide by 100 """
    benchmark_return_series = []
    for f in bmk_list:
        rs = pd.Series(pd.read_csv(config['index_path'] + benchmark_source[f], \
                                   sep='\t',parse_dates=True)['Return']/100+1)
        if fee_adjust:
            monthly_fee = benchmark_index_fees[f] / 12
            print f,': Adjusting benchmark returns by underlying monthly fee',monthly_fee
            rs -= monthly_fee
        benchmark_return_series.append(rs)
    return benchmark_return_series

def load_asset_class_returns(asset_list=['US_LargeCap']):
    """ loads the list of asset class returns by looking up benchmarks and splicing them """
    asset_class_returns = []
    for a in asset_list:
        print 'Loaded',a
        asset_class_returns.append(splice_returns(load_benchmark_returns(asset_class_bmks[a], fee_adjust=True), name=a))
    return asset_class_returns
    
def splice_returns(constituents, name=None, resample_base=True):
    """ Takes a list of monthly returns TimeSeries and concatenates them in order giving precidence to the earlier items 
    To do this we normalize to monthly frequency EOM dates
    We are splicing the constitents INTO the first one listed"""
    if resample_base:
        master_series = constituents[0].resample('M', how='prod')
    else:
        master_series = constituents[0]
    try:  #in case there is nothing to splice
        for c in constituents[1:]:
            master_series = master_series.combine_first(c.resample('M', how='prod')) 
    except:
        pass 
    master_series.name = name 
    return master_series

def new_data_setup():
    """ MANUAL: things to run when new data is integrated (force regenerate all pandas cached files) 
    ********* FOR NEW DATA SETUP ONLY"""
    
    # these may be run one at a time.  if this isn't used and pandas files are not available
    # they will be run anyway by the engine.
    returns = get_all_fund_returns(force_db_read=True)    
    fs = get_style_bucket_funds(returns, force_bucket=True)
    areturns=load_asset_class_returns(asset_classes)
    allr2 = calc_all_fund_r2(returns,areturns,force_calc=True) # to run
    buckets=get_r2_bucket_funds(force_bucket=True) # to run

if __name__ == "__main__":
    main()
    