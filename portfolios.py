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

## Portfolio Definitions with allocation weight
##
## Note: list funds in the order of precedence, highest first.  

portfolio_1 = {
    'US_TotalMarket':{'alloc':0.4,'funds':[31434]}, #'VTSMX' since 1992
    'Intl_TotalMarket': {'alloc':0.2,'funds':[31200]}, #  VGTSX since 4-1996
    'US_Bond_Total': {'alloc':0.4,'funds':[31239]},# VBMFX - since 1986
}

portfolio_1equal = {
    'US_TotalMarket':{'alloc':0.33,'funds':[31434]}, #'VTSMX', 
    'Intl_TotalMarket': {'alloc':0.33,'funds':[31200]}, #  VGTSX 
    'US_Bond_Total': {'alloc':0.34,'funds':[31239]},# VBMFX
}

portfolio_2 = {
    'US_TotalMarket':{'alloc':0.35,'funds':[31434]}, #'VTSMX', 
    'Intl_TotalMarket': {'alloc':0.15,'funds':[31200]}, #  VGTSX 
    'US_Bond_Total': {'alloc':0.4,'funds':[31239]},# VBMFX
    'REIT': {'alloc':0.1,'funds':[31188]},#   VGSIX
}

portfolio_10assets = {
    'US_LargeCap': {'alloc':0.1,'funds':[31432]}, #  VFINX - Vanguard 500 Index Investor - since 1975
    'US_MidCap': {'alloc':0.1,'funds':[31473,'US_MidCap']},# Vanguard midcap index - since 1998
    'US_SmallCap': {'alloc':0.1,'funds':[31460]},# Vanguard smallcap index - since 1960
    'Intl_Developed': {'alloc':0.1,'funds':[31201,'Intl_Developed']}, # Vgd Developed Markets Intl - since 2000
    'Intl_Emerging': {'alloc':0.1,'funds':[31338]}, # Vgd Emerging - since 1994
    'TIPS': {'alloc':0.1,'funds':[16413,31320,'TIPS']},# TIP since 2003, splice Vanguard Inflation protected since 2000    
    'MUNI': {'alloc':0.1,'funds':[36088,31420]},  # MUB since 2007, VWITX Vanguard Muni investor since 1977
    'US_Bond_Total': {'alloc':0.1,'funds':[31239]},# VBMFX - Vanguard total bond- since 1986
    'REIT': {'alloc':0.1,'funds':[31188,'REIT']},# VGSIX - Vanguard REIT - since 2001
    'US_Treas_1-3': {'alloc':0.1,'funds':[16432,'US_Treas_1-3']}, # SHY - iShares Treas 1-3yr -since 2002
}

portfolio_5assets = {
    'US_TotalMarket':{'alloc':0.2,'funds':[31434]}, #VTSMX - Vanguard Total Stock Market 
    'Intl_TotalMarket': {'alloc':0.2,'funds':[31200]}, #  VGTSX - Vanguard Total Intl Stock 
    'US_Bond_Total': {'alloc':0.2,'funds':[31239]},# VBMFX - Vanguard total bond- since 1986
    'REIT': {'alloc':0.2,'funds':[31188,'REIT']},# VGSIX - Vanguard REIT - since 2001
    'US_Treas_1-3': {'alloc':0.2,'funds':[16432,'US_Treas_1-3']}, # SHY - iShares Treas 1-3yr -since 2002
}

us_total_only = {
    'US_TotalMarket':{'alloc':1.0,'funds':[31434]}, #'VTSMX', 
}

us_bond_only = {
    'US_Bond_Total': {'alloc':1.0,'funds':[31239]},# VBMFX
}

intl_total_only = {
    'Intl_TotalMarket': {'alloc':1.0,'funds':[31200,'Intl_TotalMarket']}, #  VGTSX
}

