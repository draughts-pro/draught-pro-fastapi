import secrets
import string
from datetime import datetime, timedelta
from typing import Optional
from app.models.game import (
    GameRoom,
    Player,
    PieceColor,
    GameStatus,
    GameVariant,
)
from app.core.config import settings


class RoomManager:
    def __init__(self):
        self.rooms: dict[str, GameRoom] = {}
        self.player_to_room: dict[str, str] = {}  # Track which room a player is in

    def create_room(
        self, player_id: str, player_name: str, variant: GameVariant
    ) -> GameRoom:
        """Create a new game room"""
        if len(self.rooms) >= settings.MAX_ROOMS:
            raise ValueError("Maximum room limit reached")

        room_id = self._generate_room_id()
        player = Player(id=player_id, name=player_name, color=PieceColor.LIGHT)

        room = GameRoom(id=room_id, players=[player], variant=variant)

        self.rooms[room_id] = room
        self.player_to_room[player_id] = room_id

        return room

    def join_room(self, room_id: str, player_id: str, player_name: str) -> GameRoom:
        """Join an existing room"""
        room = self.rooms.get(room_id)

        if not room:
            raise ValueError("Room not found")

        # Check if player is already in room (reconnection)
        existing_player = next((p for p in room.players if p.id == player_id), None)
        if existing_player:
            existing_player.isConnected = True
            existing_player.disconnectedAt = None
            existing_player.name = player_name  # Update name if changed
            room.lastActivityAt = datetime.utcnow()
            return room

        if room.status == GameStatus.FINISHED:
            raise ValueError("Game has ended")

        if room.status != GameStatus.WAITING:
            raise ValueError("Game already started")

        if len(room.players) >= 2:
            raise ValueError("Room is full")

        player = Player(
            id=player_id, 
            name=player_name, 
            color=PieceColor.DARK,
            isConnected=True
        )
        room.players.append(player)
        room.lastActivityAt = datetime.utcnow()

        self.player_to_room[player_id] = room_id

        return room

    def get_room(self, room_id: str) -> Optional[GameRoom]:
        """Get room by ID"""
        room = self.rooms.get(room_id)
        if room:
            room.lastActivityAt = datetime.utcnow()
        return room

    def set_player_ready(self, room_id: str, player_id: str, ready: bool) -> bool:
        """Set player ready status"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        player = next((p for p in room.players if p.id == player_id), None)
        if not player:
            return False

        player.isReady = ready
        room.lastActivityAt = datetime.utcnow()
        return True

    def can_start_game(self, room_id: str) -> bool:
        """Check if game can start"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        return len(room.players) == 2 and all(p.isReady for p in room.players)

    def start_game(self, room_id: str) -> bool:
        """Start the game"""
        if not self.can_start_game(room_id):
            return False

        room = self.rooms[room_id]
        room.status = GameStatus.PLAYING
        room.lastActivityAt = datetime.utcnow()
        return True

    def update_game_state(
        self, room_id: str, board: any, current_turn: PieceColor
    ) -> bool:
        """Update game state after a move"""
        room = self.rooms.get(room_id)
        if not room or room.status != GameStatus.PLAYING:
            return False

        room.board = board
        room.currentTurn = current_turn
        room.lastActivityAt = datetime.utcnow()
        return True

    def end_game(self, room_id: str, winner: Optional[PieceColor]) -> bool:
        """End the game"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        room.status = GameStatus.FINISHED
        room.winner = winner
        room.lastActivityAt = datetime.utcnow()
        return True

    def remove_player(self, room_id: str, player_id: str) -> Optional[GameRoom]:
        """Remove a player from a room"""
        room = self.rooms.get(room_id)
        if not room:
            return None

        room.players = [p for p in room.players if p.id != player_id]
        self.player_to_room.pop(player_id, None)

        # Delete room if empty
        if len(room.players) == 0:
            self.rooms.pop(room_id, None)
            return None

        room.lastActivityAt = datetime.utcnow()
        return room

    def get_player_room(self, player_id: str) -> Optional[str]:
        """Get the room ID for a player"""
        return self.player_to_room.get(player_id)

    def handle_disconnect(self, player_id: str) -> Optional[GameRoom]:
        """Handle player disconnection (mark as disconnected)"""
        room_id = self.player_to_room.get(player_id)
        if not room_id:
            return None

        room = self.rooms.get(room_id)
        if not room:
            return None

        player = next((p for p in room.players if p.id == player_id), None)
        if player:
            player.isConnected = False
            player.disconnectedAt = datetime.utcnow()
            room.lastActivityAt = datetime.utcnow()

        return room

    def cleanup_inactive_rooms(self):
        """Remove inactive rooms and disconnected players"""
        now = datetime.utcnow()
        inactive_timeout = timedelta(seconds=settings.INACTIVE_ROOM_TIMEOUT_SECONDS)
        disconnect_timeout = timedelta(seconds=60)  # 60 seconds grace period

        rooms_to_delete = []
        for room_id, room in self.rooms.items():
            # Check room inactivity
            if now - room.lastActivityAt > inactive_timeout:
                rooms_to_delete.append(room_id)
                continue

            # Check for disconnected players timeout
            # If a player has been disconnected for too long, consider them left
            disconnected_players = [
                p for p in room.players 
                if not p.isConnected and p.disconnectedAt and (now - p.disconnectedAt > disconnect_timeout)
            ]
            
            for player in disconnected_players:
                # If game is playing and player times out, they forfeit?
                # For now, just remove them which might end game or close room
                self.remove_player(room_id, player.id)

            # If room became empty after removing players
            if len(room.players) == 0:
                rooms_to_delete.append(room_id)

        for room_id in list(set(rooms_to_delete)):  # unique IDs
            room = self.rooms.pop(room_id, None)
            if room:
                for player in room.players:
                    self.player_to_room.pop(player.id, None)

        return len(rooms_to_delete)

    def _generate_room_id(self) -> str:
        """Generate a unique 6-character room code"""
        chars = string.ascii_uppercase + string.digits
        chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "")

        while True:
            room_id = "".join(secrets.choice(chars) for _ in range(6))
            if room_id not in self.rooms:
                return room_id


room_manager = RoomManager()
