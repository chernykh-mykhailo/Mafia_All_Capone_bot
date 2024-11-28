from typing import Dict, List, Optional, Type
import random
from aiogram import Bot
from aiogram.types import Message

from game.roles import Role, Mafia, Doctor, Detective, Civilian
from database.database import cursor, conn

class GameState:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.phase = "waiting"  # waiting, night, day, voting
        self.round = 0
        self.players: Dict[int, Role] = {}
        self.alive_players: List[int] = []
        self.dead_players: List[int] = []
        self.votes: Dict[int, int] = {}  # voter_id -> target_id
        self.night_actions_completed = set()
        
    def add_player(self, player_id: int, name: str) -> bool:
        """Add a player to the game."""
        if player_id in self.players or player_id in self.alive_players:
            return False
            
        # Add to database if not exists
        cursor.execute("SELECT * FROM users WHERE id = %s", (player_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (id, tg_name) VALUES (%s, %s)",
                (player_id, name)
            )
            conn.commit()
            
        # Add to game state
        self.alive_players.append(player_id)
        self.players[player_id] = None  # Role will be assigned later
        return True
    
    def remove_player(self, player_id: int) -> bool:
        if player_id not in self.players:
            return False
        if player_id in self.alive_players:
            self.alive_players.remove(player_id)
        self.players.pop(player_id)
        return True
    
    def assign_roles(self) -> None:
        """Assign roles to players based on the number of players."""
        players = self.alive_players.copy()
        random.shuffle(players)
        
        # Clear existing roles
        self.players.clear()
        
        total_players = len(players)
        
        if total_players < 3:
            raise ValueError("Потрібно мінімум 3 гравці для початку гри")
            
        # For 3 players: 1 Mafia, 1 Doctor, 1 Civilian
        if total_players == 3:
            # Assign Mafia (Al Capone)
            mafia_id = players.pop()
            self.players[mafia_id] = Mafia(mafia_id)
            
            # Assign Doctor
            doctor_id = players.pop()
            self.players[doctor_id] = Doctor(doctor_id)
            
            # Last player is Civilian
            civilian_id = players.pop()
            self.players[civilian_id] = Civilian(civilian_id)
            
        # For 4+ players: add Detective and more Civilians
        else:
            # Assign Mafia (Al Capone)
            mafia_id = players.pop()
            self.players[mafia_id] = Mafia(mafia_id)
            
            # Assign Doctor
            doctor_id = players.pop()
            self.players[doctor_id] = Doctor(doctor_id)
            
            # Assign Detective if enough players
            if len(players) >= 2:
                detective_id = players.pop()
                self.players[detective_id] = Detective(detective_id)
            
            # Remaining players are Civilians
            for player_id in players:
                self.players[player_id] = Civilian(player_id)
    
    def kill_player(self, player_id: int) -> None:
        if player_id in self.alive_players:
            self.alive_players.remove(player_id)
            self.dead_players.append(player_id)
            self.players[player_id].is_alive = False
    
    def is_game_over(self) -> Optional[str]:
        mafia_count = sum(1 for pid in self.alive_players if isinstance(self.players[pid], Mafia))
        civilian_count = len(self.alive_players) - mafia_count
        
        if mafia_count == 0:
            return "civilians"
        elif mafia_count >= civilian_count:
            return "mafia"
        return None
    
    def reset_night_actions(self) -> None:
        self.night_actions_completed.clear()
        for role in self.players.values():
            role.night_action_used = False
    
    def reset_votes(self) -> None:
        self.votes.clear()
    
    def get_vote_results(self) -> Optional[int]:
        if not self.votes:
            return None
            
        vote_counts = {}
        for target_id in self.votes.values():
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
        
        max_votes = max(vote_counts.values())
        candidates = [pid for pid, votes in vote_counts.items() if votes == max_votes]
        
        return candidates[0] if len(candidates) == 1 else None
    
    async def announce_roles(self, bot: Bot) -> None:
        for player_id, role in self.players.items():
            await bot.send_message(
                chat_id=player_id,
                text=f"Ваша роль: {role.name}\n{role.get_night_prompt()}"
            )
    
    def save_to_db(self) -> None:
        cursor.execute("""
            INSERT INTO game_states (chat_id, phase, round)
            VALUES (%s, %s, %s)
            ON CONFLICT (chat_id) DO UPDATE
            SET phase = %s, round = %s
        """, (self.chat_id, self.phase, self.round, self.phase, self.round))
        conn.commit()
    
    @classmethod
    def load_from_db(cls, chat_id: int) -> 'GameState':
        cursor.execute("""
            SELECT phase, round FROM game_states
            WHERE chat_id = %s
        """, (chat_id,))
        result = cursor.fetchone()
        
        if result:
            game_state = cls(chat_id)
            game_state.phase = result[0]
            game_state.round = result[1]
            return game_state
        return cls(chat_id)
