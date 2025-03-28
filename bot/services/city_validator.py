import json
import os
from pathlib import Path
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class CityValidator:
    def __init__(self, cities_file: str = None):
        self.cities_file = cities_file or str(Path(__file__).parent / 'cities.json')
        self.cities = {}
        self.last_modified = 0  # Инициализируем атрибут
        self.synonyms = {
            "спб": "санкт-петербург",
            "питер": "санкт-петербург",
            "нск": "новосибирск"
        }
        self.load_cities()

    def load_cities(self):
        """Загрузка и обновление списка городов"""
        try:
            current_mtime = os.path.getmtime(self.cities_file)
            if current_mtime != self.last_modified:
                with open(self.cities_file, 'r', encoding='utf-8') as f:
                    self.cities = json.load(f)
                self.last_modified = current_mtime
                logger.info(f"Loaded {len(self.cities)} cities")
        except Exception as e:
            logger.error(f"Error loading cities: {e}")
            self.cities = {}

    def normalize_name(self, name: str) -> str:
        """Нормализация названия города"""
        name = name.strip().lower()
        return self.synonyms.get(name, name)

    def validate_city(self, city_name: str) -> Tuple[bool, Optional[str]]:
        """Проверка и нормализация города"""
        self.load_cities()  # Проверяем обновления файла

        normalized = self.normalize_name(city_name)
        if normalized in self.cities:
            return True, self.cities[normalized]

        # Проверка частичных совпадений
        for city_key in self.cities:
            if normalized in city_key:
                return True, self.cities[city_key]

        return False, None


# Глобальный экземпляр
city_validator = CityValidator()