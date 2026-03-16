"""
Queen - A logikai réteg, a "nyers, érzelemmentes igazság".

Feladata:
1. Chain of Thought (CoT) - logikai levezetés
2. Tények ellenőrzése és összefüggések keresése
3. Érzelemmentes, tiszta logika - csak a tények számítanak
4. King számára előkészített logikai váz

A Queen nem beszél a felhasználóval, csak a Kingnek dolgozik.
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

class Queen:
    """
    A Királynő - a logika ura.
    
    Jellemzői:
    - Érzelemmentes
    - Csak a tények számítanak
    - Ha nincs elég információ, azt mondja
    - Soha nem hallucinál
    - Minden állítást forrással vagy levezetéssel támaszt alá
    """
    
    def __init__(self, scratchpad, model_wrapper=None, config: Dict = None):
        self.scratchpad = scratchpad
        self.model = model_wrapper
        self.name = "queen"
        self.config = config or {}
        
        # Konfiguráció (alapértékek)
        default_config = {
            'enabled': True,
            'require_proof': True,
            'max_facts': 10,
            'temperature': 0.1,
            'max_tokens': 512,
            'use_model': False,
            'personality': 'precise, logical, factual, emotionless'
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Állapot - HOZZÁADVA a model_loaded
        self.state = {
            'status': 'idle',
            'thoughts_count': 0,
            'last_thought': None,
            'contradictions_found': 0,
            'errors': [],
            'model_loaded': False  # <-- EZT ADD IDE
        }
        
        # Logikai szabályok
        self.logic_rules = [
            self._check_contradiction,
            self._check_implication,
            self._check_temporal,
            self._check_causal
        ]
        
        # Ha van modell, elindítjuk a betöltést háttérben
        if self.config['use_model'] and self.model:
            threading.Thread(target=self._load_model, daemon=True).start()
        
        print("👸 Queen: Királynő ébred. A logika az én birodalmam.")

    def _load_model(self):
        """Modell betöltése háttérben"""
        try:
            success = self.model.load()
            self.state['model_loaded'] = success
            if success:
                print("👸 Queen: Modell betöltve")
            else:
                print("👸 Queen: Modell betöltési hiba")
        except Exception as e:
            self.state['model_loaded'] = False
            self.state['errors'].append(f"Model load error: {e}")
            print(f"👸 Queen: Modell hiba: {e}")
    
    def start(self):
        """Queen indítása"""
        self.state['status'] = 'ready'
        self.scratchpad.set_state('queen_status', 'ready', self.name)
        print("👸 Queen: Készen állok a logikai feladatokra.")
    
    def stop(self):
        """Queen leállítása"""
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('queen_status', 'stopped', self.name)
        if self.model and hasattr(self.model, 'unload'):
            self.model.unload()
        print("👸 Queen: Leállt.")
    
    # --- FŐ FELDOLGOZÓ METÓDUS ---
    
    def think(self, intent_packet: Dict, context: Dict = None) -> Dict[str, Any]:
        """
        Fő belépési pont - logikai levezetés.
        
        Bemenet: intent_packet + opcionális kontextus (Valet-től)
        Kimenet: {
            'thought': [          # CoT lépések
                'Tény: ...',
                'Levezetés: ...',
                'Következtetés: ...'
            ],
            'facts': [...],        # Felhasznált tények
            'conclusion': str,      # Végső következtetés
            'confidence': float,    # 0.0 - 1.0
            'warnings': [...]       # Figyelmeztetések
        }
        """
        start_time = time.time()
        self.state['status'] = 'thinking'
        
        try:
            # 1. Tények összegyűjtése
            facts = self._gather_facts(intent_packet, context)
            
            # 2. Logikai levezetés
            thought_steps = []
            conclusions = []
            warnings = []
            
            # Alap tények rögzítése
            thought_steps.append(f"TÉNYEK: {len(facts)} darab")
            for i, fact in enumerate(facts[:5]):  # Max 5 tényt sorolunk fel
                thought_steps.append(f"  {i+1}. {fact}")
            
            if len(facts) > 5:
                thought_steps.append(f"  ... és még {len(facts)-5} tény")
            
            # Logikai szabályok alkalmazása
            for rule in self.logic_rules:
                try:
                    result = rule(intent_packet, facts)
                    if result:
                        if isinstance(result, dict):
                            if 'thought' in result:
                                thought_steps.append(result['thought'])
                            if 'conclusion' in result:
                                conclusions.append(result['conclusion'])
                            if 'warning' in result:
                                warnings.append(result['warning'])
                        else:
                            thought_steps.append(result)
                except Exception as e:
                    thought_steps.append(f"  [Szabály hiba: {e}]")
            
            # 3. Következtetés összeállítása
            if conclusions:
                final_conclusion = self._synthesize_conclusion(conclusions)
            else:
                final_conclusion = self._default_conclusion(intent_packet, facts)
            
            # 4. Bizonyossági szint számítása
            confidence = self._calculate_confidence(facts, warnings)
            
            # 5. Ha van modell és használjuk, kérjük meg a CoT-re
            if self.config['use_model'] and self.model and self.model.state.get('loaded'):
                model_thought = self._get_model_thought(intent_packet, facts)
                if model_thought:
                    thought_steps.append("--- MODELL LOGIKA ---")
                    thought_steps.extend(model_thought)
            
            # Eredmény összeállítása
            result = {
                'thought': thought_steps,
                'facts': facts,
                'conclusion': final_conclusion,
                'confidence': confidence,
                'warnings': warnings,
                'processing_time': time.time() - start_time
            }
            
            # Állapot frissítés
            self.state['thoughts_count'] += 1
            self.state['last_thought'] = result
            self.state['status'] = 'idle'
            
            # Mentés a scratchpadbe (King később olvashatja)
            self.scratchpad.write(self.name, result, 'queen_thought')
            
            return result
            
        except Exception as e:
            error = str(e)
            self.state['errors'].append(error)
            self.state['status'] = 'error'
            
            return {
                'thought': [f"HIBA: {error}"],
                'facts': [],
                'conclusion': "Nem sikerült logikai levezetést készíteni.",
                'confidence': 0.0,
                'warnings': [error],
                'processing_time': time.time() - start_time
            }
    
    def _gather_facts(self, intent_packet: Dict, context: Dict = None) -> List[str]:
        """
        Tények összegyűjtése több forrásból:
        - Intent packet
        - Valet kontextus (ha van)
        - Scratchpad (rövid távú memória)
        - Korábbi Queen gondolatok
        """
        facts = []
        
        # 1. Intent packet
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '')
        if text:
            facts.append(f"Felhasználói input: {text}")
        
        intent_class = payload.get('intent', {}).get('class', 'unknown')
        facts.append(f"Szándék: {intent_class}")
        
        # 2. Valet kontextus
        if context:
            if 'facts' in context:
                facts.extend([f"[Valet] {f}" for f in context['facts']])
            if 'summary' in context:
                facts.append(f"[Összefoglaló] {context['summary']}")
        
        # 3. Scratchpad - korábbi üzenetek
        recent = self.scratchpad.read(limit=10)
        for entry in recent:
            if entry.get('type') == 'response':
                module = entry.get('module', 'unknown')
                content = entry.get('content', {})
                if isinstance(content, dict) and 'response' in content:
                    facts.append(f"[{module}] {content['response'][:100]}")
        
        # 4. Korábbi Queen gondolatok
        last_queen = self.scratchpad.read_last('queen_thought')
        if last_queen:
            content = last_queen.get('content', {})
            if isinstance(content, dict) and 'conclusion' in content:
                facts.append(f"[Korábbi következtetés] {content['conclusion']}")
        
        # Limitálás
        if len(facts) > self.config['max_facts']:
            facts = facts[:self.config['max_facts']]
        
        return facts
    
    # --- LOGIKAI SZABÁLYOK ---
    
    def _check_contradiction(self, intent_packet: Dict, facts: List[str]) -> Optional[Dict]:
        """
        Ellentmondások keresése a tények között.
        """
        contradictions = []
        
        # Egyszerű ellentmondás keresés (A és nem A)
        for i, fact1 in enumerate(facts):
            for fact2 in facts[i+1:]:
                # Ha az egyik állítja, a másik tagadja
                words1 = set(fact1.lower().split())
                words2 = set(fact2.lower().split())
                
                # Kulcsszavak ellentmondáshoz
                negations = {'nem', 'nincs', 'soha', 'nem lehet'}
                
                # Ha van közös tartalom, de ellentétes előjel
                common = words1.intersection(words2) - negations
                if common and ((negations.intersection(words1)) != (negations.intersection(words2))):
                    contradictions.append(f"Ellentmondás: '{fact1}' vs '{fact2}'")
        
        if contradictions:
            return {
                'thought': "Ellentmondásvizsgálat: problémát találtam",
                'warning': contradictions[0],
                'conclusion': "Ellentmondásos információk"
            }
        
        return None
    
    def _check_implication(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Logikai implikációk keresése (ha A, akkor B).
        """
        implications = []
        
        # Egyszerű szabályok (bővíthető)
        rules = [
            (['vásárol', 'vesz'], 'van'),
            (['elmegy', 'utazik'], 'nincs otthon'),
            (['megnéz', 'ellenőriz'], 'tudni fogja')
        ]
        
        for fact in facts:
            fact_lower = fact.lower()
            for triggers, consequence in rules:
                if any(t in fact_lower for t in triggers):
                    # Keressük a tárgyat
                    words = fact.split()
                    for word in words:
                        if len(word) > 3 and word not in triggers:
                            implications.append(f"Ha {word} {triggers[0]}, akkor {word} {consequence}")
                            break
        
        if implications:
            return f"Implikációk: {', '.join(implications[:2])}"
        
        return None
    
    def _check_temporal(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Időbeli összefüggések keresése.
        """
        temporal = []
        
        # Dátumok keresése
        for fact in facts:
            if '202' in fact or 'ma' in fact or 'holnap' in fact or 'tegnap' in fact:
                temporal.append(f"Időbeli: {fact}")
        
        if temporal:
            return f"Időbeli tények: {len(temporal)} darab"
        
        return None
    
    def _check_causal(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Oksági kapcsolatok keresése.
        """
        causal = []
        
        # Oksági szavak
        causal_words = ['mert', 'ezért', 'amiatt', 'következtében', 'okozza']
        
        for fact in facts:
            if any(word in fact.lower() for word in causal_words):
                causal.append(f"Oksági: {fact}")
        
        if causal:
            return f"Oksági kapcsolatok: {len(causal)} darab"
        
        return None
    
    def _synthesize_conclusion(self, conclusions: List[str]) -> str:
        """
        Több következtetés összefésülése egybe.
        """
        if not conclusions:
            return "Nincs egyértelmű következtetés."
        
        # Különböző típusú következtetések kezelése
        unique = list(set(conclusions))
        
        if len(unique) == 1:
            return unique[0]
        
        # Ha több van, próbáljuk összefoglalni
        if any('ellentmondás' in c for c in unique):
            return "Ellentmondásos információk miatt nem lehet egyértelmű következtetést levonni."
        
        return "; ".join(unique[:2]) + ("..." if len(unique) > 2 else "")
    
    def _default_conclusion(self, intent_packet: Dict, facts: List[str]) -> str:
        """
        Alapértelmezett következtetés, ha nincs specifikus.
        """
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '')
        
        if not facts:
            return "Nincs elegendő információ a logikai levezetéshez."
        
        if '?' in text:
            return "Kérdés érkezett, tények alapján válaszolni kell."
        
        return "A rendelkezésre álló tények alapján nincs szükség további logikai levezetésre."
    
    def _calculate_confidence(self, facts: List[str], warnings: List[str]) -> float:
        """
        Bizonyossági szint számítása.
        """
        base = 0.5  # Alap bizonyosság
        
        # Tények száma növeli
        base += min(0.3, len(facts) * 0.05)
        
        # Figyelmeztetések csökkentik
        base -= min(0.4, len(warnings) * 0.1)
        
        # Ha van ellentmondás, jelentősen csökken
        if any('ellentmondás' in w for w in warnings):
            base -= 0.3
        
        return max(0.1, min(0.99, base))
    
    def _get_model_thought(self, intent_packet: Dict, facts: List[str]) -> Optional[List[str]]:
        """
        Modell használata a CoT generálásához (ha van).
        """
        if not self.model:
            return None
        
        try:
            # Prompt összeállítása a modellnek
            prompt = self._build_model_prompt(intent_packet, facts)
            
            # Generálás
            response = self.model.generate(
                prompt=prompt,
                max_tokens=self.config['max_tokens'],
                temperature=self.config['temperature']
            )
            
            # Feldolgozás
            lines = response.strip().split('\n')
            return [line.strip() for line in lines if line.strip()]
            
        except Exception as e:
            self.state['errors'].append(f"Model thought error: {e}")
            return None
    
    def _build_model_prompt(self, intent_packet: Dict, facts: List[str]) -> str:
        """
        Prompt összeállítása a modellnek a CoT-hez.
        """
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '')
        
        prompt = f"""Feladat: Logikai levezetés készítése az alábbi információk alapján.

Rendelkezésre álló tények:
{chr(10).join(f'- {fact}' for fact in facts)}

Felhasználói üzenet: {text}

Kérlek, gondold végig lépésről lépésre:
1. Mik a legfontosabb tények?
2. Vannak-e ellentmondások?
3. Milyen logikai következtetéseket lehet levonni?
4. Mi a végső következtetés?

Válasz (csak a logikai lépéseket sorold fel, röviden, tömören):"""
        
        return prompt
    
    # --- KING INTEGRÁCIÓ ---
    
    def get_thought_for_king(self, intent_packet: Dict, context: Dict = None) -> str:
        """
        Egyszerűsített kimenet a King számára.
        A Queen gondolatait a King beépítheti a promptjába.
        """
        thought = self.think(intent_packet, context)
        
        # Összecsomagolás a Kingnek
        result = f"""<Queen logika>
{chr(10).join(thought['thought'])}
Következtetés: {thought['conclusion']}
Bizonyosság: {thought['confidence']:.1%}
{'FIGYELMEZTETÉS: ' + chr(10).join(thought['warnings']) if thought['warnings'] else ''}
</Queen logika>"""
        
        return result
    
    # --- ÁLLAPOT ---
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'thoughts_count': self.state['thoughts_count'],
            'contradictions_found': self.state['contradictions_found'],
            'last_thought_time': self.state['last_thought'].get('processing_time') if self.state['last_thought'] else None,
            'errors': self.state['errors'][-5:],  # Utolsó 5 hiba
            'config': self.config
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    queen = Queen(s)
    
    # Teszt intent
    test_intent = {
        'payload': {
            'text': 'Holnap megyek Budapestre, de tegnap még azt mondtam, hogy nem megyek sehova.',
            'intent': {'class': 'travel'}
        }
    }
    
    # Teszt kontextus
    test_context = {
        'facts': [
            'Korábban: "Nem megyek sehova a héten"',
            'Felhasználó szeret utazni'
        ]
    }
    
    # Gondolkodás
    result = queen.think(test_intent, test_context)
    
    print("Queen gondolatai:")
    for step in result['thought']:
        print(f"  {step}")
    print(f"\nKövetkeztetés: {result['conclusion']}")
    print(f"Bizonyosság: {result['confidence']:.1%}")
    if result['warnings']:
        print(f"Figyelmeztetések: {result['warnings']}")
    
    # King formátum
    print("\n--- Kingnek küldve ---")
    print(queen.get_thought_for_king(test_intent, test_context))
