from cryptography.fernet import Fernet, InvalidToken
import os
import logging
from typing import Union

class CryptoService:
    def __init__(self, secret_key: str):
        self.cipher = Fernet(secret_key.encode())

    def encrypt(self, data: str) -> bytes:
        """Шифрование текстовых данных"""
        try:
            return self.cipher.encrypt(data.encode())
        except Exception as e:
            logging.error(f"Encryption error: {e}")
            raise

    def decrypt(self, encrypted_data: Union[bytes, str]) -> str:
        """Дешифрование данных с обработкой разных типов ввода"""
        try:
            if isinstance(encrypted_data, str):
                encrypted_data = encrypted_data.encode()

            return self.cipher.decrypt(encrypted_data).decode()
        except InvalidToken:
            logging.error("Decryption failed - invalid token")
            raise
        except Exception as e:
            logging.error(f"Decryption error: {e}")
            raise

    @staticmethod
    def generate_key() -> str:
        """Генерация нового ключа (для первоначальной настройки)"""
        return Fernet.generate_key().decode()
