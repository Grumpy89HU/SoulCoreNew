"""
Queen - A logikai réteg, a "nyers, érzelemmentes igazság".

Feladata:
1. Chain of Thought (CoT) - logikai levezetés
2. Tények ellenőrzése és összefüggések keresése
3. Érzelemmentes, tiszta logika - csak a tények számítanak
4. King számára előkészített logikai váz
5. Ellentmondások detektálása

A Queen nem beszél a felhasználóval, csak a Kingnek dolgozik.
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import re

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
            'require_proof': True,           # Minden állításhoz bizonyíték kell
            'max_facts': 15,                  # Maximum ennyi tényt használ
            'max_thought_steps': 10,           # Maximum CoT lépések száma
            'temperature': 0.1,                # Nagyon alacsony hőmérséklet (precíz)
            'max_tokens': 512,                  # CoT hossza
            'use_model': False,                 # Külön modell használata (ha van)
            'personality': 'precise, logical, factual, emotionless',
            'contradiction_threshold': 0.7,     # Ellentmondás küszöb
            'confidence_threshold': 0.6,        # Minimum bizonyosság
            'enable_thought_validation': True,  # Gondolatmenet validálása
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Állapot
        self.state = {
            'status': 'idle',
            'thoughts_count': 0,
            'last_thought': None,
            'contradictions_found': 0,
            'errors': [],
            'model_loaded': False,
            'avg_processing_time': 0
        }
        
        # Logikai szabályok (bővíthető)
        self.logic_rules = [
            self._check_contradiction,
            self._check_implication,
            self._check_temporal,
            self._check_causal,
            self._check_consistency,
            self._check_factual_accuracy
        ]
        
        # Ismert logikai hibák
        self.logical_fallacies = {
            'circular_reasoning': r'(?:mert|because).+\1',
            'false_dilemma': r'(?:vagy|or).+(?:vagy|or).+(?:nincs más|no other)',
            'hasty_generalization': r'(?:mindig|always|soha|never).+(?:egy|one)',
        }
        
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
            'warnings': [...],       # Figyelmeztetések
            'fallacies': [...],      # Logikai hibák
            'processing_time': float
        }
        """
        start_time = time.time()
        self.state['status'] = 'thinking'
        
        # Alapértelmezett eredmény
        result = {
            'thought': [],
            'facts': [],
            'conclusion': "Nem sikerült logikai levezetést készíteni.",
            'confidence': 0.0,
            'warnings': [],
            'fallacies': [],
            'processing_time': 0
        }
        
        try:
            # 1. Tények összegyűjtése
            facts = self._gather_facts(intent_packet, context)
            result['facts'] = facts
            
            # 2. Logikai levezetés
            thought_steps, conclusions, warnings, fallacies = self._apply_logic(intent_packet, facts)
            result['thought'] = thought_steps
            result['warnings'] = warnings
            result['fallacies'] = fallacies
            
            # 3. Következtetés összeállítása
            if conclusions:
                final_conclusion = self._synthesize_conclusion(conclusions)
            else:
                final_conclusion = self._default_conclusion(intent_packet, facts)
            result['conclusion'] = final_conclusion
            
            # 4. Bizonyossági szint számítása
            confidence = self._calculate_confidence(facts, warnings, fallacies)
            result['confidence'] = confidence
            
            # 5. Ha van modell és használjuk, kérjük meg a CoT-re
            if self.config['use_model'] and self.model and self.state.get('model_loaded'):
                model_thought = self._get_model_thought(intent_packet, facts)
                if model_thought:
                    result['thought'].append("--- MODELL LOGIKA ---")
                    result['thought'].extend(model_thought)
            
            # 6. Gondolatmenet validálása (ha be van kapcsolva)
            if self.config['enable_thought_validation']:
                validation_warnings = self._validate_thought(result['thought'])
                result['warnings'].extend(validation_warnings)
            
            # Állapot frissítés
            self.state['thoughts_count'] += 1
            self.state['last_thought'] = result
            
            # Feldolgozási idő
            processing_time = time.time() - start_time
            result['processing_time'] = processing_time
            
            # Mozgóátlag számítás
            if self.state['avg_processing_time'] == 0:
                self.state['avg_processing_time'] = processing_time
            else:
                self.state['avg_processing_time'] = (
                    self.state['avg_processing_time'] * 0.9 + processing_time * 0.1
                )
            
            # Mentés a scratchpadbe (King később olvashatja)
            self.scratchpad.write(self.name, result, 'queen_thought')
            
        except Exception as e:
            error = str(e)
            self.state['errors'].append(error)
            result['thought'] = [f"HIBA: {error}"]
            result['warnings'] = [error]
        
        finally:
            self.state['status'] = 'idle'
        
        return result
    
    def _gather_facts(self, intent_packet: Dict, context: Dict = None) -> List[str]:
        """
        Tények összegyűjtése több forrásból:
        - Intent packet
        - Valet kontextus (ha van)
        - Scratchpad (rövid távú memória)
        - Korábbi Queen gondolatok
        """
        facts = []
        
        try:
            # 1. Intent packet
            payload = intent_packet.get('payload', {})
            if isinstance(payload, dict):
                text = payload.get('text', '')
                if text and isinstance(text, str):
                    facts.append(f"User input: {text}")
                
                intent_class = payload.get('intent', {}).get('class', 'unknown')
                facts.append(f"Intent: {intent_class}")
            
            # 2. Valet kontextus
            if context and isinstance(context, dict):
                if 'facts' in context and isinstance(context['facts'], list):
                    facts.extend([f"[Context] {f}" for f in context['facts'] if isinstance(f, str)])
                if 'summary' in context and isinstance(context['summary'], str):
                    facts.append(f"[Summary] {context['summary']}")
            
            # 3. Scratchpad - korábbi üzenetek
            recent = self.scratchpad.read(limit=10)
            for entry in recent:
                if isinstance(entry, dict) and entry.get('type') == 'response':
                    module = entry.get('module', 'unknown')
                    content = entry.get('content', {})
                    if isinstance(content, dict) and 'response' in content:
                        response_text = content['response']
                        if isinstance(response_text, str):
                            facts.append(f"[{module}] {response_text[:100]}")
            
            # 4. Korábbi Queen gondolatok
            last_queen = self.scratchpad.read_last('queen_thought')
            if last_queen and isinstance(last_queen, dict):
                content = last_queen.get('content', {})
                if isinstance(content, dict) and 'conclusion' in content:
                    facts.append(f"[Previous conclusion] {content['conclusion']}")
            
        except Exception as e:
            self.state['errors'].append(f"Facts gathering error: {e}")
        
        # Limitálás
        if len(facts) > self.config['max_facts']:
            facts = facts[:self.config['max_facts']]
        
        return facts
    
    def _apply_logic(self, intent_packet: Dict, facts: List[str]) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Logikai szabályok alkalmazása.
        Visszaad: (thought_steps, conclusions, warnings, fallacies)
        """
        thought_steps = []
        conclusions = []
        warnings = []
        fallacies = []
        
        # Alap tények rögzítése
        thought_steps.append(f"FACTS: {len(facts)} items")
        for i, fact in enumerate(facts[:5]):
            thought_steps.append(f"  {i+1}. {fact}")
        
        if len(facts) > 5:
            thought_steps.append(f"  ... and {len(facts)-5} more")
        
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
                        if 'fallacy' in result:
                            fallacies.append(result['fallacy'])
                    elif isinstance(result, str):
                        thought_steps.append(result)
            except Exception as e:
                thought_steps.append(f"  [Rule error: {e}]")
        
        # Logikai hibák keresése
        for fact in facts:
            if isinstance(fact, str):
                fallacy = self._detect_fallacy(fact)
                if fallacy:
                    fallacies.append(fallacy)
        
        # Limitálás
        if len(thought_steps) > self.config['max_thought_steps']:
            thought_steps = thought_steps[:self.config['max_thought_steps']]
        
        return thought_steps, conclusions, warnings, fallacies
    
    def _detect_fallacy(self, text: str) -> Optional[str]:
        """
        Logikai hibák detektálása.
        """
        text_lower = text.lower()
        
        for fallacy_name, pattern in self.logical_fallacies.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                return f"Potential {fallacy_name.replace('_', ' ')}"
        
        return None
    
    def _validate_thought(self, thought_steps: List[str]) -> List[str]:
        """
        Gondolatmenet validálása (következetesség, logikai ugrások).
        """
        warnings = []
        
        # Ellenőrizzük, hogy van-e logikai ugrás
        for i, step in enumerate(thought_steps[:-1]):
            next_step = thought_steps[i + 1]
            
            # Ha a lépések között nagy a távolság
            if len(step.split()) > 20 and len(next_step.split()) > 20:
                # Egyszerű heurisztika: ha nincs közös szó, lehet ugrás
                step_words = set(step.lower().split())
                next_words = set(next_step.lower().split())
                common = step_words.intersection(next_words)
                
                if len(common) < 2 and len(step_words) > 5 and len(next_words) > 5:
                    warnings.append(f"Possible logical gap between step {i+1} and {i+2}")
        
        return warnings
    
    # --- LOGIKAI SZABÁLYOK ---
    
    def _check_contradiction(self, intent_packet: Dict, facts: List[str]) -> Optional[Dict]:
        """
        Ellentmondások keresése a tények között.
        """
        contradictions = []
        
        for i, fact1 in enumerate(facts):
            if not isinstance(fact1, str):
                continue
            for fact2 in facts[i+1:]:
                if not isinstance(fact2, str):
                    continue
                
                # Egyszerű ellentmondás keresés (A és nem A)
                words1 = set(fact1.lower().split())
                words2 = set(fact2.lower().split())
                
                # Kulcsszavak ellentmondáshoz
                negations = {'nem', 'nincs', 'soha', 'nem lehet', 'not', 'never', 'cannot'}
                affirmations = {'van', 'igen', 'lehet', 'is', 'can'}
                
                # Ha van közös tartalom, de ellentétes előjel
                common = words1.intersection(words2) - negations - affirmations
                
                # Számoljuk a tagadásokat és állításokat
                neg1 = len(words1.intersection(negations))
                neg2 = len(words2.intersection(negations))
                
                if common and ((neg1 > 0) != (neg2 > 0)):
                    contradictions.append(f"Contradiction: '{fact1[:50]}' vs '{fact2[:50]}'")
                    self.state['contradictions_found'] += 1
                    break
        
        if contradictions:
            return {
                'thought': "Contradiction analysis: problem found",
                'warning': contradictions[0],
                'conclusion': "Contradictory information"
            }
        
        return None
    
    def _check_implication(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Logikai implikációk keresése (ha A, akkor B).
        """
        implications = []
        
        # Egyszerű szabályok (bővíthető)
        rules = [
            (['buy', 'purchase', 'get', 'take'], 'have'),
            (['go', 'travel', 'leave'], 'not be here'),
            (['see', 'watch', 'check'], 'know'),
            (['learn', 'study', 'read'], 'understand'),
        ]
        
        for fact in facts:
            if not isinstance(fact, str):
                continue
            fact_lower = fact.lower()
            for triggers, consequence in rules:
                if any(t in fact_lower for t in triggers):
                    # Keressük a tárgyat
                    words = fact.split()
                    for word in words:
                        word_lower = word.lower()
                        if len(word_lower) > 3 and word_lower not in triggers:
                            implications.append(f"If {word_lower} {triggers[0]}, then {word_lower} {consequence}")
                            break
        
        if implications:
            return f"Implications: {', '.join(implications[:2])}"
        
        return None
    
    def _check_temporal(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Időbeli összefüggések keresése.
        """
        temporal = []
        
        # Dátumok és időbeli kifejezések keresése
        time_patterns = [
            r'\d{4}', r'\d{1,2}\.\s*\d{1,2}\.',  # Dátumok
            r'today|yesterday|tomorrow|now|then',
            r'before|after|during|while',
            r'always|never|sometimes|often',
        ]
        
        for fact in facts:
            if not isinstance(fact, str):
                continue
            for pattern in time_patterns:
                if re.search(pattern, fact, re.IGNORECASE):
                    temporal.append(f"Temporal: {fact[:100]}")
                    break
        
        if temporal:
            return f"Temporal facts: {len(temporal)} items"
        
        return None
    
    def _check_causal(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Oksági kapcsolatok keresése.
        """
        causal = []
        
        # Oksági szavak (többnyelvű)
        causal_words = [
            'because', 'since', 'as', 'therefore', 'thus', 'hence', 'so',
            'mert', 'ezért', 'amiatt', 'következtében', 'okozza', 'miatt'
        ]
        
        for fact in facts:
            if not isinstance(fact, str):
                continue
            if any(word in fact.lower() for word in causal_words):
                causal.append(f"Causal: {fact[:100]}")
        
        if causal:
            return f"Causal relationships: {len(causal)} items"
        
        return None
    
    def _check_consistency(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Következetesség ellenőrzése.
        """
        # Nincs implementálva, helyettesítő
        return None
    
    def _check_factual_accuracy(self, intent_packet: Dict, facts: List[str]) -> Optional[str]:
        """
        Tényszerű pontosság ellenőrzése (alap verzió).
        """
        # Nincs implementálva, helyettesítő
        return None
    
    def _synthesize_conclusion(self, conclusions: List[str]) -> str:
        """
        Több következtetés összefésülése egybe.
        """
        if not conclusions:
            return "No clear conclusion."
        
        # Különböző típusú következtetések kezelése
        unique = list(set(conclusions))
        
        if len(unique) == 1:
            return unique[0]
        
        # Ha több van, próbáljuk összefoglalni
        if any('contradiction' in c.lower() for c in unique):
            return "Due to contradictory information, no definitive conclusion can be drawn."
        
        if len(unique) <= 3:
            return "Multiple conclusions: " + "; ".join(unique)
        
        return f"Multiple conclusions: {unique[0]}; {unique[1]}; ..."
    
    def _default_conclusion(self, intent_packet: Dict, facts: List[str]) -> str:
        """
        Alapértelmezett következtetés, ha nincs specifikus.
        """
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '') if isinstance(payload, dict) else ''
        
        if not facts:
            return "Insufficient information for logical deduction."
        
        if '?' in text:
            return "Question received, need to answer based on facts."
        
        return "Based on available facts, no further logical deduction needed."
    
    def _calculate_confidence(self, facts: List[str], warnings: List[str], fallacies: List[str]) -> float:
        """
        Bizonyossági szint számítása.
        """
        base = 0.5  # Alap bizonyosság
        
        # Tények száma növeli
        base += min(0.3, len(facts) * 0.03)
        
        # Figyelmeztetések csökkentik
        base -= min(0.4, len(warnings) * 0.1)
        
        # Logikai hibák csökkentik
        base -= min(0.3, len(fallacies) * 0.15)
        
        # Ha van ellentmondás, jelentősen csökken
        if any('contradiction' in w.lower() for w in warnings):
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
            if isinstance(response, str):
                lines = response.strip().split('\n')
                return [line.strip() for line in lines if line.strip()]
            return None
            
        except Exception as e:
            self.state['errors'].append(f"Model thought error: {e}")
            return None
    
    def _build_model_prompt(self, intent_packet: Dict, facts: List[str]) -> str:
        """
        Prompt összeállítása a modellnek a CoT-hez.
        """
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '') if isinstance(payload, dict) else ''
        
        prompt = f"""Task: Create a logical deduction based on the following information.

Available facts:
{chr(10).join(f'- {fact}' for fact in facts)}

User message: {text}

Please think step by step:
1. What are the most important facts?
2. Are there any contradictions?
3. What logical conclusions can be drawn?
4. What is the final conclusion?

Answer (list the logical steps briefly, concisely):"""
        
        return prompt
    
    # --- KING INTEGRÁCIÓ ---
    
    def get_thought_for_king(self, intent_packet: Dict, context: Dict = None) -> str:
        """
        Egyszerűsített kimenet a King számára.
        A Queen gondolatait a King beépítheti a promptjába.
        """
        thought = self.think(intent_packet, context)
        
        # Összecsomagolás a Kingnek
        result_parts = ["<Queen logic>"]
        result_parts.extend(thought['thought'])
        result_parts.append(f"Conclusion: {thought['conclusion']}")
        result_parts.append(f"Confidence: {thought['confidence']:.1%}")
        if thought['warnings']:
            result_parts.append(f"WARNING: {', '.join(thought['warnings'])}")
        if thought['fallacies']:
            result_parts.append(f"Fallacies detected: {', '.join(thought['fallacies'])}")
        result_parts.append("</Queen logic>")
        
        return "\n".join(result_parts)
    
    # --- ÁLLAPOT ---
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'thoughts_count': self.state['thoughts_count'],
            'contradictions_found': self.state['contradictions_found'],
            'avg_processing_time': round(self.state['avg_processing_time'] * 1000, 2),
            'last_thought_time': self.state['last_thought'].get('processing_time') if self.state['last_thought'] else None,
            'errors': self.state['errors'][-5:],
            'model_loaded': self.state['model_loaded'],
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
            'text': 'I said yesterday that I wouldn\'t go anywhere, but now I\'m going to Budapest tomorrow.',
            'intent': {'class': 'travel'}
        }
    }
    
    # Teszt kontextus
    test_context = {
        'facts': [
            'Previously: "Not going anywhere this week"',
            'User likes to travel'
        ]
    }
    
    # Gondolkodás
    result = queen.think(test_intent, test_context)
    
    print("Queen thoughts:")
    for step in result['thought']:
        print(f"  {step}")
    print(f"\nConclusion: {result['conclusion']}")
    print(f"Confidence: {result['confidence']:.1%}")
    if result['warnings']:
        print(f"Warnings: {result['warnings']}")
    
    # King formátum
    print("\n--- For King ---")
    print(queen.get_thought_for_king(test_intent, test_context))