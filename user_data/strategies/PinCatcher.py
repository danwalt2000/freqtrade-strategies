# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class PinCatcher(IStrategy):

    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # adjust based on market conditions. We would recommend to keep it low for quick turn arounds
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {
        "0": 0.1
    }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.25

    # Optimal timeframe for the strategy
    timeframe = '1h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macd_diff'] = dataframe['macd'] / dataframe['close'] * 100
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        stoch_fast = ta.STOCHF(dataframe)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']

        dataframe['sma7'] = ta.SMA(dataframe, timeperiod=7)
        dataframe['sma10'] = ta.SMA(dataframe, timeperiod=10)
        dataframe['sma21'] = ta.SMA(dataframe, timeperiod=21)
        dataframe['sma50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma100'] = ta.SMA(dataframe, timeperiod=100)
        dataframe['sma200'] = ta.SMA(dataframe, timeperiod=200)

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=25)
        dataframe['rsi100'] = ta.RSI(dataframe, timeperiod=100)

        # required for graphing
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=12, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        dataframe['sar'] = ta.SAR(dataframe)
        dataframe["diff"] =  dataframe["close"] - dataframe["sar"]
        dataframe["diff_bool"] = dataframe["diff"] > 0
        dataframe["positive_trend_periods"] = dataframe["diff_bool"].tail(25).sum()
        dataframe["down_direction"] = (dataframe["diff"].rolling(2).sum() / 2) < 0
        dataframe["up_direction"] = (dataframe["diff"].rolling(2).sum() / 2) > 0
        dataframe["up_far"] = (dataframe["diff"].rolling(20).min()) > 0
        dataframe["sar_alpha"] = (dataframe["sar"] / dataframe["sar"].shift(1) - 1) * 100 
        dataframe["max_sar_alpha"] = dataframe["sar_alpha"].rolling(10).max()
        dataframe["min_sar_alpha"] = dataframe["sar_alpha"].rolling(10).min()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    (
                        (dataframe['macd'] < 0) & 
                        (dataframe['macd'] > dataframe['macd'].shift(1)) & 
                        (dataframe['rsi100'] < 50) &
                        (dataframe['close'] < dataframe["sma10"]) &
                        (dataframe["sma100"] < dataframe["sma200"]) &
                        dataframe["down_direction"]
                    ) 
                    | 
                    (
                        (dataframe["min_sar_alpha"] < -3) & 
                        (dataframe['macd'] > dataframe['macd'].shift(1)) & 
                        (dataframe['close'] < dataframe["sma10"]) &
                        (dataframe["sma100"] < dataframe["sma200"])

                    )
                )
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # different strategy used for sell points, due to be able to duplicate it to 100%
        dataframe.loc[
            (
                (dataframe['macd_diff'] > 1) & (dataframe['macd'] < dataframe['macd'].shift(1)) & (dataframe["sma100"] > dataframe["sma100"].shift(1)) 
                |
                (dataframe["up_far"]) & (dataframe['macd'] < dataframe['macd'].shift(1)) & (dataframe["sma100"] > dataframe["sma100"].shift(1)) 
                |
                (
                    (dataframe["up_far"]) &
                    (dataframe["max_sar_alpha"] > 0.5) &
                    (dataframe["rsi100"] > 55) & 
                    (dataframe['macd'] < dataframe['macd'].shift(1)) & 
                    (dataframe["sma100"] > dataframe["sma100"].shift(1))
                ) 
                | 
                (
                    (dataframe["positive_trend_periods"] > 20) &
                    (dataframe["max_sar_alpha"] > 3) &
                    (dataframe['macd'] < dataframe['macd'].shift(1)) 
                )
            ),
            'exit_long'] = 1
        return dataframe
