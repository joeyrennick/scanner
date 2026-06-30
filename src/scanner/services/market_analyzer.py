from scanner.data.market_data import download_price_data
from scanner.indicators.atr import add_atr
from scanner.indicators.moving_averages import add_moving_averages
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.indicators.volume import add_volume_indicators
from scanner.models.market_data import MarketData
from scanner.models.stock_analysis import StockAnalysis
from scanner.scoring.score_engine import calculate_score_breakdown
import logging


class MarketAnalyzer:
    logger = logging.getLogger("scanner")
    def analyze(self, ticker: str, spy_return: float) -> StockAnalysis:
        self.logger.info(f"Downloading {ticker}")
        data = download_price_data(ticker)

        data = add_moving_averages(data)
        data = add_atr(data)
        data = add_volume_indicators(data)

        market_data = MarketData(ticker=ticker, history=data)

        rs = calculate_relative_strength(
            market_data.history,
            spy_return,
        )

        score_breakdown = calculate_score_breakdown(
            price=market_data.price,
            ma20=market_data.ma20,
            ma50=market_data.ma50,
            ma200=market_data.ma200,
            relative_strength=rs,
            relative_volume=market_data.relative_volume,
            atr14=market_data.atr14,
        )
        self.logger.info(f"Finished analyzing {ticker}")

        return StockAnalysis(
            ticker=market_data.ticker,
            price=market_data.price,
            ma20=market_data.ma20,
            ma50=market_data.ma50,
            ma200=market_data.ma200,
            relative_strength=rs,
            atr14=market_data.atr14,
            avg_volume_20=market_data.avg_volume_20,
            relative_volume=market_data.relative_volume,
            score_breakdown=score_breakdown,
        )