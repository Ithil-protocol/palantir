from typing import List

from palantir.clock import Clock
from palantir.constants import (
    GAUSS_RANDOM_SLIPPAGE,
)
from palantir.db import Quote
from palantir.ithil import Ithil
from palantir.metrics import MetricsLogger
from palantir.oracle import PriceOracle
from palantir.types import (
    Account,
    Currency,
    Price,
)
from palantir.util import Percent


NO_FEES = lambda _: 0.0


NO_INTEREST = lambda _src_token, _dst_token, _collateral, _principal: 0.0


NO_SLIPPAGE = lambda price: price


def make_test_quotes_from_prices(prices: List[Price]) -> List[Quote]:
    return [
        Quote(id=0, coin='', vs_currency='usd', timestamp=0, price=price)
        for price in prices
    ]


def test_trade_zero_fees_zero_interest_with_profit():
    """
    Trader invests in DAI/WETH with a profit of 10%.
    Collateral of 100.0, leverage of x10.
    No fees and no interest.
    Position in closed with a profit.
    """
    DAI_INSURANCE_LIQUIDITY = 1000.0
    DAI_LIQUIDITY = 750000.0
    COLLATERAL = 100.0
    PRINCIPAL = 1000.0

    quotes = {
        Currency('dai'): make_test_quotes_from_prices(
            [1.0, 1.0]
        ),
        Currency('ethereum'): make_test_quotes_from_prices(
            [4000, 4000 + Percent(10).of(4000)]
        ),
    }
    periods = len(list(quotes.values())[0])
    clock = Clock(periods)
    metrics_logger = MetricsLogger(clock)
    ithil = Ithil(
        apply_slippage=NO_SLIPPAGE,
        calculate_fees=NO_FEES,
        calculate_interest_rate=NO_INTEREST,
        calculate_liquidation_fee=lambda _: 0.0,
        clock=clock,
        insurance_pool={
            Currency("dai"): DAI_INSURANCE_LIQUIDITY,
        },
        metrics_logger=metrics_logger,
        price_oracle=PriceOracle(
            clock=clock,
            quotes=quotes,
        ),
        split_fees=lambda fees: (0.0, fees),
        vaults={
            Currency('dai'): DAI_LIQUIDITY,
        },
    )

    position_id = ithil.open_position(
        trader=Account("0xabcd"),
        src_token=Currency("dai"),
        dst_token=Currency("ethereum"),
        collateral_token=Currency("dai"),
        collateral=COLLATERAL,
        principal=PRINCIPAL,
        max_slippage_percent=10,
    )

    assert position_id is not None
    assert position_id in ithil.positions, metrics_logger.metrics

    clock.step()

    assert ithil.can_liquidate_position(position_id) == False

    trader_pl, liquidation_pl = ithil.close_position(position_id)

    assert trader_pl == Percent(10).of(PRINCIPAL)
    assert liquidation_pl == 0.0
    assert ithil.vaults[Currency("dai")] == DAI_LIQUIDITY
    assert ithil.insurance_pool[Currency("dai")] == DAI_INSURANCE_LIQUIDITY


def test_trade_zero_fees_zero_interest_with_partial_loss():
    """
    Trader invests in DAI/WETH with a loss of 5%.
    Collateral of 100.0, leverage of x10.
    No fees and no interest.
    Position in closed with a loss fully covered by the collateral.
    """
    COLLATERAL = 100.0
    PRINCIPAL = 1000.0
    DAI_INSURANCE_LIQUIDITY = 1000.0
    DAI_LIQUIDITY = 750000.0

    quotes = {
        Currency("ethereum"): make_test_quotes_from_prices(
            [4400, 4400 - Percent(5).of(4400)]
        ),
        Currency("dai"): make_test_quotes_from_prices(
            [1.0, 1.0]
        )
    }
    periods = len(list(quotes.values())[0])
    clock = Clock(periods)
    metrics_logger = MetricsLogger(clock)
    ithil = Ithil(
        apply_slippage=NO_SLIPPAGE,
        calculate_fees=NO_FEES,
        calculate_interest_rate=NO_INTEREST,
        calculate_liquidation_fee=lambda _: 0.0,
        clock=clock,
        insurance_pool={
            Currency("dai"): DAI_INSURANCE_LIQUIDITY,
        },
        metrics_logger=metrics_logger,
        price_oracle=PriceOracle(
            clock=clock,
            quotes=quotes,
        ),
        split_fees=lambda fees: (0.0, fees),
        vaults={
            Currency("dai"): DAI_LIQUIDITY,
        },
    )

    position_id = ithil.open_position(
        trader=Account("0xabcd"),
        src_token=Currency("dai"),
        dst_token=Currency("ethereum"),
        collateral_token=Currency("dai"),
        collateral=COLLATERAL,
        principal=PRINCIPAL,
        max_slippage_percent=10,
    )

    assert position_id is not None
    assert position_id in ithil.active_positions

    clock.step()

    assert ithil.can_liquidate_position(position_id) == False

    trader_pl, liquidation_pl = ithil.close_position(position_id)

    assert trader_pl == -Percent(5).of(PRINCIPAL)
    assert liquidation_pl == 0.0
    assert ithil.vaults[Currency("dai")] == DAI_LIQUIDITY
    assert ithil.insurance_pool[Currency("dai")] == DAI_INSURANCE_LIQUIDITY


def test_trade_zero_fees_zero_interest_with_total_loss():
    """
    Trader invests in DAI/WETH with a loss of 120% of collateral.
    Collateral of 100.0, leverage of x10.
    No fees and no interest.
    Position in closed with a loss not fully covered by the collateral.
    LPs are compensated by the insurance pool.
    """
    DAI_INSURANCE_LIQUIDITY = 1000.0
    DAI_LIQUIDITY = 750000.0
    COLLATERAL = 100.0
    PRINCIPAL = 1000.0

    quotes = {
        Currency("dai"): make_test_quotes_from_prices([1.0, 1.0]),
        Currency("ethereum"): make_test_quotes_from_prices([4400, 4400 - Percent(12).of(4400)])
    }
    periods = len(list(quotes.values())[0])
    clock = Clock(periods)
    metrics_logger = MetricsLogger(clock)
    ithil = Ithil(
        apply_slippage=NO_SLIPPAGE,
        calculate_fees=NO_FEES,
        calculate_interest_rate=NO_INTEREST,
        calculate_liquidation_fee=lambda _: 0.0,
        clock=clock,
        insurance_pool={
            Currency("dai"): DAI_INSURANCE_LIQUIDITY,
        },
        metrics_logger=metrics_logger,
        price_oracle=PriceOracle(
            clock=clock,
            quotes=quotes,
        ),
        split_fees=lambda fees: (0.0, fees),
        vaults={
            Currency("dai"): DAI_LIQUIDITY,
        },
    )

    position_id = ithil.open_position(
        trader=Account("0xabcd"),
        src_token=Currency("dai"),
        dst_token=Currency("ethereum"),
        collateral_token=Currency("dai"),
        collateral=COLLATERAL,
        principal=PRINCIPAL,
        max_slippage_percent=10,
    )

    assert position_id is not None
    assert position_id in ithil.active_positions

    clock.step()

    assert ithil.can_liquidate_position(position_id) == True

    trader_pl, liquidation_pl = ithil.close_position(position_id)

    assert trader_pl == -COLLATERAL
    assert liquidation_pl == 0.0
    assert ithil.vaults[Currency("dai")] == DAI_LIQUIDITY

    loss = Percent(12).of(PRINCIPAL)
    assert ithil.insurance_pool[Currency("dai")] == DAI_INSURANCE_LIQUIDITY - (loss - COLLATERAL)


def test_trade_fees_zero_interest_with_profit():
    """
    Trader invests in DAI/WETH with a profit of 10%.
    Collateral of 100.0, leverage of x10.
    1% fees on collateral and no interest.
    Fees are split 50/50 between governance and insurance pool.
    Position in closed with a profit.
    """
    DAI_INSURANCE_LIQUIDITY = 1000.0
    DAI_LIQUIDITY = 750000.0
    COLLATERAL = 100.0
    PRINCIPAL = 1000.0

    quotes = {
        Currency('dai'): make_test_quotes_from_prices(
            [1.0, 1.0]
        ),
        Currency('ethereum'): make_test_quotes_from_prices(
            [4000, 4000 + Percent(10).of(4000)]
        ),
    }
    periods = len(list(quotes.values())[0])
    clock = Clock(periods)
    metrics_logger = MetricsLogger(clock)
    ithil = Ithil(
        apply_slippage=NO_SLIPPAGE,
        calculate_fees=lambda position: position.collateral / 100.0,
        calculate_interest_rate=NO_INTEREST,
        calculate_liquidation_fee=lambda _: 0.0,
        clock=clock,
        insurance_pool={
            Currency("dai"): DAI_INSURANCE_LIQUIDITY,
        },
        metrics_logger=metrics_logger,
        price_oracle=PriceOracle(
            clock=clock,
            quotes=quotes,
        ),
        split_fees=lambda fees: (fees / 2.0, fees / 2.0),
        vaults={
            Currency('dai'): DAI_LIQUIDITY,
        },
    )

    position_id = ithil.open_position(
        trader=Account("0xabcd"),
        src_token=Currency("dai"),
        dst_token=Currency("ethereum"),
        collateral_token=Currency("dai"),
        collateral=COLLATERAL,
        principal=PRINCIPAL,
        max_slippage_percent=10,
    )

    assert position_id is not None
    assert position_id in ithil.positions, metrics_logger.metrics

    position = ithil.active_positions[position_id]
    FEES = ithil.calculate_fees(position)
    GOVERNANCE_FEES, INSURANCE_FEES = ithil.split_fees(FEES)

    clock.step()

    assert ithil.can_liquidate_position(position_id) == False

    trader_pl, liquidation_pl = ithil.close_position(position_id)

    assert trader_pl == Percent(10).of(PRINCIPAL) - FEES
    assert liquidation_pl == 0.0
    assert ithil.vaults[Currency("dai")] == DAI_LIQUIDITY
    assert ithil.insurance_pool[Currency("dai")] == DAI_INSURANCE_LIQUIDITY + INSURANCE_FEES
    assert ithil.governance_pool[Currency("dai")] == GOVERNANCE_FEES


def test_trade_fees_zero_interest_with_total_loss_with_insurance_liquidity():
    """
    Trader invests in DAI/WETH with a loss of 120%.
    Collateral of 100.0, leverage of x10.
    Fees are split 50/50 between governance and insurance pool.
    Position is closed with a total loss, repaid by insurance.
    """
    DAI_INSURANCE_LIQUIDITY = 1000.0
    DAI_LIQUIDITY = 750000.0
    COLLATERAL = 100.0
    PRINCIPAL = 1000.0

    quotes = {
        Currency("dai"): make_test_quotes_from_prices([1.0, 1.0]),
        Currency("ethereum"): make_test_quotes_from_prices([4400, 4400 - Percent(12).of(4400)])
    }
    periods = len(list(quotes.values())[0])
    clock = Clock(periods)
    metrics_logger = MetricsLogger(clock)
    ithil = Ithil(
        apply_slippage=NO_SLIPPAGE,
        calculate_fees=lambda position: position.collateral / 100.0,
        calculate_interest_rate=NO_INTEREST,
        calculate_liquidation_fee=lambda _: 0.0,
        clock=clock,
        insurance_pool={
            Currency("dai"): DAI_INSURANCE_LIQUIDITY,
        },
        metrics_logger=metrics_logger,
        price_oracle=PriceOracle(
            clock=clock,
            quotes=quotes,
        ),
        split_fees=lambda fees: (fees / 2.0, fees / 2.0),
        vaults={
            Currency("dai"): DAI_LIQUIDITY,
        },
    )

    position_id = ithil.open_position(
        trader=Account("0xabcd"),
        src_token=Currency("dai"),
        dst_token=Currency("ethereum"),
        collateral_token=Currency("dai"),
        collateral=COLLATERAL,
        principal=PRINCIPAL,
        max_slippage_percent=10.0,
    )

    assert position_id is not None
    assert position_id in ithil.positions, metrics_logger.metrics

    clock.step()

    assert ithil.can_liquidate_position(position_id) == True

    trader_pl, liquidation_pl = ithil.close_position(position_id)

    assert trader_pl == -COLLATERAL
    assert liquidation_pl == 0.0
    assert ithil.vaults[Currency("dai")] == DAI_LIQUIDITY
    assert ithil.insurance_pool[Currency("dai")] == DAI_INSURANCE_LIQUIDITY - Percent(20).of(COLLATERAL)
    assert ithil.governance_pool[Currency("dai")] == 0.0 # We can't collect fees in case of total loss


def test_trade_zero_fees_interest_rate_with_profit():
    """
    Trader invests in DAI/WETH with a profit of 10%.
    Collateral of 100.0, leverage of x10.
    No fees and fixed annual interest rate of 3%.
    Position is closed with a profit.
    """
    DAI_INSURANCE_LIQUIDITY = 1000.0
    DAI_LIQUIDITY = 750000.0
    COLLATERAL = 100.0
    PRINCIPAL = 1000.0

    quotes = {
        Currency("dai"): make_test_quotes_from_prices([1.0, 1.0]),
        Currency("ethereum"): make_test_quotes_from_prices([4000, 4000 + Percent(10).of(4000)]),
    }
    periods = len(list(quotes.values())[0])
    clock = Clock(periods)
    metrics_logger = MetricsLogger(clock)
    ithil = Ithil(
        apply_slippage=NO_SLIPPAGE,
        calculate_fees=NO_FEES,
        calculate_interest_rate=lambda _src_token, _dst_token, _collateral, _principal: 0.03,
        calculate_liquidation_fee=lambda _: 0.0,
        clock=clock,
        insurance_pool={
            Currency("dai"): DAI_INSURANCE_LIQUIDITY,
        },
        metrics_logger=metrics_logger,
        price_oracle=PriceOracle(
            clock=clock,
            quotes=quotes,
        ),
        split_fees=lambda fees: (0.0, fees),
        vaults={
            Currency("dai"): DAI_LIQUIDITY,
        }
    )

    position_id = ithil.open_position(
        trader=Account("0xabcd"),
        src_token=Currency("dai"),
        dst_token=Currency("ethereum"),
        collateral_token=Currency("dai"),
        collateral=COLLATERAL,
        principal=PRINCIPAL,
        max_slippage_percent=10,
    )

    assert position_id is not None
    assert position_id in ithil.positions, metrics_logger.metrics

    position = ithil.active_positions[position_id]

    clock.step()

    INTEREST = ithil.calculate_interest(position)

    assert ithil.can_liquidate_position(position_id) == False

    trader_pl, liquidation_pl = ithil.close_position(position_id)

    assert trader_pl == Percent(10).of(PRINCIPAL) - INTEREST
    assert liquidation_pl == 0.0
    assert ithil.vaults[Currency("dai")] == DAI_LIQUIDITY + INTEREST
    assert ithil.insurance_pool[Currency("dai")] == DAI_INSURANCE_LIQUIDITY
    assert ithil.governance_pool[Currency("dai")] == 0.0 # No fees were distributed

def test_trade_zero_fees_zero_interest_with_loss_and_liquidation():
    """
    Trader invests in DAI/WETH with a loss of 80% of collateral.
    Collateral of 100.0, leverage of x10.
    No fees and no interest.
    Position in closed with a loss not fully covered by the collateral.
    LPs are compensated by the insurance pool.
    Liquidator in compensated by insurance pool.
    """
    DAI_INSURANCE_LIQUIDITY = 1000.0
    DAI_LIQUIDITY = 750000.0
    COLLATERAL = 100.0
    PRINCIPAL = 1000.0

    quotes = {
        Currency("dai"): make_test_quotes_from_prices([1.0, 1.0]),
        Currency("ethereum"): make_test_quotes_from_prices([4400, 4400 - Percent(8).of(4400)]),
    }
    periods = len(list(quotes.values())[0])
    clock = Clock(periods)
    metrics_logger = MetricsLogger(clock)
    ithil = Ithil(
        apply_slippage=NO_SLIPPAGE,
        calculate_fees=NO_FEES,
        calculate_interest_rate=NO_INTEREST,
        calculate_liquidation_fee=lambda _: 1.0,
        clock=clock,
        insurance_pool={
            Currency("dai"): DAI_INSURANCE_LIQUIDITY,
        },
        metrics_logger=metrics_logger,
        price_oracle=PriceOracle(
            clock=clock,
            quotes=quotes,
        ),
        split_fees=lambda fees: (0.0, fees),
        vaults={
            Currency("dai"): DAI_LIQUIDITY,
        },
    )

    position_id = ithil.open_position(
        trader=Account("0xabcd"),
        src_token=Currency("dai"),
        dst_token=Currency("ethereum"),
        collateral_token=Currency("dai"),
        collateral=COLLATERAL,
        principal=PRINCIPAL,
        max_slippage_percent=10,
    )

    assert position_id is not None
    assert position_id in ithil.active_positions

    clock.step()

    position = ithil.active_positions[position_id]
    LIQUIDATION_FEE = ithil.calculate_liquidation_fee(position)

    assert ithil.can_liquidate_position(position_id) == True

    trader_pl, liquidation_pl = ithil.liquidate_position(position_id)

    assert trader_pl == -(Percent(80).of(COLLATERAL) + LIQUIDATION_FEE)
    assert liquidation_pl == LIQUIDATION_FEE == 1.0
