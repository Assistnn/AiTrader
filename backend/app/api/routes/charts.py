"""
Charts API routes.
Reference: 08_API仕様 Section 3-8
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.chart_config import ChartConfig
from app.models.trade_history import TradeHistory
from app.schemas.chart import (
    OhlcvItem,
    IndicatorDataResponse,
    MarkerItem,
    ChartConfigResponse,
    ChartConfigUpdateRequest,
)
from app.api.deps import get_current_user
from app.api.response import ok
from app.services.exchange.pair_normalizer import PairNormalizer
from app.services.pipeline.bitbank_data_provider import BitbankDataProvider
from app.services.pipeline.gmo_fx_data_provider import GmoFxDataProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/charts", tags=["charts"])


@router.get("/ohlcv")
async def get_ohlcv(
    pair: str = Query(...),
    timeframe: str = Query("H1"),
    limit: int = Query(200, ge=1, le=1000),
    user: User = Depends(get_current_user),
):
    """OHLCV データ取得（取引所公開APIから直接取得）. Reference: 08_API仕様 §3-8"""
    if PairNormalizer.is_crypto(pair):
        provider = BitbankDataProvider()
    elif PairNormalizer.is_fx(pair):
        provider = GmoFxDataProvider()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown pair: {pair}")

    try:
        bars = await provider.get_ohlcv(pair, timeframe, limit)
    except (ValueError, RuntimeError) as e:
        logger.warning("Failed to fetch OHLCV for %s %s: %s", pair, timeframe, e)
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        await provider.close()

    items = [
        OhlcvItem(
            t=bar.timestamp,
            o=bar.open,
            h=bar.high,
            l=bar.low,
            c=bar.close,
            v=bar.volume,
        )
        for bar in bars
    ]

    return ok(items)


@router.get("/indicators")
async def get_indicators(
    pair: str = Query(...),
    timeframe: str = Query("H1"),
    indicators: str = Query(""),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """指標データ取得 (stub: 実計算は将来実装)."""
    # Stub: return empty indicator data
    indicator_names = [n.strip() for n in indicators.split(",") if n.strip()]
    return ok([
        IndicatorDataResponse(name=name, values=[])
        for name in indicator_names
    ])


@router.get("/markers")
async def get_markers(
    pair: str = Query(...),
    timeframe: str = Query("H1"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """マーカー（売買サイン）取得."""
    q = (
        select(TradeHistory)
        .where(TradeHistory.user_id == user.id, TradeHistory.pair == pair)
        .order_by(TradeHistory.opened_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    trades = result.scalars().all()

    markers: list[MarkerItem] = []
    for t in trades:
        if t.opened_at:
            markers.append(MarkerItem(
                timestamp=t.opened_at,
                type="entry",
                side=t.side,
                price=float(t.entry_price) if t.entry_price else None,
                label=f"{t.side} entry",
            ))
        if t.closed_at:
            markers.append(MarkerItem(
                timestamp=t.closed_at,
                type="exit",
                side=t.side,
                price=float(t.exit_price) if t.exit_price else None,
                label=t.exit_reason,
            ))

    return ok(markers)


@router.get("/config")
async def get_chart_config(
    pair: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """チャート設定取得."""
    q = select(ChartConfig).where(
        ChartConfig.user_id == user.id,
        ChartConfig.pair == pair,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(status_code=404, detail="Chart config not found")

    return ok(ChartConfigResponse(
        id=config.id,
        pair=config.pair,
        timeframe=config.timeframe,
        indicators=config.indicators,
        chart_type=config.chart_type,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


@router.put("/config")
async def update_chart_config(
    req: ChartConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """チャート設定更新."""
    q = select(ChartConfig).where(
        ChartConfig.user_id == user.id,
        ChartConfig.pair == req.pair,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        config = ChartConfig(
            user_id=user.id,
            pair=req.pair,
            timeframe=req.timeframe or "H1",
            indicators=req.indicators or [],
            chart_type=req.chart_type or "candlestick",
        )
        db.add(config)
    else:
        update_data = req.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field != "pair":
                setattr(config, field, value)

    await db.flush()
    await db.commit()

    return ok(ChartConfigResponse(
        id=config.id,
        pair=config.pair,
        timeframe=config.timeframe,
        indicators=config.indicators,
        chart_type=config.chart_type,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))
