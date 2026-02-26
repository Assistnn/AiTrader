"""
Seed test data for dynamic testing.

Usage:
    cd backend && python -m scripts.seed_testdata

Creates:
    - 1 user: test@example.com / TestPass1!
    - 3 traders: FX×2 (USD/JPY, EUR/JPY), Crypto×1 (BTC/JPY)
    - 10 trade history records
    - 10 pipeline log records
    - 3 config change records
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory, engine
from app.models.config_change import ConfigChange
from app.models.pipeline_log import PipelineLog
from app.models.trade_history import TradeHistory
from app.models.trader import Trader
from app.models.user import User
from app.services.auth.password import hash_password

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NOW = datetime.utcnow()
USER_EMAIL = "test@example.com"
USER_PASSWORD = "12345678"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ts(days_ago: int = 0, hours_ago: int = 0) -> datetime:
    return NOW - timedelta(days=days_ago, hours=hours_ago)


def _exec_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------
async def seed_user(session: AsyncSession) -> User:
    """Create or fetch the test user."""
    result = await session.execute(select(User).where(User.email == USER_EMAIL))
    user = result.scalar_one_or_none()
    if user:
        print(f"  User already exists: id={user.id}, email={user.email}")
        return user

    user = User(
        email=USER_EMAIL,
        password_hash=hash_password(USER_PASSWORD),
        display_name="テストユーザー",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    print(f"  Created user: id={user.id}, email={user.email}")
    return user


async def seed_traders(session: AsyncSession, user_id: int) -> list[Trader]:
    """Create 3 traders: 2 FX + 1 Crypto."""
    result = await session.execute(
        select(Trader).where(Trader.user_id == user_id)
    )
    existing = result.scalars().all()
    if existing:
        print(f"  Traders already exist: {len(existing)} traders")
        return list(existing)

    traders_data = [
        {
            "trader_name": "FX-USD-001",
            "trade_type": "FX",
            "symbols": ["USD_JPY"],
            "capital_jpy": Decimal("1000000"),
            "order_unit_lots": Decimal("1.0"),
            "strategy_text": "USD/JPY trend following strategy",
            "status": "running",
            "is_active": True,
        },
        {
            "trader_name": "FX-EUR-002",
            "trade_type": "FX",
            "symbols": ["EUR_JPY"],
            "capital_jpy": Decimal("500000"),
            "order_unit_lots": Decimal("0.5"),
            "strategy_text": "EUR/JPY range breakout strategy",
            "status": "stopped",
            "is_active": False,
        },
        {
            "trader_name": "CRYPTO-BTC-001",
            "trade_type": "crypto",
            "symbols": ["BTC_JPY"],
            "capital_jpy": Decimal("300000"),
            "order_unit_lots": Decimal("0.001"),
            "strategy_text": "BTC/JPY momentum strategy",
            "status": "running",
            "is_active": True,
        },
    ]

    traders = []
    for td in traders_data:
        t = Trader(user_id=user_id, **td)
        session.add(t)
        traders.append(t)
    await session.flush()

    for t in traders:
        print(f"  Created trader: id={t.id}, name={t.trader_name}")
    return traders


async def seed_trade_history(
    session: AsyncSession, user_id: int, traders: list[Trader]
) -> list[TradeHistory]:
    """Create 10 trade history records across traders."""
    result = await session.execute(
        select(TradeHistory).where(TradeHistory.user_id == user_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("  Trade history already exists, skipping")
        return []

    trades_data = [
        # Trader 0 (FX-USD): 4 trades
        {
            "trader_id": 0, "pair": "USD_JPY", "side": "BUY",
            "amount": Decimal("10000"), "entry_price": Decimal("149.500"),
            "exit_price": Decimal("150.200"), "realized_pnl": Decimal("7000"),
            "realized_pnl_pips": Decimal("70.0"), "rr_ratio": Decimal("2.33"),
            "tp_pips": Decimal("100.0"), "sl_pips": Decimal("30.0"),
            "exit_reason": "tp_hit",
            "opened_at": _ts(days_ago=5, hours_ago=10),
            "closed_at": _ts(days_ago=5, hours_ago=2),
            "hold_duration_min": 480,
        },
        {
            "trader_id": 0, "pair": "USD_JPY", "side": "SELL",
            "amount": Decimal("10000"), "entry_price": Decimal("150.800"),
            "exit_price": Decimal("150.200"), "realized_pnl": Decimal("6000"),
            "realized_pnl_pips": Decimal("60.0"), "rr_ratio": Decimal("2.0"),
            "tp_pips": Decimal("80.0"), "sl_pips": Decimal("30.0"),
            "exit_reason": "tp_hit",
            "opened_at": _ts(days_ago=4, hours_ago=8),
            "closed_at": _ts(days_ago=4, hours_ago=1),
            "hold_duration_min": 420,
        },
        {
            "trader_id": 0, "pair": "USD_JPY", "side": "BUY",
            "amount": Decimal("10000"), "entry_price": Decimal("150.000"),
            "exit_price": Decimal("149.700"), "realized_pnl": Decimal("-3000"),
            "realized_pnl_pips": Decimal("-30.0"), "rr_ratio": Decimal("-1.0"),
            "tp_pips": Decimal("60.0"), "sl_pips": Decimal("30.0"),
            "exit_reason": "sl_hit",
            "opened_at": _ts(days_ago=2, hours_ago=6),
            "closed_at": _ts(days_ago=2, hours_ago=4),
            "hold_duration_min": 120,
        },
        {
            "trader_id": 0, "pair": "USD_JPY", "side": "BUY",
            "amount": Decimal("10000"), "entry_price": Decimal("149.800"),
            "exit_price": None, "realized_pnl": None,
            "opened_at": _ts(hours_ago=3), "closed_at": None,
        },
        # Trader 1 (FX-EUR): 3 trades
        {
            "trader_id": 1, "pair": "EUR_JPY", "side": "BUY",
            "amount": Decimal("5000"), "entry_price": Decimal("162.300"),
            "exit_price": Decimal("162.900"), "realized_pnl": Decimal("3000"),
            "realized_pnl_pips": Decimal("60.0"), "rr_ratio": Decimal("1.5"),
            "tp_pips": Decimal("80.0"), "sl_pips": Decimal("40.0"),
            "exit_reason": "tp_hit",
            "opened_at": _ts(days_ago=3, hours_ago=10),
            "closed_at": _ts(days_ago=3, hours_ago=4),
            "hold_duration_min": 360,
        },
        {
            "trader_id": 1, "pair": "EUR_JPY", "side": "SELL",
            "amount": Decimal("5000"), "entry_price": Decimal("163.000"),
            "exit_price": Decimal("163.500"), "realized_pnl": Decimal("-2500"),
            "realized_pnl_pips": Decimal("-50.0"), "rr_ratio": Decimal("-1.25"),
            "tp_pips": Decimal("80.0"), "sl_pips": Decimal("40.0"),
            "exit_reason": "sl_hit",
            "opened_at": _ts(days_ago=1, hours_ago=8),
            "closed_at": _ts(days_ago=1, hours_ago=6),
            "hold_duration_min": 120,
        },
        {
            "trader_id": 1, "pair": "EUR_JPY", "side": "BUY",
            "amount": Decimal("5000"), "entry_price": Decimal("162.500"),
            "exit_price": Decimal("163.100"), "realized_pnl": Decimal("3000"),
            "realized_pnl_pips": Decimal("60.0"), "rr_ratio": Decimal("2.0"),
            "tp_pips": Decimal("60.0"), "sl_pips": Decimal("30.0"),
            "exit_reason": "tp_hit",
            "opened_at": _ts(days_ago=1, hours_ago=3),
            "closed_at": _ts(days_ago=1),
            "hold_duration_min": 180,
        },
        # Trader 2 (CRYPTO-BTC): 3 trades
        {
            "trader_id": 2, "pair": "BTC_JPY", "side": "BUY",
            "amount": Decimal("0.01"), "entry_price": Decimal("6500000"),
            "exit_price": Decimal("6650000"), "realized_pnl": Decimal("1500"),
            "realized_pnl_pips": Decimal("15000"), "rr_ratio": Decimal("1.5"),
            "exit_reason": "tp_hit",
            "opened_at": _ts(days_ago=4, hours_ago=12),
            "closed_at": _ts(days_ago=4, hours_ago=2),
            "hold_duration_min": 600,
        },
        {
            "trader_id": 2, "pair": "BTC_JPY", "side": "SELL",
            "amount": Decimal("0.005"), "entry_price": Decimal("6700000"),
            "exit_price": Decimal("6750000"), "realized_pnl": Decimal("-250"),
            "realized_pnl_pips": Decimal("-5000"), "rr_ratio": Decimal("-0.5"),
            "exit_reason": "sl_hit",
            "opened_at": _ts(days_ago=2, hours_ago=10),
            "closed_at": _ts(days_ago=2, hours_ago=8),
            "hold_duration_min": 120,
        },
        {
            "trader_id": 2, "pair": "BTC_JPY", "side": "BUY",
            "amount": Decimal("0.008"), "entry_price": Decimal("6600000"),
            "exit_price": Decimal("6800000"), "realized_pnl": Decimal("1600"),
            "realized_pnl_pips": Decimal("20000"), "rr_ratio": Decimal("2.0"),
            "exit_reason": "tp_hit",
            "opened_at": _ts(days_ago=1, hours_ago=15),
            "closed_at": _ts(hours_ago=5),
            "hold_duration_min": 600,
        },
    ]

    records = []
    for td in trades_data:
        trader_idx = td.pop("trader_id")
        exec_id = _exec_id()
        th = TradeHistory(
            user_id=user_id,
            trader_id=traders[trader_idx].id,
            execution_id=exec_id,
            **td,
        )
        session.add(th)
        records.append((th, exec_id, trader_idx))
    await session.flush()
    print(f"  Created {len(records)} trade history records")
    return records


async def seed_pipeline_logs(
    session: AsyncSession,
    user_id: int,
    traders: list[Trader],
    trade_records: list,
) -> None:
    """Create pipeline logs for each closed trade (m1-m4 stages)."""
    result = await session.execute(
        select(PipelineLog).where(PipelineLog.user_id == user_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("  Pipeline logs already exist, skipping")
        return

    stages = ["m1", "m2", "m3", "m4"]
    count = 0

    for th, exec_id, trader_idx in trade_records:
        if th.closed_at is None:
            continue  # skip open position

        for i, stage in enumerate(stages):
            log = PipelineLog(
                user_id=user_id,
                execution_id=exec_id,
                trader_id=traders[trader_idx].id,
                pair=th.pair,
                timestamp=th.opened_at + timedelta(seconds=i * 2),
                stage=stage,
                mode="rule",
                input_snapshot=_make_input_snapshot(stage, th),
                output_snapshot=_make_output_snapshot(stage, th),
                config_snapshot={"mode": "rule", "timeframe": "M15"},
                elapsed_ms=Decimal(str(round(50 + i * 30, 2))),
            )
            session.add(log)
            count += 1

    await session.flush()
    print(f"  Created {count} pipeline log records")


def _make_input_snapshot(stage: str, trade: TradeHistory) -> dict:
    base = {"pair": trade.pair, "side": trade.side}
    if stage == "m1":
        return {**base, "type": "direction_analysis", "timeframes": ["H4", "H1"]}
    if stage == "m2":
        return {**base, "type": "setup_check", "m1_result": "UP"}
    if stage == "m3":
        return {**base, "type": "entry_signal", "entry_price": str(trade.entry_price)}
    return {**base, "type": "exit_management", "current_price": str(trade.exit_price or trade.entry_price)}


def _make_output_snapshot(stage: str, trade: TradeHistory) -> dict:
    if stage == "m1":
        direction = "UP" if trade.side == "BUY" else "DOWN"
        return {"direction": direction, "confidence": 0.82, "reason_codes": ["trend_aligned"]}
    if stage == "m2":
        return {"setup_valid": True, "confidence": 0.75, "reason_codes": ["pullback_complete"]}
    if stage == "m3":
        return {
            "action": "ENTRY",
            "price": str(trade.entry_price),
            "confidence": 0.78,
            "reason_codes": ["signal_confirmed"],
        }
    pnl = float(trade.realized_pnl) if trade.realized_pnl else 0
    return {
        "action": trade.exit_reason or "unknown",
        "pnl": pnl,
        "reason_codes": [trade.exit_reason or "manual"],
    }


async def seed_config_changes(
    session: AsyncSession, user_id: int, traders: list[Trader]
) -> None:
    """Create 3 config change records."""
    result = await session.execute(
        select(ConfigChange).where(ConfigChange.user_id == user_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("  Config changes already exist, skipping")
        return

    changes = [
        ConfigChange(
            user_id=user_id,
            trader_id=traders[0].id,
            config_type="model_stage",
            stage="m1",
            config_before={"mode": "rule", "timeframe": "H1"},
            config_after={"mode": "aiAssist", "timeframe": "H1"},
            changed_by=user_id,
            change_reason="M1をAIアシストモードに変更",
            changed_at=_ts(days_ago=3),
        ),
        ConfigChange(
            user_id=user_id,
            trader_id=traders[0].id,
            config_type="trader",
            stage=None,
            config_before={"order_unit_lots": "0.5"},
            config_after={"order_unit_lots": "1.0"},
            changed_by=user_id,
            change_reason="ロットサイズを増加",
            changed_at=_ts(days_ago=2),
        ),
        ConfigChange(
            user_id=user_id,
            trader_id=traders[2].id,
            config_type="safeguard",
            stage=None,
            config_before={"daily_loss_limit_pct": 3.0},
            config_after={"daily_loss_limit_pct": 5.0},
            changed_by=user_id,
            change_reason="日次損失上限を緩和",
            changed_at=_ts(days_ago=1),
        ),
    ]

    for c in changes:
        session.add(c)
    await session.flush()
    print(f"  Created {len(changes)} config change records")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    print("=== Seed Test Data ===")
    async with async_session_factory() as session:
        try:
            user = await seed_user(session)
            traders = await seed_traders(session, user.id)
            trade_records = await seed_trade_history(session, user.id, traders)
            await seed_pipeline_logs(session, user.id, traders, trade_records)
            await seed_config_changes(session, user.id, traders)
            await session.commit()
            print("=== Done! All test data seeded successfully. ===")
        except Exception as e:
            await session.rollback()
            print(f"ERROR: {e}")
            raise
        finally:
            await session.close()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
