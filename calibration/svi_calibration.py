from Utilities.svi_read_data import get_wind_data
from Utilities.svi_prepare_vol_data import calculate_vol_BS
from calibration.SviCalibrationInput import SviInputSet
import Utilities.svi_calibration_utility as svi_util
import math
import pandas as pd
import matplotlib.pyplot as plt
from Utilities.utilities import *
import numpy as np
import datetime
import os
import pickle

# with open(os.path.abspath('..')+'/intermediate_data/svi_calibration_50etf_puts_noZeroVol.pickle','rb') as f:
#     calibrered_params_ts = pickle.load(f)[0]
# with open(os.path.abspath('..')+'/intermediate_data/svi_dataset_50etf_puts_noZeroVol.pickle','rb') as f:
#     svi_dataset = pickle.load(f)[0]

evalDate = ql.Date(1, 9, 2015)
# endDate = ql.Date(28, 9, 2017)
endDate = ql.Date(30, 9, 2017)
calendar = ql.China()
daycounter = ql.ActualActual()

svi_dataset = {}
calibrered_params_ts = {}
count = 0
while evalDate <= endDate:

    evalDate = calendar.advance(evalDate, ql.Period(1, ql.Days))
    # if to_dt_date(evalDate) in svi_dataset.keys(): continue
    ql.Settings.instance().evaluationDate = evalDate
    print(evalDate)
    try:
        curve = get_curve_treasury_bond(evalDate, daycounter)
        vols, spot_close, mktData, mktFlds, optionData, optionFlds, optionids = get_wind_data(evalDate)
    except:
        continue
    yield_ts = ql.YieldTermStructureHandle(curve)
    dividend_ts = ql.YieldTermStructureHandle(ql.FlatForward(evalDate, 0.0, daycounter))
    datestr = str(evalDate.year()) + "-" + str(evalDate.month()) + "-" + str(evalDate.dayOfMonth())
    intraday_etf = pd.read_json(os.path.abspath('..') + '\marketdata\intraday_etf_' + datestr + '.json')
    spot = intraday_etf.loc[intraday_etf.index[-1]].values[0]
    svi_data = SviInputSet(to_dt_date(evalDate),spot)
    # print(spot,spot)
    for optionid in optionids:
        optionDataIdx = optionData[optionFlds.index('wind_code')].index(optionid)
        # if optionData[optionFlds.index('call_or_put')][optionDataIdx] == '认购':
        if optionData[optionFlds.index('call_or_put')][optionDataIdx] == '认沽':
            temp = pd.to_datetime(optionData[optionFlds.index('exercise_date')][optionDataIdx])
            mdate = datetime.date(temp.year,temp.month,temp.day)
            maturitydt = ql.Date(mdate.day, mdate.month, mdate.year)
            mktindex = mktData[mktFlds.index('option_code')].index(optionid)
            strike = optionData[optionFlds.index('exercise_price')][optionDataIdx]
            close = mktData[mktFlds.index('close')][mktindex]
            open_price = mktData[mktFlds.index('open')][mktindex]
            ttm = daycounter.yearFraction(evalDate, maturitydt)
            rf = curve.zeroRate(maturitydt, daycounter, ql.Continuous).rate()
            Ft = spot * math.exp(rf*ttm)
            moneyness = math.log(strike/Ft, math.e)
            optiontype = ql.Option.Put
            exercise = ql.EuropeanExercise(maturitydt)
            payoff = ql.PlainVanillaPayoff(optiontype, strike)
            option = ql.EuropeanOption(payoff, exercise)
            flat_vol_ts = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(evalDate, calendar, 0.0, daycounter))
            process = ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(spot)), dividend_ts, yield_ts,
                                                   flat_vol_ts)
            option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
            #error = 0.0
            try:
                implied_vol = option.impliedVolatility(close, process, 1.0e-4, 300, 0.0, 4.0)
            except RuntimeError:
                continue
            #implied_vol2, error = calculate_vol_BS(maturitydt, optiontype, strike, spot, dividend_ts, yield_ts,
            #                                      close, evalDate, calendar, daycounter, precision = 0.05, maxVol = 0.5, step = 0.0001)
            #print(implied_vol,'---',implied_vol2)
            totalvariance = (implied_vol**2)*ttm
            svi_data.update_data(mdate,strike,moneyness,implied_vol,ttm,totalvariance,close,open_price)
    svi_dataset.update({to_dt_date(evalDate):svi_data})

    calibrered_params = {}
    for mdate in svi_data.dataSet.keys():
        optimization_data = []
        data_mdate = svi_data.dataSet.get(mdate)
        logMoneynesses = data_mdate.moneyness
        totalvariance = data_mdate.totalvariance
        vol = data_mdate.volatility
        #print('vols : ',vol)
        optimization_data.append(logMoneynesses)
        optimization_data.append(data_mdate.totalvariance)
        ttm = data_mdate.ttm
        params = svi_util.get_svi_optimal_params(optimization_data, ttm, 5)
        #print('params : ',params)
        calibrered_params.update({mdate:params})
        a_star, b_star, rho_star, m_star, sigma_star = params
        x_svi = np.arange(min(logMoneynesses)-0.005, max(logMoneynesses)+0.02, 0.1/100)  # log_forward_moneyness
        tv_svi = np.multiply(
            a_star + b_star*(rho_star*(x_svi-m_star)+np.sqrt((x_svi - m_star)**2 + sigma_star**2)), ttm)
        vol_svi = np.sqrt(
            a_star + b_star*(rho_star*(x_svi-m_star) + np.sqrt((x_svi - m_star)**2 + sigma_star**2)))
        # plt.figure()
        # plt.plot(logMoneynesses, vol, 'ro')
        # plt.plot(x_svi, vol_svi, 'b--')
        # plt.title('vol, '+str(evalDate)+', '+str(mdate))
        #plt.figure(count)
        #count += 1
        #plt.plot(logMoneynesses, totalvariance, 'ro')
        #plt.plot(x_svi, tv_svi, 'b--')
        #plt.title('tv, '+str(evalDate)+', '+str(mdate))
    # plt.show()
    #print(calibrered_params)
    calibrered_params_ts.update({to_dt_date(evalDate):calibrered_params})
print('calibrered_params_ts',calibrered_params_ts)
with open(os.path.abspath('..')+'/intermediate_data/svi_calibration_50etf_puts_noZeroVol_itd_2.pickle','wb') as f:
    pickle.dump([calibrered_params_ts],f)

print('svi',svi_dataset)
with open(os.path.abspath('..')+'/intermediate_data/svi_dataset_50etf_puts_noZeroVol_itd_2.pickle','wb') as f:
    pickle.dump([svi_dataset],f)
#








