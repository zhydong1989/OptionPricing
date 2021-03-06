from Utilities.utilities import *
from bs_model.bs_estimate_vol import estimiate_bs_constant_vol
import QuantLib as ql
import timeit
import os
import pickle

with open(os.path.abspath('..') +'/intermediate_data/total_hedging_bs_estimated_vols_call.pickle','rb') as f:
    estimated_vols = pickle.load(f)[0]


start = timeit.default_timer()

calendar = ql.China()
daycounter = ql.ActualActual()


evalDate = ql.Date(1, 9, 2015)
#evalDate = ql.Date(28, 9, 2017)
endDate = ql.Date(10, 10, 2017)

# estimated_vols = {}
while evalDate < endDate:
    print('Start : ', evalDate)

    evalDate = calendar.advance(evalDate, ql.Period(1, ql.Days))
    if to_dt_date(evalDate) in estimated_vols.keys():
        print(evalDate,' : ',estimated_vols.get(to_dt_date(evalDate)))
        continue
    ql.Settings.instance().evaluationDate = evalDate
    try:
        print(evalDate)

        estimate_vol, min_sse = estimiate_bs_constant_vol(evalDate, calendar, daycounter,['认购'])
        estimated_vols.update({to_dt_date(evalDate):estimate_vol})
        print(estimate_vol)
    except Exception as e:
        print(e)
        continue

print('estimatied_vols = ',estimated_vols)
stop = timeit.default_timer()
print('calibration time : ',stop-start)

with open(os.path.abspath('..') +'/intermediate_data/total_hedging_bs_estimated_vols_call.pickle','wb') as f:
    pickle.dump([estimated_vols],f)


