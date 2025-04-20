from custom_logger import logger
from game.game import Game
from config import config
from config import persona

# --- 시뮬레이션 실행 ---
if __name__ == "__main__":
    # 플레이어 설정
    player_configurations = [
        {"name": "카이지", "persona": persona.kaiji_persona, "loan": 3000000},
        {"name": "안도", "persona": persona.ando_persona, "loan": 3000000},
        {"name": "후루하타", "persona": persona.huruhata_persona, "loan": 3000000},
        {"name": "키타미", "persona": persona.kitami_persona, "loan": 3000000},
        {"name": "후나이", "persona": persona.funai_persona, "loan": 3000000},
#        {"name": "사카자키", "persona": persona.sakazaki_persona, "loan": 3000000},
#        {"name": "이시다", "persona": persona.ishida_persona, "loan": 3000000},
#        {"name": "니시노", "persona": persona.nishino_persona, "loan": 3000000},
#        {"name": "오오츠키", "persona": persona.ohtsuki_persona, "loan": 3000000},
#        {"name": "마키타", "persona": persona.makita_persona, "loan": 3000000},        
    ]
    if len(player_configurations) != config.TOTAL_PLAYERS:
        logger.warning(f"Number of player configurations ({len(player_configurations)}) does not match TOTAL_PLAYERS ({config.TOTAL_PLAYERS}). Adjusting TOTAL_PLAYERS.")
        TOTAL_PLAYERS = len(player_configurations)

    # 게임 인스턴스 생성 및 실행
    game = Game(player_configurations)
    game.run_simulation()

    # --- 시뮬레이션 종료 후 서사 요약 생성 호출 추가 ---
    if game.game_over:
        # 최종 결과 로그가 먼저 기록되도록 보장 (선택적이지만 권장)
        if not hasattr(game, 'final_player_statuses'):
             game.log_final_results() # 아직 호출되지 않았다면 호출

        # AI에게 요약 생성 요청
        game.generate_narrative_summary()
    else:
        logger.warning("시뮬레이션이 정상적으로 종료되지 않아 서사 요약을 생성할 수 없습니다.")

