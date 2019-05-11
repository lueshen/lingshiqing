#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  5 17:22:55 2019

@author: lueshen
"""

import pandas as pd
import numpy as np
import statistics
import progressbar
from datetime import datetime
from arch import arch_model
import warnings
warnings.filterwarnings('ignore')
warnings.simplefilter("ignore")
# =============================================================================
# Define risk free rate, reference to US treasury yield curve as of 20190322
# https://www.treasury.gov/resource-center/data-chart-center/interest-rates/pages/TextView.aspx?data=yieldYear&year=2019
# 1m, 2m, 3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y
# =============================================================================
# Define risk free rate according to US
yieldCurveDict = {
                    '2019-04-22': 2.49,
                    '2019-05-22': 2.48,
                    '2019-06-22': 2.46,
                    '2019-09-22': 2.48,
                    '2020-03-22': 2.45,
                    '2021-03-22': 2.31,
                    '2022-03-22': 2.24,
                    '2024-03-22': 2.24,
                    '2026-03-22': 2.34,
                    '2029-03-22': 2.44,
                    '2039-03-22': 2.69,
                    '2049-03-22': 2.88
                }

# Derive forward rates from US treasury yield curve
curvePoints = ['2019-03-22'] + list(yieldCurveDict.keys())

forwardCurveDict = {}
fwdCurveDict = {0:0}
for i in range(len(yieldCurveDict)):
    datePoint1 = curvePoints[i]
    datePoint2 = curvePoints[i + 1]
    busDateDiff1 = np.busday_count(curvePoints[0], datePoint1)
    busDateDiff2 = np.busday_count(curvePoints[0], datePoint2)
    if (datePoint1 == curvePoints[0]):
        forwardCurveDict[datePoint2] = yieldCurveDict[datePoint2]
        fwdCurveDict[busDateDiff2] = yieldCurveDict[datePoint2]
    else:
        yieldAtDate1 = yieldCurveDict[datePoint1]
        yieldAtDate2 = yieldCurveDict[datePoint2]
        forwardCurveDict[datePoint2] = float((yieldAtDate2 * busDateDiff2 - yieldAtDate1 * busDateDiff1) / (busDateDiff2 - busDateDiff1))
        fwdCurveDict[busDateDiff2] = float((yieldAtDate2 * busDateDiff2 - yieldAtDate1 * busDateDiff1) / (busDateDiff2 - busDateDiff1))

# Function to get risk free rate given a date (datetime.date object)
def getRiskFreeRateByDate(inputDate):
    for i in range(len(forwardCurveDict)):
        datePoint1 = datetime.strptime(curvePoints[i],'%Y-%m-%d').date()
        datePoint2 = datetime.strptime(curvePoints[i + 1],'%Y-%m-%d').date()
        if (inputDate >= datePoint1 and inputDate < datePoint2):
            return forwardCurveDict[curvePoints[i + 1]]
    return 0

# Function to get risk free rate given a business date count from 20190322
def getRiskFreeRate(dayCounts):
    dayCountPoints = list(fwdCurveDict.keys())
    for i in range(len(dayCountPoints)-1):
        dayCount1 = dayCountPoints[i]
        dayCount2 = dayCountPoints[i + 1]
        if (dayCounts >= dayCount1 and dayCounts < dayCount2):
            return fwdCurveDict[dayCount2]
    return 0

# =============================================================================
# Repo Rates
# =============================================================================
repoRateDict = {
                'Crude Oil WTI':    0.01,
                'Ethanol':          0.01,
                'Gold':             0.01,
                'Natural Gas':      0.01,
                'Silver':           0.01
               }

# =============================================================================
# Utility functions
# =============================================================================
commodityCurrDict = {
                    'Crude Oil WTI':    0.01,
                    'Ethanol':          0.0001,
                    'Gold':             1,
                    'Natural Gas':      0.001,
                    'Silver':           0.01
                    }

def get_currency_divisor(commodity):
    return commodityCurrDict[commodity]

def get_best_model(logRtSeries, pLimit, oLimit, qLimit):
    # To do: add model checking with white noise using ljungbox test
    best_aic = np.inf
    best_order = None
    best_mdl = None

    for pValue in range(pLimit):
        for oValue in range(oLimit):
            for qValue in range(qLimit):
                try:
                    tmp_mdl = arch_model(y = logRtSeries,
                                         p = pValue,
                                         o = oValue,
                                         q = qValue,
                                         dist = 'Normal')
                    tmp_res = tmp_mdl.fit(update_freq=5, disp='off')
                    tmp_aic = tmp_res.aic
                    if tmp_aic < best_aic:
                        best_aic = tmp_aic
                        best_order = [pValue, oValue, qValue]
                        best_mdl = tmp_res
                except:
                    continue
    
    output = {}
    output['Best AIC'] = best_aic
    output['Best Order'] = best_order
    output['Best Model'] = best_mdl
    
    return output

# Use GARCH vol to price Asian option (Monte Carlo)
def garchPricer(startPrice, strikePrice, garchModel, repo, expBusDays, numPath):
    sumCallPrice = 0
    sumPutPrice = 0
    res = garchModel['Best Model']
    mu = res.params['mu']
    volForecasts = res.forecast(horizon=expBusDays)
    vol = np.sqrt(volForecasts.residual_variance.iloc[-1].values)
    
    for i in range(numPath):
        ulyPrice = startPrice
        sumUlyPrice = 0
        dt = 1 / 252
        randomGenerator = np.random.normal(0, np.sqrt(dt), expBusDays)
        discountRate = 0
        
        # Simulated one path of underlying price
        for j in range(expBusDays):
            dWt = randomGenerator[j]
            rt = getRiskFreeRate(j) / 100
            dLogSt = mu + vol[j] * dWt
            discountRate += rt * dt
            ulyPrice = ulyPrice * np.exp(dLogSt)
            sumUlyPrice += ulyPrice
    
        avgUlyPrice = sumUlyPrice / expBusDays
        
        # True for call, false for put
        sumCallPrice += max(avgUlyPrice - strikePrice, 0) * np.exp(-discountRate)
        sumPutPrice += max(strikePrice - avgUlyPrice, 0) * np.exp(-discountRate)
    
    output = {
                'Call': sumCallPrice / numPath,
                'Put': sumPutPrice / numPath
            }
    
    return output

# Pricing Asian Option with fixed vol (Monte Carlo)   
def nonGarchPricer(startPrice, strikePrice, vol, repo, expBusDays, numPath):
    sumCallPrice = 0
    sumPutPrice = 0
    
    for i in range(numPath):
        ulyPrice = startPrice
        sumUlyPrice = 0
        dt = 1 / 252
        randomGenerator = np.random.normal(0, np.sqrt(dt), expBusDays)
        discountRate = 0
        
        # Simulated one path of underlying price
        for j in range(expBusDays):
            dWt = randomGenerator[j]
            rt = getRiskFreeRate(j) / 100
            dLogSt = (rt - repo) * dt + vol * dWt
            discountRate += rt * dt
            ulyPrice = ulyPrice * np.exp(dLogSt)
            sumUlyPrice += ulyPrice
    
        avgUlyPrice = sumUlyPrice / expBusDays
        
        # True for call, false for put
        sumCallPrice += max(avgUlyPrice - strikePrice, 0) * np.exp(-discountRate)
        sumPutPrice += max(strikePrice - avgUlyPrice, 0) * np.exp(-discountRate)
    
    output = {
                'Call': sumCallPrice / numPath,
                'Put': sumPutPrice / numPath
            }
    
    return output
# =============================================================================
# Data Preprocessing
# =============================================================================

# Load underlying data from git
df_uly = pd.read_csv("../Underlying Data/Underlying Data.csv", sep=',')

# Preprocess dataframe, set up index, fill nan with latest previous values
df_uly.index = pd.to_datetime(df_uly['Date']).dt.date
df_uly = df_uly.drop('Date', axis = 1)

# Load option data from git
df_opt = pd.read_csv("../Option Price Data/Option Data.csv", sep=',')

# Preprocess dataframe, convert dates, calculate days to maturity
df_opt.columns = ['Start Date','Maturity Date','Strike','Put','Call','Underlying']
df_opt['Maturity Date'] = pd.to_datetime(df_opt['Maturity Date']).dt.date
df_opt['Start Date'] = '2019-3-25'
df_opt['Start Date'] = pd.to_datetime(df_opt['Start Date']).dt.date
df_opt['Exp BusDays'] = np.busday_count(df_opt['Start Date'], df_opt['Maturity Date']) + 1

# =============================================================================
# Get best GARCH model for underlyings whose options we will price later
# =============================================================================
masterObj = {}

ulyList = np.unique(df_opt['Underlying'])
for underlying in progressbar.progressbar(ulyList):
    tmp_uly = underlying[:-8]
    TS_uly = df_uly[tmp_uly].dropna()
    TS_logRt = (np.log(TS_uly) - np.log(TS_uly.shift(1))).dropna()
    masterObj[tmp_uly] = {
                            'Start Price': TS_uly[-1],
                            'Volatility': statistics.stdev(TS_logRt),
                            'Best Model': get_best_model(TS_logRt, 10, 10, 10)
                         }

# =============================================================================
# Execute garchPricer and collect results
# =============================================================================
nonGarchFairPriceCall = []
nonGarchFairPricePut = []
garchFairPriceCall = []
garchFairPricePut = []

# Number of Monte Carlo simulated paths
numPath = 10000

# Loop through options
for row in progressbar.progressbar(df_opt.index):
    # Retrieve the name of the underlying
    tmp_uly = df_opt['Underlying'][row][:-8]
    tmp_strike = df_opt['Strike'][row] * get_currency_divisor(tmp_uly)
    tmp_maturity = df_opt['Maturity Date'][row]
    tmp_expBusDays = df_opt['Exp BusDays'][row]
    
    # Retrieve the underlying historical data
    tmp_s0 = masterObj[tmp_uly]['Start Price']
    tmp_vol = masterObj[tmp_uly]['Volaitility']
    tmp_model = masterObj[tmp_uly]['Best Model']
    
    nonGarchResults = nonGarchPricer(tmp_s0, tmp_strike, tmp_vol, repoRateDict[tmp_uly], tmp_expBusDays, numPath)
    nonGarchFairPriceCall.append(nonGarchResults['Call'])
    nonGarchFairPricePut.append(nonGarchResults['Put'])
    
    garchResults = garchPricer(tmp_s0, tmp_strike, tmp_model, repoRateDict[tmp_uly], tmp_expBusDays, numPath)
    garchFairPriceCall.append(garchResults['Call'])
    garchFairPriceCall.append(garchResults['Put'])
    
df_opt['Put (MC non-GARCH)'] = nonGarchFairPricePut
df_opt['Call (MC non-GARCH)'] = nonGarchFairPriceCall
df_opt['Put (MC GARCH)'] = garchFairPricePut
df_opt['Call (MC GARCH)'] = garchFairPriceCall
















