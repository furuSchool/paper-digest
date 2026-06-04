from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import get_db
from models import Source, SourceInterest
from schemas import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead])
async def list_sources(db: AsyncSession = Depends(get_db)) -> list[Source]:
    result = await db.execute(select(Source).options(selectinload(Source.interests)).order_by(Source.id))
    return list(result.scalars().all())


@router.post("", response_model=SourceRead, status_code=201)
async def create_source(body: SourceCreate, db: AsyncSession = Depends(get_db)) -> Source:
    source = Source(**body.model_dump(exclude={"interests"}))
    db.add(source)
    await db.flush()

    for interest_data in body.interests:
        interest = SourceInterest(source_id=source.id, **interest_data.model_dump())
        db.add(interest)

    await db.commit()
    await db.refresh(source, attribute_names=["interests"])
    return source


@router.put("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: int, body: SourceUpdate, db: AsyncSession = Depends(get_db)
) -> Source:
    result = await db.execute(
        select(Source).options(selectinload(Source.interests)).where(Source.id == source_id)
    )
    source = result.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    for key, value in body.model_dump(exclude={"interests"}).items():
        setattr(source, key, value)

    # interests を差し替え
    interest_result = await db.execute(
        select(SourceInterest).where(SourceInterest.source_id == source_id)
    )
    for old in interest_result.scalars().all():
        await db.delete(old)

    for interest_data in body.interests:
        interest = SourceInterest(source_id=source_id, **interest_data.model_dump())
        db.add(interest)

    await db.commit()
    await db.refresh(source, attribute_names=["interests"])
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
