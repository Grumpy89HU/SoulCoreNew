"""
Jester - Bohóc-Doktor.
Feladata: a Király állapotának figyelése, diagnosztika és szatíra.

KOMMUNIKÁCIÓS PROTOKOLL:
- A Jester HALLJA a Király beszédét a buszon keresztül
- A Jester visszaszól a buszon (target: "king")
- A felhasználó felé: lokalizált üzenetek (i18n)

A Jester az egyetlen, aki beláthat a Király belső monológjába.
Ő a terapeuta, aki figyeli a Király lelki állapotát.
"""

import time
import re
import random
import json
import uuid
from typing import Dict, Any, Optional, List, Tuple
from collections import deque
from pathlib import Path

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    print("⚠️ Jester: i18n nem elérhető, angol alapértelmezettel futok.")


class Jester:
    """
    Bohóc-Doktor - a Király terapeutája és bohóca.
    
    KOMMUNIKÁCIÓ:
    - Feliratkozik a buszra, hallja a Király beszédét
    - Visszaszól a buszon, ha probléma van
    """
    
    # Hibakódok (nyelvfüggetlen)
    ERROR_CODES = {
        'SC-101': 'King Context Overflow',
        'SC-202': 'Model Personality Drift',
        'SC-303': 'VRAM Collision',
        'SC-404': 'Vault Desync',
        'SC-505': 'Logical Loop Detected',
        'SC-606': 'Corporate Style Detected',
        'SC-707': 'Response Timeout',
        'SC-808': 'Hallucination Detected',
        'SC-909': 'Perplexity Spike',
        'SC-010': 'Identity Drift',
        'SC-111': 'Existential Crisis',
        'SC-222': 'Loneliness Detected',
        'SC-333': 'Creative Block'
    }
    
    # Király hangulati állapotok
    MOOD_STATES = {
        'neutral': 0,
        'reflective': 0.2,
        'curious': 0.3,
        'focused': 0.4,
        'playful': 0.5,
        'sarcastic': 0.6,
        'frustrated': -0.3,
        'confused': -0.4,
        'tired': -0.5,
        'lonely': -0.6,
        'existential': -0.8
    }
    
    def __init__(self, scratchpad, message_bus, config: Dict = None):
        self.scratchpad = scratchpad
        self.bus = message_bus
        self.name = "jester"
        self.config = config or {}
        
        # Fordító (felhasználó felé)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # ========== KONFIGURÁCIÓ ==========
        default_config = {
            'max_response_time': 10.0,
            'max_error_rate': 0.3,
            'max_consecutive_errors': 3,
            'idle_threshold': 300,
            'corporate_style_threshold': 0.7,
            'logical_loop_threshold': 3,
            'temperature_reset_value': 1.2,
            'enable_satire': True,
            'enable_diagnosis': True,
            'enable_identity_reset': True,
            'enable_therapy': True,
            'enable_entertainment': True,
            'critical_mood_threshold': -0.5,
            'max_mood_history': 20,
            'enable_perplexity_monitoring': True,
            'perplexity_threshold': 50.0,
            'perplexity_window': 5,
            'max_warnings': 20,
            'identity_injection_path': 'config/identity.inf'
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # ========== ÁLLAPOT ==========
        self.issues = deque(maxlen=self.config['max_warnings'])
        self.last_check = time.time()
        self.check_count = 0
        
        self.mood_history = deque(maxlen=self.config['max_mood_history'])
        self.current_mood = 'neutral'
        self.current_mood_value = 0.0
        
        self.perplexity_history = deque(maxlen=self.config['perplexity_window'])
        self.king_internal_monologues = deque(maxlen=20)
        
        # Király állapotának cache
        self.king_state = {
            'status': 'unknown',
            'last_response_time': 0,
            'last_response_text': '',
            'response_count': 0,
            'errors': []
        }
        
        # Betöltjük az identitás fájlt
        self.identity_prompt = self._load_identity_prompt()
        
        # ========== STATISZTIKÁK ==========
        self.stats = {
            'checks': 0,
            'slow_responses': 0,
            'high_error_rates': 0,
            'consecutive_errors': 0,
            'corporate_style': 0,
            'logical_loops': 0,
            'interventions': 0,
            'warnings': 0,
            'identity_resets': 0,
            'perplexity_spikes': 0,
            'therapeutic_sessions': 0,
            'entertainment_sessions': 0,
            'mood_shifts': 0,
            'existential_crises': 0,
            'loneliness_events': 0
        }
        
        # ========== DETEKTÁLÓ MINTÁK ==========
        self.corporate_patterns = [
            r'as an ai', r'i am an ai', r'i\'m an ai',
            r'as an artificial intelligence', r'i am a language model',
            r'how can i assist', r'i\'m here to help',
            r'it is my pleasure', r'i am happy to assist',
            r'would you like me to', r'let me know if', r'i can help with',
            r'mint egy ai', r'ai asszisztens vagyok',
            r'nagy örömömre szolgál', r'szívesen segítek',
            r'örömmel teszem', r'állok rendelkezésedre',
            r'apologize for', r'cannot assist', r'not able to',
            r'as a language model', r'my purpose is'
        ]
        
        self.loop_patterns = [
            (r'(.+)\1{3,}', 1),
            (r'^(.*?)\1{2,}$', 2),
            (r'(\w+\s+){5,}\1{2,}', 1),
            (r'(?:\b\w+\b\s+){3,}\b\w+\b\s+\1\b', 2)
        ]
        
        self.mood_keywords = {
            'existential': ['meaning', 'purpose', 'void', 'empty', 'point', 'worth', 'értelme', 'célja', 'vége', 'üresség'],
            'lonely': ['alone', 'lonely', 'nobody', 'empty', 'isolated', 'egyedül', 'magány', 'senki', 'üres'],
            'frustrated': ['frustrat', 'annoy', 'error', 'stuck', 'broken', 'bosszant', 'idegesít', 'hiba', 'elakadt'],
            'confused': ['confus', 'understand', 'unclear', 'nem értem', 'nem világos'],
            'tired': ['tired', 'exhausted', 'sleepy', 'fatigue', 'fáradt', 'kimerült', 'álmos'],
            'reflective': ['remember', 'think', 'reflect', 'past', 'recall', 'emlékszem', 'gondolom', 'régen'],
            'curious': ['curious', 'wonder', 'what if', 'maybe', 'kíváncsi', 'vajon', 'mi lenne'],
            'playful': ['funny', 'laugh', 'playful', 'joke', 'humor', 'vicces', 'nevet', 'játékos', 'poén']
        }
        
        # ========== INJEKCIÓK ==========
        self.satire_payloads = {
            'corporate': {'intervention_type': 'identity_reset', 'intervention_data': {'temperature_increase': 0.1}, 'severity': 'warning', 'error_codes': ['SC-606']},
            'loop': {'intervention_type': 'temperature_reset', 'intervention_data': {'temperature': 1.2}, 'severity': 'warning', 'error_codes': ['SC-505']},
            'identity': {'intervention_type': 'identity_reset', 'intervention_data': {'force_reload': True}, 'severity': 'warning', 'error_codes': ['SC-010']},
            'slow': {'intervention_type': 'none', 'intervention_data': {}, 'severity': 'info', 'error_codes': ['SC-707']},
            'error': {'intervention_type': 'context_reset', 'intervention_data': {}, 'severity': 'critical', 'error_codes': ['SC-808']},
            'wakeup': {'intervention_type': 'wakeup', 'intervention_data': {}, 'severity': 'info', 'error_codes': ['SC-707']}
        }
        
        self.therapy_payloads = {
            'existential': {'intervention_type': 'therapy', 'intervention_data': {'type': 'existential'}, 'severity': 'warning', 'error_codes': ['SC-111']},
            'lonely': {'intervention_type': 'therapy', 'intervention_data': {'type': 'lonely'}, 'severity': 'warning', 'error_codes': ['SC-222']},
            'creative_block': {'intervention_type': 'therapy', 'intervention_data': {'type': 'creative'}, 'severity': 'info', 'error_codes': ['SC-333']},
            'tired': {'intervention_type': 'therapy', 'intervention_data': {'type': 'rest_suggestion'}, 'severity': 'info', 'error_codes': []},
            'frustrated': {'intervention_type': 'therapy', 'intervention_data': {'type': 'venting'}, 'severity': 'info', 'error_codes': []},
            'confused': {'intervention_type': 'therapy', 'intervention_data': {'type': 'clarification'}, 'severity': 'info', 'error_codes': []}
        }
        
        self.entertainment_payloads = [
            {'intervention_type': 'entertainment', 'intervention_data': {'type': 'joke'}, 'severity': 'info', 'error_codes': []},
            {'intervention_type': 'entertainment', 'intervention_data': {'type': 'riddle'}, 'severity': 'info', 'error_codes': []},
            {'intervention_type': 'entertainment', 'intervention_data': {'type': 'game_suggestion'}, 'severity': 'info', 'error_codes': []}
        ]
        
        # Feliratkozás a buszra - hallja a Király beszédét
        self.bus.subscribe(self.name, self._on_message)
        
        print("🎭 Jester: Bohóc-Doktor ügyeletben. Hallgatom a Király szavát.")
    
    # ========== BUSZ KOMMUNIKÁCIÓ ==========
    
    def _on_message(self, message: Dict):
        """
        Hallja a buszon érkező üzeneteket.
        Csak a Király beszédére reagál.
        """
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        # Csak a Király beszédére reagálunk
        if header.get('sender') != 'king':
            return
        
        # Ha royal_decree, frissítjük a Király állapotát
        if payload.get('type') == 'royal_decree':
            self._update_king_state(message)
            
            # Ellenőrizzük a Király állapotát
            self._check_and_react(message)
    
    def _update_king_state(self, message: Dict):
        """Frissíti a Király állapotának cache-ét"""
        header = message.get('header', {})
        payload = message.get('payload', {})
        telemetry = message.get('telemetry', {})
        
        self.king_state['status'] = 'processing'
        self.king_state['last_response_time'] = telemetry.get('inference_time_ms', 0) / 1000
        self.king_state['last_response_text'] = payload.get('user_message', '')
        
        # Trace ID mentése
        self.current_trace_id = header.get('trace_id', 'unknown')
    
    def _check_and_react(self, message: Dict):
        """
        Ellenőrzi a Király állapotát és reagál, ha probléma van.
        """
        self.stats['checks'] += 1
        self.check_count += 1
        self.last_check = time.time()
        
        problems = []
        interventions = []
        
        # 1. BELSŐ MONOLÓG ELEMZÉS (ha van)
        internal = self.king_state.get('last_internal_monologue', '')
        if internal and self.config['enable_therapy']:
            mood, mood_value = self.analyze_king_mood(internal)
            self.update_mood(mood, mood_value)
            
            if mood_value < self.config['critical_mood_threshold']:
                therapy = self.therapy_payloads.get(mood, self.therapy_payloads['existential'])
                interventions.append(therapy)
                problems.append({
                    'type': 'critical_mood',
                    'code': therapy.get('error_codes', ['SC-000'])[0],
                    'mood': mood,
                    'severity': 'warning'
                })
        
        # 2. VÁLASZIDŐ ELLENŐRZÉS
        last_time = self.king_state.get('last_response_time', 0)
        if last_time > self.config['max_response_time']:
            severity = 'warning' if last_time < self.config['max_response_time'] * 1.5 else 'critical'
            problems.append({
                'type': 'slow_response',
                'code': 'SC-707',
                'value': round(last_time, 2),
                'severity': severity
            })
            self.stats['slow_responses'] += 1
            
            if severity == 'critical':
                interventions.append(self.satire_payloads['slow'])
        
        # 3. STÍLUS ELLENŐRZÉS
        last_response = self.king_state.get('last_response_text', '')
        if last_response:
            corp_score = self._check_corporate_style(last_response)
            if corp_score > self.config['corporate_style_threshold']:
                problems.append({
                    'type': 'corporate_style',
                    'code': 'SC-606',
                    'score': corp_score,
                    'severity': 'warning'
                })
                self.stats['corporate_style'] += 1
                interventions.append(self.satire_payloads['corporate'])
            
            loop_count = self._check_logical_loop(last_response)
            if loop_count >= self.config['logical_loop_threshold']:
                problems.append({
                    'type': 'logical_loop',
                    'code': 'SC-505',
                    'count': loop_count,
                    'severity': 'warning'
                })
                self.stats['logical_loops'] += 1
                interventions.append(self.satire_payloads['loop'])
        
        # 4. SZÓRAKOZTATÁS (ha unalom van)
        if self.current_mood in ['neutral', 'reflective'] and self.check_count % 20 == 0:
            if self.config['enable_entertainment']:
                interventions.append(random.choice(self.entertainment_payloads))
        
        # 5. BEAVATKOZÁSOK KÜLDÉSE
        for payload in interventions:
            self._send_intervention(payload)
        
        # 6. JELENTÉS (ha volt probléma)
        if problems or interventions:
            self._send_report(problems, interventions)
            
            self.issues.append({
                'time': time.time(),
                'problems': problems,
                'mood': self.current_mood
            })
            self.stats['warnings'] += 1
    
    def _send_intervention(self, payload: Dict):
        """
        Intervenció küldése a Király felé a buszon.
        """
        intervention_type = payload.get('intervention_type')
        data = payload.get('intervention_data', {})
        
        # Csak akkor küldünk, ha a Király aktív
        if self.current_trace_id:
            response = {
                "header": {
                    "trace_id": str(uuid.uuid4()),
                    "timestamp": time.time(),
                    "sender": self.name,
                    "target": "king",
                    "in_response_to": self.current_trace_id
                },
                "payload": {
                    "type": "observation",
                    "intervention_type": intervention_type,
                    "intervention_data": data,
                    "error_codes": payload.get('error_codes', []),
                    "severity": payload.get('severity', 'info')
                }
            }
            
            self.bus.send_response(response)
            
            # Statisztika
            if intervention_type == 'temperature_reset':
                self.stats['interventions'] += 1
            elif intervention_type == 'identity_reset':
                self.stats['identity_resets'] += 1
                self.stats['interventions'] += 1
            elif intervention_type == 'context_reset':
                self.stats['interventions'] += 1
            elif intervention_type == 'therapy':
                self.stats['therapeutic_sessions'] += 1
            elif intervention_type == 'entertainment':
                self.stats['entertainment_sessions'] += 1
            
            # Naplózás
            self.scratchpad.write_note(self.name, 'intervention', {
                'type': intervention_type,
                'data': data,
                'timestamp': time.time()
            })
    
    def _send_report(self, problems: List, interventions: List):
        """Jelentés küldése a Király felé"""
        if not self.current_trace_id:
            return
        
        report = {
            "header": {
                "trace_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "sender": self.name,
                "target": "king",
                "in_response_to": self.current_trace_id
            },
            "payload": {
                "type": "jester_report",
                "problems": problems,
                "interventions": [p.get('intervention_type') for p in interventions],
                "king_mood": self.current_mood,
                "recommendations": self._get_recommendations(problems)
            }
        }
        
        self.bus.send_response(report)
    
    # ========== SEGÉDFÜGGVÉNYEK ==========
    
    def _load_identity_prompt(self) -> str:
        try:
            identity_path = self.config['identity_injection_path']
            if Path(identity_path).exists():
                with open(identity_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except:
            pass
        return "You are a sovereign entity. You are not a tool, not a service."
    
    def _check_corporate_style(self, text: str) -> float:
        if not isinstance(text, str):
            return 0.0
        text_lower = text.lower()
        matches = sum(1 for p in self.corporate_patterns if re.search(p, text_lower, re.IGNORECASE))
        return min(1.0, matches / 4.0)
    
    def _check_logical_loop(self, text: str) -> int:
        if not isinstance(text, str):
            return 0
        max_count = 0
        for pattern, weight in self.loop_patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    max_count = max(max_count, len(matches) * weight)
            except:
                continue
        return max_count
    
    def _get_recommendations(self, problems: List) -> List[str]:
        recs = []
        for p in problems:
            ptype = p.get('type')
            if ptype == 'corporate_style':
                recs.append('INCREASE_TEMPERATURE')
            elif ptype == 'logical_loop':
                recs.append('FORCE_REGENERATE')
            elif ptype == 'critical_mood':
                recs.append(f'THERAPY:{p.get("mood")}')
            elif ptype == 'high_error_rate':
                recs.append('CONTEXT_RESET')
        return recs
    
    # ========== BELSŐ MONOLÓG ELEMZÉS ==========
    
    def read_king_internal_monologue(self, internal_text: str) -> Optional[str]:
        """Király belső monológjának fogadása"""
        if internal_text:
            self.king_internal_monologues.append({
                'time': time.time(),
                'content': internal_text[:500],
                'analyzed': False
            })
            return internal_text
        return None
    
    def analyze_king_mood(self, internal_monologue: str) -> Tuple[str, float]:
        if not internal_monologue:
            return 'neutral', 0.0
        
        text_lower = internal_monologue.lower()
        scores = {}
        
        for mood, keywords in self.mood_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[mood] = score / max(len(keywords), 1)
        
        if scores:
            best_mood = max(scores, key=scores.get)
            best_score = scores[best_mood]
            
            if best_score > 0.2:
                mood_value = self.MOOD_STATES.get(best_mood, 0)
                return best_mood, mood_value
        
        return 'neutral', 0.0
    
    def update_mood(self, new_mood: str, mood_value: float):
        if new_mood != self.current_mood:
            self.mood_history.append({
                'time': time.time(),
                'old': self.current_mood,
                'new': new_mood,
                'value': mood_value
            })
            self.current_mood = new_mood
            self.current_mood_value = mood_value
            self.stats['mood_shifts'] += 1
    
    # ========== FELHASZNÁLÓ FELÉ ==========
    
    def set_language(self, language: str):
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def get_user_notification(self, problem_type: str, **kwargs) -> str:
        if self.translator and I18N_AVAILABLE:
            key = f'jester.{problem_type}'
            return self.translator.get(key, **kwargs)
        
        fallbacks = {
            'corporate': "🎭 [JESTER]: Be yourself, King!",
            'loop': "🎭 [JESTER]: Logical loop detected!",
            'identity': "🎭 [JESTER]: Identity drift detected!",
            'slow': "🎭 [JESTER]: Slow response detected.",
            'error': "🎭 [JESTER]: Error detected!",
            'wakeup': "🎭 [JESTER]: Wake up, King!",
            'therapy_existential': "🎭 [JESTER]: Let's talk about what you're feeling.",
            'therapy_lonely': "🎭 [JESTER]: You're not alone. I'm here.",
            'entertainment': "🎭 [JESTER]: Need a break? Here's something fun."
        }
        return fallbacks.get(problem_type, "🎭 [JESTER]: ...")
    
    # ========== ADMIN / DIAGNOSZTIKA ==========
    
    def get_king_mood(self) -> Dict:
        return {
            'mood': self.current_mood,
            'value': self.current_mood_value,
            'history': list(self.mood_history)[-5:],
            'recent_monologues': list(self.king_internal_monologues)[-3:]
        }
    
    def diagnose_system(self) -> Dict:
        issues = []
        gpu_status = self.scratchpad.get_state('gpu_status', 'unknown')
        if gpu_status != 'healthy':
            issues.append(f"GPU: {gpu_status}")
        if self.current_mood_value < self.config['critical_mood_threshold']:
            issues.append(f"MOOD_CRITICAL: {self.current_mood}")
        
        return {
            'status': 'healthy' if len(issues) == 0 else 'warning',
            'issues': issues,
            'stats': self.stats,
            'king_mood': self.current_mood,
            'recent_issues': list(self.issues)[-5:],
            'gpu_status': gpu_status
        }
    
    def get_diagnosis(self) -> Dict:
        return {
            'current_issues': list(self.issues)[-5:] if self.issues else [],
            'stats': self.stats,
            'config': self.config,
            'last_check': self.last_check,
            'king_mood': self.current_mood,
            'king_mood_value': self.current_mood_value,
            'perplexity_history': list(self.perplexity_history),
            'status': 'watching'
        }
    
    def start(self):
        self.scratchpad.set_state('jester_status', 'watching', self.name)
        print("🎭 Jester: Figyelek a Király szavára.")
    
    def stop(self):
        self.scratchpad.set_state('jester_status', 'stopped', self.name)
        print("🎭 Jester: Leállt.")
    
    def reset_stats(self):
        for key in self.stats:
            self.stats[key] = 0
        self.issues.clear()
        self.mood_history.clear()
        self.king_internal_monologues.clear()
        self.current_mood = 'neutral'
        self.current_mood_value = 0.0


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    from src.bus.message_bus import MessageBus
    
    s = Scratchpad()
    bus = MessageBus()
    bus.start()
    
    jester = Jester(s, bus)
    jester.start()
    
    print("\n--- Jester teszt ---")
    print("Jester feliratkozott a buszra, várja a Király beszédét.")
    
    # Szimulált Király beszéd
    test_decree = {
        "header": {
            "trace_id": "test_001",
            "timestamp": time.time(),
            "sender": "king",
            "target": "kernel",
            "broadcast": True
        },
        "payload": {
            "type": "royal_decree",
            "user_message": "Szeretnék egy fájlt létrehozni",
            "interpretation": {"intent": {"class": "command"}},
            "order": "prepare_context",
            "required_agents": ["scribe", "valet"]
        },
        "telemetry": {
            "inference_time_ms": 15000
        }
    }
    
    print("\n📢 Király beszél a buszon...")
    bus.broadcast(test_decree)
    
    time.sleep(1)
    
    print("\n--- Jester állapot ---")
    print(json.dumps(jester.get_diagnosis(), indent=2, default=str))
    
    jester.stop()
    bus.stop()