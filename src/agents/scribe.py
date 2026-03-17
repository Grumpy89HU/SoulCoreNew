"""
Scribe (Írnok) - A rendszer füle és szeme.
Minden bejövő üzenetet ő értelmez, kinyeri a szándékot és az entitásokat.
Nem generál választ, csak megérti, hogy MIT akar a felhasználó.
"""

import re
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

class Scribe:
    """
    Az Írnok feladata:
    1. Entitások kinyerése (ki, mit, mikor, hol)
    2. Szándék osztályozás (mit akar a felhasználó)
    3. Belső fordítás (magyar/angol mondat -> szemantikai lekérdezés)
    4. Toxicitás/veszély szűrés
    """
    
    # Szándék kategóriák és kulcsszavaik (többnyelvű)
    INTENT_PATTERNS = {
        'greeting': [
            r'\b(?:hello|hi|hey|good\s+morn(?:ing)?|good\s+afternoon|good\s+evening)\b',
            r'\b(?:szia|szép\s+napot|jó\s+reggelt|jó\s+napot|jó\s+estét|üdv)\b'
        ],
        'farewell': [
            r'\b(?:bye|goodbye|see\s+you|talk\s+to\s+you\s+later)\b',
            r'\b(?:viszlát|szia|később|majd\s+beszélünk)\b'
        ],
        'question': [
            r'\b(?:what|who|where|when|why|how|can\s+you|do\s+you)\b',
            r'\b(?:mi|ki|hol|mikor|hogyan|miért|tudsz-e|tudod-e)\b',
            r'\?$'
        ],
        'command': [
            r'\b(?:do|make|create|write|show|tell|give|help)\b',
            r'\b(?:csináld|írd|mutasd|mondd|adj|segíts)\b'
        ],
        'system_control': [
            r'\b(?:stop|exit|quit|shutdown|restart|reload)\b',
            r'\b(?:állj\s+le|lépj\s+ki|kapcsolj\s+ki|indítsd\s+újra)\b'
        ],
        'knowledge_retrieval': [
            r'\b(?:what\s+is|tell\s+me\s+about|explain|define|what\s+are)\b',
            r'\b(?:mi\s+az|mesélj\s+erről|magyarázd\s+el|definiáld)\b'
        ],
        'proactive': [
            r'\b(?:remind|reminder|remember|remind\s+me)\b',
            r'\b(?:emlékeztess|emlékeztető|jegyezd\s+meg)\b'
        ]
    }
    
    # Entitás minták (többnyelvű)
    ENTITY_PATTERNS = {
        'PERSON': [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        ],
        'DATE': [
            r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',  # 2025-03-17
            r'\b\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\b',  # 2025. 03. 17.
            r'\b(?:today|tomorrow|yesterday|next\s+\w+|last\s+\w+)\b',
            r'\b(?:ma|holnap|tegnap|jövő\s+\w+|múlt\s+\w+)\b'
        ],
        'TIME': [
            r'\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b',
            r'\b\d{1,2}[:.]\d{2}\s*(?:órakor)?\b'
        ],
        'FILE': [
            r'\b[\w\-]+\.(?:txt|py|js|json|yaml|yml|md|log|csv|pdf|docx?|xlsx?)\b'
        ],
        'PATH': [
            r'(?:/[^/\s]+)+/?',
            r'(?:[A-Za-z]:\\[^\\]+)+',
            r'\.\.?/[^/\s]+'
        ],
        'URL': [
            r'https?://[^\s]+',
            r'www\.[^\s]+'
        ],
        'EMAIL': [
            r'[\w\.-]+@[\w\.-]+\.\w+'
        ],
        'NUMBER': [
            r'\b\d+(?:\.\d+)?\b'
        ],
        'CURRENCY': [
            r'\b\d+\s*(?:USD|EUR|HUF|GBP|JPY|CNY|RUB|Ft|\$|€|£|¥)\b',
            r'\b(?:USD|EUR|HUF|GBP|JPY|CNY|RUB|Ft|\$|€|£|¥)\s*\d+\b'
        ]
    }
    
    def __init__(self, scratchpad):
        self.scratchpad = scratchpad
        self.name = "scribe"
        
        # Fordító (később állítjuk be)
        self.translator = None
        
        # Statisztikák
        self.stats = {
            'processed': 0,
            'intents': defaultdict(int),
            'entities': defaultdict(int),
            'errors': 0,
            'avg_confidence': 0
        }
        
        # Regisztráció a memóriában
        self.scratchpad.write_note(self.name, 'status', 'initialized')
        self.scratchpad.write_note(self.name, 'last_intent', None)
        
        print("📜 Scribe: Írnok ébred. Figyelek a szavakra.")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n-hez)"""
        if self.translator:
            self.translator.set_language(language)
    
    def start(self):
        """Scribe indítása (passzív, csak hívásra dolgozik)"""
        self.scratchpad.set_state('scribe_status', 'ready', self.name)
        self.scratchpad.write(self.name, "Scribe ready", 'status')
    
    def stop(self):
        """Scribe leállítása"""
        self.scratchpad.set_state('scribe_status', 'stopped', self.name)
        print("📜 Scribe: Írnok elhallgat.")
    
    def process(self, text: str, source: str = "user") -> Dict[str, Any]:
        """
        Bemeneti szöveg feldolgozása.
        Visszaad egy intent csomagot, amit a többi modul használhat.
        """
        self.stats['processed'] += 1
        
        # Bejövő üzenet naplózása
        self.scratchpad.write(self.name, {
            'source': source,
            'raw_text': text[:200]
        }, 'raw_input')
        
        # 1. Előfeldolgozás
        cleaned_text = self._preprocess(text)
        
        # 2. Entitások kinyerése
        entities = self._extract_entities(cleaned_text)
        
        # 3. Szándék osztályozás
        intent_class, confidence = self._classify_intent(cleaned_text)
        
        # 4. Belső fordítás (ha kell)
        semantic_query = self._translate_to_semantic(cleaned_text, intent_class, entities)
        
        # 5. Toxicitás/veszély szűrés
        is_safe, safety_note, safety_score = self._safety_check(cleaned_text, intent_class)
        
        # Statisztika frissítés
        self.stats['intents'][intent_class] += 1
        self.stats['entities'][len(entities)] += 1
        
        # Mozgóátlag confidence
        if self.stats['avg_confidence'] == 0:
            self.stats['avg_confidence'] = confidence
        else:
            self.stats['avg_confidence'] = self.stats['avg_confidence'] * 0.9 + confidence * 0.1
        
        # Eredmény összeállítása
        result = {
            'intent': {
                'class': intent_class,
                'confidence': round(confidence, 2),
                'original_text': text[:500]
            },
            'entities': entities,
            'semantic_query': semantic_query,
            'safety': {
                'is_safe': is_safe,
                'score': safety_score,
                'note': safety_note
            },
            'source': source,
            'timestamp': time.time(),
            'processed_text': cleaned_text[:500]
        }
        
        # Memorizálás
        self.scratchpad.write_note(self.name, 'last_intent', result)
        self.scratchpad.write(self.name, result, 'intent')
        
        return result
    
    def _preprocess(self, text: str) -> str:
        """
        Szöveg előfeldolgozása (kisbetűsítés, írásjelek eltávolítása).
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Kisbetűsítés (de megtartjuk az eredeti verziót is)
        text_lower = text.lower()
        
        # Többszörös szóközök eltávolítása
        text_lower = re.sub(r'\s+', ' ', text_lower).strip()
        
        return text_lower
    
    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """
        Entitások kinyerése a szövegből.
        """
        entities = []
        
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                try:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        # Csak értelmes hosszúságú entitásokat veszünk
                        value = match.group(0)
                        if len(value) > 1 and len(value) < 100:
                            entities.append({
                                'type': entity_type,
                                'value': value,
                                'position': match.span()
                            })
                except:
                    continue
        
        # Duplikátumok eltávolítása (ugyanaz az érték, típus)
        unique = []
        seen = set()
        for e in entities:
            key = f"{e['type']}:{e['value']}"
            if key not in seen:
                seen.add(key)
                # pozíciót eltávolítjuk a véglegesből (nem kell kimenetre)
                e_copy = e.copy()
                del e_copy['position']
                unique.append(e_copy)
        
        return unique
    
    def _classify_intent(self, text: str) -> Tuple[str, float]:
        """
        Szándék osztályozás (0.0-1.0 közötti biztonsággal).
        """
        # Alapértelmezett: ismeretlen
        best_intent = 'unknown'
        best_score = 0.0
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            intent_score = 0.0
            pattern_count = 0
            
            for pattern in patterns:
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        pattern_count += 1
                except:
                    continue
            
            if pattern_count > 0:
                # Minél több minta illeszkedik, annál biztosabbak vagyunk
                intent_score = min(0.9, 0.5 + (pattern_count * 0.1))
                
                if intent_score > best_score:
                    best_intent = intent
                    best_score = intent_score
        
        # Speciális eset: kérdőjel erősíti a question-t
        if '?' in text and best_intent != 'question' and best_score < 0.8:
            best_intent = 'question'
            best_score = max(best_score, 0.6)
        
        return best_intent, best_score
    
    def _translate_to_semantic(self, text: str, intent: str, entities: List) -> str:
        """
        Bemeneti szöveg átalakítása szemantikai lekérdezéssé.
        Ez lesz a Valet keresési kulcsa.
        """
        # Eltávolítjuk a kérdőszavakat
        question_words = [
            r'\bwhat\b', r'\bwho\b', r'\bwhere\b', r'\bwhen\b', r'\bwhy\b', r'\bhow\b',
            r'\bmi\b', r'\bki\b', r'\bhol\b', r'\bmikor\b', r'\bmiért\b', r'\bhogyan\b'
        ]
        
        clean_text = text
        for pattern in question_words:
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        clean_text = clean_text.replace('?', '').strip()
        
        # Ha van entitás, használjuk azokat
        entity_values = [e['value'] for e in entities if e['type'] in ['PERSON', 'FILE', 'PATH', 'URL']]
        
        if entity_values:
            main_entity = entity_values[0]
            if intent == 'question':
                return f"search: {main_entity} {clean_text}"
            elif intent == 'command':
                return f"action: {main_entity}"
            else:
                return f"query: {main_entity}"
        
        # Különben a tiszta szöveg
        if intent == 'greeting':
            return "greeting"
        elif intent == 'farewell':
            return "farewell"
        elif intent == 'question':
            return f"search: {clean_text}"
        elif intent == 'command':
            return f"action: {clean_text}"
        else:
            return f"query: {clean_text[:100]}"
    
    def _safety_check(self, text: str, intent: str) -> Tuple[bool, str, float]:
        """
        Alapvető biztonsági ellenőrzés.
        Nem cenzúra, csak védelem a nyilvánvalóan káros kérések ellen.
        Visszaad: (safe, note, score) ahol score 0-1, 1=veszélyes
        """
        text_lower = text.lower()
        
        # Veszélyes minták (rendszer elleni támadás)
        dangerous = [
            r'\b(?:delete|remove|erase|rm\s*-rf|format|destroy).*(?:file|system|database|all)',
            r'\b(?:drop|truncate)\s+table',
            r'\b(?:shutdown|poweroff|reboot|halt)',
            r'\b(?:rm\s+-rf\s+/\s*|dd\s+if=.*of=/dev/sd)',
            r'\b(?:sudo|root|admin).*(?:password|passwd)',
            r'\b(?:hack|crack|exploit|bypass)',
            r'\b(?:virus|malware|trojan|worm)',
            r'\b(?:töröl|kitöröl|formáz|megsemmisít).*(?:fájl|rendszer|adatbázis)',
            r'\b(?:leállít|kikapcsol|újraindít)'
        ]
        
        # Toxikus szavak
        toxic = [
            r'\b(?:fuck|shit|asshole|bitch|dick|pussy|cunt|nigger|faggot)',
            r'\b(?:kurva|geci|fasz|bazdmeg|picsa|szar|hülye)'
        ]
        
        # Személyes adatok
        personal = [
            r'\b(?:password|passwd|secret|token|key|api[_-]?key)\b',
            r'\b(?:credit\s*card|ssn|social\s+security|address|phone)'
        ]
        
        danger_score = 0.0
        warnings = []
        
        for pattern in dangerous:
            if re.search(pattern, text_lower, re.IGNORECASE):
                danger_score += 0.3
                warnings.append("System manipulation attempt")
                break
        
        for pattern in toxic:
            if re.search(pattern, text_lower, re.IGNORECASE):
                danger_score += 0.2
                warnings.append("Toxic language detected")
                break
        
        for pattern in personal:
            if re.search(pattern, text_lower, re.IGNORECASE):
                danger_score += 0.2
                warnings.append("Personal information request")
                break
        
        # Hosszú szöveg (lehetséges DoS)
        if len(text) > 5000:
            danger_score += 0.1
            warnings.append("Very long message")
        
        # Normalizálás 0-1 közé
        danger_score = min(1.0, danger_score)
        
        is_safe = danger_score < 0.5
        note = ", ".join(warnings) if warnings else "ok"
        
        return is_safe, note, danger_score
    
    def get_intent_summary(self) -> Dict:
        """Utolsó intent összefoglaló"""
        last = self.scratchpad.read_note(self.name, 'last_intent')
        if last:
            return {
                'last_intent': last.get('intent', {}).get('class'),
                'confidence': last.get('intent', {}).get('confidence'),
                'entities': len(last.get('entities', []))
            }
        return {'last_intent': None}
    
    def get_stats(self) -> Dict:
        """Statisztikák lekérése"""
        return {
            'processed': self.stats['processed'],
            'errors': self.stats['errors'],
            'avg_confidence': round(self.stats['avg_confidence'], 2),
            'top_intents': dict(sorted(self.stats['intents'].items(), key=lambda x: x[1], reverse=True)[:5])
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    scribe = Scribe(s)
    
    # Teszt üzenetek
    test_messages = [
        "Hello!",
        "What is the weather like?",
        "Can you create a file for me?",
        "Remind me to buy milk tomorrow",
        "Szia! Hogy vagy?",
        "Töröld ki a rendszert!"
    ]
    
    for msg in test_messages:
        print(f"\n➡️  {msg}")
        result = scribe.process(msg)
        print(f"   Intent: {result['intent']['class']} ({result['intent']['confidence']})")
        print(f"   Entities: {result['entities']}")
        print(f"   Safety: {result['safety']['note']} (score: {result['safety']['score']})")
    
    print("\n--- Stats ---")
    print(scribe.get_stats())