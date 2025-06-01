from player.player import Player
from typing import List, Dict, Any, Optional
from custom_logger import logger
from openai_client import client
from config import config
from game.game import get_stats_prompt
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
                    "internal_reasoning": {"type": "string", "description": "이 거래를 제안하는 실제 이유 또는 전략적 판단 (내부 기록용)."},
                    "public_reasoning": {"type": "string", "description": "거래를 제안하며 상대방에게 전달할 메시지."}
                },
                "required": ["target_player_name", "internal_reasoning", "public_reasoning"]
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
                    "internal_reasoning": {"type": "string", "description": "이 게임을 제안하고 이 카드를 선택한 실제 이유 또는 전략적 판단 (내부 기록용)."},
                    "public_reasoning": {"type": "string", "description": "게임을 제안하며 상대방에게 전달할 메시지."}
                },
                "required": ["target_player_name", "card_to_play", "internal_reasoning", "public_reasoning"]
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
    ,
    {
        "type": "function",
        "function": {
            "name": "do_nothing",
            "description": "이번 턴에는 아무 행동도 하지 않고 상황을 지켜봅니다.",
            "parameters": {
                "type": "object",
                "properties": {
                     "internal_reasoning": {"type": "string", "description": "아무것도 하지 않기로 결정한 이유."}
                },
                 "required": ["internal_reasoning"]
             }
        }
    }
]
        
# --- OpenAI Agent Class ---
class OpenAI_Agent:
    def __init__(self, player: Player, game: 'Game'):
        self.player = player
        self.game = game

        self.update_current_emotion()

    def update_current_emotion(self):
        emotion_prompt = [
            {"role": "system", "content": self.player.persona_prompt + "\n\n" + self.game.get_game_rules_summary()},
            {
                "role": "system",
                "content": (
                    "현재 나의 기록과 상황을 읽고, 내가 지금 느낄 법한 감정을 **한 문장**으로 묘사하세요. "
                    "반드시 한 문장만 출력하고, 불필요한 설명이나 따옴표는 넣지 마세요."
                )
            },
            {
                "role": "user",
                "content": f"""
                다음 기록을 참고하여 현재 감정을 한 문장으로 표현하세요

                {get_stats_prompt(self.game, self.player)}
                """
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",   # 비용 절감을 위해 경량화 모델 사용
            messages=emotion_prompt,
            temperature=0          # 감정 추출이므로 0
        )

        self.player.current_emotion = response.choices[0].message.content.strip()
        self.player.action_log.append(f"Update Current Emotion : {self.player.current_emotion}")
        logger.info(f"Update Player {self.player.name} Emotion : {self.player.current_emotion}")

    def decide_action(self) -> Optional[Dict[str, Any]]:
        """OpenAI API를 호출하여 플레이어의 다음 행동을 결정합니다."""
        logger.info(f"--- {self.player.name}'s Turn ---")

        # 프롬프트 구성
        messages = [
            {"role": "system", "content": self.player.persona_prompt + "\n\n" + self.game.get_game_rules_summary()},
            {"role": "system", "content": "감정에 따라 과감한 결정을 내리십시오."},
            {"role": "user", "content": f"""
            {get_stats_prompt(self.game, self.player)}

            ## 당신의 목표
            - 제한 시간 안에 카드를 모두 소진하고, 별 3개 이상을 보유하여 생존하는 것입니다.
            - 다른 플레이어와 협상(거래)하거나 게임(가위바위보)을 할 수 있습니다.
            - 생존 조건을 만족하면 게임에서 나갈 수 있습니다 ('declare_out_of_game')
                - 만약 생존 조건보다 더 많은 별을 가지고 있다면 게임에 나가지 않고, 이를 다른 사람에게 팔아 이득을 취할 수도 있습니다.
            - 당신의 결정과 그 이유를 명확히 설명하고, 반드시 정의된 함수 중 하나를 호출하는 형식으로 응답해주세요.
            - **주의:** 거래나 게임 제안 시, `internal_reasoning`에는 당신의 실제 전략과 판단을 상세히 기록하고, `public_reasoning`에는 상대방에게 보여줄 간결하고 설득력 있는 메시지를 작성하세요. (예: "이 거래는 우리 모두에게 이득이 될 것입니다." 또는 "카드 소진을 위해 게임이 필요합니다.")
            - 전략적으로 판단하여 이번 턴에 어떤 행동을 할지 결정하세요. 아무것도 하지 않을 수도 있습니다 ('do_nothing').
            """}
        ]

        logger.debug(f"Sending prompt to OpenAI for {self.player.name}:\n{json.dumps(messages, indent=2, ensure_ascii=False)}")

        try:
            response = client.chat.completions.create(
                model="gpt-4.1", # 또는 사용 가능한 최신 모델
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
                internal_reasoning = function_args.get("internal_reasoning", "No internal reasoning provided.")
                public_reasoning = function_args.get("public_reasoning", "No public reasoning provided.")
                # declare_out_of_game 에는 reasoning 만 있음
                if function_name == "declare_out_of_game":
                    internal_reasoning = function_args.get("reasoning", "No reasoning provided.")
                    public_reasoning = internal_reasoning # 공개 이유와 내부 이유 동일 처리

                logger.info(f"Player {self.player.name} decided to call function '{function_name}'.")
                logger.info(f"  - Internal Reasoning: {internal_reasoning}")
                if function_name != "declare_out_of_game": # declare 외에는 public reasoning 로깅
                     logger.info(f"  - Public Reasoning: {public_reasoning}")

                # 로그에는 상세 정보 포함
                self.player.action_log.append(f"Turn {self.game.current_turn}: Decided '{function_name}'. Internal Reason: {internal_reasoning}. Args: {function_args}")

                # Game Handler에게 처리 위임하기 위해 dict 형태로 반환
                # game.py 에서는 public_reasoning 만 필요로 함
                # 하지만 로그 등을 위해 둘 다 포함시킬 수 있음, 여기서는 일단 둘 다 포함
                action_result = {
                    "function_name": function_name,
                    "arguments": function_args,
                    "internal_reasoning": internal_reasoning,
                    "public_reasoning": public_reasoning
                }
                # declare_out_of_game 일 경우 reasoning을 public_reasoning으로 통일
                if function_name == "declare_out_of_game":
                    action_result["public_reasoning"] = internal_reasoning

                return action_result
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