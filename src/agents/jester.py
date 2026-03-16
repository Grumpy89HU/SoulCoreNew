"""
Jester - Bohóc-Doktor.
Feladata: a Király állapotának figyelése.
- Ha a Király túl lassú -> jelez
- Ha a Király hibázik -> jelez
- Ha a Király túl sokat hibázik -> riaszt
- Ha a Király "elaludt" (nem válaszol) -> ébreszt
"""

import time
from typing import Dict, Any, Optional, List

class Jester:
    """
    Bohóc-Doktor.
    
    Nem beszél a felhasználóval.
    Nem elemez szövegeket.
    Csak a Király állapotát figyeli.
    
    Ha baj van, JSON-t ír a buszba, amit mások (pl. orchestrator) olvashatnak.
    """
    
    def __init__(self, scratchpad):
        self.scratchpad = scratchpad
        self.name = "jester"
        
        # Konfiguráció (később config fájlból)
        self.config = {
            'max_response_time': 10.0,  # 10 másodperc max
            'max_error_rate': 0.3,       # 30% hibaarány
            'max_consecutive_errors': 3,  # 3 egymás utáni hiba
            'idle_threshold': 300         # 5 perc inaktivitás
        }
        
        # Detektált problémák
        self.issues = []
        self.last_check = time.time()
        
        print("🎭 Jester: Bohóc-Doktor ügyeletben. Királyt figyelem.")
    
    def start(self):
        self.scratchpad.set_state('jester_status', 'watching', self.name)
    
    def stop(self):
        self.scratchpad.set_state('jester_status', 'stopped', self.name)
    
    def check_king(self, king_state: Dict) -> Optional[Dict[str, Any]]:
        """
        Király állapotának ellenőrzése.
        Meghívható:
        - Rendszeresen (heartbeat)
        - Eseményre (pl. új response)
        
        Visszaad egy report-ot, ha problémát talál.
        """
        print(f"🎭 Jester check: {king_state}")  # <-- EZT ADD IDE
        problems = []
        
        # 1. Válaszidő ellenőrzés
        last_time = king_state.get('last_response_time')
        if last_time and last_time > self.config['max_response_time']:
            problems.append({
                'type': 'slow_response',
                'value': last_time,
                'threshold': self.config['max_response_time'],
                'severity': 'warning' if last_time < self.config['max_response_time'] * 1.5 else 'critical'
            })
        
        # 2. Hibák ellenőrzése
        errors = king_state.get('errors', [])
        if errors:
            # Hibaarány
            response_count = max(king_state.get('response_count', 1), 1)
            error_rate = len(errors) / response_count
            
            if error_rate > self.config['max_error_rate']:
                problems.append({
                    'type': 'high_error_rate',
                    'value': error_rate,
                    'threshold': self.config['max_error_rate'],
                    'severity': 'critical',
                    'errors': errors[-5:]  # utolsó 5 hiba
                })
            
            # Egymás utáni hibák
            if len(errors) >= self.config['max_consecutive_errors']:
                last_errors = errors[-self.config['max_consecutive_errors']:]
                if all(e for e in last_errors):  # mind hiba
                    problems.append({
                        'type': 'consecutive_errors',
                        'count': len(last_errors),
                        'threshold': self.config['max_consecutive_errors'],
                        'severity': 'critical',
                        'errors': last_errors
                    })
        
        # 3. Inaktivitás ellenőrzés
        last_response_time = king_state.get('last_response_time')
        if last_response_time:
            time_since_response = time.time() - (time.time() - last_response_time)  # ez nem jó, javítandó
            # TODO: utolsó response timestamp kellene
        
        # Ha van probléma, report készítés
        if problems:
            report = {
                'header': {
                    'timestamp': time.time(),
                    'sender': self.name,
                    'type': 'king_status_report'
                },
                'payload': {
                    'king_state': {
                        'status': king_state.get('status'),
                        'response_count': king_state.get('response_count', 0),
                        'average_response_time': king_state.get('average_response_time', 0)
                    },
                    'problems': problems,
                    'summary': self._summarize_problems(problems)
                }
            }
            
            # Elmentjük a problémát
            self.issues.append({
                'time': time.time(),
                'problems': problems,
                'summary': report['payload']['summary']
            })
            
            # Csak az utolsó 10-et tartjuk
            if len(self.issues) > 10:
                self.issues = self.issues[-10:]
            
            return report
        
        return None
    
    def _summarize_problems(self, problems: List) -> str:
        """Problémák összefoglalása egy mondatban"""
        if not problems:
            return "Minden rendben"
        
        criticals = [p for p in problems if p.get('severity') == 'critical']
        warnings = [p for p in problems if p.get('severity') == 'warning']
        
        if criticals:
            types = [p['type'] for p in criticals]
            return f"KRITIKUS: {', '.join(types)}"
        elif warnings:
            types = [p['type'] for p in warnings]
            return f"FIGYELMEZTETÉS: {', '.join(types)}"
        
        return "Ismeretlen probléma"
    
    def get_diagnosis(self) -> Dict:
        """Teljes diagnózis lekérése"""
        return {
            'current_issues': self.issues[-5:] if self.issues else [],
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
        print(f"\n--- Ellenőrzés ---")
        report = jester.check_king(state)
        if report:
            print(f"Probléma: {report['payload']['summary']}")
            for p in report['payload']['problems']:
                print(f"  - {p['type']}: {p.get('severity')}")
        else:
            print("Minden rendben")
