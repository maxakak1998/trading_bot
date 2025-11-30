FROM freqtradeorg/freqtrade:develop

# Install FreqAI dependencies
RUN pip install --user datasieve lightgbm xgboost
