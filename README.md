Copyright 2013 Betterment

This file is part of The Index Portfolio Whitepaper Engine.

The Index Portfolio Whitepaper Engine is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

The Index Portfolio Whitepaper Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with The Index Portfolio Whitepaper Engine.  If not, see <http://www.gnu.org/licenses/>.

Active Funds vs Index Funds using CRSP(R) Survivor-bias-free database
=============

This is the code used to conduct the research for a whitepaper created by Richard Ferri of Portfolio Solutions, LLC 
and Alex Benke of Betterment.  The whitepaper may be downloaded here: <https://www.betterment.com/resources/WhitePaper.pdf>

Data requirements
-------
Running this program requires obtaining several data sets.  
* The CRSP Survivor-bias-free database.  <http://www.crsp.com/products/mutual_funds.htm>
* Index data to use the risk-adjusted and benchmark index comparison features - stored in /data (see example_data.csv 
  for format)

Environment requirements
-------
The following environment and Python libraries were used for the research.  Other versions may work, but have not been tested.
* MacOS X 10.8.3
* Python 2.7.2 <http://www.python.org/>
* Pandas 0.10.0 <http://pandas.pydata.org/>
* Numpy 1.6.1 <http://www.numpy.org/>
* Matplotlib 1.2.0

Setup
-------

1. Import data from CRSP to Sqlite3
	All data used by the engine originates from the CRSP ascii files imported via sql to a database.

	We converted the CRSP-provided schema to sqlite format.  We only used part of the 
	schema for our needs (stored in ./schema/*.part1.txt) but the other part is also included for 
	future use (./schema/*part2*.txt)

	Run:
	`sqlite3 crsp2012.db < mfdb_create_load_procedure_sqlite_part1.txt`

2. Configure path settings
    Rename `settings.example.py` to `settings.py` and edit it with the path to your sqlite database and input benchmark
    data files.

3. Set up portfolio definition
	Use portfolio.py to create a portfolio definition similar to the examples there, with funds and weightings.  
	In most cases the crsp fund number (crsp_fundno in the database) is used.  Support is also provided for benchmark
	index data for a number of asset classes.  This data comes from .csv files that can be added if you want to add more
	benchmarks or freshen the data.

	For the risk adjustment (sharpe calculation), we use 1-month tbill from the federal reserve as the risk free rate.  
	The data for this calculation is in ./data/1mo-tbill.csv.

4. Check meta data and mappings
	metamappings.py controls the asset class mappings to benchmark data which needs to be updated if asset classes are
	added or benchmarks are changed.  

	This file also stores the mapping of each asset class to the crsp style codes.  If these are adjusted after engine.py has
	been run, the style buckets must be regenerated (e.g. by removing the bucketed_style.pandas file)

5. A note about getting new data
	crsp_data_wrappers.py holds functions that interface with the database.  If you add a table and need to access it, or 
	need to tweak a query of existing data, it should be done here.

Running
-------

1. Run engine.py with desired arguments
	To see possible arguments:
	`python engine.py --help`

	A decent description of these is also provided as a method description in engine.engine() 

    A note on caching
    -----------------
	We use pandas object saving to file in order to cache data to make re-runs faster.  The first time
	the engine is run, it will create a number of .pandas cache files storing the returns, styles, tickets, etc.
	Subsequent runs will be much faster once this is done.

2. Outputs
	Aside from a lot of logging (useful to redirect to a file), the output will be:
	* .png file with the main result bar chart of excess returns for each trial (raw data also output - see below)
	* .png file for the sharpe ratio bar chart
	* fund_list*.csv files with the list of funds used in each asset class.
	* returns_diff.csv is the actual difference in active and passive returns for each trial, which is graphed ultimately. 