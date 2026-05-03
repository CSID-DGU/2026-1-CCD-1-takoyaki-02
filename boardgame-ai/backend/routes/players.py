"""플레이어 HTTP CRUD 라우터."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/players", tags=["players"])


class PlayerCreate(BaseModel):
    playername: str


class PlayerUpdate(BaseModel):
    playername: str


@router.post("", status_code=201)
def create_player(body: PlayerCreate, request: Request) -> dict:
    orch = request.app.state.orchestrator
    return orch.add_player(body.playername)


@router.post("/start_registration", status_code=201)
def start_registration(request: Request) -> dict:
    """이름 없는 임시 player_id를 발급하고 즉시 좌석 등록 phase 진입."""
    orch = request.app.state.orchestrator
    return orch.start_registration()


@router.post("/{player_id}/finalize", status_code=200)
def finalize_player(player_id: str, body: PlayerCreate, request: Request) -> dict:
    """등록 완료 후 이름 확정."""
    orch = request.app.state.orchestrator
    try:
        orch.finalize_player(player_id, body.playername)
    except KeyError:
        raise HTTPException(status_code=404, detail="Player not found") from None
    return {"ok": True}


@router.patch("/{player_id}", status_code=200)
def update_player(player_id: str, body: PlayerUpdate, request: Request) -> dict:
    orch = request.app.state.orchestrator
    try:
        orch.edit_player(player_id, body.playername)
    except KeyError:
        raise HTTPException(status_code=404, detail="Player not found") from None
    return {"ok": True}


@router.delete("/{player_id}", status_code=200)
def delete_player(player_id: str, request: Request) -> dict:
    orch = request.app.state.orchestrator
    try:
        orch.remove_player(player_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Player not found") from None
    return {"ok": True}


@router.get("", status_code=200)
def list_players(request: Request) -> list:
    orch = request.app.state.orchestrator
    return orch.get_players_list()
