from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from enum import Enum


class PieceColor(str, Enum):
    DARK = "dark"
    LIGHT = "light"


class GameVariant(str, Enum):
    INTERNATIONAL = "international"
    NIGERIAN = "nigerian"
    AMERICAN = "american"


class GameStatus(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


class Position(BaseModel):
    row: int = Field(..., ge=0, lt=20)
    col: int = Field(..., ge=0, lt=20)


class Piece(BaseModel):
    color: PieceColor
    isKing: bool


class MoveData(BaseModel):
    from_pos: Position = Field(..., alias="from")
    to: Position
    captures: Optional[list[Position]] = None

    class Config:
        populate_by_name = True


class Player(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=50)
    color: PieceColor
    isReady: bool = False
    isConnected: bool = True
    disconnectedAt: Optional[datetime] = None


class GameRoom(BaseModel):
    id: str
    players: list[Player] = Field(default_factory=list, max_length=2)
    board: Optional[list[list[Optional[Piece]]]] = None
    currentTurn: PieceColor = PieceColor.LIGHT
    status: GameStatus = GameStatus.WAITING
    variant: GameVariant
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    lastActivityAt: datetime = Field(default_factory=datetime.utcnow)
    winner: Optional[PieceColor] = None


# WebSocket Event Models
class CreateRoomRequest(BaseModel):
    playerId: str = Field(..., min_length=1, max_length=100)
    playerName: str = Field(..., min_length=1, max_length=50)
    variant: GameVariant


class JoinRoomRequest(BaseModel):
    roomId: str = Field(..., min_length=6, max_length=6)
    playerId: str = Field(..., min_length=1, max_length=100)
    playerName: str = Field(..., min_length=1, max_length=50)


class PlayerReadyRequest(BaseModel):
    roomId: str
    playerId: str
    ready: bool


class MakeMoveRequest(BaseModel):
    roomId: str
    playerId: str
    move: MoveData
    newBoard: list[list[Optional[Piece]]]
    nextTurn: PieceColor


class GameOverRequest(BaseModel):
    roomId: str
    winner: Optional[PieceColor]
    reason: str


class LeaveRoomRequest(BaseModel):
    roomId: str
    playerId: str
