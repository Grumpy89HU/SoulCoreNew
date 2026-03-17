"""
King - A Király, aki éppen uralkodik.
Lehet Gemma, Llama, bármi. A rendszer nem tudja, nem is akarja tudni, hogy melyik.
A Király feladata: válaszolni, ha kell.
"""

import time
import json
import threading
import random
from typing import Dict, Any, Optional

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    print("⚠️ King: i18n nem elérhető, angol alapértelmezettel futok.")

class King:
    """
    A Király.
    
    - Nem tudja, hogy ő melyik modell
    - Nem tudja, hogy ki a felhasználó (az a user)
    - Kap egy intent JSON-t, visszaad egy response JSON-t
    - A Jester figyeli az állapotát
    - Identitását a scratchpadből kapja (oda a main tölti)
    """
    
    def __init__(self, scratchpad, model_wrapper=None):
        self.scratchpad = scratchpad
        self.model = model_wrapper
        self.valet = None
        self.queen = None
        self.name = "king"
        
        # Fordító (később állítjuk be a felhasználó nyelvére)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Állapot (ezt figyeli a Jester)
        self.state = {
            'status': 'idle',
            'last_response_time': None,
            'last_response_text': None,
            'response_count': 0,
            'average_response_time': 0,
            'errors': [],
            'current_task': None,
            'model_loaded': False
        }
        
        # Identitás (scratchpadből jön)
        self.identity = {
            'name': 'King',
            'title': 'The Sovereign',
            'personality': 'wise, curious, sovereign'
        }
        
        # Ha van modell, elindítjuk a betöltést háttérben
        if self.model:
            threading.Thread(target=self._load_model, daemon=True).start()
        
        print("👑 King: Király trónra lépett.")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
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
            
            # 2. Identitás betöltése a scratchpadből
            self._load_identity()
            
            # 3. Prompt összeállítása
            prompt = self._build_prompt(intent_packet)
            
            # 4. Válasz generálása
            response = self._generate_response(prompt)
            
            # 5. Válasz csomag összeállítása
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
            
            # 6. Állapot frissítés
            self.state['last_response_text'] = response[:200]
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
    
    def _load_identity(self):
        """Identitás betöltése a scratchpadből"""
        stored = self.scratchpad.read_note(self.name, 'personality')
        if stored and isinstance(stored, str):
            # Egyszerű string esetén
            self.identity['personality'] = stored
        elif stored and isinstance(stored, dict):
            # Összetett identitás esetén
            self.identity.update(stored)
        
        # Név a scratchpadből
        name = self.scratchpad.read_note(self.name, 'name')
        if name:
            self.identity['name'] = name
    
    def _should_respond(self, intent_packet: Dict) -> bool:
        """Döntés: válaszoljon-e erre az intentre"""
        payload = intent_packet.get('payload', {})
        intent = payload.get('intent', {})
        
        if not isinstance(intent, dict):
            return False
        
        # Ha a célpont a király, és van értelmes intent
        if intent.get('target') == 'king' and intent.get('class') != 'none':
            return True
        
        # Proaktív üzenetekre is válaszoljon
        if intent.get('class') == 'PROACTIVE':
            return True
        
        return False
    
    def _build_prompt(self, intent_packet: Dict) -> str:
        """
        Prompt összeállítása az intent packetből.
        Ezt kapja majd a modell.
        """
        payload = intent_packet.get('payload', {})
        if not isinstance(payload, dict):
            payload = {}
        
        text = payload.get('text', '')
        if not isinstance(text, str):
            text = str(text)
        
        # Felhasználó neve
        user_name = self.scratchpad.get_state('user_name', 'User')
        
        # Nyelv
        language = self.scratchpad.get_state('user_language', 'en')
        if self.translator:
            self.translator.set_language(language)
        
        # Valet kontextus (ha van)
        valet_context = ""
        if hasattr(self, 'valet') and self.valet is not None:
            try:
                context = self.valet.prepare_context(intent_packet)
                if isinstance(context, dict):
                    if context.get('summary'):
                        valet_context = f"[Context] {context['summary']}\n"
                    if context.get('facts'):
                        facts = context['facts'][:3]
                        if facts:
                            valet_context += "Facts:\n" + "\n".join(f"- {f}" for f in facts) + "\n"
            except Exception as e:
                print(f"👑 King: Valet error: {e}")
        
        # Queen logika (ha van)
        queen_logic = ""
        if hasattr(self, 'queen') and self.queen is not None:
            try:
                queen_result = self.queen.think(intent_packet, None)
                if isinstance(queen_result, dict) and queen_result.get('conclusion'):
                    queen_logic = f"[Logic] {queen_result['conclusion']}\n"
            except Exception as e:
                print(f"👑 King: Queen error: {e}")
        
        # Az utolsó néhány üzenet (ismétlés elkerülésére)
        recent_messages = self.scratchpad.read(limit=5, msg_type='response')
        last_responses = []
        for msg in recent_messages:
            if isinstance(msg, dict) and msg.get('module') == 'king':
                content = msg.get('content', {})
                if isinstance(content, dict) and 'response' in content:
                    resp = content['response']
                    if isinstance(resp, str) and resp:
                        last_responses.append(resp[:50])
        
        no_repeat = ""
        if last_responses and random.random() < 0.3:  # 30% eséllyel emlékeztet
            no_repeat = f"(Avoid repeating: {', '.join(last_responses[-2:])})\n"
        
        # Prompt építés - i18n használatával
        if self.translator and I18N_AVAILABLE:
            # Strukturált prompt i18n-ből
            system = self.translator.get('prompts.king.system')
            personality = self.translator.get('prompts.king.personality', personality=self.identity['personality'])
            
            prompt = f"""{system}
{personality}

{valet_context}{queen_logic}{no_repeat}
{user_name}: {text}

{self.identity['name']}:"""
        else:
            # Fallback angol prompt
            prompt = f"""You are {self.identity['name']}, {self.identity.get('title', 'a sovereign entity')}.
Personality: {self.identity['personality']}

{valet_context}{queen_logic}{no_repeat}
{user_name}: {text}

{self.identity['name']}:"""
        
        return prompt
    
    def _generate_response(self, prompt: str) -> str:
        """Válasz generálása - modell hívás"""
        
        # Ha van modell és be van töltve
        if self.model and self.state.get('model_loaded'):
            try:
                response = self.model.generate(
                    prompt=prompt,
                    max_tokens=256,
                    temperature=0.7
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
                
                # Hibaválasz i18n-ből
                if self.translator:
                    return f"[{self.translator.get('errors.generation_error', error=str(e))}]"
                return f"[Generation error: {e}]"
        
        # Ha van modell, de még tölt
        elif self.model and not self.state.get('model_loaded'):
            if self.translator:
                return self.translator.get('prompts.king.thinking')
            return "Thinking... (model loading)"
        
        # Dummy mód (nincs modell)
        else:
            # Egyszerű válasz az intent alapján
            if "hello" in prompt.lower() or "hi" in prompt.lower() or "szia" in prompt.lower():
                if self.translator:
                    return self.translator.get('prompts.king.greeting', user=self.scratchpad.get_state('user_name', 'User'))
                return f"Hello {self.scratchpad.get_state('user_name', 'User')}!"
            elif "?" in prompt:
                if self.translator:
                    return self.translator.get('prompts.king.thinking')
                return "Interesting question. Let me think..."
            else:
                if self.translator:
                    return "OK."
                return "I understand."
    
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
        
        # Állapot mentése (Jesternek)
        self.scratchpad.write_note(self.name, 'state', dict(self.state))
    
    def get_state(self) -> Dict:
        """Állapot lekérése (Jester hívja)"""
        if isinstance(self.state, dict):
            return self.state
        return {
            'status': 'error',
            'last_response_time': None,
            'response_count': 0,
            'average_response_time': 0,
            'errors': [f"Invalid state: {type(self.state)}"],
            'current_task': None,
            'model_loaded': False
        }
    
    def get_mood(self) -> str:
        """Aktuális hangulat (UI-nak)"""
        if self.state['average_response_time'] > 5:
            return "thoughtful"
        elif self.state['average_response_time'] > 2:
            return "calm"
        else:
            return "lively"

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    s.set_state('user_name', 'TestUser')
    s.write_note('king', 'personality', 'curious, helpful, witty')
    
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
            'text': 'Hello!'
        }
    }
    
    response = king.process(test_intent)
    print(json.dumps(response, indent=2))
    print("\nKing state:", king.get_state())
    print("King mood:", king.get_mood())