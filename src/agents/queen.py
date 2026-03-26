"""
Queen - A logikai réteg, a "nyers, érzelemmentes igazság".

KOMMUNIKÁCIÓS PROTOKOLL:
- A Queen HALLJA a Király beszédét a buszon keresztül
- A Queen visszaszól a buszon (target: "king")
- A belső működés nyelvfüggetlen, a gyorsaság és hatékonyság a lényeg

BELSŐ KOMMUNIKÁCIÓS FORMÁTUM (válasz):
{
    "type": "queen_thought",
    "target": "king",
    "trace_id": "uuid",
    "timestamp": 1234567890,
    "payload": {
        "thought": [...],        # CoT lépések
        "facts": [...],          # Felhasznált tények
        "conclusion": "...",     # Végső következtetés
        "confidence": 0.85,      # Bizonyosság
        "warnings": [...],       # Figyelmeztetések
        "fallacies": [...],      # Logikai hibák
        "contradictions": [...]  # Ellentmondások
    }
}
"""

import time
import json
import threading
import hashlib
import uuid
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, asdict, field
import re


@dataclass
class QueenThought:
    """Queen gondolatmenetének struktúrája (JSON-ban továbbítható)"""
    thought: List[str] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    fallacies: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    trace_id: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


class Queen:
    """
    A Királynő - a logika ura.
    
    KOMMUNIKÁCIÓ:
    - Feliratkozik a buszra, hallja a Király beszédét
    - Ha a Király kéri, logikai levezetést végez
    - Visszaszól a buszon a Kingnek
    """
    
    # Logikai hibák mintái (nyelvfüggetlen)
    LOGICAL_FALLACIES = {
        'circular_reasoning': [
            r'(?:mert|because).+\1',
            r'azért mert', r'because because'
        ],
        'false_dilemma': [
            r'(?:vagy|or).+(?:vagy|or).+(?:nincs más|no other)',
            r'either.*or.*no alternative'
        ],
        'hasty_generalization': [
            r'(?:mindig|always|soha|never).+(?:egy|one)',
            r'all.*are.*because.*one'
        ],
        'appeal_to_authority': [
            r'azért mert.*mondta', r'because.*said so',
            r'as.*said', r'according to.*trust'
        ],
        'ad_hominem': [
            r'but.*is.*(?:wrong|stupid)', r'but.*is.*(?:rossz|hülye)'
        ]
    }
    
    def __init__(self, scratchpad, model_wrapper=None, message_bus=None, config: Dict = None):
        self.scratchpad = scratchpad
        self.model = model_wrapper
        self.bus = message_bus
        self.name = "queen"
        self.config = config or {}
        
        # Konfiguráció
        default_config = {
            'enabled': True,
            'require_proof': True,
            'max_facts': 15,
            'max_thought_steps': 10,
            'temperature': 0.1,
            'max_tokens': 512,
            'use_model': False,
            'contradiction_threshold': 0.7,
            'confidence_threshold': 0.6,
            'enable_thought_validation': True,
            'cache_ttl': 300,
            'max_cache_size': 100,
            'complexity_threshold': 0.6  # Komplexitás küszöb a Queen bekapcsolásához
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Állapot
        self.state = {
            'status': 'idle',
            'thoughts_count': 0,
            'contradictions_found': 0,
            'last_thought': None,
            'errors': [],
            'model_loaded': False,
            'avg_processing_time_ms': 0
        }
        
        # Cache
        self.thought_cache = {}
        self.cache_ttl = self.config['cache_ttl']
        self.recent_thoughts = deque(maxlen=20)
        
        # Időbeli kifejezések mintái
        self.time_patterns = [
            r'\d{4}', r'\d{1,2}\.\s*\d{1,2}\.',
            r'today|yesterday|tomorrow|now|then',
            r'before|after|during|while',
            r'always|never|sometimes|often',
            r'ma|tegnap|holnap|most|akkor',
            r'előtt|után|alatt|míg',
            r'mindig|soha|néha|gyakran'
        ]
        
        # Oksági szavak
        self.causal_words = [
            'because', 'since', 'as', 'therefore', 'thus', 'hence', 'so',
            'mert', 'ezért', 'amiatt', 'következtében', 'okozza', 'miatt',
            'due to', 'result of', 'caused by'
        ]
        
        # Ha van busz, feliratkozunk
        if self.bus:
            self.bus.subscribe(self.name, self._on_message)
        
        # Modell betöltés
        if self.config['use_model'] and self.model:
            threading.Thread(target=self._load_model, daemon=True).start()
        
        print("👸 Queen: Királynő ébred.")
        if self.bus:
            print("👸 Queen: Broadcast módban működöm, hallgatom a Király szavát.")
        else:
            print("👸 Queen: Hagyományos módban működöm.")
    
    # ========== BUSZ KOMMUNIKÁCIÓ ==========
    
    def _on_message(self, message: Dict):
        """
        Hallja a buszon érkező üzeneteket.
        Ha a Király royal_decree-je érkezik és kéri a Queen-t, dolgozik.
        """
        if not self.bus:
            return
        
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        # Csak a Király beszédére reagálunk
        if header.get('sender') != 'king':
            return
        
        # Csak royal_decree típusra
        if payload.get('type') != 'royal_decree':
            return
        
        # Ellenőrizzük, hogy kell-e a Queen
        required_agents = payload.get('required_agents', [])
        if self.name not in required_agents:
            return
        
        trace_id = header.get('trace_id', '')
        user_message = payload.get('user_message', '')
        interpretation = payload.get('interpretation', {})
        
        # Komplexitás ellenőrzés - ha alacsony, nem kell Queen
        complexity = interpretation.get('complexity', 'medium')
        if complexity == 'low' and self.config.get('skip_low_complexity', True):
            print(f"👸 Queen: Alacsony komplexitás, kihagyás ({trace_id[:8]})")
            return
        
        # Logikai levezetés végzése
        thought = self._think(user_message, interpretation, {})
        
        # Válasz küldése a Kingnek
        response = {
            "header": {
                "trace_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "sender": self.name,
                "target": "king",
                "in_response_to": trace_id
            },
            "payload": {
                "type": "logic_response",
                "logic": thought.to_dict()
            }
        }
        
        self.bus.send_response(response)
        print(f"👸 Queen: Logikai levezetés küldve a Kingnek ({trace_id[:8]})")
    
    # ========== LOGIKAI LEVEZETÉS ==========
    
    def _think(self, user_text: str, interpretation: Dict, context: Dict) -> QueenThought:
        """
        Logikai levezetés végzése.
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        
        result = QueenThought(trace_id=trace_id)
        
        try:
            # Tények összegyűjtése
            facts = self._gather_facts_for_thought(user_text, interpretation, context)
            result.facts = facts[:self.config['max_facts']]
            
            # Logikai levezetés
            thought_steps, contradictions, warnings, fallacies = self._apply_logic_to_facts(facts)
            result.thought = thought_steps[:self.config['max_thought_steps']]
            result.contradictions = contradictions
            result.warnings = warnings
            result.fallacies = fallacies
            
            # Következtetés
            result.conclusion = self._synthesize_conclusion_from_facts(facts, contradictions, warnings)
            
            # Bizonyosság
            result.confidence = self._calculate_confidence_from_facts(facts, warnings, fallacies, contradictions)
            
            # Validálás
            if self.config['enable_thought_validation']:
                validation_warnings = self._validate_thought(result.thought)
                result.warnings.extend(validation_warnings)
            
            # Modell használata (ha van)
            if self.config['use_model'] and self.model and self.state['model_loaded']:
                model_thought = self._get_model_thought_for_facts(user_text, facts)
                if model_thought:
                    result.thought.append("--- MODEL LOGIC ---")
                    result.thought.extend(model_thought)
            
        except Exception as e:
            self.state['errors'].append(str(e))
            result.thought = [f"ERROR: {str(e)}"]
            result.warnings.append(str(e))
            result.confidence = 0.0
        
        finally:
            result.processing_time_ms = (time.time() - start_time) * 1000
            
            # Statisztika
            if self.state['avg_processing_time_ms'] == 0:
                self.state['avg_processing_time_ms'] = result.processing_time_ms
            else:
                self.state['avg_processing_time_ms'] = (
                    self.state['avg_processing_time_ms'] * 0.9 + result.processing_time_ms * 0.1
                )
            
            self.state['thoughts_count'] += 1
            self.state['last_thought'] = result.to_dict()
            self.recent_thoughts.append(result.to_dict())
        
        return result
    
    def _gather_facts_for_thought(self, user_text: str, interpretation: Dict, context: Dict) -> List[str]:
        """Tények összegyűjtése a levezetéshez"""
        facts = []
        
        # User input
        if user_text:
            facts.append(f"USER: {user_text[:200]}")
        
        # Intent
        intent_class = interpretation.get('intent', {}).get('class', 'unknown')
        facts.append(f"INTENT: {intent_class}")
        
        # Komplexitás
        complexity = interpretation.get('complexity', 'medium')
        facts.append(f"COMPLEXITY: {complexity}")
        
        # Kontextus (Valet-től) - itt jöhet a Valet-től kapott context
        if context:
            ctx_facts = context.get('facts', [])
            if isinstance(ctx_facts, list):
                for f in ctx_facts[:5]:
                    if isinstance(f, str):
                        facts.append(f"[CONTEXT] {f}")
            
            summary = context.get('summary', '')
            if summary:
                facts.append(f"[SUMMARY] {summary[:150]}")
        
        # Scratchpad - korábbi üzenetek
        recent = self.scratchpad.read(limit=10)
        for entry in recent:
            if isinstance(entry, dict) and entry.get('type') == 'response':
                content = entry.get('content', {})
                if isinstance(content, dict):
                    response = content.get('response', '')
                    if response:
                        facts.append(f"[HISTORY] {response[:100]}")
        
        # Korábbi Queen gondolatok
        if self.recent_thoughts:
            last = self.recent_thoughts[-1]
            if isinstance(last, dict) and last.get('conclusion'):
                facts.append(f"[PREVIOUS] {last['conclusion'][:100]}")
        
        # Duplikáció szűrés
        seen = set()
        unique_facts = []
        for f in facts:
            key = hashlib.md5(f.encode()).hexdigest()[:16]
            if key not in seen:
                seen.add(key)
                unique_facts.append(f)
        
        return unique_facts[:self.config['max_facts']]
    
    def _apply_logic_to_facts(self, facts: List[str]) -> Tuple[List[str], List[str], List[str], List[str]]:
        """Logikai szabályok alkalmazása"""
        thought_steps = []
        contradictions = []
        warnings = []
        fallacies = []
        
        # Alap tények
        thought_steps.append(f"FACTS: {len(facts)} items")
        for i, fact in enumerate(facts[:5]):
            thought_steps.append(f"  {i+1}. {fact[:100]}")
        
        if len(facts) > 5:
            thought_steps.append(f"  ... and {len(facts)-5} more")
        
        # Ellentmondás keresés
        contrad = self._check_contradiction_in_facts(facts)
        if contrad:
            contradictions.append(contrad)
            thought_steps.append(f"CONTRADICTION: {contrad[:100]}")
            self.state['contradictions_found'] += 1
        
        # Implikációk
        implications = self._check_implication_in_facts(facts)
        if implications:
            thought_steps.append(f"IMPLICATIONS: {implications[:100]}")
        
        # Időbeli összefüggések
        temporal = self._check_temporal_in_facts(facts)
        if temporal:
            thought_steps.append(f"TEMPORAL: {temporal[:100]}")
        
        # Oksági kapcsolatok
        causal = self._check_causal_in_facts(facts)
        if causal:
            thought_steps.append(f"CAUSAL: {causal[:100]}")
        
        # Logikai hibák
        for fact in facts:
            fallacy = self._detect_fallacy_in_text(fact)
            if fallacy:
                fallacies.append(fallacy)
        
        # Figyelmeztetések
        if len(facts) < 2:
            warnings.append("Insufficient facts for reliable deduction")
        
        if contradictions:
            warnings.append(f"Contradiction detected: {contradictions[0][:50]}")
        
        return thought_steps, contradictions, warnings, fallacies
    
    def _check_contradiction_in_facts(self, facts: List[str]) -> Optional[str]:
        """Ellentmondások keresése"""
        contradictions = []
        
        for i, fact1 in enumerate(facts):
            if not isinstance(fact1, str):
                continue
            for fact2 in facts[i+1:]:
                if not isinstance(fact2, str):
                    continue
                
                words1 = set(fact1.lower().split())
                words2 = set(fact2.lower().split())
                
                negations = {'nem', 'nincs', 'soha', 'nem lehet', 'not', 'never', 'cannot', 'no'}
                affirmations = {'van', 'igen', 'lehet', 'is', 'can', 'yes'}
                
                content1 = words1 - negations - affirmations
                content2 = words2 - negations - affirmations
                common = content1.intersection(content2)
                
                if common:
                    neg1 = len(words1.intersection(negations))
                    neg2 = len(words2.intersection(negations))
                    
                    if (neg1 > 0) != (neg2 > 0):
                        contradictions.append(f"'{fact1[:80]}' vs '{fact2[:80]}'")
                        break
        
        return contradictions[0] if contradictions else None
    
    def _check_implication_in_facts(self, facts: List[str]) -> Optional[str]:
        """Implikációk keresése"""
        implications = []
        
        rules = [
            (['buy', 'purchase', 'get', 'take', 'vesz'], 'have'),
            (['go', 'travel', 'leave', 'megy', 'utazik'], 'not be here'),
            (['see', 'watch', 'check', 'lát', 'néz'], 'know'),
            (['learn', 'study', 'read', 'tanul', 'olvas'], 'understand')
        ]
        
        for fact in facts:
            if not isinstance(fact, str):
                continue
            fact_lower = fact.lower()
            for triggers, consequence in rules:
                if any(t in fact_lower for t in triggers):
                    words = fact.split()
                    for word in words:
                        word_lower = word.lower()
                        if len(word_lower) > 3 and word_lower not in triggers:
                            implications.append(f"If {word_lower} then {consequence}")
                            break
        
        return "; ".join(implications[:2]) if implications else None
    
    def _check_temporal_in_facts(self, facts: List[str]) -> Optional[str]:
        """Időbeli összefüggések"""
        temporal = []
        for fact in facts:
            if not isinstance(fact, str):
                continue
            for pattern in self.time_patterns:
                if re.search(pattern, fact, re.IGNORECASE):
                    temporal.append(fact[:100])
                    break
        
        if temporal:
            count = len(temporal)
            return f"{count} temporal items"
        return None
    
    def _check_causal_in_facts(self, facts: List[str]) -> Optional[str]:
        """Oksági kapcsolatok"""
        causal = []
        for fact in facts:
            if not isinstance(fact, str):
                continue
            if any(word in fact.lower() for word in self.causal_words):
                causal.append(fact[:100])
        
        if causal:
            return f"{len(causal)} causal relationships"
        return None
    
    def _detect_fallacy_in_text(self, text: str) -> Optional[str]:
        """Logikai hibák detektálása"""
        if not isinstance(text, str):
            return None
        
        text_lower = text.lower()
        for fallacy_name, patterns in self.LOGICAL_FALLACIES.items():
            for pattern in patterns:
                try:
                    if re.search(pattern, text_lower, re.IGNORECASE):
                        return fallacy_name.replace('_', ' ')
                except:
                    continue
        return None
    
    def _validate_thought(self, thought_steps: List[str]) -> List[str]:
        """Gondolatmenet validálása"""
        warnings = []
        for i, step in enumerate(thought_steps[:-1]):
            if i >= len(thought_steps) - 1:
                break
            
            next_step = thought_steps[i + 1]
            step_words = set(step.lower().split())
            next_words = set(next_step.lower().split())
            common = step_words.intersection(next_words)
            
            if len(common) < 2 and len(step_words) > 10 and len(next_words) > 10:
                warnings.append(f"Possible logical gap between steps {i+1} and {i+2}")
        
        return warnings
    
    def _synthesize_conclusion_from_facts(self, facts: List[str], contradictions: List[str], warnings: List[str]) -> str:
        """Következtetés összeállítása"""
        if not facts:
            return "INSUFFICIENT INFORMATION: No facts available for logical deduction."
        
        if contradictions:
            return f"CONTRADICTORY: {contradictions[0][:100]}. Cannot determine truth."
        
        if len(facts) < 2:
            return "LIMITED INFORMATION: Only one fact available. Conclusion may be incomplete."
        
        return "ANALYSIS COMPLETE: Proceed with response based on facts."
    
    def _calculate_confidence_from_facts(self, facts: List[str], warnings: List[str],
                                         fallacies: List[str], contradictions: List[str]) -> float:
        """Bizonyossági szint"""
        base = 0.5
        base += min(0.3, len(facts) * 0.03)
        base -= min(0.4, len(warnings) * 0.1)
        base -= min(0.3, len(fallacies) * 0.15)
        if contradictions:
            base -= 0.3
        return max(0.1, min(0.99, base))
    
    def _get_model_thought_for_facts(self, user_text: str, facts: List[str]) -> Optional[List[str]]:
        """Modell használata a CoT generálásához"""
        if not self.model:
            return None
        
        try:
            # Egyszerűbb prompt a gyorsaságért
            facts_text = "\n".join([f"- {f}" for f in facts[:5]])
            prompt = f"""Facts:
{facts_text}

Question: {user_text}

Logical conclusion:"""
            
            response = self.model.generate(
                prompt=prompt,
                max_tokens=self.config['max_tokens'],
                temperature=self.config['temperature']
            )
            
            if isinstance(response, str):
                lines = response.strip().split('\n')
                return [line.strip() for line in lines if line.strip() and len(line) > 10][:5]
            return None
            
        except Exception as e:
            self.state['errors'].append(f"Model thought error: {e}")
            return None
    
    def _load_model(self):
        """Modell betöltése"""
        if not self.model:
            return
        
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
    
    # ========== RÉGI API (KOMPATIBILITÁS) ==========
    
    def process_request(self, request: Dict) -> Dict:
        """
        JSON kérés feldolgozása (régi API kompatibilitás).
        """
        start_time = time.time()
        trace_id = request.get('trace_id', str(uuid.uuid4()))
        payload = request.get('payload', {})
        
        user_text = payload.get('text', '')
        interpretation = payload.get('intent', {})
        context = payload.get('context', {})
        
        thought = self._think(user_text, interpretation, context)
        
        return {
            "type": "queen_thought",
            "target": "king",
            "trace_id": trace_id,
            "timestamp": time.time(),
            "payload": thought.to_dict()
        }
    
    def think(self, intent_packet: Dict, context: Dict = None) -> Dict:
        """Régi API kompatibilitás"""
        payload = intent_packet.get('payload', {})
        user_text = payload.get('text', '')
        interpretation = payload.get('intent', {})
        
        thought = self._think(user_text, interpretation, context or {})
        
        return {
            'thought': thought.thought,
            'facts': thought.facts,
            'conclusion': thought.conclusion,
            'confidence': thought.confidence,
            'warnings': thought.warnings,
            'fallacies': thought.fallacies,
            'processing_time': thought.processing_time_ms / 1000
        }
    
    def get_thought_for_king_old(self, intent_packet: Dict, context: Dict = None) -> str:
        """Régi szöveges formátum a Kingnek"""
        result = self.think(intent_packet, context)
        
        parts = ["<Queen logic>"]
        parts.extend(result['thought'])
        parts.append(f"Conclusion: {result['conclusion']}")
        parts.append(f"Confidence: {result['confidence']:.1%}")
        
        if result['warnings']:
            parts.append(f"WARNING: {', '.join(result['warnings'])}")
        
        parts.append("</Queen logic>")
        
        return "\n".join(parts)
    
    # ========== PUBLIKUS API ==========
    
    def get_state(self) -> Dict:
        return {
            "type": "queen_state",
            "timestamp": time.time(),
            "payload": {
                'status': self.state['status'],
                'thoughts_count': self.state['thoughts_count'],
                'contradictions_found': self.state['contradictions_found'],
                'avg_processing_time_ms': round(self.state['avg_processing_time_ms'], 2),
                'cache_size': len(self.thought_cache),
                'errors': self.state['errors'][-5:],
                'model_loaded': self.state['model_loaded']
            }
        }
    
    def start(self):
        self.state['status'] = 'ready'
        self.scratchpad.set_state('queen_status', 'ready', self.name)
        print("👸 Queen: Készen állok a logikai feladatokra.")
    
    def stop(self):
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('queen_status', 'stopped', self.name)
        if self.model and hasattr(self.model, 'unload'):
            self.model.unload()
        print("👸 Queen: Leállt.")
    
    def clear_cache(self):
        self.thought_cache.clear()
        print("👸 Queen: Cache törölve.")
    
    def set_complexity_threshold(self, threshold: float):
        """Komplexitás küszöb beállítása"""
        self.config['complexity_threshold'] = max(0.0, min(1.0, threshold))
        print(f"👸 Queen: Komplexitás küszöb: {self.config['complexity_threshold']}")


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    queen = Queen(s)
    queen.start()
    
    # Régi API teszt
    test_intent = {
        'payload': {
            'text': "I said yesterday that I wouldn't go anywhere, but now I'm going to Budapest tomorrow.",
            'intent': {'class': 'travel'}
        }
    }
    
    result = queen.think(test_intent)
    print("Queen thought:")
    print(json.dumps(result, indent=2, default=str))
    
    print("\n--- Queen State ---")
    print(json.dumps(queen.get_state(), indent=2))
    
    queen.stop()