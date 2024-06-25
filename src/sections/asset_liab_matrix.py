import asyncio
import heapq
import time
import os

from asyncio import AbstractEventLoop
import plotly.express as px  # type: ignore
import pandas as pd  # type: ignore

from typing import Any
import streamlit as st
from driftpy.drift_client import DriftClient
from driftpy.pickle.vat import Vat

from driftpy.constants.spot_markets import mainnet_spot_market_configs, devnet_spot_market_configs
from driftpy.constants.perp_markets import mainnet_perp_market_configs, devnet_perp_market_configs

from scenario import get_usermap_df


def asset_liab_matrix_page(loop: AbstractEventLoop, vat: Vat, drift_client: DriftClient, env='mainnet'):
    NUMBER_OF_SPOT = 18
    NUMBER_OF_PERP = 32

    oracle_distort = 0
    price_scenario_users, user_keys, distorted_oracles =  loop.run_until_complete(get_usermap_df(drift_client, vat.users,
                                                                'oracles', oracle_distort, 
                                                                None, 'ignore stables', n_scenarios=0, all_fields=True))
    
    df = pd.DataFrame(price_scenario_users[0], index=user_keys)

    
    perp_market_inspect = 0 # sol-perp
    def get_rattt(row):
        df1 = pd.Series([val/row['spot_asset'] * (row['perp_liability']+row['spot_liability']) 
                        if val > 0 else 0 for key,val in row['net_v'].items()]
                        )
        df1.index = ['spot_'+str(x)+'_all' for x in df1.index]

        df2 = pd.Series([val/(row['spot_asset']) * (row['perp_liability']) 
                        if val > 0 else 0 for key,val in row['net_v'].items()]
                        )
        df2.index = ['spot_'+str(x)+'_all_perp' for x in df2.index]

        df3 = pd.Series([val/(row['spot_asset']) * (row['spot_liability']) 
                        if val > 0 else 0 for key,val in row['net_v'].items()]
                        )
        df3.index = ['spot_'+str(x)+'_all_spot' for x in df3.index]
        
        df4 = pd.Series([val/(row['spot_asset']) * (row['net_p'][perp_market_inspect]) 
                        if val > 0 and row['net_p'][0] > 0 else 0 for key,val in row['net_v'].items()]
                        )
        df4.index = ['spot_'+str(x)+'_perp_'+str(perp_market_inspect)+'_long' for x in df4.index]

        df5 = pd.Series([val/(row['spot_asset']) * (row['net_p'][perp_market_inspect]) 
                        if val > 0 and row['net_p'][perp_market_inspect] < 0 else 0 for key,val in row['net_v'].items()]
                        )
        df5.index = ['spot_'+str(x)+'_perp_'+str(perp_market_inspect)+'_short' for x in df5.index]
        


        
        dffin = pd.concat([
            df1,
            df2,
            df3,
            df4,
            df5,
        ])
        return dffin
    df = pd.concat([df, df.apply(get_rattt, axis=1)],axis=1)
    res = pd.DataFrame({('spot'+str(i)): (df["spot_"+str(i)+'_all'].sum(), 
                                        df["spot_"+str(i)+'_all_spot'].sum(),
                                        df["spot_"+str(i)+'_all_perp'].sum() ,
                                        df["spot_"+str(i)+'_perp_'+str(perp_market_inspect)+'_long'].sum(),
                                        df["spot_"+str(i)+'_perp_'+str(perp_market_inspect)+'_short'].sum())
                                        for i in range(NUMBER_OF_SPOT)},
                                        
                    
                    index=['all_liabilities', 'all_spot', 'all_perp', 
                           'perp_'+str(perp_market_inspect)+'_long', 
                           'perp_'+str(perp_market_inspect)+'_short']).T

    if env == 'mainnet': #mainnet_spot_market_configs
        res.index = [x.symbol for x in mainnet_spot_market_configs]
        res.index.name = 'spot assets'

    matcol, detcol = st.columns(2)
    matcol.write(res)
    tabs = detcol.tabs(['FULL'] + [x.symbol for x in mainnet_spot_market_configs])

    tabs[0].dataframe(df)

    for idx, tab in enumerate(tabs[1:]):
        important_cols = [x for x in df.columns if 'spot_'+str(idx) in x]
        toshow = df[['spot_asset', 'net_usd_value']+important_cols]
        toshow = toshow[toshow[important_cols].abs().sum(axis=1)!=0].sort_values(by="spot_"+str(idx)+'_all', ascending=False)
        tab.write(f'{ len(toshow)} users with this asset to cover liabilities')
        tab.dataframe(toshow)

