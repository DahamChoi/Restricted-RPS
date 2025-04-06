from player.player import Player
from typing import List, Dict, Any, Optional
from custom_logger import logger
from openai_client import client
from config import config
import json
from game.game import Game

# --- Function Schemas (OpenAI Function Calling용) ---
functions_available_to_agent = [
    {
        "type": "function",
        "function": {
            "name": "propose_trade",
            "description": "다른 플레이어에게 자원 거래를 제안합니다. 각 항목은 자신이 제공할 것과 상대방에게 받을 것을 명시합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_player_name": {"type": "string", "description": "거래를 제안할 상대방 플레이어의 이름"},
                    "give_stars": {"type": "integer", "description": "내가 주려는 별의 개수", "default": 0},
                    "give_rock": {"type": "integer", "description": "내가 주려는 바위 카드의 개수", "default": 0},
                    "give_scissors": {"type": "integer", "description": "내가 주려는 가위 카드의 개수", "default": 0},
                    "give_paper": {"type": "integer", "description": "내가 주려는 보 카드의 개수", "default": 0},
                    "give_money": {"type": "integer", "description": "내가 주려는 현금", "default": 0},
                    "receive_stars": {"type": "integer", "description": "내가 받으려는 별의 개수", "default": 0},
                    "receive_rock": {"type": "integer", "description": "내가 받으려는 바위 카드의 개수", "default": 0},
                    "receive_scissors": {"type": "integer", "description": "내가 받으려는 가위 카드의 개수", "default": 0},
                    "receive_paper": {"type": "integer", "description": "내가 받으려는 보 카드의 개수", "default": 0},
                    "receive_money": {"type": "integer", "description": "내가 받으려는 현금", "default": 0},
                    "reasoning": {"type": "string", "description": "이 거래를 제안하는 이유 또는 전략적 판단."}
                },
                "required": ["target_player_name", "reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_match",
            "description": "다른 플레이어에게 가위바위보 게임을 제안하고 내가 낼 카드를 선택합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_player_name": {"type": "string", "description": "게임을 제안할 상대방 플레이어의 이름"},
                    "card_to_play": {"type": "string", "enum": ["rock", "scissors", "paper"], "description": "내가 이번 게임에 사용할 카드"},
                    "reasoning": {"type": "string", "description": "이 게임을 제안하고 이 카드를 선택한 이유 또는 전략적 판단."}
                },
                "required": ["target_player_name", "card_to_play", "reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "declare_out_of_game",
            "description": "생존 조건을 만족했을 때 게임에서 나가겠다고 선언합니다.",
             "parameters": {
                "type": "object",
                "properties": {
                     "reasoning": {"type": "string", "description": "게임에서 나가기로 결정한 이유."}
                },
                 "required": ["reasoning"]
             }
        }
    }
    #,
    #{
    #    "type": "function",
    #    "function": {
    #        "name": "do_nothing",
    #        "description": "이번 턴에는 아무 행동도 하지 않고 상황을 지켜봅니다.",
    #        "parameters": {
    #            "type": "object",
    #            "properties": {
    #                 "reasoning": {"type": "string", "description": "아무것도 하지 않기로 결정한 이유."}
    #            },
    #             "required": ["reasoning"]
    #         }
    #    }
    #}
]

# --- OpenAI Agent Class ---
class OpenAI_Agent:
    def __init__(self, player: Player, game: 'Game'):
        self.player = player
        self.game = game

    def decide_action(self) -> Optional[Dict[str, Any]]:
        """OpenAI API를 호출하여 플레이어의 다음 행동을 결정합니다."""
        logger.info(f"--- {self.player.name}'s Turn ---")

        # 1. 현재 상태 정보 수집
        my_items = self.player.get_items_dict()
        other_players_info = self.game.get_other_players_info(exclude_player_name=self.player.name)
        dashboard_info = self.game.get_dashboard_info()

        # 2. 프롬프트 구성
        messages = [
            {"role": "system", "content": self.player.persona_prompt + "\n\n" + self.game.get_game_rules_summary()},
            {"role": "user", "content": f"""
            ## 현재 당신의 상태 ({self.player.name})
            - 별: {my_items['star_number']}개
            - 카드: 바위 {my_items['rock_card_number']}장, 가위 {my_items['scissors_card_number']}장, 보 {my_items['paper_card_number']}장 (총 {self.player.get_total_cards()}장)
            - 현금: {my_items['money']} 엔 {'(초기 대출금 ' + str(self.player.initial_loan) + ' 엔 포함)' if self.player.initial_loan > 0 else ''}
            - 현재 상태: {self.player.status}

            ## 현재 게임 상황 (전광판)
            - 생존 플레이어 수: {dashboard_info['alive_users']}명
            - 남은 시간: {dashboard_info['remain_time']}분 ({self.game.current_turn}/{config.MAX_TURNS} 턴)
            - 전체 남은 카드: 바위 {dashboard_info['all_rock_card_number']}, 가위 {dashboard_info['all_scissors_card_number']}, 보 {dashboard_info['all_paper_card_number']}

            ## 다른 활성 플레이어 정보 (이름과 보유 별 개수만 공개됨)
            {json.dumps(other_players_info, indent=2, ensure_ascii=False) if other_players_info else "다른 활성 플레이어가 없습니다."}

            ## 당신의 목표
            - 제한 시간 안에 카드를 모두 소진하고, 별 3개 이상을 보유하여 생존하는 것입니다.
            - 다른 플레이어와 협상(거래)하거나 게임(가위바위보)을 할 수 있습니다.
            - 생존 조건을 만족하면 게임에서 나갈 수 있습니다 ('declare_out_of_game')
                - 만약 생존 조건보다 더 많은 별을 가지고 있다면 게임에 나가지 않고, 이를 다른 사람에게 팔아 이득을 취할 수도 있습니다.
            - 당신의 결정과 그 이유를 명확히 설명하고, 반드시 정의된 함수 중 하나를 호출하는 형식으로 응답해주세요.
            """}
            #             - 전략적으로 판단하여 이번 턴에 어떤 행동을 할지 결정하세요. 아무것도 하지 않을 수도 있습니다 ('do_nothing').
        ]

        logger.debug(f"Sending prompt to OpenAI for {self.player.name}:\n{json.dumps(messages, indent=2, ensure_ascii=False)}")

        try:
            response = client.chat.completions.create(
                model="gpt-4o", # 또는 사용 가능한 최신 모델
                messages=messages,
                tools=functions_available_to_agent,
                #tool_choice="auto", # OpenAI가 메시지에 따라 함수 호출 여부 결정
                tool_choice="required",
                # response_format={"type": "json_object"}, # 만약 전체 응답을 JSON으로 받고 싶다면 사용 (function calling과 함께는?)
                temperature=0.7 # 약간의 창의성 부여
            )
            response_message = response.choices[0].message
            logger.debug(f"Received response from OpenAI for {self.player.name}:\n{response_message}")

            tool_calls = response_message.tool_calls
            if tool_calls:
                # 함수 호출이 있는 경우
                function_call_data = tool_calls[0].function # 첫 번째 함수 호출만 처리한다고 가정
                function_name = function_call_data.name
                function_args = json.loads(function_call_data.arguments)
                reasoning = function_args.get("reasoning", "No reasoning provided.")

                logger.info(f"Player {self.player.name} decided to call function '{function_name}'. Reasoning: {reasoning}")
                self.player.action_log.append(f"Turn {self.game.current_turn}: Decided '{function_name}'. Reason: {reasoning}. Args: {function_args}")

                # Game Handler에게 처리 위임하기 위해 dict 형태로 반환
                return {
                    "function_name": function_name,
                    "arguments": function_args
                }
            else:
                # 함수 호출 없이 텍스트 응답만 온 경우 (예: do_nothing을 텍스트로 말한 경우)
                # 이 시나리오에서는 do_nothing 함수 호출을 기본으로 유도했으므로, 이 경우는 예외처리 또는 do_nothing으로 간주
                logger.warning(f"Player {self.player.name} did not return a function call. Interpreting as 'do_nothing'. Response: {response_message.content}")
                self.player.action_log.append(f"Turn {self.game.current_turn}: Decided 'do_nothing' (Implicit). Reason: No function call returned.")
                return {
                    "function_name": "do_nothing",
                    "arguments": {"reasoning": "AI did not explicitly call a function."}
                }

        except Exception as e:
            logger.error(f"Error calling OpenAI API for {self.player.name}: {e}")
            # API 오류 시 안전하게 do_nothing 처리
            self.player.action_log.append(f"Turn {self.game.current_turn}: Action failed due to API error. Defaulting to 'do_nothing'.")
            return {
                    "function_name": "do_nothing",
                    "arguments": {"reasoning": "API call failed."}
                }