FROM freqtradeorg/freqtrade:develop_freqai

# develop_freqai already includes: XGBoost, LightGBM, datasieve
# Only install additional dependencies not in base image
RUN pip install --user pandas_ta scipy
