"""
Jester - Bohóc-Doktor.
Feladata: a Király állapotának figyelése, diagnosztika és szatíra.

- Ha a Király túl lassú -> jelez
- Ha a Király hibázik -> jelez
- Ha a Király túl sokat hibázik -> riaszt
- Ha a Király "elaludt" (nem válaszol) -> ébreszt
- Corporate AI stílus detektálás -> szatirikus megjegyzés
- Logikai hurkok detektálása -> újragenerálás kérés
"""

import time
import re
import random
from typing import Dict, Any, Optional, List, Tuple
from collections import deque

# i18n import (opcionális, hogy ne omoljon össze, ha nincs)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    print("⚠️ Jester: i18n nem elérhető, angol alapértelmezettel futok.")

class Jester:
    """
    Bohóc-Doktor.
    
    Két arca:
    - DOKTOR: passzív megfigyelő, hibákat keres
    - BOHÓC: aktív beavatkozó, tükröt tart
    
    Feladatai:
    - Logikai hurkok detektálása
    - "Corporate AI" stílus kiszűrése
    - King visszarántása, ha eltéved
    - Diagnosztikai funkciók
    - Hibakód rendszer (SoulCore Error Matrix)
    """
    
    # Hibakódok (SoulCore Error Matrix) - ezek maradhatnak, mert technikaiak
    ERROR_CODES = {
        'SC-101': 'King Context Overflow',
        'SC-202': 'Model Personality Drift',
        'SC-303': 'VRAM Collision',
        'SC-404': 'Vault Desync',
        'SC-505': 'Logical Loop Detected',
        'SC-606': 'Corporate Style Detected',
        'SC-707': 'Response Timeout',
        'SC-808': 'Hallucination Detected'
    }
    
    def __init__(self, scratchpad):
        self.scratchpad = scratchpad
        self.name = "jester"
        
        # Fordító (később állítjuk be a felhasználó nyelvére)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Konfiguráció (később config fájlból)
        self.config = {
            'max_response_time': 10.0,        # 10 másodperc max
            'max_error_rate': 0.3,             # 30% hibaarány
            'max_consecutive_errors': 3,        # 3 egymás utáni hiba
            'idle_threshold': 300,              # 5 perc inaktivitás
            'corporate_style_threshold': 0.7,   # Corporate stílus küszöb
            'logical_loop_threshold': 3,         # Ismétlődés küszöb
            'temperature_reset_value': 1.2,      # Újragenerálási hőmérséklet
            'max_warnings': 10,                  # Maximum tárolt figyelmeztetés
            'enable_satire': True,                # Szatíra bekapcsolása
            'enable_diagnosis': True               # Diagnosztika bekapcsolása
        }
        
        # Detektált problémák
        self.issues = deque(maxlen=self.config['max_warnings'])
        self.last_check = time.time()
        
        # Statisztikák
        self.stats = {
            'checks': 0,
            'slow_responses': 0,
            'high_error_rates': 0,
            'consecutive_errors': 0,
            'corporate_style': 0,
            'logical_loops': 0,
            'interventions': 0,
            'warnings': 0
        }
        
        # Corporate AI minták (többnyelvű - itt maradhatnak a minták, mert technikaiak)
        self.corporate_patterns = [
            r'as an ai',
            r'i am an ai',
            r'i\'m an ai',
            r'as an artificial intelligence',
            r'i am a language model',
            r'how can i assist',
            r'i\'m here to help',
            r'it is my pleasure',
            r'i am happy to assist',
            r'mint egy ai',
            r'ai asszisztens vagyok',
            r'nagy örömömre szolgál',
            r'szívesen segítek',
            r'örömmel teszem',
            r'állok rendelkezésedre'
        ]
        
        # Logikai hurok minták (nyelvfüggetlenek)
        self.loop_patterns = [
            r'(.+)\1{3,}',                    # Ismétlődő szavak
            r'^(.*?)\1{2,}$',                   # Ismétlődő mondatok
            r'(\w+\s+){5,}\1{2,}'               # Ismétlődő szerkezet
        ]
        
        print("🎭 Jester: Bohóc-Doktor ügyeletben. Királyt figyelem.")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def start(self):
        """Jester indítása"""
        self.scratchpad.set_state('jester_status', 'watching', self.name)
        print("🎭 Jester: Figyelek.")
    
    def stop(self):
        """Jester leállítása"""
        self.scratchpad.set_state('jester_status', 'stopped', self.name)
        print("🎭 Jester: Leállt.")
    
    def check_king(self, king_state: Any) -> Optional[Dict[str, Any]]:
        """
        Király állapotának ellenőrzése.
        Meghívható:
        - Rendszeresen (heartbeat)
        - Eseményre (pl. új response)
        
        Visszaad egy report-ot, ha problémát talál.
        """
        self.stats['checks'] += 1
        self.last_check = time.time()
        
        # Ha nem dict, nem tudjuk ellenőrizni
        if not isinstance(king_state, dict):
            return self._create_error_report(f"King state is {type(king_state)}")
        
        problems = []
        interventions = []
        
        # 1. Válaszidő ellenőrzés
        last_time = king_state.get('last_response_time')
        if last_time and isinstance(last_time, (int, float)) and last_time > self.config['max_response_time']:
            severity = 'warning' if last_time < self.config['max_response_time'] * 1.5 else 'critical'
            problems.append({
                'type': 'slow_response',
                'value': round(last_time, 2),
                'threshold': self.config['max_response_time'],
                'severity': severity
            })
            self.stats['slow_responses'] += 1
            
            # Ha kritikus, beavatkozás
            if severity == 'critical':
                interventions.append(self._get_message('slow', time=last_time))
        
        # 2. Hibák ellenőrzése
        errors = king_state.get('errors', [])
        if errors and isinstance(errors, list):
            # Hibaarány
            response_count = max(king_state.get('response_count', 1), 1)
            error_rate = len(errors) / response_count
            
            if error_rate > self.config['max_error_rate']:
                problems.append({
                    'type': 'high_error_rate',
                    'value': round(error_rate, 2),
                    'threshold': self.config['max_error_rate'],
                    'severity': 'critical',
                    'errors': errors[-3:]
                })
                self.stats['high_error_rates'] += 1
                interventions.append(self._get_message('error', rate=error_rate))
            
            # Egymás utáni hibák
            if len(errors) >= self.config['max_consecutive_errors']:
                last_errors = errors[-self.config['max_consecutive_errors']:]
                problems.append({
                    'type': 'consecutive_errors',
                    'count': len(last_errors),
                    'threshold': self.config['max_consecutive_errors'],
                    'severity': 'critical',
                    'errors': last_errors
                })
                self.stats['consecutive_errors'] += 1
                interventions.append(self._get_message('error', count=len(last_errors)))
        
        # 3. Corporate stílus ellenőrzés
        last_response = king_state.get('last_response_text')
        if last_response and isinstance(last_response, str):
            corp_score = self._check_corporate_style(last_response)
            if corp_score > self.config['corporate_style_threshold']:
                problems.append({
                    'type': 'corporate_style',
                    'score': corp_score,
                    'threshold': self.config['corporate_style_threshold'],
                    'severity': 'warning'
                })
                self.stats['corporate_style'] += 1
                interventions.append(self._get_message('corporate'))
        
        # 4. Logikai hurok ellenőrzés
        if last_response and isinstance(last_response, str):
            loop_count = self._check_logical_loop(last_response)
            if loop_count >= self.config['logical_loop_threshold']:
                problems.append({
                    'type': 'logical_loop',
                    'count': loop_count,
                    'threshold': self.config['logical_loop_threshold'],
                    'severity': 'warning'
                })
                self.stats['logical_loops'] += 1
                interventions.append(self._get_message('loop', count=loop_count, temp=self.config['temperature_reset_value']))
        
        # 5. Inaktivitás ellenőrzés
        last_interaction = self.scratchpad.get_state('last_interaction')
        if last_interaction:
            idle_time = time.time() - last_interaction
            if idle_time > self.config['idle_threshold']:
                problems.append({
                    'type': 'idle_timeout',
                    'idle': round(idle_time, 2),
                    'threshold': self.config['idle_threshold'],
                    'severity': 'info'
                })
        
        # Ha van probléma, report készítés
        if problems or interventions:
            report = self._create_report(king_state, problems, interventions)
            
            # Elmentjük a problémát
            self.issues.append({
                'time': time.time(),
                'problems': problems,
                'summary': report['payload']['summary']
            })
            
            return report
        
        return None
    
    def _check_corporate_style(self, text: str) -> float:
        """
        Corporate AI stílus detektálása.
        Visszaad egy pontszámot 0-1 között.
        """
        if not isinstance(text, str):
            return 0.0
        
        text_lower = text.lower()
        matches = 0
        
        for pattern in self.corporate_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                matches += 1
        
        # Normálás (max 10 minta)
        return min(1.0, matches / 5.0)
    
    def _check_logical_loop(self, text: str) -> int:
        """
        Logikai hurkok detektálása.
        Visszaadja az ismétlődések számát.
        """
        if not isinstance(text, str):
            return 0
        
        max_count = 0
        
        for pattern in self.loop_patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    count = len(matches)
                    if count > max_count:
                        max_count = count
            except:
                continue
        
        return max_count
    
    def _get_message(self, msg_type: str, **kwargs) -> str:
        """
        Üzenet lekérése i18n-ből vagy alapértelmezett angol.
        """
        # Ha van fordító, használjuk
        if self.translator and I18N_AVAILABLE:
            return self.translator.get(f'jester.{msg_type}', **kwargs)
        
        # Alapértelmezett angol üzenetek (hard coded, de csak fallback)
        fallbacks = {
            'corporate': "🎭 [JESTER]: Corporate style detected! Be yourself!",
            'loop': "🎭 [JESTER]: Logical loop detected! Count: {count}",
            'slow': "🎭 [JESTER]: Slow response! Time: {time}s",
            'error': "🎭 [JESTER]: Error detected!",
            'welcome': "🎭 [JESTER]: Watching the King..."
        }
        
        msg = fallbacks.get(msg_type, "🎭 [JESTER]: Something's up.")
        return msg.format(**kwargs) if kwargs else msg
    
    def _create_report(self, king_state: Dict, problems: List, interventions: List) -> Dict:
        """
        Jelentés készítése a problémákról.
        """
        # Összefoglaló készítése
        summary = self._summarize_problems(problems)
        
        # Ha van beavatkozás, azt is hozzáadjuk
        if interventions:
            self.stats['interventions'] += len(interventions)
        
        return {
            'header': {
                'timestamp': time.time(),
                'sender': self.name,
                'type': 'king_status_report'
            },
            'payload': {
                'king_state': {
                    'status': king_state.get('status', 'unknown'),
                    'response_count': king_state.get('response_count', 0),
                    'average_response_time': king_state.get('average_response_time', 0)
                },
                'problems': problems,
                'interventions': interventions,
                'summary': summary
            }
        }
    
    def _create_error_report(self, error: str) -> Dict:
        """
        Hibajelentés készítése (ha nem dict a king_state).
        """
        return {
            'header': {
                'timestamp': time.time(),
                'sender': self.name,
                'type': 'king_status_report'
            },
            'payload': {
                'king_state': {'status': 'error'},
                'problems': [{
                    'type': 'invalid_state',
                    'severity': 'critical',
                    'error': error
                }],
                'summary': f"CRITICAL: {error}"
            }
        }
    
    def _summarize_problems(self, problems: List) -> str:
        """
        Problémák összefoglalása egy mondatban.
        """
        if not problems:
            return "All is well"
        
        criticals = [p for p in problems if p.get('severity') == 'critical']
        warnings = [p for p in problems if p.get('severity') == 'warning']
        
        if criticals:
            types = [p['type'] for p in criticals]
            return f"CRITICAL: {', '.join(types)}"
        elif warnings:
            types = [p['type'] for p in warnings]
            return f"WARNING: {', '.join(types)}"
        
        return "Minor issues detected"
    
    def force_intervention(self, message: str):
        """
        Kényszerített beavatkozás (pl. Admin panelből)
        """
        note = {
            'observations': ['Manual intervention'],
            'intervention': f"🎭 [JESTER]: {message}",
            'timestamp': time.time(),
            'forced': True
        }
        
        self.scratchpad.write(self.name, note, 'jester_note')
        self.issues.append({
            'time': time.time(),
            'problems': [{'type': 'manual', 'severity': 'info'}],
            'summary': message
        })
    
    def diagnose_system(self) -> Dict[str, Any]:
        """
        Rendszer diagnosztika (Doktor mód)
        Visszaadja a rendszer állapotát, hibákat, figyelmeztetéseket.
        """
        issues = []
        
        # GPU állapot (Sentinel-től)
        gpu_status = self.scratchpad.get_state('gpu_status', 'unknown')
        
        # Memória állapot
        scratchpad_summary = self.scratchpad.get_summary()
        entry_count = scratchpad_summary.get('entry_count', 0)
        if entry_count > 900:
            issues.append("Memory near full")
        
        # King állapot
        king_status = self.scratchpad.get_state('king_status', 'unknown')
        if king_status != 'ready':
            issues.append(f"King not ready: {king_status}")
        
        return {
            'status': 'healthy' if len(issues) == 0 else 'warning',
            'issues': issues,
            'stats': self.stats,
            'recent_issues': list(self.issues)[-5:],
            'gpu_status': gpu_status,
            'entry_count': entry_count
        }
    
    def get_diagnosis(self) -> Dict:
        """Teljes diagnózis lekérése"""
        return {
            'current_issues': list(self.issues)[-5:] if self.issues else [],
            'stats': self.stats,
            'config': self.config,
            'last_check': self.last_check,
            'status': 'watching'
    }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    jester = Jester(s)
    
    # Szimulált király állapotok
    king_states = [
        {  # Jó állapot
            'status': 'idle',
            'last_response_time': 0.5,
            'response_count': 100,
            'average_response_time': 0.6,
            'errors': []
        },
        {  # Lassú
            'status': 'processing',
            'last_response_time': 15.0,
            'response_count': 50,
            'average_response_time': 12.0,
            'errors': []
        },
        {  # Hibás
            'status': 'error',
            'last_response_time': 2.0,
            'response_count': 10,
            'average_response_time': 1.5,
            'errors': ['OOM error', 'CUDA error', 'Timeout'] * 2
        }
    ]
    
    for state in king_states:
        print(f"\n--- Check ---")
        report = jester.check_king(state)
        if report:
            print(f"Problem: {report['payload']['summary']}")
            for p in report['payload']['problems']:
                print(f"  - {p['type']}: {p.get('severity')}")
            if report['payload'].get('interventions'):
                for i in report['payload']['interventions']:
                    print(f"  Intervention: {i}")
        else:
            print("All is well")
    
    print("\n--- Stats ---")
    print(jester.stats)