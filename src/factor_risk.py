import pandas as pd
import os
from sklearn.decomposition import PCA 
from sklearn.preprocessing import StandardScaler
    
stonks = [
          'COIN',
          'SQ',
          'PYPL',
          'NVDA',
          'AMD',
          'HOOD',
          'GME',
          'CME',
         ]
futs = ['ES=F',
          'NQ=F',
          'RTY=F',
          'GC=F',
          'CL=F',
          '2YY=F',
          'ZN=F',]

crypto_coin_tickers = [
    #majors
    "BTC-USD",
    "ETH-USD",
    "BNB-USD",
    "SOL-USD",
    
    #dino
    "ADA-USD",
    "LTC-USD",
    "BCH-USD",
    "XRP-USD",
    "XLM-USD",
    
    #eth defi
    'UNI7083-USD',
    'AAVE-USD',
    'CRV-USD',
    'DYDX-USD',
    'ETHDYDX-USD',
        
    #solana projs
    "JUP29210-USD",
    "JTO-USD",
    "TNSR-USD",
    "DRIFT31278-USD",
    "KMNO-USD",
    "ORCA-USD",
    "RAY-USD",
    "FIDA-USD",
    "SBR-USD",
    
    #memes
    "DOGE-USD",
    "SHIB-USD",
    "MOTHER-USD",
    "WIF-USD",
    "BONK-USD",
    "PEPE24478-USD",
]

def data_capture():
    time_periods = ['daily', 'intra']
    tickers_dict = {
            'stonks': stonks, 
            'futures': futs,
            'crypto': crypto_coin_tickers
            }

    dfs = {tp: {} for tp in time_periods}

    fold = 'crypto_historical_data'
    assert(os.path.exists(fold))
    for nom, tickers_list in tickers_dict.items():
        for tp in time_periods:
            
            ff = fold+'/'+tp+'_'+nom+'_20240623.csv'
            hist_df = None

            if os.path.exists(ff):
                hist_df = pd.read_csv(ff, header=[0,1,2], index_col=[0])
                hist_df = hist_df.droplevel(2, axis=1)
            else:
                if tp == 'intra':
                    hist_df = yf.download(tickers_list, interval='1m')
                    hist_df.to_csv(ff)
                else:
                    hist_df = yf.download(tickers_list)
                    hist_df.to_csv(ff)
            
            dfs[tp][nom] = hist_df
    # intra_hist_df = dfs['intra']['crypto']
    # intra_hist_df.index = pd.to_datetime(intra_hist_df.index)
    #(intra_hist_df['Adj Close'].ffill().pct_change()+1).cumprod().resample('5min').last()
    # data = dfs['daily']['crypto']['Adj Close'].clip(1e-6,1e9).pct_change().clip(-.1, .1).iloc[1:]


def build_factor_model(data):


    # Define rolling window size (e.g., 250 days for a yearly window in trading days)
    max_window_size = 180
    min_valid_count = 5  # Minimum valid non-NaN points required to perform PCA
    pca_components = 5

    # Standardize data within each window
    def standardize(data_window):
        scaler = StandardScaler()
        standardized_data = scaler.fit_transform(data_window)
        # print(res)
        return pd.DataFrame(standardized_data, index=data_window.index, columns=data_window.columns), scaler

    # Store results
    pca_results = []

    # Rolling window PCA with best-effort approach
    for end_idx in range(max_window_size, len(data)):
        start_idx = max(0, end_idx - max_window_size)
        window_data = data.iloc[start_idx:end_idx]
        
        # Remove columns with too few valid data points
        valid_data = window_data.dropna(axis=1, thresh=min_valid_count)
        
        # If valid_data is empty or has insufficient columns, skip PCA
        if valid_data.shape[1] < 2:
            continue
        # print(valid_data)
        # Standardize data
        standardized_data, scaler = standardize(valid_data)
        
    
        # Impute missing values with column mean
        valid_data_imputed = valid_data.fillna(valid_data.mean())

        # Standardize data
        standardized_data, scaler = standardize(valid_data_imputed)
        
        # Perform PCA
        pca = PCA(n_components=min(valid_data_imputed.shape[1], pca_components))
        pca.fit(standardized_data)
        # print('explained', sum(pca.explained_variance_ratio_))
        
        # Transform the next available data point (immediately after the current window)
        if end_idx < len(data):
            next_point = data.iloc[end_idx]
            next_point_valid = next_point[valid_data_imputed.columns]
            
            # Impute missing values in the next data point
            next_point_imputed = next_point_valid.fillna(valid_data.mean())
            
            if next_point_imputed.isna().sum() == 0:  # Proceed if the next point has no NaNs in the valid columns
                next_point_standardized = scaler.transform(next_point_imputed.values.reshape(1, -1))
                pca_result = pca.transform(next_point_standardized)
                pca_results.append((data.index[end_idx], pca_result[0]))
            else:
                pca_results.append((data.index[end_idx], [np.nan] * pca.n_components_))
        
    # Convert results to a DataFrame for analysis
    pca_results_df = pd.DataFrame([x[1] for x in pca_results],
                                index=[x[0] for x in pca_results],
                                columns=[f'PC{i+1}' for i in range(pca.n_components_)])

    # print(pca_results_df.head())
    return pca_results_df


def plot_resid_returns(data, pca_results_df):
    res_rets = {}

    # Choose a single asset
    for asset_name in data.columns:
        if asset_name not in data.columns:
            raise ValueError(f"{asset_name} not found in the dataset.")

        # Isolate and align the returns of the single asset
        asset_returns = data[asset_name].dropna()
        common_dates = pca_results_df.index.intersection(asset_returns.index)
        asset_returns_aligned = asset_returns.loc[common_dates]
        pca_factors_aligned = pca_results_df.loc[common_dates]

        # Standardize the asset returns
        scaler = StandardScaler()
        asset_returns_standardized = scaler.fit_transform(asset_returns_aligned.values.reshape(-1, 1)).flatten()

        # Get the PCA factors from the DataFrame
        pca_factors = pca_factors_aligned.values
        try:
            # Compute the pseudo-inverse of the PCA factors
            pca_factors_pinv = np.linalg.pinv(pca_factors)

            # Project the standardized returns onto the PCA factors
            asset_pca_scores = np.dot(asset_returns_standardized.reshape(1, -1), pca_factors_pinv.T)

            # Reconstruct the returns from PCA factors
            reconstructed_returns_standardized = np.dot(asset_pca_scores, pca_factors.T)

            # Calculate residuals
            residuals_standardized = asset_returns_standardized - reconstructed_returns_standardized.flatten()

            # Inverse transform the residuals to the original scale
            residuals_original_scale = scaler.inverse_transform(residuals_standardized.reshape(-1, 1)).flatten()

            # Create a DataFrame for better readability
            residuals_df = pd.DataFrame(residuals_original_scale, index=common_dates, columns=['Residuals'])
            res_rets[asset_name] = residuals_df['Residuals']
        except:
            pass
        
        

    pd.concat(res_rets,axis=1).clip(-1,1).cumsum().plot()