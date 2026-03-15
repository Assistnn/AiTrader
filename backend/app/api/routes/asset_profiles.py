"""
Asset Profiles API routes.
Reference: 07_データベーススキーマ — asset_profiles (監査対応)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.asset_profile import AssetProfile
from app.models.user import User
from app.api.deps import get_current_user
from app.api.response import ok

router = APIRouter(prefix="/api/v1/asset-profiles", tags=["asset-profiles"])


class AssetProfileItem(BaseModel):
    id: int
    pair: str
    asset_type: str = Field(alias="assetType")
    pip_size: float = Field(alias="pipSize")
    pip_digits: int = Field(alias="pipDigits")
    pip_value_per_lot: float = Field(alias="pipValuePerLot")
    default_min_lot: float = Field(alias="defaultMinLot")
    default_max_lot: float = Field(alias="defaultMaxLot")
    default_tp_multiplier: float = Field(alias="defaultTpMultiplier")
    default_sl_multiplier: float = Field(alias="defaultSlMultiplier")

    model_config = {"populate_by_name": True}


class AssetProfileCreateRequest(BaseModel):
    pair: str
    asset_type: str = Field(alias="assetType")
    pip_size: float = Field(alias="pipSize")
    pip_digits: int = Field(alias="pipDigits")
    pip_value_per_lot: float = Field(alias="pipValuePerLot")
    default_min_lot: float = Field(default=0.01, alias="defaultMinLot")
    default_max_lot: float = Field(default=100.0, alias="defaultMaxLot")
    default_tp_multiplier: float = Field(default=1.5, alias="defaultTpMultiplier")
    default_sl_multiplier: float = Field(default=1.0, alias="defaultSlMultiplier")

    model_config = {"populate_by_name": True}


@router.get("")
async def list_asset_profiles(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全アセットプロファイル一覧."""
    q = select(AssetProfile).order_by(AssetProfile.asset_type, AssetProfile.pair)
    result = await db.execute(q)
    profiles = result.scalars().all()

    return ok([
        AssetProfileItem(
            id=p.id,
            pair=p.pair,
            assetType=p.asset_type,
            pipSize=float(p.pip_size),
            pipDigits=p.pip_digits,
            pipValuePerLot=float(p.pip_value_per_lot),
            defaultMinLot=float(p.default_min_lot),
            defaultMaxLot=float(p.default_max_lot),
            defaultTpMultiplier=float(p.default_tp_multiplier),
            defaultSlMultiplier=float(p.default_sl_multiplier),
        )
        for p in profiles
    ])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_asset_profile(
    req: AssetProfileCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """アセットプロファイル追加（新通貨ペア対応）."""
    existing = await db.execute(
        select(AssetProfile).where(AssetProfile.pair == req.pair)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset profile for pair '{req.pair}' already exists",
        )

    profile = AssetProfile(
        pair=req.pair,
        asset_type=req.asset_type,
        pip_size=req.pip_size,
        pip_digits=req.pip_digits,
        pip_value_per_lot=req.pip_value_per_lot,
        default_min_lot=req.default_min_lot,
        default_max_lot=req.default_max_lot,
        default_tp_multiplier=req.default_tp_multiplier,
        default_sl_multiplier=req.default_sl_multiplier,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # Reload PriceNormalizer cache
    from app.services.exchange.price_normalizer import PriceNormalizer
    await PriceNormalizer.load_from_db()

    return ok(AssetProfileItem(
        id=profile.id,
        pair=profile.pair,
        assetType=profile.asset_type,
        pipSize=float(profile.pip_size),
        pipDigits=profile.pip_digits,
        pipValuePerLot=float(profile.pip_value_per_lot),
        defaultMinLot=float(profile.default_min_lot),
        defaultMaxLot=float(profile.default_max_lot),
        defaultTpMultiplier=float(profile.default_tp_multiplier),
        defaultSlMultiplier=float(profile.default_sl_multiplier),
    ))
