import anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import ai, models, schemas
from app.database import get_db

router = APIRouter(prefix="/api", tags=["searches"])


def _build_search_context(search: models.Search) -> str:
    lines = [
        f"Water body: {search.water_body_normalized or search.water_body}",
        f"Target species: {search.species}",
        f"Season: {search.season}",
        f"Summary: {search.summary or 'n/a'}",
        f"Best conditions: {search.best_conditions or 'n/a'}",
        "Recommended gear:",
    ]
    for g in search.gear_items:
        lines.append(f"  - [{g.category}] {g.name}" + (f" — {g.notes}" if g.notes else ""))
    lines.append("Techniques:")
    for t in search.techniques:
        lines.append(f"  - {t.title}: {t.description}")
    return "\n".join(lines)


def _handle_ai_errors(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except anthropic.APIStatusError as e:
        raise HTTPException(
            status_code=502, detail=f"Claude API error ({e.status_code}): {e.message}"
        )
    except anthropic.APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the Claude API: {e}")


@router.post("/waterbodies/lookup", response_model=schemas.WaterBodyLookupResponse)
def lookup_water_body(payload: schemas.WaterBodyLookupRequest):
    result = _handle_ai_errors(ai.lookup_water_body, payload.water_body)
    return schemas.WaterBodyLookupResponse(
        water_body_normalized=result["water_body_normalized"],
        species=result["species"],
    )


@router.post("/searches", response_model=schemas.SearchDetail)
def create_search(payload: schemas.SearchCreate, db: Session = Depends(get_db)):
    tips = _handle_ai_errors(
        ai.generate_fishing_tips,
        payload.water_body_normalized or payload.water_body,
        payload.species,
        payload.season,
    )

    search = models.Search(
        water_body=payload.water_body,
        water_body_normalized=payload.water_body_normalized,
        species=payload.species,
        season=payload.season,
        summary=tips.get("summary"),
        best_conditions=tips.get("best_conditions"),
    )
    db.add(search)
    db.flush()

    for idx, t in enumerate(tips.get("techniques", [])):
        db.add(
            models.Technique(
                search_id=search.id,
                order_index=idx,
                title=t["title"],
                description=t["description"],
            )
        )

    for g in tips.get("gear", []):
        db.add(
            models.GearItem(
                search_id=search.id,
                category=g["category"],
                name=g["name"],
                notes=g.get("notes"),
            )
        )

    db.commit()
    db.refresh(search)
    return search


@router.get("/searches", response_model=list[schemas.SearchListItem])
def list_searches(db: Session = Depends(get_db)):
    return db.query(models.Search).order_by(models.Search.created_at.desc()).all()


@router.get("/searches/{search_id}", response_model=schemas.SearchDetail)
def get_search(search_id: int, db: Session = Depends(get_db)):
    search = db.get(models.Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    return search


@router.delete("/searches/{search_id}", status_code=204)
def delete_search(search_id: int, db: Session = Depends(get_db)):
    search = db.get(models.Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    db.delete(search)
    db.commit()


@router.post("/searches/{search_id}/ask", response_model=schemas.AskResponse)
def ask_question(search_id: int, payload: schemas.AskRequest, db: Session = Depends(get_db)):
    search = db.get(models.Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    context = _build_search_context(search)
    history = [{"role": m.role, "content": m.content} for m in search.messages]

    answer = _handle_ai_errors(ai.answer_question, context, history, payload.question)

    db.add(models.Message(search_id=search.id, role="user", content=payload.question))
    db.add(models.Message(search_id=search.id, role="assistant", content=answer))
    db.commit()

    return schemas.AskResponse(answer=answer)
