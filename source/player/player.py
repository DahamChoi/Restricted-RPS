from config import config
from typing import List, Dict, Any, Optional
from custom_logger import logger

# --- Player Class ---
class Player:
    def __init__(self, name: str, persona_prompt: str, initial_loan: int = 0):
        self.name = name
        self.persona_prompt = persona_prompt
        self.stars = config.INITIAL_STARS
        self.cards = {
            "rock": config.INITIAL_CARDS_EACH_TYPE,
            "scissors": config.INITIAL_CARDS_EACH_TYPE,
            "paper": config.INITIAL_CARDS_EACH_TYPE
        }
        self.money = initial_loan
        self.status = config.PLAYER_STATUS_ACTIVE
        self.initial_loan = -initial_loan
        self.action_log = [] # 플레이어별 행동 기록

    def get_total_cards(self) -> int:
        return sum(self.cards.values())

    def get_items_dict(self) -> Dict[str, Any]:
        return {
            "star_number": self.stars,
            "rock_card_number": self.cards["rock"],
            "scissors_card_number": self.cards["scissors"],
            "paper_card_number": self.cards["paper"],
            "money": self.money
        }

    def check_survival_condition(self) -> bool:
        return self.get_total_cards() == 0 and self.stars >= 3

    def is_active(self) -> bool:
        return self.status == config.PLAYER_STATUS_ACTIVE

    def update_status(self, new_status: str, reason: str = ""):
        if self.status == config.PLAYER_STATUS_ACTIVE: # 이미 게임 오버 상태면 변경하지 않음
            self.status = new_status
            log_msg = f"Player {self.name} status changed to {new_status}."
            if reason:
                log_msg += f" Reason: {reason}"
            logger.info(log_msg)
            self.action_log.append(f"Status changed to {new_status}. Reason: {reason}")
