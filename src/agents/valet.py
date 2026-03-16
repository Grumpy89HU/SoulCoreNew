"""
Valet (Lakáj) - A memória-logisztika és a Tények Őre.

Feladata:
1. Rövid távú memória (Scratchpad) kezelése és összegzése
2. Hosszú távú memória előkészítése (később: vektor DB + gráf DB)
3. Kontextus összeállítása a King számára (Context Briefing)
4. Hallucináció-gát - tények ellenőrzése
"""

import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

class Valet:
    """
    A Lakáj - a memória őre.
    
    Felépítése:
    - Rövid táv: Scratchpad (már van)
    - Hosszú táv: Vektor DB (később) + Gráf DB (később)
    
    Jelenleg: csak Scratchpad, de a felület kész a bővítésre.
    """
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "valet"
        self.config = config or {}
        
        # Konfiguráció (alapértékek)
        default_config = {
            'max_context_tokens': 1500,      # Maximum kontextus hossz (token)
            'max_recent_messages': 5,         # Ennyi üzenet megy a kontextusba
            'summary_length': 200,             # Összefoglaló hossza (karakter)
            'enable_tracking': True,           # Tracking bekapcsolása
            'enable_validation': True,         # Tényellenőrzés bekapcsolása
            'forget_after_days': 30,           # Ennyi nap után "archiválás"
            'important_threshold': 0.7,         # Fontossági küszöb
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Tracking adatok (ki miről beszélt, mikor)
        self.tracking = {
            'topics': defaultdict(int),        # Témák gyakorisága
            'entities': defaultdict(int),       # Entitások gyakorisága
            'last_mentioned': {},                # Utolsó említés (időbélyeg)
            'relationships': defaultdict(set),   # Kapcsolatok (ki-mihez kötődik)
        }
        
        # Állapot
        self.state = {
            'status': 'idle',
            'processed_messages': 0,
            'summaries_created': 0,
            'warnings_issued': 0,
            'last_cleanup': time.time()
        }
        
        print("👔 Valet: Lakáj ébred. Őrzöm a tényeket.")
    
    def start(self):
        """Valet indítása"""
        self.state['status'] = 'ready'
        self.scratchpad.set_state('valet_status', 'ready', self.name)
        print("👔 Valet: Készen állok.")
    
    def stop(self):
        """Valet leállítása"""
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('valet_status', 'stopped', self.name)
        print("👔 Valet: Leállt.")
    
    # --- KONTEXTUS ÖSSZEÁLLÍTÁS (Context Briefing) ---
    
    def prepare_context(self, intent_packet: Dict) -> Dict[str, Any]:
        """
        Kontextus összeállítása a King számára.
        Ezt kapja majd a King a prompt építéshez.
        
        Visszaad:
        {
            'summary': 'rövid összefoglaló',
            'facts': ['tény1', 'tény2'],
            'recent': ['üzenet1', 'üzenet2'],
            'warnings': ['figyelmeztetés1'],
            'tracking': {'topics': {...}, 'entities': {...}}
        }
        """
        context = {
            'summary': '',
            'facts': [],
            'recent': [],
            'warnings': [],
            'tracking': {},
            'timestamp': time.time()
        }
        
        # 1. Rövid távú memória (Scratchpad)
        scratchpad_summary = self.scratchpad.get_summary()
        
        # 2. Utolsó N üzenet
        recent = self.scratchpad.read(limit=self.config['max_recent_messages'])
        for entry in recent:
            if entry.get('type') == 'response':
                sender = entry.get('module', 'unknown')
                content = entry.get('content', {})
                if isinstance(content, dict):
                    text = content.get('response', '')
                else:
                    text = str(content)
                context['recent'].append(f"{sender}: {text[:100]}")
        
        # 3. Fontos tények kinyerése
        facts = self._extract_facts(recent)
        context['facts'] = facts[:5]  # Max 5 tény
        
        # 4. Összefoglaló készítése
        context['summary'] = self._create_summary(intent_packet, facts)
        
        # 5. Tracking adatok
        if self.config['enable_tracking']:
            context['tracking'] = {
                'topics': dict(self.tracking['topics'].most_common(5)),
                'last_mentioned': self.tracking['last_mentioned']
            }
        
        # 6. Aktuális intent figyelmeztetések
        if self.config['enable_validation']:
            warning = self._validate_intent(intent_packet, facts)
            if warning:
                context['warnings'].append(warning)
                self.state['warnings_issued'] += 1
        
        return context
    
    def _extract_facts(self, recent_entries: List) -> List[str]:
        """
        Tények kinyerése a legutóbbi üzenetekből.
        Egyszerű szabályalapú megközelítés.
        """
        facts = []
        
        for entry in recent_entries:
            content = entry.get('content', {})
            if isinstance(content, dict):
                # Ha response
                if 'response' in content:
                    text = content['response']
                # Ha intent
                elif 'intent' in content:
                    text = content.get('intent', {}).get('original_text', '')
                else:
                    text = str(content)
            else:
                text = str(content)
            
            # Tények keresése (pl. "az X az Y", "X van", stb.)
            patterns = [
                (r'az?\s+(\w+)\s+(van|nincs|lesz|volt)', 'állapot'),
                (r'(\w+)\s+az?\s+(\w+)', 'azonosság'),
                (r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', 'dátum'),
            ]
            
            for pattern, fact_type in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        fact = f"{fact_type}: {' '.join(match)}"
                    else:
                        fact = f"{fact_type}: {match}"
                    if fact not in facts:
                        facts.append(fact)
        
        return facts
    
    def _create_summary(self, intent_packet: Dict, facts: List[str]) -> str:
        """
        Rövid összefoglaló készítése a King számára.
        """
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '')
        
        # Ha nincs tény, egyszerű összefoglaló
        if not facts:
            return f"Grumpy üzenete: {text[:100]}..."
        
        # Tények összefoglalása
        fact_summary = ". ".join(facts[:3])
        
        return f"Grumpy azt írja: {text[:50]}... Előzmények: {fact_summary}"
    
    def _validate_intent(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Intent ellenőrzése a tények alapján.
        Ha ellentmondást talál, figyelmeztetést ad.
        """
        payload = intent_packet.get('payload', {})
        intent = payload.get('intent', {})
        text = payload.get('text', '')
        
        # Egyszerű ellentmondás keresés
        contradictions = []
        
        for fact in facts:
            # Ha a tény tagadást tartalmaz
            if 'nincs' in fact or 'nem' in fact:
                # És a szöveg állítja az ellenkezőjét
                if any(word in text for word in fact.split()[1:3]):
                    contradictions.append(fact)
        
        if contradictions:
            return f"Ellentmondás a korábbiakkal: {contradictions[0]}"
        
        return None
    
    # --- MEMÓRIA KEZELÉS ---
    
    def remember(self, key: str, value: Any, importance: float = 0.5):
        """
        Fontos információ elmentése a hosszú távú memóriába.
        Jelenleg csak Scratchpad, később vektor DB.
        """
        # Fontosság alapján döntjük el, hogy megy-e a hosszú távúba
        if importance > self.config['important_threshold']:
            # Hosszú távú memória (később)
            self.scratchpad.write_note(self.name, f"longterm_{key}", {
                'value': value,
                'importance': importance,
                'time': time.time()
            })
        
        # Mindig megy a rövid távúba
        self.scratchpad.write_note(self.name, key, value)
    
    def recall(self, key: str, default=None):
        """Információ előhívása a memóriából"""
        # Először rövid táv
        value = self.scratchpad.read_note(self.name, key)
        if value is not None:
            return value
        
        # Aztán hosszú táv (később)
        value = self.scratchpad.read_note(self.name, f"longterm_{key}")
        if value is not None:
            return value.get('value') if isinstance(value, dict) else value
        
        return default
    
    # --- TRACKING (ki miről beszélt) ---
    
    def track_message(self, intent_packet: Dict):
        """
        Üzenet nyomon követése.
        Kinyeri a témákat és entitásokat.
        """
        if not self.config['enable_tracking']:
            return
        
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '')
        intent = payload.get('intent', {}).get('class', 'unknown')
        
        # Téma hozzáadása
        self.tracking['topics'][intent] += 1
        self.tracking['last_mentioned'][intent] = time.time()
        
        # Entitások keresése (ha van)
        entities = payload.get('entities', [])
        for entity in entities:
            if isinstance(entity, dict):
                etype = entity.get('type', 'unknown')
                evalue = entity.get('value', '')
                key = f"{etype}:{evalue}"
                self.tracking['entities'][key] += 1
                self.tracking['last_mentioned'][key] = time.time()
                
                # Kapcsolat a témával
                self.tracking['relationships'][intent].add(key)
    
    def get_tracking(self, topic: str = None) -> Dict:
        """Tracking adatok lekérése"""
        if topic:
            return {
                'count': self.tracking['topics'].get(topic, 0),
                'last': self.tracking['last_mentioned'].get(topic),
                'related': list(self.tracking['relationships'].get(topic, []))
            }
        
        return {
            'topics': dict(self.tracking['topics']),
            'entities': dict(self.tracking['entities']),
            'relationships': {
                k: list(v) for k, v in self.tracking['relationships'].items()
            }
        }
    
    # --- KARBANTARTÁS ---
    
    def cleanup(self, force: bool = False):
        """
        Régi memória tisztítása.
        - Ha egy téma/téma régi, csökkentjük a súlyát
        - Ha nagyon régi, "archiváljuk"
        """
        now = time.time()
        forget_after = self.config['forget_after_days'] * 86400
        
        # Régi témák súlyozása
        for topic, last_time in list(self.tracking['last_mentioned'].items()):
            age = now - last_time
            if age > forget_after:
                # Archiválás (később)
                if topic in self.tracking['topics']:
                    del self.tracking['topics'][topic]
                del self.tracking['last_mentioned'][topic]
                if topic in self.tracking['relationships']:
                    del self.tracking['relationships'][topic]
            elif age > forget_after // 2:
                # Súly csökkentése
                if topic in self.tracking['topics']:
                    self.tracking['topics'][topic] = max(
                        1, self.tracking['topics'][topic] // 2
                    )
        
        self.state['last_cleanup'] = now
        self.state['processed_messages'] += 1
    
    # --- ÁLLAPOT ---
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'processed': self.state['processed_messages'],
            'summaries': self.state['summaries_created'],
            'warnings': self.state['warnings_issued'],
            'tracking': {
                'topics': len(self.tracking['topics']),
                'entities': len(self.tracking['entities'])
            },
            'config': self.config
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    valet = Valet(s)
    
    # Teszt intent
    test_intent = {
        'payload': {
            'text': 'Holnap megyek Budapestre a konferenciára',
            'intent': {'class': 'travel'},
            'entities': [
                {'type': 'LOCATION', 'value': 'Budapest'},
                {'type': 'DATE', 'value': 'holnap'}
            ]
        }
    }
    
    # Tracking
    valet.track_message(test_intent)
    
    # Kontextus
    context = valet.prepare_context(test_intent)
    print("Kontextus:", context)
    
    # Állapot
    print("Állapot:", valet.get_state())