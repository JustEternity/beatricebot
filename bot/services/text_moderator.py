import re
import logging
from typing import Tuple, Dict, Any
import os

# Принудительно отключаем GPU и оптимизации для Mac
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

logger = logging.getLogger(__name__)

class TextModerator:
    def __init__(self, use_ai_model: bool = False):
        """
        :param use_ai_model: Флаг использования нейросетевой модели токсичности
        """
        self.use_ai_model = use_ai_model
        self.toxicity_model = None
        self._init_dictionaries()
        self.toxicity_threshold = 0.85

        if self.use_ai_model:
            self._load_ai_model()

    def _load_ai_model(self):
        """Ленивая инициализация нейросетевой модели"""
        try:
            from transformers import pipeline
            self.toxicity_model = pipeline(
                "text-classification",
                model="SkolkovoInstitute/russian_toxicity_classifier",
                device="cpu",
                framework="tf"
            )
        except ImportError:
            logger.error("Transformers not installed, AI model disabled")
            self.use_ai_model = False
        except Exception as e:
            logger.error(f"AI model init error: {str(e)}")
            self.use_ai_model = False

    def _init_dictionaries(self):
        """Инициализация словарей для модерации"""
        self.toxic_words = {
            'уёбище', 'дебил', 'идиот', 'дурак', 'мудак', 'пидор', 'говно',
            'сука', 'блядь', 'хуй', 'пизда', 'ебан', 'заеб', 'падла', 'тварь',
            'даун', 'далбоеб', 'ублюдок', 'педик', 'гей', 'лесби', 'транс'
        }

        self.toxic_phrases = {
            'ёп твою', 'твою мать', 'твою налево', 'иди нахуй', 'пошёл нахуй',
            'иди в жопу', 'иди в пизду', 'соси хуй', 'ёб твою'
        }

        self.ad_keywords = {
            'купи', 'куплю', 'продам', 'продаю', 'закажи', 'скидка',
            'акция', 'распродажа', 'спецпредложение', 'промокод',
            'http', 'https', 'www', '.ru', '.com', 't.me'
        }

        self.extremism_dict = {
            'убей', 'убийство', 'убийца', 'казнить', 'расстрелять',
            'взорвать', 'взрыв', 'террорист', 'фашист', 'нацист',
            'джихад', 'шахид', 'исламское государство', 'смерть неверным'
        }

        self.safe_extremism_context = {
            'борьба с терроризмом', 'против экстремизма',
            'осуждение насилия', 'против расизма', 'экстремист', 'расист', 'расик'
        }

        self.alcohol_words = {
            'алкоголь', 'пиво', 'водка', 'вино', 'коньяк', 'пьянка', 'запой'
        }

        self.drug_words = {
            'наркотик', 'героин', 'кокаин', 'метамфетамин', 'марихуана', 'наркотики', 'гашиш', 'drug', 'drugs'
        }

    def _contains_phrase(self, text: str, phrases: set) -> bool:
        """Проверяет наличие фразы в тексте"""
        lower_text = text.lower()
        return any(re.search(r'\b' + re.escape(phrase) + r'\b', lower_text)
               for phrase in phrases)

    def check_toxicity(self, text: str) -> Dict[str, Any]:
        """Проверка токсичности текста"""
        lower_text = text.lower()

        # Проверка по черным спискам
        if any(re.search(r'\b' + re.escape(word) + r'\b', lower_text)
           for word in self.toxic_words):
            return {'is_toxic': True, 'score': 0.99, 'method': 'word_list'}

        if self._contains_phrase(text, self.toxic_phrases):
            return {'is_toxic': True, 'score': 0.97, 'method': 'phrase'}

        # Проверка нейросетевой моделью (если доступна)
        if self.use_ai_model and self.toxicity_model:
            try:
                result = self.toxicity_model(text)[0]
                return {
                    'is_toxic': result['label'] == 'toxic'
                              and result['score'] > self.toxicity_threshold,
                    'score': result['score'],
                    'method': 'model'
                }
            except Exception as e:
                logger.error(f"Toxicity model error: {str(e)}")

        return {'is_toxic': False, 'score': 0.0, 'method': 'basic'}

    def check_advertisement(self, text: str) -> Dict[str, Any]:
        """Проверка на рекламу"""
        lower_text = text.lower()
        found_keywords = [word for word in self.ad_keywords
                         if re.search(r'\b' + re.escape(word) + r'\b', lower_text)]

        return {
            'is_ad': len(found_keywords) >= 2,
            'score': 0.95 if len(found_keywords) >= 2 else 0.0,
            'method': 'keywords',
            'found': found_keywords
        }

    def check_substances(self, text: str) -> Dict[str, Any]:
        """Проверка упоминаний веществ"""
        lower_text = text.lower()
        alcohol = any(re.search(r'\b' + re.escape(word) + r'\b', lower_text)
                     for word in self.alcohol_words)
        drugs = any(re.search(r'\b' + re.escape(word) + r'\b', lower_text)
                    for word in self.drug_words)

        return {
            'has_substances': alcohol or drugs,
            'score': 0.95 if alcohol or drugs else 0.0,
            'method': 'word_list'
        }

    def check_extremism(self, text: str) -> Dict[str, Any]:
        """Проверка экстремизма"""
        if self._contains_phrase(text, self.safe_extremism_context):
            return {'is_extremist': False, 'score': 0.0, 'method': 'safe_context'}

        found_phrases = [phrase for phrase in self.extremism_dict
                        if self._contains_phrase(text, {phrase})]

        return {
            'is_extremist': len(found_phrases) > 0,
            'score': min(0.9 + 0.02 * len(found_phrases), 1.0),
            'method': 'word_list',
            'found': found_phrases
        }

    def validate_text(self, text: str) -> Tuple[bool, str]:
        """Основной метод валидации текста"""
        if len(text) < 2:
            return False, "⚠️ Текст слишком короткий"

        if len(text) > 500:
            return False, "⚠️ Текст слишком длинный (макс. 500 символов)"

        results = {
            'toxicity': self.check_toxicity(text),
            'advertisement': self.check_advertisement(text),
            'substances': self.check_substances(text),
            'extremism': self.check_extremism(text)
        }

        if not all([
            not results['toxicity']['is_toxic'],
            not results['advertisement']['is_ad'],
            not results['substances']['has_substances'],
            not results['extremism']['is_extremist']
        ]):
            reasons = []
            if results['toxicity']['is_toxic']:
                reasons.append("токсичное содержание")
            if results['advertisement']['is_ad']:
                reasons.append("реклама")
            if results['substances']['has_substances']:
                reasons.append("запрещенные вещества")
            if results['extremism']['is_extremist']:
                reasons.append("экстремизм")

            return False, f"⚠️ Текст содержит: {', '.join(reasons)}"

        return True, "✅ Текст соответствует правилам"