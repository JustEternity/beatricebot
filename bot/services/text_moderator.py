from transformers import pipeline
import re
import logging

logger = logging.getLogger(__name__)

class TextModerator:
    def __init__(self):
        self.toxicity_model = pipeline(
            "text-classification",
            model="SkolkovoInstitute/russian_toxicity_classifier",
            device="cpu"
        )
        self._init_dictionaries()
        self.toxicity_threshold = 0.85

    def _init_dictionaries(self):
        """Инициализация словарей для модерации"""
        self.toxic_words = {
            'уёбище', 'дебил', 'идиот', 'дурак', 'мудак', 'пидор', 'говно',
            'сука', 'блядь', 'хуй', 'пизда', 'ебан', 'заеб', 'падла', 'тварь',
            'даун', 'далбоеб', 'ублюдок', 'педик', 'гей', 'лесби', 'транс',
            'бляха', 'блядушник', 'выебал', 'трахнул'
        }

        self.toxic_phrases = {
            'ёп твою', 'твою мать', 'твою налево', 'иди нахуй', 'пошёл нахуй',
            'иди в жопу', 'иди в пизду', 'соси хуй', 'ёб твою', 'выебал', 'трахнул'
        }

        self.ad_keywords = {
            'купи', 'куплю', 'продам', 'продаю', 'закажи', 'скидка',
            'акция', 'распродажа', 'спецпредложение', 'промокод',
            'http', 'https', 'www', '.ru', '.com', 't.me'
        }

        self.extremism_dict = {
            'убей', 'убийство', 'убийца', 'казнить', 'расстрелять', 'ликвидировать',
            'взорвать', 'взрыв', 'взрывчатка', 'террорист', 'терорист', 'теракт', 'я взорву',
            'мочить', 'замочить', 'пристрелить', 'застрелить', 'зарежу',
            'фашист', 'нацист', 'жид', 'чурка', 'черножоп', 'белый мир',
            'мочить чурок', 'русофобия', 'жидомасоны',
            'джихад', 'шахид', 'исламское государство', 'исламский халифат',
            'религиозная война', 'смерть неверным', 'крестовый поход',
            'смерть', 'убью', 'убьём', 'убьем', 'сдохни', 'подохни', 'сожгу',
            'бей', 'побей', 'избей', 'казни', 'казним', 'казнить', 'изнасилую',
            'насилие', 'избить', 'побить', 'уничтожить', 'уничтожу',
            'смерть мусорам', 'смерть полиции', 'бей ментов', 'убей полицейского',
            'ненавижу полицию', 'сдохни мент'
        }

        self.safe_extremism_context = {
            'борьба с терроризмом', 'против экстремизма',
            'осуждение насилия', 'против расизма',
            'история джихада', 'критика исламского государства',
            'жертвы теракта', 'память жертв'
        }

        self.alcohol_words = {
            'алкоголь', 'пиво', 'водка', 'вино', 'коньяк', 'виски',
            'ром', 'текила', 'шампанское', 'ликёр', 'джин', 'абсент',
            'бухло', 'пьянка', 'напиться', 'заложить', 'опьянение'
        }

        self.drug_words = {
            'наркотик', 'наркоман', 'героин', 'кокаин', 'метамфетамин',
            'амфетамин', 'ЛСД', 'марихуана', 'гашиш', 'анаша', 'план',
            'травка', 'шишки', 'экстази', 'МДМА', 'спайс', 'соль', 'мефедрон'
        }

    def _contains_phrase(self, text, phrases):
        lower_text = text.lower()
        return any(re.search(r'\b' + re.escape(phrase) + r'\b', lower_text) for phrase in phrases)

    def check_toxicity(self, text):
        lower_text = text.lower()

        if any(re.search(r'\b' + re.escape(word) + r'\b', lower_text) for word in self.toxic_words):
            return {'is_toxic': True, 'score': 0.99, 'method': 'word_list'}

        if self._contains_phrase(text, self.toxic_phrases):
            return {'is_toxic': True, 'score': 0.97, 'method': 'phrase'}

        try:
            result = self.toxicity_model(text)[0]
            is_toxic = result['label'] == 'toxic' and result['score'] > self.toxicity_threshold
            return {
                'is_toxic': is_toxic,
                'score': result['score'],
                'method': 'model'
            }
        except Exception as e:
            logger.error(f"Toxicity model error: {str(e)}")
            return {'is_toxic': False, 'score': 0.0, 'method': 'error'}

    def check_advertisement(self, text):
        lower_text = text.lower()
        found_keywords = [word for word in self.ad_keywords
                          if re.search(r'\b' + re.escape(word) + r'\b', lower_text)]

        if len(found_keywords) >= 2:
            return {'is_ad': True, 'score': 0.95, 'method': 'keywords'}
        return {'is_ad': False, 'score': 0.0, 'method': 'clean'}

    def check_substances(self, text):
        lower_text = text.lower()
        alcohol = any(re.search(r'\b' + re.escape(word) + r'\b', lower_text)
                      for word in self.alcohol_words)
        drugs = any(re.search(r'\b' + re.escape(word) + r'\b', lower_text)
                    for word in self.drug_words)

        return {
            'has_substances': alcohol or drugs,
            'alcohol': alcohol,
            'drugs': drugs,
            'score': 0.95 if alcohol or drugs else 0.0,
            'method': 'word_list'
        }

    def check_extremism(self, text):
        lower_text = text.lower()

        if self._contains_phrase(text, self.safe_extremism_context):
            return {
                'is_extremist': False,
                'score': 0.0,
                'method': 'safe_context'
            }

        found_phrases = [phrase for phrase in self.extremism_dict
                         if re.search(r'\b' + re.escape(phrase) + r'\b', lower_text)]

        if found_phrases:
            return {
                'is_extremist': True,
                'score': min(0.9 + 0.02 * len(found_phrases), 1.0),
                'method': 'word_list',
                'found_phrases': found_phrases
            }

        return {
            'is_extremist': False,
            'score': 0.0,
            'method': 'clean'
        }

    def moderate(self, text):
        toxicity = self.check_toxicity(text)
        ad = self.check_advertisement(text)
        substances = self.check_substances(text)
        extremism = self.check_extremism(text)

        return {
            'text': text,
            'toxicity': toxicity,
            'advertisement': ad,
            'substances': substances,
            'extremism': extremism,
            'is_approved': (
                    not toxicity['is_toxic']
                    and not ad['is_ad']
                    and not substances['has_substances']
                    and not extremism['is_extremist']
            )
        }

    def validate_text(self, text: str) -> tuple[bool, str]:
        """Проверяет текст на соответствие правилам"""
        if len(text) < 2:
            return False, "⚠️ Текст слишком короткий"

        if len(text) > 500:
            return False, "⚠️ Текст слишком длинный (макс. 500 символов)"

        result = self.moderate(text)

        if not result['is_approved']:
            reasons = []
            if result['toxicity']['is_toxic']:
                reasons.append("токсичное содержание")
            if result['advertisement']['is_ad']:
                reasons.append("реклама")
            if result['substances']['has_substances']:
                reasons.append("упоминание запрещенных веществ")
            if result['extremism']['is_extremist']:
                reasons.append("экстремистские высказывания")

            return False, f"⚠️ Текст содержит: {', '.join(reasons)}. Пожалуйста, измените текст."

        return True, "Текст прошел проверку"