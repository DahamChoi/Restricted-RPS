
from typing import List, Dict, Any, Optional
from custom_logger import logger, logger_final
from player.player import Player
from openai_client import client
from config import config
import json

# --- Game Class ---
class Game:
    def __init__(self, player_configs: List[Dict[str, Any]]):
        from agent.agent import OpenAI_Agent
        self.players = {conf["name"]: Player(conf["name"], conf["persona"], conf.get("loan", 0)) for conf in player_configs}
        self.current_turn = 0
        self.max_turns = config.MAX_TURNS
        self.game_over = False
        self.winner = None # 또는 생존자 목록

        # 각 플레이어에게 Agent 할당
        self.agents = {name: OpenAI_Agent(player, self) for name, player in self.players.items()}

        # 게임 초기 상태 로그
        logger.info("="*30)
        logger.info("Limited Rock-Paper-Scissors Simulation Start!")
        logger.info(f"Initial Players ({len(self.players)}): {list(self.players.keys())}")
        for name, player in self.players.items():
             logger.info(f"  - {name}: Stars={player.stars}, Cards={player.cards}, Money={player.money}, Loan={player.initial_loan}")
        logger.info("="*30)


    def get_player(self, name: str) -> Optional[Player]:
        return self.players.get(name)

    def get_active_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.is_active()]

    # --- Function Implementations (Game Logic) ---

    def get_user_items(self, user_name: str) -> Optional[Dict[str, Any]]:
        """플레이어의 현재 자원 정보를 반환 (에이전트가 직접 호출하는 것이 아님)"""
        player = self.get_player(user_name)
        if player:
            return player.get_items_dict()
        return None

    def get_other_players_info(self, exclude_player_name: str = None) -> List[Dict[str, Any]]:
        """현재 활성 상태인 다른 플레이어들의 공개 정보 (이름, 별 개수) 반환"""
        active_players = self.get_active_players()
        info_list = []
        for player in active_players:
            if player.name != exclude_player_name:
                info_list.append({
                    "user_name": player.name,
                    "user_stars": player.stars
                    # 카드 개수 등 비공개 정보는 포함하지 않음
                })
        return info_list

    def get_dashboard_info(self) -> Dict[str, Any]:
        """현재 게임 전광판 현황 반환"""
        active_players = self.get_active_players()
        total_cards = {"rock": 0, "scissors": 0, "paper": 0}
        for player in active_players:
            for card_type, count in player.cards.items():
                total_cards[card_type] += count

        return {
            "alive_users": len(active_players),
            "remain_time": (self.max_turns - self.current_turn) * config.TIME_PER_TURN,
            "all_rock_card_number": total_cards["rock"],
            "all_scissors_card_number": total_cards["scissors"],
            "all_paper_card_number": total_cards["paper"],
        }

    def _validate_trade(self, player1: Player, player2: Player, args: Dict[str, Any]) -> bool:
        """거래 유효성 검증 (자원 보유 여부 등)"""
        if not player1 or not player2 or not player1.is_active() or not player2.is_active():
            logger.warning(f"Trade validation failed: One or both players inactive or not found.")
            return False
        if player1.stars < args.get('give_stars', 0): return False
        if player1.cards['rock'] < args.get('give_rock', 0): return False
        if player1.cards['scissors'] < args.get('give_scissors', 0): return False
        if player1.cards['paper'] < args.get('give_paper', 0): return False
        if player1.money < args.get('give_money', 0): return False

        # 자기 자신과의 거래 방지
        if player1.name == player2.name:
             logger.warning(f"Trade validation failed: Player {player1.name} cannot trade with themselves.")
             return False

        return True

    def execute_trade(self, player1: Player, player2: Player, args: Dict[str, Any]):
        """실제 거래 실행 (자원 교환)"""
        logger.info(f"Executing trade between {player1.name} and {player2.name}.")
        log_entry = f"Turn {self.current_turn}: Trade executed with {player2.name}."

        # Player 1 주는 아이템 차감
        player1.stars -= args.get('give_stars', 0)
        player1.cards['rock'] -= args.get('give_rock', 0)
        player1.cards['scissors'] -= args.get('give_scissors', 0)
        player1.cards['paper'] -= args.get('give_paper', 0)
        player1.money -= args.get('give_money', 0)
        log_entry += f" Gave: {args.get('give_stars', 0)}*, R:{args.get('give_rock', 0)}, S:{args.get('give_scissors', 0)}, P:{args.get('give_paper', 0)}, M:{args.get('give_money', 0)}."

        # Player 2 받는 아이템 증가
        player2.stars += args.get('give_stars', 0)
        player2.cards['rock'] += args.get('give_rock', 0)
        player2.cards['scissors'] += args.get('give_scissors', 0)
        player2.cards['paper'] += args.get('give_paper', 0)
        player2.money += args.get('give_money', 0)

        # Player 1 받는 아이템 증가
        player1.stars += args.get('receive_stars', 0)
        player1.cards['rock'] += args.get('receive_rock', 0)
        player1.cards['scissors'] += args.get('receive_scissors', 0)
        player1.cards['paper'] += args.get('receive_paper', 0)
        player1.money += args.get('receive_money', 0)
        log_entry += f" Received: {args.get('receive_stars', 0)}*, R:{args.get('receive_rock', 0)}, S:{args.get('receive_scissors', 0)}, P:{args.get('receive_paper', 0)}, M:{args.get('receive_money', 0)}."

        # Player 2 주는 아이템 차감
        player2.stars -= args.get('receive_stars', 0)
        player2.cards['rock'] -= args.get('receive_rock', 0)
        player2.cards['scissors'] -= args.get('receive_scissors', 0)
        player2.cards['paper'] -= args.get('receive_paper', 0)
        player2.money -= args.get('receive_money', 0)

        logger.info(f"Trade completed. {player1.name} state: {player1.get_items_dict()}. {player2.name} state: {player2.get_items_dict()}")
        player1.action_log.append(log_entry)
        player2.action_log.append(f"Turn {self.current_turn}: Accepted trade with {player1.name}.") # 상대방 로그에도 기록

    def _validate_match(self, player1: Player, player2: Player, card_to_play: str) -> bool:
        """게임 유효성 검증 (플레이어 활성 상태, 카드 보유 여부)"""
        if not player1 or not player2 or not player1.is_active() or not player2.is_active():
            logger.warning(f"Match validation failed: One or both players inactive or not found.")
            return False
        if player1.cards.get(card_to_play, 0) <= 0:
            logger.warning(f"Match validation failed: {player1.name} does not have card '{card_to_play}'.")
            return False
        # 상대방 카드 보유 여부는 상대방이 결정할 때 체크
        # 자기 자신과의 게임 방지
        if player1.name == player2.name:
            logger.warning(f"Match validation failed: Player {player1.name} cannot play against themselves.")
            return False
        return True

    def play_match(self, player1: Player, player2: Player, card1: str, card2: str):
        """가위바위보 게임 실행 및 결과 처리"""
        logger.info(f"Playing match: {player1.name} ({card1}) vs {player2.name} ({card2})")
        log_entry_p1 = f"Turn {self.current_turn}: Played '{card1}' against {player2.name} ('{card2}')."
        log_entry_p2 = f"Turn {self.current_turn}: Played '{card2}' against {player1.name} ('{card1}')."

        # 카드 소모
        player1.cards[card1] -= 1
        player2.cards[card2] -= 1

        winner = None
        loser = None
        is_draw = False

        if card1 == card2:
            is_draw = True
            logger.info("Result: Draw.")
            log_entry_p1 += " Result: Draw."
            log_entry_p2 += " Result: Draw."
        elif (card1 == 'rock' and card2 == 'scissors') or \
             (card1 == 'scissors' and card2 == 'paper') or \
             (card1 == 'paper' and card2 == 'rock'):
            winner = player1
            loser = player2
            logger.info(f"Result: {player1.name} wins.")
            log_entry_p1 += " Result: Win."
            log_entry_p2 += " Result: Lose."
        else:
            winner = player2
            loser = player1
            logger.info(f"Result: {player2.name} wins.")
            log_entry_p1 += " Result: Lose."
            log_entry_p2 += " Result: Win."

        # 별 이동
        if winner and loser:
            winner.stars += 1
            loser.stars -= 1
            logger.info(f"{winner.name} gains a star (now {winner.stars}), {loser.name} loses a star (now {loser.stars}).")
            log_entry_p1 += f" Stars: {player1.stars}."
            log_entry_p2 += f" Stars: {player2.stars}."
            # 별 0개 이하 시 즉시 탈락 처리 (Game Master 역할 일부 선처리)
            if loser.stars <= 0:
                loser.update_status(config.PLAYER_STATUS_ELIMINATED_NO_STAR, f"Lost all stars in a match against {winner.name}")
        else: # 무승부
             log_entry_p1 += f" Stars: {player1.stars}."
             log_entry_p2 += f" Stars: {player2.stars}."


        logger.info(f"Match completed. {player1.name} state: {player1.get_items_dict()}. {player2.name} state: {player2.get_items_dict()}")
        player1.action_log.append(log_entry_p1)
        player2.action_log.append(log_entry_p2)


    def handle_action(self, player_name: str, action: Dict[str, Any]):
        """플레이어의 결정된 행동을 처리 (Game Anchor 역할 일부 포함)"""
        player = self.get_player(player_name)
        if not player or not player.is_active():
            logger.warning(f"Cannot handle action for inactive or non-existent player {player_name}.")
            return

        func_name = action["function_name"]
        args = action["arguments"]

        if func_name == "propose_trade":
            target_player_name = args.get("target_player_name")
            target_player = self.get_player(target_player_name)

            if not target_player or not target_player.is_active():
                logger.warning(f"{player.name} proposed trade to inactive/invalid player {target_player_name}. Trade failed.")
                player.action_log.append(f"Turn {self.current_turn}: Trade proposal to {target_player_name} failed (target inactive/invalid).")
                return

            # --- Game Anchor: 상대방에게 거래 의사 묻기 ---
            # 여기서는 단순화를 위해 상대방(AI)도 OpenAI 호출을 통해 결정한다고 가정
            # 실제 구현 시에는 비용/시간 문제로 규칙 기반 또는 더 간단한 로직 사용 가능
            logger.info(f"{player.name} proposes trade to {target_player_name}. Asking {target_player_name} for response...")

            accept_trade = self.ask_trade_response(target_player, player, args) # 상대방에게 거래 수락 여부 결정 요청

            if accept_trade:
                 # 거래 유효성 재검증 (상대방이 수락 시점에 필요한 자원을 가지고 있는지)
                 if self._validate_trade(player, target_player, args) and \
                    self._validate_received_items(target_player, args): # 상대방이 줄 아이템 검증
                     logger.info(f"{target_player_name} accepted the trade from {player.name}.")
                     self.execute_trade(player, target_player, args)
                 else:
                     logger.warning(f"Trade between {player.name} and {target_player_name} failed validation after acceptance. No trade executed.")
                     player.action_log.append(f"Turn {self.current_turn}: Trade with {target_player_name} accepted but failed validation.")
                     target_player.action_log.append(f"Turn {self.current_turn}: Accepted trade with {player.name} but failed validation.")

            else:
                 logger.info(f"{target_player_name} rejected the trade from {player.name}.")
                 player.action_log.append(f"Turn {self.current_turn}: Trade proposal to {target_player_name} was rejected.")
                 target_player.action_log.append(f"Turn {self.current_turn}: Rejected trade proposal from {player.name}.")


        elif func_name == "propose_match":
            target_player_name = args.get("target_player_name")
            card_to_play = args.get("card_to_play")
            target_player = self.get_player(target_player_name)

            if not self._validate_match(player, target_player, card_to_play):
                logger.warning(f"{player.name}'s match proposal to {target_player_name} with {card_to_play} is invalid.")
                player.action_log.append(f"Turn {self.current_turn}: Match proposal to {target_player_name} failed (invalid).")
                return

            # --- Game Anchor: 상대방에게 게임 수락 및 카드 선택 요청 ---
            logger.info(f"{player.name} proposes a match to {target_player_name} (playing {card_to_play}). Asking {target_player_name} for response...")

            target_card = self.ask_match_response(target_player, player) # 상대방에게 게임 수락 및 카드 결정 요청

            if target_card: # 상대방이 게임을 수락하고 카드를 선택한 경우
                logger.info(f"{target_player_name} accepted the match and chose '{target_card}'.")
                if target_player.cards.get(target_card, 0) > 0: # 상대방 카드 유효성 검증
                     self.play_match(player, target_player, card_to_play, target_card)
                else:
                     logger.warning(f"{target_player_name} accepted match but chose invalid card '{target_card}'. Match cancelled.")
                     player.action_log.append(f"Turn {self.current_turn}: Match with {target_player_name} cancelled (opponent chose invalid card).")
                     target_player.action_log.append(f"Turn {self.current_turn}: Accepted match with {player.name} but chose invalid card '{target_card}'.")
            else:
                logger.info(f"{target_player_name} rejected the match proposed by {player.name}.")
                player.action_log.append(f"Turn {self.current_turn}: Match proposal to {target_player_name} was rejected.")
                target_player.action_log.append(f"Turn {self.current_turn}: Rejected match proposal from {player.name}.")


        elif func_name == "declare_out_of_game":
            if player.check_survival_condition():
                logger.info(f"{player.name} declares 'Out of Game' successfully!")
                player.update_status(config.PLAYER_STATUS_OUT_SUCCESS, "Met survival conditions.")
            else:
                logger.warning(f"{player.name} tried to declare 'Out of Game' but did not meet conditions (Stars: {player.stars}, Cards: {player.get_total_cards()}).")
                player.action_log.append(f"Turn {self.current_turn}: Attempted 'Out of Game' but failed conditions.")

        elif func_name == "do_nothing":
            logger.info(f"{player.name} chose to do nothing this turn.")
            # 로그는 OpenAI_Agent.decide_action 에서 이미 기록됨

    def _validate_received_items(self, receiving_player: Player, trade_args: Dict[str, Any]) -> bool:
        """거래 시 상대방(수락자)이 제공해야 할 아이템을 가지고 있는지 검증"""
        if receiving_player.stars < trade_args.get('receive_stars', 0): return False
        if receiving_player.cards['rock'] < trade_args.get('receive_rock', 0): return False
        if receiving_player.cards['scissors'] < trade_args.get('receive_scissors', 0): return False
        if receiving_player.cards['paper'] < trade_args.get('receive_paper', 0): return False
        if receiving_player.money < trade_args.get('receive_money', 0): return False
        return True


    def ask_trade_response(self, target_player: Player, proposing_player: Player, proposal_args: Dict[str, Any]) -> bool:
        """ (Game Anchor 역할) 대상 플레이어(AI)에게 거래 제안에 대한 응답을 요청 """
        if not target_player.is_active(): return False # 응답할 수 없는 상태

        # 대상 플레이어에게 상황 전달 및 결정 요청
        messages = [
            {"role": "system", "content": target_player.persona_prompt + "\n\n" + self.get_game_rules_summary()},
            {"role": "user", "content": f"""
            ## 거래 제안 도착
            플레이어 '{proposing_player.name}'로부터 다음 내용의 거래 제안을 받았습니다:

            **{proposing_player.name}가 당신에게 주려는 것:**
            - 별: {proposal_args.get('give_stars', 0)}개
            - 바위 카드: {proposal_args.get('give_rock', 0)}장
            - 가위 카드: {proposal_args.get('give_scissors', 0)}장
            - 보 카드: {proposal_args.get('give_paper', 0)}장
            - 현금: {proposal_args.get('give_money', 0)} 엔

            **{proposing_player.name}가 당신에게 받으려는 것:**
            - 별: {proposal_args.get('receive_stars', 0)}개
            - 바위 카드: {proposal_args.get('receive_rock', 0)}장
            - 가위 카드: {proposal_args.get('receive_scissors', 0)}장
            - 보 카드: {proposal_args.get('receive_paper', 0)}장
            - 현금: {proposal_args.get('receive_money', 0)} 엔

            ## 현재 당신의 상태 ({target_player.name})
            - 별: {target_player.stars}개
            - 카드: 바위 {target_player.cards['rock']}장, 가위 {target_player.cards['scissors']}장, 보 {target_player.cards['paper']}장 (총 {target_player.get_total_cards()}장)
            - 현금: {target_player.money} 엔

            ## 당신의 결정
            이 거래 제안을 수락하시겠습니까? 당신의 생존 목표와 현재 자원 상황, {proposing_player.name}의 의도 등을 고려하여 신중하게 판단하세요.
            반드시 'accept' 또는 'reject' 중 하나로만 응답하고, 그 이유를 간략하게 설명해주세요.
            게임의 생존을 충족했다면, 남은 자원으로 돈을 최대한으로 획득해야합니다.

            **응답 형식:**
            ```json
            {{
              "decision": "accept | reject",
              "reasoning": "거래를 수락/거절하는 이유..."
            }}
            ```
            """}
        ]

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"}, # JSON 응답 강제
                temperature=0.5
            )
            decision_data = json.loads(response.choices[0].message.content)
            decision = decision_data.get("decision")
            reasoning = decision_data.get("reasoning", "No reasoning provided.")

            logger.info(f"{target_player.name}'s response to trade proposal: {decision}. Reasoning: {reasoning}")
            target_player.action_log.append(f"Turn {self.current_turn}: Responded '{decision}' to trade from {proposing_player.name}. Reason: {reasoning}")

            return decision == "accept"

        except Exception as e:
            logger.error(f"Error getting trade response from {target_player.name}: {e}")
            target_player.action_log.append(f"Turn {self.current_turn}: Failed to respond to trade from {proposing_player.name} due to API error. Defaulting to reject.")
            return False # 오류 시 안전하게 거절 처리

    def ask_match_response(self, target_player: Player, proposing_player: Player) -> Optional[str]:
        """ (Game Anchor 역할) 대상 플레이어(AI)에게 게임 제안에 대한 응답 및 카드 선택 요청 """
        if not target_player.is_active() or target_player.get_total_cards() == 0:
             logger.warning(f"{target_player.name} cannot respond to match: Inactive or no cards left.")
             return None # 게임 불가

        # 대상 플레이어에게 상황 전달 및 결정 요청
        messages = [
            {"role": "system", "content": target_player.persona_prompt + "\n\n" + self.get_game_rules_summary()},
            {"role": "user", "content": f"""
            ## 게임 제안 도착
            플레이어 '{proposing_player.name}' (별 {proposing_player.stars}개 보유) 가 당신에게 가위바위보 게임을 제안했습니다.
            승리하면 상대의 별 1개를 얻고, 패배하면 당신의 별 1개를 잃습니다. 무승부 시 변화는 없습니다.
            어떤 경우든 당신은 카드 1장을 소모하게 됩니다.

            ## 현재 당신의 상태 ({target_player.name})
            - 별: {target_player.stars}개
            - 보유 카드: 바위 {target_player.cards['rock']}장, 가위 {target_player.cards['scissors']}장, 보 {target_player.cards['paper']}장 (총 {target_player.get_total_cards()}장)
            - 현금: {target_player.money} 엔

            ## 당신의 결정
            이 게임 제안을 수락하시겠습니까? 만약 수락한다면, 어떤 카드를 내시겠습니까?
            당신의 생존 목표, 현재 자원, {proposing_player.name}의 상태 등을 고려하여 전략적으로 판단하세요.
            거절할 수도 있습니다. 하지만, 거절을 반복할 경우 카드를 제한시간안에 소모하지 못해 게임에 패배할 수 있습니다.

            **응답 형식 (JSON):**
            - 수락 시: `{{"decision": "accept", "card_to_play": "rock | scissors | paper", "reasoning": "수락 및 카드 선택 이유..."}}`
            - 거절 시: `{{"decision": "reject", "reasoning": "거절 이유..."}}`

            반드시 위 형식 중 하나로 응답해주세요. 사용 가능한 카드가 없으면 거절해야 합니다.
            """}
        ]

        available_cards = [card for card, count in target_player.cards.items() if count > 0]
        if not available_cards: # 낼 카드가 없으면 거절 외 선택지 없음
             logger.warning(f"{target_player.name} has no cards left to play. Rejecting match automatically.")
             target_player.action_log.append(f"Turn {self.current_turn}: Rejected match from {proposing_player.name} (no cards left).")
             return None

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.6
            )
            decision_data = json.loads(response.choices[0].message.content)
            decision = decision_data.get("decision")
            reasoning = decision_data.get("reasoning", "No reasoning provided.")
            card_choice = decision_data.get("card_to_play")

            logger.info(f"{target_player.name}'s response to match proposal: {decision}. Card: {card_choice or 'N/A'}. Reasoning: {reasoning}")

            if decision == "accept" and card_choice in available_cards:
                target_player.action_log.append(f"Turn {self.current_turn}: Accepted match from {proposing_player.name}, playing '{card_choice}'. Reason: {reasoning}")
                return card_choice
            else:
                 if decision == "accept" and card_choice not in available_cards:
                     logger.warning(f"{target_player.name} accepted match but chose unavailable card '{card_choice}'. Treating as reject.")
                     target_player.action_log.append(f"Turn {self.current_turn}: Rejected match from {proposing_player.name} (chose unavailable card '{card_choice}'). Reason: {reasoning}")
                 else: # 명시적 reject 또는 다른 문제
                     target_player.action_log.append(f"Turn {self.current_turn}: Rejected match from {proposing_player.name}. Reason: {reasoning}")
                 return None # 거절 또는 유효하지 않은 카드 선택

        except Exception as e:
            logger.error(f"Error getting match response from {target_player.name}: {e}")
            target_player.action_log.append(f"Turn {self.current_turn}: Failed to respond to match from {proposing_player.name} due to API error. Defaulting to reject.")
            return None # 오류 시 안전하게 거절


    def remove_eliminated_players(self):
        """ (Game Master 역할) 탈락 조건 확인 및 처리 """
        eliminated_this_turn = []
        for player in self.get_active_players(): # 활성 플레이어만 확인
            if player.stars <= 0 and player.status == config.PLAYER_STATUS_ACTIVE:
                player.update_status(config.PLAYER_STATUS_ELIMINATED_NO_STAR, "Ran out of stars")
                eliminated_this_turn.append(player.name)
            # 시간 초과 탈락은 게임 종료 시 한 번에 처리

        if eliminated_this_turn:
            logger.info(f"Players eliminated due to no stars: {eliminated_this_turn}")

    def check_game_end(self) -> bool:
        """ (Game Master 역할) 게임 종료 조건 확인 """
        active_players = self.get_active_players()
        successful_players = [p for p in self.players.values() if p.status == config.PLAYER_STATUS_OUT_SUCCESS]

        # 1. 시간 종료
        if self.current_turn >= self.max_turns:
            logger.info("="*30)
            logger.info("Game Over: Time limit reached!")
            logger.info("="*30)
            # 시간 종료 시 활성 상태인 플레이어는 탈락 처리
            for player in active_players:
                player.update_status(config.PLAYER_STATUS_ELIMINATED_TIME_OUT, "Game time expired")
            self.game_over = True
            return True

        # 2. 모든 플레이어가 활성 상태가 아닐 때 (성공 또는 탈락)
        if not active_players:
            logger.info("="*30)
            logger.info("Game Over: No active players remaining!")
            logger.info("="*30)
            self.game_over = True
            return True

        # 3. 한 명만 남았을 때
        if len(active_players) == 1 and len(self.players) > 1:
            logger.info(f"Game Over: Only one player ({active_players[0].name}) remains active.")
            # 남은 플레이어의 상태 처리 (예: 생존 조건 미달 시 탈락)
            last_player = active_players[0]
            if not last_player.check_survival_condition():
                 last_player.update_status(config.PLAYER_STATUS_ELIMINATED_TIME_OUT, "Last player standing but failed conditions at time end (simulated)")
            self.game_over = True
            return True

        return False

    def progress_turn(self):
        """한 턴을 진행시킵니다."""
        if self.game_over:
            logger.warning("Attempted to progress turn but game is already over.")
            return

        self.current_turn += 1
        logger.info(f"\n===== Turn {self.current_turn}/{self.max_turns} Start =====")
        logger.info(f"Remaining Time: {(self.max_turns - self.current_turn) * config.TIME_PER_TURN} minutes")

        # 플레이어 순서 결정 (여기서는 고정 순서 사용, 랜덤화 가능)
        player_order = list(self.players.keys())
        # random.shuffle(player_order) # 매 턴 순서 섞기

        # 각 활성 플레이어의 행동 결정 및 처리
        for player_name in player_order:
            player = self.get_player(player_name)
            if player and player.is_active():
                agent = self.agents[player_name]
                action = agent.decide_action() # AI가 행동 결정 (OpenAI API 호출)

                if action:
                    # 결정된 행동 처리 (Game Anchor 역할 수행)
                    self.handle_action(player_name, action)
                else:
                    # 에이전트가 결정을 반환하지 못한 경우 (오류 등)
                    logger.error(f"Agent for {player_name} failed to return an action.")
                    player.action_log.append(f"Turn {self.current_turn}: Failed to get action decision.")

                # 행동 후 즉시 별 개수 체크 (매치 후 바로 반영되지만, 혹시 모를 다른 상황 대비)
                self.remove_eliminated_players()
                # 중간에 게임 종료 조건 만족 시 루프 중단 (예: 전원 탈락)
                if self.check_game_end(): break

            elif player and not player.is_active():
                logger.debug(f"Skipping turn for {player_name} (Status: {player.status})")


        # --- Game Master 역할 수행 ---
        logger.info(f"--- End of Turn {self.current_turn} ---")

        # 1. 탈락자 최종 확인 (턴 동안 별 잃은 플레이어 정리)
        self.remove_eliminated_players()

        # 2. 게임 종료 조건 확인
        if not self.game_over: # 플레이어 행동 중 게임이 끝나지 않았다면 여기서 최종 확인
            self.check_game_end()

        # 3. 현재 상황 요약 로그 (선택적)
        if not self.game_over:
             self.log_turn_summary()
        else:
             self.log_final_results()


    def log_turn_summary(self):
        """턴 종료 시 요약 정보 로깅"""
        logger.info("--- Turn Summary ---")
        dashboard = self.get_dashboard_info()
        logger.info(f"Active Players: {dashboard['alive_users']}")
        for player in self.players.values():
             if player.is_active():
                 logger.info(f"  - {player.name}: Stars={player.stars}, Cards={player.get_total_cards()}, Money={player.money}")
             elif player.status == config.PLAYER_STATUS_OUT_SUCCESS:
                  logger.info(f"  - {player.name}: Status=OUT (Success)")
             else:
                  logger.info(f"  - {player.name}: Status={player.status}")
        logger.info("-" * 20)


    def log_final_results(self):
        """게임 종료 시 최종 결과 로깅"""
        logger.info("="*30)
        logger.info("Final Game Results")
        logger.info("="*30)
        survivors = []
        eliminated = []
        for player in self.players.values():
            final_status_reason = player.action_log[-1] if player.action_log else "N/A" # 마지막 로그에서 상태 변경 이유 추정
            log_line = f"- {player.name}: Status={player.status}, Stars={player.stars}, Cards={player.get_total_cards()}, Money={player.money}"
                     # f", Last Action/Reason: {final_status_reason}"
            if player.status == config.PLAYER_STATUS_OUT_SUCCESS:
                survivors.append(log_line)
            else:
                eliminated.append(log_line)

        logger.info("--- Survivors ---")
        if survivors:
            for line in survivors: logger.info(line)
        else:
            logger.info("No survivors.")

        logger.info("--- Eliminated ---")
        if eliminated:
            for line in eliminated: logger.info(line)
        else:
            logger.info("No players eliminated (should not happen if game ended).")

        # 상세 로그 출력
        # for name, player in self.players.items():
        #     logger_final.info(f"\n--- Action Log for {name} ---")
        #     for log in player.action_log:
        #         logger_final.info(log)

    def get_game_rules_summary(self) -> str:
        """Agent에게 제공할 게임 규칙 요약"""
        return f"""
        ## 게임: 한정 가위바위보 규칙 요약
        - 시작 조건: 별 {config.INITIAL_STARS}개, 가위/바위/보 카드 각 {config.INITIAL_CARDS_EACH_TYPE}장 (총 {config.INITIAL_CARDS_EACH_TYPE*3}장).
        - 진행: 다른 플레이어와 1:1 대면 게임 또는 자원 거래.
        - 게임(가위바위보): 승리 시 상대 별 1개 획득, 패배 시 별 1개 상실. 무승부 시 변화 없음. 사용한 카드는 소멸.
        - 거래: 카드, 별, 현금 등 자유롭게 교환 가능 (상호 동의 필요).
        - 생존 조건: 총 {config.MAX_TURNS*config.TIME_PER_TURN}분 ({config.MAX_TURNS}턴) 안에 1) 모든 카드 소진, 2) 별 3개 이상 보유.
        - 탈락 조건: 별 0개 이하가 되거나, 제한 시간 초과 시.
        - 목표: 생존 조건을 만족하고 게임에서 나가는 것 ('declare_out_of_game' 함수 사용).
        - 상호작용: `propose_trade`, `propose_match` 함수로 제안. 제안 받은 경우 AI가 응답.
        - 행동 없음: `do_nothing` 함수 사용 가능.
        - 시간: 매 턴 10분씩 감소.
        """

    def run_simulation(self):
        """게임 시뮬레이션 실행"""
        while not self.game_over:
            self.progress_turn()
            # time.sleep(1)

    def log_final_results(self):
        """게임 종료 시 최종 결과 로깅"""
        logger.info("="*30)
        logger.info("Final Game Results")
        logger.info("="*30)
        survivors = []
        eliminated = []
        # 상세 로그를 위해 플레이어별 최종 상태 저장
        self.final_player_statuses = {}
        for player in self.players.values():
            final_status_reason = player.action_log[-1] if player.action_log else "N/A"
            status_info = {
                "status": player.status,
                "stars": player.stars,
                "cards": player.get_total_cards(),
                "money": player.money
            }
            self.final_player_statuses[player.name] = status_info

            log_line = f"- {player.name}: Status={player.status}, Stars={player.stars}, Cards={player.get_total_cards()}, Money={player.money}"
            if player.status == config.PLAYER_STATUS_OUT_SUCCESS:
                survivors.append(log_line)
            else:
                eliminated.append(log_line)

        logger.info("--- Survivors ---")
        if survivors:
            for line in survivors: logger.info(line)
        else:
            logger.info("No survivors.")

        logger.info("--- Eliminated ---")
        if eliminated:
            for line in eliminated: logger.info(line)
        else:
            logger.info("No players eliminated (error in logic?).")

    def generate_narrative_summary(self):
        """AI를 사용하여 게임의 서사적 요약을 생성합니다."""
        if not self.game_over:
            logger.warning("게임이 끝나기 전에 서사 요약을 생성할 수 없습니다.")
            return

        logger.info("\n" + "="*30)
        logger.info("AI를 사용하여 서사 요약 생성 중...")
        logger.info("="*30)

        # 1. 모든 로그와 최종 상태 수집
        full_log_text = ""
        # 턴별로 로그를 모아 시간 순서대로 재구성
        turn_logs = {} # {turn_number: [log_entry_string, ...]}

        max_log_turn = 0
        for name, player in self.players.items():
            for log_entry in player.action_log:
                 try:
                     # 로그에서 턴 번호 추출 시도
                     if log_entry.startswith("Turn "):
                         turn_part = log_entry.split(":")[0] # "Turn X"
                         turn_num = int(turn_part.split(" ")[1])
                         max_log_turn = max(max_log_turn, turn_num)
                         if turn_num not in turn_logs:
                             turn_logs[turn_num] = []
                         # 플레이어 이름과 함께 로그 추가
                         turn_logs[turn_num].append(f"[{name}] {log_entry}")
                     # 'Status changed' 로그 등 턴 정보 없는 경우 처리 (선택적)
                     # else:
                     #     if 0 not in turn_logs: turn_logs[0] = [] # 턴 0 또는 별도 그룹
                     #     turn_logs[0].append(f"[{name}] {log_entry}")
                 except Exception as e:
                     logger.debug(f"Could not parse turn number from log: {log_entry} - {e}")
                     # 파싱 실패 시 로그를 마지막 턴에 추가하거나 별도 처리
                     if max_log_turn not in turn_logs: turn_logs[max_log_turn]=[]
                     turn_logs[max_log_turn].append(f"[{name}] {log_entry}")


        # 시간 순서대로 로그 결합
        for turn in sorted(turn_logs.keys()):
             # 턴 0 또는 기타 로그 먼저 표시 (선택적)
             # if turn == 0:
             #     full_log_text += "\n--- Game Setup/Misc Logs ---\n"
             # else:
             full_log_text += f"\n--- Turn {turn} ---\n"
             # 해당 턴의 로그 추가
             full_log_text += "\n".join(turn_logs[turn])
             full_log_text += "\n"


        final_status_summary = "\n--- Final Status ---\n"
        if hasattr(self, 'final_player_statuses'):
            for name, status_info in self.final_player_statuses.items():
                 final_status_summary += (
                     f"- {name}: Status={status_info['status']}, Stars={status_info['stars']}, "
                     f"Cards={status_info['cards']}, Money={status_info['money']}\n"
                 )
        else: # log_final_results가 호출되지 않은 경우 대비
             final_status_summary += "최종 상태 정보를 가져올 수 없습니다.\n"


        # 2. AI에게 보낼 프롬프트 구성
        narrative_prompt = f"""
        다음은 '한정 가위바위보' 게임 시뮬레이션의 상세 로그와 최종 결과입니다.
        당신은 이 게임의 모든 것을 지켜본 관찰자입니다. 아래 데이터를 바탕으로, 게임에서 벌어진 주요 사건, 플레이어들의 심리와 전략 변화, 결정적인 순간들을 포함하여, 마치 소설의 한 장면이나 흥미로운 분석 칼럼처럼 재구성해주세요.

        **게임 개요:**
        - 참가자: {list(self.players.keys())}
        - 시작 조건: 별 {config.INITIAL_STARS}개, 카드 종류별 {config.INITIAL_CARDS_EACH_TYPE}장씩. 일부 플레이어는 초기 대출금이 있음.
        - 목표: 제한 시간({config.MAX_TURNS*config.TIME_PER_TURN}분, {config.MAX_TURNS}턴) 내에 모든 카드를 소진하고 별 3개 이상을 보유하여 생존.
        - 주요 행동: 다른 플레이어와 1:1 가위바위보 게임 (승패에 따라 별 이동), 자원(별, 카드, 현금) 거래.

        **상세 게임 로그 (시간 순):**
        {full_log_text}

        **최종 결과:**
        {final_status_summary}

        **요청:**
        위 로그에 기록된 플레이어들의 행동과 명시된 'Reasoning'(이유/근거)을 적극적으로 활용하여, 각 플레이어의 의도와 게임의 흐름을 생생하게 묘사해주세요. 단순히 로그를 나열하는 것이 아니라, 인과 관계와 극적인 요소를 부각하여 전지적 시점에서 읽기 쉬운 글을 작성해야 합니다. 전체 게임을 아우르는 하나의 완성된 이야기나 칼럼 형식으로 만들어주세요.
        """

        # 3. OpenAI API 호출 (텍스트 생성 요청)
        try:
            logger.info("OpenAI API 호출하여 서사 요약 생성 요청 중...")
            response = client.chat.completions.create(
                model="gpt-4o", # 혹은 최신 GPT-4 모델
                messages=[
                    {"role": "system", "content": "당신은 복잡한 게임 로그를 분석하여 흥미로운 이야기나 칼럼으로 재구성하는 뛰어난 작가입니다."},
                    {"role": "user", "content": narrative_prompt}
                ],
                temperature=0.7, # 창의성을 위해 약간 높게 설정
                max_tokens=2048
            )

            narrative_summary = response.choices[0].message.content

            logger.info("--- AI 생성 서사 요약 ---")
            logger_final.info(narrative_summary)
            logger.info("--- 서사 요약 끝 ---")

        except Exception as e:
            logger.error(f"서사 요약 생성 중 오류 발생: {e}")
            print("\n[AI 서사 요약 생성에 실패했습니다.]")