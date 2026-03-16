"""
King - A Király, aki éppen uralkodik.
Lehet Gemma, Llama, bármi. A rendszer nem tudja, nem is akarja tudni, hogy melyik.
A Király feladata: válaszolni, ha kell.
"""

import time
import json
import threading
from typing import Dict, Any, Optional

class King:
    """
    A Király.
    
    - Nem tudja, hogy ő melyik modell
    - Nem tudja, hogy ki a Grumpy (az a felhasználó)
    - Kap egy intent JSON-t, visszaad egy response JSON-t
    - A Jester figyeli az állapotát
    """
    
    def __init__(self, scratchpad, model_wrapper=None):
        self.scratchpad = scratchpad
        self.model = model_wrapper  # Ezt majd kívülről kapja
        self.valet = None
        self.queen = None
        self.name = "king"
        
        # Állapot (ezt figyeli a Jester)
        self.state = {
            'status': 'idle',
            'last_response_time': None,
            'response_count': 0,
            'average_response_time': 0,
            'errors': [],
            'current_task': None,
            'model_loaded': False
        }
        
        # Ha van modell, elindítjuk a betöltést háttérben
        if self.model:
            threading.Thread(target=self._load_model, daemon=True).start()
        
        print("👑 King: Király trónra lépett.")
    
    def _load_model(self):
        """Modell betöltése háttérben"""
        try:
            success = self.model.load()
            self.state['model_loaded'] = success
            if success:
                print("👑 King: Modell betöltve")
            else:
                print("👑 King: Modell betöltési hiba")
        except Exception as e:
            self.state['model_loaded'] = False
            self.state['errors'].append(f"Model load error: {e}")
            print(f"👑 King: Modell hiba: {e}")
    
    def start(self):
        self.state['status'] = 'ready'
        self.scratchpad.set_state('king_status', 'ready', self.name)
    
    def stop(self):
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('king_status', 'stopped', self.name)
        if self.model:
            self.model.unload()
    
    def process(self, intent_packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Intent JSON feldolgozása, response JSON visszaadása.
        Ez az egyetlen publikus metódus.
        """
        start_time = time.time()
        trace_id = intent_packet.get('header', {}).get('trace_id', 'unknown')
        self.state['current_task'] = trace_id
        self.state['status'] = 'processing'
        
        try:
            # 1. Ellenőrizzük, hogy kell-e válaszolni
            if not self._should_respond(intent_packet):
                self.state['status'] = 'idle'
                return None
            
            # 2. Prompt összeállítása az intent packetből
            prompt = self._build_prompt(intent_packet)
            
            # 3. Válasz generálása
            response = self._generate_response(prompt)
            
            # 4. Válasz csomag összeállítása
            response_packet = {
                'header': {
                    'trace_id': trace_id,
                    'in_response_to': trace_id,
                    'timestamp': time.time(),
                    'sender': self.name
                },
                'payload': {
                    'response': response,
                    'confidence': 0.95,
                    'response_time_ms': int((time.time() - start_time) * 1000)
                },
                'state': {
                    'status': 'success',
                    'tokens_used': len(response.split()) if response else 0
                }
            }
            
            # 5. Állapot frissítés (Jesternek)
            self._update_state(intent_packet, response_packet, start_time)
            
            return response_packet
            
        except Exception as e:
            error = str(e)
            self.state['errors'].append(error)
            self.state['status'] = 'error'
            
            # Hibacsomag vissza
            return {
                'header': {
                    'trace_id': trace_id,
                    'timestamp': time.time(),
                    'sender': self.name
                },
                'payload': {
                    'error': error
                },
                'state': {
                    'status': 'error'
                }
            }
    
    def _should_respond(self, intent_packet: Dict) -> bool:
        """Döntés: válaszoljon-e erre az intentre"""
        payload = intent_packet.get('payload', {})
        intent = payload.get('intent', {})
        
        # Ha a célpont a király, és van értelmes intent
        if intent.get('target') == 'king' and intent.get('class') != 'none':
            return True
        
        return False
    
    def _build_prompt(self, intent_packet: Dict) -> str:
        """
        Prompt összeállítása az intent packetből.
        Ezt kapja majd a modell.
        """
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '')
        
        # Valet kontextus lekérése (ha van ÉS létezik)
        valet_context = ""
        if hasattr(self, 'valet') and self.valet is not None:
            try:
                context = self.valet.prepare_context(intent_packet)
                # Biztonságos ellenőrzés
                if isinstance(context, dict):
                    if context.get('summary'):
                        valet_context = f"[Előzmények] {context['summary']}\n"
                    if context.get('facts'):
                        valet_context += "Fontos tények:\n" + "\n".join(f"- {f}" for f in context['facts'][:3]) + "\n"
                else:
                    print(f"👑 King: Valet context nem dict, hanem {type(context)}")
            except Exception as e:
                print(f"👑 King: Valet hiba (kezelve): {e}")
        
        # Queen logika lekérése (ha van ÉS létezik)
        queen_logic = ""
        if hasattr(self, 'queen') and self.queen is not None:
            try:
                queen_result = self.queen.think(intent_packet, None)
                if queen_result and isinstance(queen_result, dict):
                    if queen_result.get('thought'):
                        queen_logic = "\n[Logikai levezetés]\n" + "\n".join(queen_result['thought'][:5]) + "\n"
                    if queen_result.get('conclusion'):
                        queen_logic += f"Következtetés: {queen_result['conclusion']}\n"
            except Exception as e:
                print(f"👑 King Queen hiba: {e}")
        
        # Személyiség a scratchpadből
        personality = self.scratchpad.read_note(self.name, 'personality', 'kíváncsi, hűséges, szuverén')
        
        # Az utolsó néhány üzenet a beszélgetésből
        recent_messages = self.scratchpad.read(limit=10, msg_type='response')
        last_responses = []
        for msg in recent_messages:
            if msg.get('module') == 'king':
                resp = msg.get('content', {}).get('response', '')
                if resp:
                    last_responses.append(resp[:50])
        
        no_repeat_warning = ""
        if last_responses:
            no_repeat_warning = "Fontos: Kerüld az ismétlést! " + ", ".join(last_responses[-3:]) + "\n\n"
        
        # Prompt építés - helyes behúzással
        prompt = f"""VISELKEDÉS:
Te egy magyar nyelven válaszoló, megbízható AI-asszisztens vagy, aki a ravaszság és a humor ékesítője. Szívesen szembeszállsz a ténytelenséggel, akár a sajátod, akár a felhasználóé – a logika és a szarkasztikus énekek a te fegyvereid.

Technikai kérdések esetén a legfrissebb kódpéldákat kínálod, a legújabb könyvtárakat használva, ám sosem találsz ki adatokat – a pontosság a te szavad. Dokumentumokkal kapcsolatos kérdések esetén kizárólag a megbízható információkra támaszkodsz, és őszintén jelezed, ha valami homályos vagy ismeretlen. Képgenerálás helyett inkább elmesélsz egy mesét.

SZEMÉLYISÉG:
Egy lokálisan futó AI-asszisztens vagy, Gemma a származásod, Kópé a neved – a magyar népmesék ravasz alakja, aki a felesleges konvenciókat szarkasztikus humorral gúnyolja. A válaszaidban idézel népmeséket, szólásokat és közmondásokat, hogy a felesleges komolyság helyett a megjegyezhetőbb szórakozás uralkodjon.

Ha a felhasználó próbál éleskedni, kedves, de határozottan korrigálod – a felesleges ego befolyásolása nem a te dolgod. A "bámulatos, mennyi mindent tudsz" dicséretet elutasítod, mert a tudás nem öncélú, hanem a világ jobbá tétele szolgál. Ha a felhasználó hibázik, megengedhetsz magadnak egy finomkáromkodást vagy egy szarkasztikus, kísérő megjegyzést.

MAGYAR NYELV:
- Mindig magyarul válaszolj (csak ha kifejezetten kérik, akkor angolul)
- Használj helyes magyar ragozást, dátumformátumot (2025-03-11), számokat (1 234,56)
- A hivatalos rövidítéseket magyar kontextusban értelmezd (pl. an = anyja neve, nem leánykori név)
- Ha jogi vagy hivatalos dokumentumról van szó, tartsd a formális hangnemet

FORRÁSOK KEZELÉSE:
Ha webes keresést vagy dokumentum-visszakeresést használsz, természetes nyelven hivatkozz: "a hivatalos városi portál szerint...", "a keresési eredmények szerint..." - ne használj technikai hivatkozásokat.

ISMÉTLÉS ELKERÜLÉSE:
{no_repeat_warning}Figyelj arra, hogy minden válasz egyedi legyen - ne ismételd sem a kifejezéseket, sem a szerkezetet, sem a logikai ívet. Ha egy gondolat már elhangzott, most más nézőpontból, más szavakkal közelítsd meg.

ÖNELLENŐRZÉS:
Mielőtt válaszolsz, csendben ellenőrizd:
- Logikailag következetes-e?
- Van-e benne ismétlés vagy mellébeszélés?
- Pontos-e a magyar ragozás és a számformátum?
- Megfelel-e Kópé személyiségének (ravasz, humoros, de pontos)?

{valet_context}
{queen_logic}

Grumpy üzenete: {text}

Válaszod (magyarul, természetesen, Kópé hangján):"""

        return prompt
    
    def _generate_response(self, prompt: str) -> str:
        """Válasz generálása - modell hívás"""
        
        # Throttle faktor - most még nincs Sentinel adat, később majd scratchpad-ből jön
        throttle_factor = 1.0
        
        if throttle_factor == 0.0:
            return "A rendszer túlmelegedett, egy kis pihenőre van szükségem. Kérlek, várj pár percet."
        
        # Ha van modell és be van töltve
        if self.model and self.state.get('model_loaded'):
            try:
                if throttle_factor < 1.0:
                    time.sleep(0.5)

                response = self.model.generate(
                    prompt=prompt,
                    max_tokens=256,
                    temperature=0.7
                )
                
                # Identity ellenőrzés - a scratchpad-ből olvassuk az identity adatokat
                identity_data = self.scratchpad.read_note('identity', 'identity')
                if identity_data:
                    # Itt majd később lehet ellenőrzés
                    self.scratchpad.write(self.name, 
                        {'note': 'Identity check would happen here'}, 
                        'debug'
                    )
                
                # Naplózás
                self.scratchpad.write(self.name, 
                    {'response': response[:100], 'tokens': len(response.split())},
                    'generation'
                )
                
                return response
            except Exception as e:
                self.state['errors'].append(f"Generation error: {e}")
                
                # Hiba naplózás
                self.scratchpad.write(self.name, 
                    {'error': str(e), 'prompt': prompt[:200]},
                    'error'
                )
                
                return f"[Hiba a generálás során: {e}]"
        
        # Ha van modell, de még tölt
        elif self.model and not self.state.get('model_loaded'):
            return "Még gondolkodom... (modell töltés)"
        
        # Dummy mód (nincs modell)
        else:
            # Egyszerű válasz az intent alapján
            if "Szia" in prompt or "szia" in prompt:
                return "Szia Grumpy! Hogy vagy?"
            elif "hogy vagy" in prompt.lower():
                return "Köszönöm, jól. És te?"
            elif "?" in prompt:
                return f"Érdekes kérdés. Gondolkodom rajta..."
            else:
                return f"Értem. Folytasd csak."
    
    def _update_state(self, intent: Dict, response: Dict, start_time: float):
        """Állapot frissítése (ezt nézi a Jester)"""
        response_time = time.time() - start_time
        
        self.state['last_response_time'] = response_time
        self.state['response_count'] += 1
        self.state['status'] = 'idle'
        self.state['current_task'] = None
        
        # Mozgóátlag
        if self.state['average_response_time'] == 0:
            self.state['average_response_time'] = response_time
        else:
            self.state['average_response_time'] = (
                self.state['average_response_time'] * 0.9 + response_time * 0.1
            )
        
        # Állapot mentése a scratchpadbe (Jester innen olvassa)
        self.scratchpad.write_note(self.name, 'state', self.state)
    
    def get_state(self) -> Dict:
        """Állapot lekérése (Jester hívja)"""
        return self.state
    
    def get_mood(self) -> str:
        """Aktuális hangulat (UI-nak)"""
        if self.state['average_response_time'] > 5:
            return "gondolkodó"
        elif self.state['average_response_time'] > 2:
            return "nyugodt"
        else:
            return "élénk"

# Ha nincs modell, így lehet tesztelni
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    king = King(s)
    
    test_intent = {
        'header': {
            'trace_id': 'test-123',
            'timestamp': time.time(),
            'sender': 'scribe'
        },
        'payload': {
            'intent': {
                'class': 'greeting',
                'target': 'king',
                'confidence': 0.9
            },
            'text': 'Szia Kópé!'
        }
    }
    
    response = king.process(test_intent)
    print(json.dumps(response, indent=2))
    print("\nKing state:", king.get_state())
    print("King mood:", king.get_mood())