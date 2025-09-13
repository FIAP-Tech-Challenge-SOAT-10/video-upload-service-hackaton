# app/domain/repositories/video_repository_interface.py
from abc import ABC, abstractmethod
from typing import Optional


class IVideoRepository(ABC):
    """Contrato para persistência de vídeos"""

    @abstractmethod
    def put(self, item: dict) -> None:
        """Insere um novo vídeo"""
        pass

    @abstractmethod
    def get(self, id_video: str) -> Optional[dict]:
        """Busca um vídeo pelo ID"""
        pass

    @abstractmethod
    def update_status(self, id_video: str, status: str) -> None:
        """Atualiza o status de um vídeo"""
        pass
