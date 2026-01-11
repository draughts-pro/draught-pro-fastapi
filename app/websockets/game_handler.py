import socketio
from app.core.config import settings
from app.services.room_manager import room_manager
from app.models.game import (
    CreateRoomRequest,
    JoinRoomRequest,
    PlayerReadyRequest,
    MakeMoveRequest,
    GameOverRequest,
    LeaveRoomRequest,
    GameStatus,
    PieceColor,
)


client_manager = None
if settings.REDIS_URL:
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        r.ping()
        client_manager = socketio.AsyncRedisManager(settings.REDIS_URL)
    except Exception:
        # Fallback to default manager if Redis is not reachable
        pass

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.CORS_ORIGINS,
    client_manager=client_manager,
    logger=settings.ENV == "development",
    engineio_logger=settings.ENV == "development",
)


@sio.event
async def connect(sid, environ):
    pass


sid_map = {}

@sio.event
async def disconnect(sid, reason=None):
    if sid not in sid_map:
        return

    room_id, player_id = sid_map[sid]

    room = room_manager.get_room(room_id)
    if room and room.status == GameStatus.PLAYING:
        player = next((p for p in room.players if p.id == player_id), None)
        if player:
            winner_color = PieceColor.LIGHT if player.color == PieceColor.DARK else PieceColor.DARK
            room_manager.end_game(room_id, winner_color)
            await sio.emit(
                "gameEnded",
                {"winner": winner_color.value, "reason": "disconnect"},
                room=room_id
            )

    room_manager.handle_disconnect(player_id)
    del sid_map[sid]


@sio.event
async def createRoom(sid, data):
    """Create a new game room"""
    try:
        request = CreateRoomRequest(**data)
        room = room_manager.create_room(
            request.playerId, request.playerName, request.variant
        )

        await sio.enter_room(sid, room.id)
        sid_map[sid] = (room.id, request.playerId)

        return {
            "success": True,
            "roomId": room.id,
            "room": room.model_dump(mode="json"),
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception:
        return {"success": False, "error": "Failed to create room"}


@sio.event
async def joinRoom(sid, data):
    """Join an existing game room"""
    try:
        request = JoinRoomRequest(**data)
        room = room_manager.join_room(
            request.roomId, request.playerId, request.playerName
        )

        await sio.enter_room(sid, request.roomId)
        sid_map[sid] = (request.roomId, request.playerId)

        event_name = "playerReconnected" if any(p.id == request.playerId and p.isConnected for p in room.players) else "playerJoined"
        
        await sio.emit(
            event_name,
            {"room": room.model_dump(mode="json"), "player": next(p for p in room.players if p.id == request.playerId).model_dump(mode="json")},
            room=request.roomId,
        )

        return {"success": True, "room": room.model_dump(mode="json")}

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception:
        return {"success": False, "error": "Failed to join room"}


@sio.event
async def playerReady(sid, data):
    """Mark player as ready"""
    try:
        request = PlayerReadyRequest(**data)
        success = room_manager.set_player_ready(
            request.roomId, request.playerId, request.ready
        )

        if not success:
            return {"success": False, "error": "Failed to set ready status"}

        room = room_manager.get_room(request.roomId)

        # Notify all players
        await sio.emit(
            "playerReadyUpdate",
            {"room": room.model_dump(mode="json")},
            room=request.roomId,
        )

        if room_manager.can_start_game(request.roomId):
            room_manager.start_game(request.roomId)
            room = room_manager.get_room(request.roomId)
            await sio.emit(
                "gameStart",
                {"room": room.model_dump(mode="json")},
                room=request.roomId,
            )

        return {"success": True}

    except Exception as e:
        print(f"Error setting player ready: {e}")
        return {"success": False, "error": "Failed to set ready status"}


@sio.event
async def makeMove(sid, data):
    """Handle a player making a move"""
    try:
        request = MakeMoveRequest(**data)
        room = room_manager.get_room(request.roomId)

        if not room:
            return {"success": False, "error": "Room not found"}

        player = next((p for p in room.players if p.id == request.playerId), None)
        if not player or player.color != room.currentTurn:
            return {"success": False, "error": "Not your turn"}

        room_manager.update_game_state(
            request.roomId, request.newBoard, request.nextTurn
        )
        serialized_board = [
            [piece.model_dump(mode="json") if piece else None for piece in row]
            for row in request.newBoard
        ]

        await sio.emit(
            "moveMade",
            {
                "move": request.move.model_dump(mode="json"),
                "board": serialized_board,
                "currentTurn": request.nextTurn.value,
                "playerId": request.playerId,
            },
            room=request.roomId,
        )

        return {"success": True}

    except Exception:
        return {"success": False, "error": "Failed to make move"}


@sio.event
async def gameOver(sid, data):
    """Handle game over"""
    try:
        request = GameOverRequest(**data)
        room_manager.end_game(request.roomId, request.winner)

        await sio.emit(
            "gameEnded",
            {"winner": request.winner.value if request.winner else None, "reason": request.reason},
            room=request.roomId,
        )

        return {"success": True}

    except Exception:
        return {"success": False, "error": "Failed to end game"}


@sio.event
async def leaveRoom(sid, data):
    try:
        request = LeaveRoomRequest(**data)

        room = room_manager.get_room(request.roomId)
        if room and room.status == GameStatus.PLAYING:
            player = next((p for p in room.players if p.id == request.playerId), None)
            if player:
                winner_color = PieceColor.LIGHT if player.color == PieceColor.DARK else PieceColor.DARK
                room_manager.end_game(request.roomId, winner_color)
                await sio.emit(
                    "gameEnded",
                    {"winner": winner_color.value, "reason": "disconnect"},
                    room=request.roomId
                )

        room = room_manager.remove_player(request.roomId, request.playerId)
        await sio.leave_room(sid, request.roomId)

        if room:
            await sio.emit(
                "playerLeft",
                {"room": room.model_dump(mode="json"), "playerId": request.playerId},
                room=request.roomId,
            )

        return {"success": True}

    except Exception:
        return {"success": False, "error": "Failed to leave room"}
