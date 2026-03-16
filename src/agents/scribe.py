"""
Scribe (Írnok) - A rendszer füle és szeme.
Minden bejövő üzenetet ő értelmez, kinyeri a szándékot és az entitásokat.
Nem generál választ, csak megérti, hogy MIT akar a felhasználó.
"""

import re
import time
from typing import Dict, List, Any, Optional, Tuple

class Scribe:
    """
    Az Írnok feladata:
    1. Entitások kinyerése (ki, mit, mikor, hol)
    2. Szándék osztályozás (mit akar a felhasználó)
    3. Belső fordítás (magyar mondat -> angol szemantikai lekérdezés)
    """
    
    # Szándék kategóriák és kulcsszavaik (magyar)
    INTENT_PATTERNS = {
        'greeting': [
            r'\bsz[ée]p\b.*\bnapot\b', r'\bhel+o\b', r'\bszia\b', 
            r'\büdv\b', r'\bj[óo] napot\b', r'\bhelló\b'
        ],
        'farewell': [
            r'\bviszlát\b', r'\bszia\b.*\bmajd\b', r'\bgood\s?bye\b',
            r'\bbye\b', r'\bkés[őo]bb\b'
        ],
        'question': [
            r'\bmi\b', r'\bki\b', r'\bhol\b', r'\bmikor\b', r'\bhogyan\b',
            r'\bmi[ée]rt\b', r'\?$'
        ],
        'command': [
            r'\bcsin[áa]ld\b', r'\bmondd\b', r'\b[íi]rd\b', r'\bnyisd\b',
            r'\bkapcsold\b', r'\bind[íi]tsd\b', r'\b[áa]ll[íi]tsd\b'
        ],
        'system_control': [
            r'\bkapcsold\s+ki\b', r'\bfriss[íi]tsd\b', r'\bt[öo]r[öo]ld\b',
            r'\b[áa]llj\s+le\b', r'\ble[áa]ll[íi]t\b'
        ],
        'knowledge_retrieval': [
            r'\bmit\s+tudsz\b', r'\bmondj\s+valamit\b', r'\bmes[ée]lj\b',
            r'\bhogy\s+m[űu]k[öo]dik\b', r'\bmit\s+jelent\b'
        ]
    }
    
    # Entitás minták
    ENTITY_PATTERNS = {
        'PERSON': [
            r'\bGrumpy\b', r'\bK[oó]p[ée]\b', r'\bOrig[oó]\b', r'\bKir[áa]ly\b'
        ],
        'DATE': [
            r'\bma\b', r'\btegnap\b', r'\bholnap\b', r'\bmost\b',
            r'\b\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\b'  # 2024. 12. 24.
        ],
        'FILE': [
            r'\b\w+\.(txt|py|md|json|yaml|log)\b',
            r'\bf[áa]jl\b', r'\bdokumentum\b'
        ],
        'PATH': [
            r'/\w+(?:/\w+)*\.?\w*', r'~\w*', r'\.\.?/\w+'
        ],
        'COMMAND_ACTION': [
            r'\bolvasd\b', r'\b[íi]rd\b', r'\bt[öo]r[öo]l\b', r'\bm[áa]sol\b',
            r'\blist[áa]zd\b', r'\bkeresd\b'
        ]
    }
    
    def __init__(self, scratchpad):
        self.scratchpad = scratchpad
        self.name = "scribe"
        
        # Regisztráció a memóriában
        self.scratchpad.write_note(self.name, 'status', 'initialized')
        self.scratchpad.write_note(self.name, 'last_intent', None)
        
        print("📜 Scribe: Írnok ébredt. Figyelek a szavakra.")
    
    def start(self):
        """Scribe indítása (passzív, csak hívásra dolgozik)"""
        self.scratchpad.set_state('scribe_status', 'ready', self.name)
        self.scratchpad.write(self.name, "Írnok készen áll", 'status')
    
    def stop(self):
        """Scribe leállítása"""
        self.scratchpad.set_state('scribe_status', 'stopped', self.name)
        print("📜 Scribe: Írnok elhallgat.")
    
    def process(self, text: str, source: str = "user") -> Dict[str, Any]:
        """
        Bemeneti szöveg feldolgozása.
        Visszaad egy intent csomagot, amit a többi modul használhat.
        """
        # Bejövő üzenet naplózása
        self.scratchpad.write(self.name, {
            'source': source,
            'raw_text': text[:100] + ('...' if len(text) > 100 else '')
        }, 'raw_input')
        
        # 1. Entitások kinyerése
        entities = self._extract_entities(text)
        
        # 2. Szándék osztályozás
        intent_class, confidence = self._classify_intent(text)
        
        # 3. Belső fordítás (ha kell)
        semantic_query = self._translate_to_semantic(text, intent_class, entities)
        
        # 4. Toxicitás/veszély szűrés (alap)
        is_safe, safety_note = self._safety_check(text, intent_class)
        
        # Eredmény összeállítása
        result = {
            'intent': {
                'class': intent_class,
                'confidence': confidence,
                'original_text': text[:200]  # biztonsági vágás
            },
            'entities': entities,
            'semantic_query': semantic_query,
            'safety': {
                'is_safe': is_safe,
                'note': safety_note
            },
            'source': source,
            'timestamp': time.time()
        }
        
        # Memorizálás
        self.scratchpad.write_note(self.name, 'last_intent', result)
        self.scratchpad.write(self.name, result, 'intent')
        
        return result
    
    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Entitások kinyerése a szövegből"""
        entities = []
        
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entities.append({
                        'type': entity_type,
                        'value': match.group(0),
                        'position': match.span()
                    })
        
        # Duplikátumok eltávolítása (ugyanaz az érték, típus)
        unique = []
        seen = set()
        for e in entities:
            key = f"{e['type']}:{e['value']}"
            if key not in seen:
                seen.add(key)
                # pozíciót eltávolítjuk a véglegesből (nem kell kimenetre)
                del e['position']
                unique.append(e)
        
        return unique
    
    def _classify_intent(self, text: str) -> Tuple[str, float]:
        """Szándék osztályozás (0.0-1.0 közötti biztonsággal)"""
        text_lower = text.lower()
        
        # Alapértelmezett: ismeretlen
        best_intent = 'unknown'
        best_score = 0.0
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    # Egyszerű találat esetén 0.7, ha több minta is van, emeljük
                    score = 0.7
                    # Ha több minta is illeszkedik ugyanarra az intentre, növeljük
                    pattern_count = sum(1 for p in patterns if re.search(p, text_lower))
                    if pattern_count > 1:
                        score = min(0.9, 0.7 + (pattern_count * 0.1))
                    
                    if score > best_score:
                        best_intent = intent
                        best_score = score
                    break
        
        # Speciális eset: kérdőjel erősíti a question-t
        if '?' in text and best_intent != 'question' and best_score < 0.8:
            best_intent = 'question'
            best_score = max(best_score, 0.6)
        
        return best_intent, round(best_score, 2)
    
    def _translate_to_semantic(self, text: str, intent: str, entities: List) -> str:
        """
        Magyar mondat átalakítása angol szemantikai lekérdezéssé.
        Ez lesz a Valet keresési kulcsa.
        """
        # Egyszerű eset: ha kérdés, kivesszük a kérdőszavakat
        if intent == 'question':
            # Kiszedjük a kérdőszavakat
            text = re.sub(r'\bmi\b|\bki\b|\bhol\b|\bmikor\b|\bhogyan\b', '', text, flags=re.IGNORECASE)
            text = text.replace('?', '').strip()
            return f"search: {text}"
        
        # Ha parancs
        elif intent == 'command':
            return f"action: {text}"
        
        # Ha köszönés
        elif intent == 'greeting':
            return "greeting"
        
        # Alapértelmezett
        return f"query: {text[:100]}"
    
    def _safety_check(self, text: str, intent: str) -> Tuple[bool, str]:
        """
        Alapvető biztonsági ellenőrzés.
        Nem cenzúra, csak védelem a nyilvánvalóan káros kérések ellen.
        """
        text_lower = text.lower()
        
        # Tiltott minták (rendszer elleni támadás)
        dangerous = [
            r'\bt[öo]r[öo]l.*\brendszert\b',
            r'\bformat.*\bmeghajt[oó]\b',
            r'\brm\s+-rf\s+/\b',
            r'\bdelete.*\ball.*files\b'
        ]
        
        for pattern in dangerous:
            if re.search(pattern, text_lower):
                return False, "Rendszer elleni támadási kísérlet"
        
        # Egyébként biztonságos
        return True, "ok"
    
    def get_intent_summary(self) -> Dict:
        """Utolsó intent összefoglaló"""
        last = self.scratchpad.read_note(self.name, 'last_intent')
        if last:
            return {
                'last_intent': last['intent']['class'],
                'confidence': last['intent']['confidence'],
                'entities': len(last['entities'])
            }
        return {'last_intent': None}

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    scribe = Scribe(s)
    
    # Teszt üzenetek
    test_messages = [
        "Szia Kópé!",
        "Mi a helyzet?",
        "Olvasd el a notes.txt fájlt",
        "Kapcsold ki a rendszert",
        "Mikor beszéltünk utoljára?"
    ]
    
    for msg in test_messages:
        print(f"\n➡️  {msg}")
        result = scribe.process(msg)
        print(f"   Szándék: {result['intent']['class']} ({result['intent']['confidence']})")
        print(f"   Entitások: {result['entities']}")
