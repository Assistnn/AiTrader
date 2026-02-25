"""
Pipeline Logs API routes.
Reference: 08_API仕様 Section 3-12
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.pipeline_log import PipelineLog
from app.schemas.pipeline_log import PipelineLogItem, PipelineLogDetail

router = APIRouter(prefix="/api/v1/pipeline-logs", tags=["pipeline-logs"])


def _get_user_id() -> int:
    """簡易: 認証済みユーザーID取得."""
    return 1


@router.get("", response_model=list[PipelineLogItem])
async def list_pipeline_logs(
    trader_id: int | None = Query(None, alias="traderId"),
    pair: str | None = None,
    stage: str | None = None,
    date_from: str | None = Query(None, alias="dateFrom"),
    date_to: str | None = Query(None, alias="dateTo"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100, alias="perPage"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """パイプラインログ照会."""
    q = select(PipelineLog).where(PipelineLog.user_id == user_id)

    if trader_id is not None:
        q = q.where(PipelineLog.trader_id == trader_id)
    if pair is not None:
        q = q.where(PipelineLog.pair == pair)
    if stage is not None:
        q = q.where(PipelineLog.stage == stage)

    q = q.order_by(PipelineLog.timestamp.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(q)
    logs = result.scalars().all()

    return [
        PipelineLogItem(
            id=log.id,
            execution_id=log.execution_id,
            trader_id=log.trader_id,
            pair=log.pair,
            timestamp=log.timestamp,
            stage=log.stage,
            mode=log.mode,
            elapsed_ms=float(log.elapsed_ms) if log.elapsed_ms is not None else None,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/{execution_id}", response_model=list[PipelineLogDetail])
async def get_pipeline_log_detail(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """実行単位のログ詳細."""
    q = (
        select(PipelineLog)
        .where(PipelineLog.user_id == user_id)
        .where(PipelineLog.execution_id == execution_id)
        .order_by(PipelineLog.stage)
    )
    result = await db.execute(q)
    logs = result.scalars().all()

    if not logs:
        raise HTTPException(status_code=404, detail="Pipeline log not found")

    return [
        PipelineLogDetail(
            id=log.id,
            execution_id=log.execution_id,
            trader_id=log.trader_id,
            pair=log.pair,
            timestamp=log.timestamp,
            stage=log.stage,
            mode=log.mode,
            input_snapshot=log.input_snapshot,
            output_snapshot=log.output_snapshot,
            config_snapshot=log.config_snapshot,
            elapsed_ms=float(log.elapsed_ms) if log.elapsed_ms is not None else None,
            created_at=log.created_at,
        )
        for log in logs
    ]
