import logging
import os
from logging.handlers import RotatingFileHandler

class Logger:
    def __init__(self,
                 name: str = __name__,
                 log_dir: str = 'logs',
                 log_file: str = None,
                 level: int = logging.INFO,
                 max_bytes: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5):
        """
        범용 로거 클래스

        :param name: 로거 이름
        :param log_dir: 로그 파일 저장 디렉토리
        :param log_file: 로그 파일 이름 (기본값은 name.log)
        :param level: 로그 레벨 (e.g., logging.DEBUG)
        :param max_bytes: 로그 파일 최대 크기 (바이트 단위)
        :param backup_count: 백업할 로그 파일 개수
        """
        self.name = name
        self.log_dir = log_dir
        self.log_file = log_file or f'{name}.log'  # name을 기반으로 파일명 지정
        self.level = level
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        self._logger = self._create_logger()

    def _create_logger(self) -> logging.Logger:
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)

        if not logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # 파일 핸들러 (회전 기능 포함)
            file_path = os.path.join(self.log_dir, self.log_file)
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def __getattr__(self, item):
        """
        logger.info, logger.debug 등을 바로 쓸 수 있도록 위임
        """
        return getattr(self._logger, item)
