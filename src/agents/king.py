"""
King - A Király, aki éppen uralkodik.
Lehet Gemma, Llama, bármi. A rendszer nem tudja, nem is akarja tudni, hogy melyik.
A Király feladata: válaszolni, ha kell.

RAG integráció:
- Valet-től kapott kontextussal dolgozik
- Graph-Vault (Neo4j) és Vector-Vault (Qdrant) adatokat építi be
- Érzelmi kontextus alapján hangolja a választ
"""

import time
import json
import threading
import random
import hashlib
import uuid
from typing import Dict, Any, Optional, List
from collections import deque

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
    - Valet-től kapott RAG kontextust épít be a válaszába
    """
    
    # Prompt verziók (különböző stílusokhoz)
    PROMPT_STYLES = {
        'default': 0,
        'concise': 1,    # Rövid, tömör
        'detailed': 2,   # Részletes, magyarázó
        'poetic': 3,     # Költői, metaforikus
        'technical': 4   # Technikai, precíz
    }
    
    def __init__(self, scratchpad, orchestrator=None, model_wrapper=None):
        self.scratchpad = scratchpad
        self.model = model_wrapper
        self.valet = None      # Valet hivatkozás (később beállítva)
        self.queen = None
        self.orchestrator = orchestrator
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
            'model_loaded': False,
            'total_tokens_generated': 0,
            'total_processing_time': 0,
            'last_mood': 'neutral',
            'rag_used': False,           # RAG használat jelző
            'last_context_summary': None  # Utolsó használt kontextus
        }
        
        # Identitás (scratchpadből jön)
        self.identity = {
            'name': 'assistant',
            'title': 'The Sovereign',
            'personality': 'wise, curious, sovereign',
            'style': 'default'
        }
        
        # Kontextus cache (gyorsítótár az ismétlődő promptokhoz)
        self.context_cache = {}
        self.cache_ttl = 300  # 5 perc
        
        # Legutóbbi válaszok (ismétlés elkerülésére)
        self.recent_responses = deque(maxlen=10)
        
        # Generálási paraméterek (dinamikusan állítható)
        self.generation_params = {
            'max_tokens': 256,
            'temperature': 0.7,
            'top_p': 0.9,
            'top_k': 40,
            'repeat_penalty': 1.1,
            'frequency_penalty': 0.0,
            'presence_penalty': 0.0
        }
        
        # Válasz callback a WebApp felé
        self.response_callback = None
        
        # Ha van modell, elindítjuk a betöltést háttérben
        if self.model:
            threading.Thread(target=self._load_model, daemon=True).start()
        
        print("👑 King: Király trónra lépett.")
    
    def set_valet(self, valet):
        """Valet modul beállítása (memória logisztika)"""
        self.valet = valet
        print("👑 King: Valet kapcsolat beállítva")
    
    def set_queen(self, queen):
        """Queen modul beállítása (CoT logika)"""
        self.queen = queen
        print("👑 King: Queen kapcsolat beállítva")
    
    # ========== FŐ BELÉPÉSI PONT (WebApp + Valet kontextus) ==========
    
    def generate_response(self, user_text: str, trace_id: str = None, 
                         conversation_id: int = None,
                         conversation_history: List[Dict] = None,
                         rag_context: Dict = None) -> str:
        """
        Egyszerű belépési pont a WebApp számára.
        Létrehoz egy intent packetet, és feldolgozza a Valet kontextussal.
        
        Args:
            user_text: A felhasználó üzenete
            trace_id: Opcionális nyomkövetési azonosító
            conversation_id: Opcionális beszélgetés azonosító
            conversation_history: Előzmények listája (opcionális)
            rag_context: Valet-től kapott RAG kontextus (opcionális)
        
        Returns:
            str: A generált válasz szövege
        """
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        # Intent packet összeállítása
        intent_packet = {
            'header': {
                'trace_id': trace_id,
                'timestamp': time.time(),
                'version': '3.0',
                'sender': 'webapp'
            },
            'payload': {
                'intent': {
                    'class': 'USER_MESSAGE',
                    'target': 'king',
                    'confidence': 1.0
                },
                'text': user_text,
                'raw_text': user_text,
                'conversation_id': conversation_id,
                'conversation_history': conversation_history or [],
                'rag_context': rag_context or {}
            }
        }
        
        # Feldolgozás a meglévő process metódussal
        response_packet = self.process(intent_packet)
        
        # Válasz szöveg kinyerése
        if response_packet and isinstance(response_packet, dict):
            payload = response_packet.get('payload', {})
            if isinstance(payload, dict):
                return payload.get('response', '')
            elif isinstance(payload, str):
                return payload
        
        return self._get_error_message("No response generated")
    
    def set_response_callback(self, callback):
        """
        Beállítja a válasz callbacket a WebApp felé.
        A callback függvény: callback(response_text, conversation_id, trace_id)
        """
        self.response_callback = callback
    
    # ========== MEGLÉVŐ METÓDUSOK (kibővítve) ==========
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def set_style(self, style: str):
        """Stílus beállítása (default, concise, detailed, poetic, technical)"""
        if style in self.PROMPT_STYLES:
            self.identity['style'] = style
    
    def set_generation_params(self, **kwargs):
        """Generálási paraméterek módosítása"""
        for key, value in kwargs.items():
            if key in self.generation_params:
                self.generation_params[key] = value
    
    def _load_model(self):
        """Modell betöltése háttérben (timeout-tal)"""
        try:
            import queue
            result_queue = queue.Queue()
            
            def load_thread():
                try:
                    success = self.model.load()
                    result_queue.put(('success', success))
                except Exception as e:
                    result_queue.put(('error', str(e)))
            
            thread = threading.Thread(target=load_thread)
            thread.daemon = True
            thread.start()
            thread.join(timeout=30)  # 30 másodperc timeout
            
            if thread.is_alive():
                print("👑 King: Modell betöltés timeout (30s)")
                self.state['model_loaded'] = False
                self.state['errors'].append("Model load timeout")
                return
            
            try:
                status, result = result_queue.get_nowait()
                if status == 'success':
                    self.state['model_loaded'] = result
                    if result:
                        print("👑 King: Modell betöltve")
                    else:
                        print("👑 King: Modell betöltési hiba")
                else:
                    self.state['model_loaded'] = False
                    self.state['errors'].append(f"Model load error: {result}")
                    print(f"👑 King: Modell hiba: {result}")
            except queue.Empty:
                self.state['model_loaded'] = False
                
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
        Ez az egyetlen publikus metódus (a generate_response ezt hívja).
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
            
            # 3. RAG kontextus kinyerése az intent_packet-ből (Valet-től jött)
            rag_context = intent_packet.get('payload', {}).get('rag_context', {})
            self.state['rag_used'] = bool(rag_context)
            
            # 4. Prompt összeállítása (cache-elve, RAG kontextussal)
            prompt = self._build_prompt_cached(intent_packet, rag_context)
            
            # 5. Válasz generálása
            response = self._generate_response(prompt)
            
            # 6. Válasz csomag összeállítása
            tokens_used = len(response.split())
            processing_time = time.time() - start_time
            
            response_packet = {
                'header': {
                    'trace_id': trace_id,
                    'in_response_to': trace_id,
                    'timestamp': time.time(),
                    'sender': self.name
                },
                'payload': {
                    'response': response,
                    'confidence': self._calculate_confidence(intent_packet),
                    'response_time_ms': int(processing_time * 1000),
                    'tokens_used': tokens_used,
                    'mood': self._get_current_mood(),
                    'rag_used': self.state['rag_used']
                },
                'state': {
                    'status': 'success',
                    'tokens_used': tokens_used,
                    'processing_time': processing_time
                }
            }
            
            # 7. Állapot frissítés
            self.state['last_response_text'] = response[:200]
            self.state['total_tokens_generated'] += tokens_used
            self.state['total_processing_time'] += processing_time
            self.state['last_context_summary'] = rag_context.get('summary', '')[:100]
            self.recent_responses.append(hashlib.md5(response.encode()).hexdigest()[:8])
            self._update_state(intent_packet, response_packet, start_time)
            
            # 8. Callback hívás (ha van)
            if self.response_callback:
                conv_id = intent_packet.get('payload', {}).get('conversation_id')
                self.response_callback(response, conv_id, trace_id)
            
            return response_packet
            
        except Exception as e:
            error = str(e)
            self.state['errors'].append(error)
            self.state['status'] = 'error'
            
            error_response = {
                'header': {
                    'trace_id': trace_id,
                    'timestamp': time.time(),
                    'sender': self.name
                },
                'payload': {
                    'error': error,
                    'mood': 'error'
                },
                'state': {
                    'status': 'error'
                }
            }
            
            if self.response_callback:
                conv_id = intent_packet.get('payload', {}).get('conversation_id')
                self.response_callback(f"Hiba: {error}", conv_id, trace_id)
            
            return error_response
    
    def _load_identity(self):
        """Identitás betöltése a scratchpadből"""
        stored = self.scratchpad.read_note(self.name, 'personality')
        if stored:
            if isinstance(stored, str):
                self.identity['personality'] = stored
            elif isinstance(stored, dict):
                self.identity.update(stored)
        
        # Név a scratchpadből
        name = self.scratchpad.read_note(self.name, 'name')
        if name:
            self.identity['name'] = name
        
        # Stílus a scratchpadből
        style = self.scratchpad.read_note(self.name, 'style')
        if style and style in self.PROMPT_STYLES:
            self.identity['style'] = style
    
    def _should_respond(self, intent_packet: Dict) -> bool:
        """Döntés: válaszoljon-e erre az intentre"""
        payload = intent_packet.get('payload', {})
        intent = payload.get('intent', {})
        
        if not isinstance(intent, dict):
            return False
        
        intent_class = intent.get('class', '')
        
        # Ha a célpont a király
        if intent.get('target') == 'king' and intent_class != 'none':
            return True
        
        # Proaktív üzenetek
        if intent_class == 'PROACTIVE':
            return True
        
        # Fontos rendszer üzenetek
        if intent_class in ['SYSTEM_ALERT', 'ERROR']:
            return True
        
        # USER_MESSAGE (WebApp-ból jön)
        if intent_class == 'USER_MESSAGE':
            return True
        
        return False
    
    def _build_prompt_cached(self, intent_packet: Dict, rag_context: Dict = None) -> str:
        """
        Prompt összeállítása cache-eléssel a gyorsításért.
        RAG kontextust is beépíti.
        """
        # Cache kulcs generálása
        payload = intent_packet.get('payload', {})
        text = payload.get('text', '')
        intent_class = payload.get('intent', {}).get('class', 'unknown')
        language = self.scratchpad.get_state('user_language', 'en')
        
        # RAG kontextus hash-e (ha van)
        rag_hash = ''
        if rag_context:
            rag_str = f"{rag_context.get('summary', '')}_{rag_context.get('facts', [])}"
            rag_hash = hashlib.md5(rag_str.encode()).hexdigest()[:8]
        
        cache_key = hashlib.md5(
            f"{text}_{intent_class}_{language}_{self.identity['style']}_{rag_hash}".encode()
        ).hexdigest()
        
        # Cache ellenőrzés
        if cache_key in self.context_cache:
            cached_time, cached_prompt = self.context_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_prompt
        
        # Új prompt építés
        prompt = self._build_prompt(intent_packet, rag_context)
        
        # Cache mentés
        self.context_cache[cache_key] = (time.time(), prompt)
        
        # Cache takarítás
        if len(self.context_cache) > 100:
            self._cleanup_cache()
        
        return prompt
    
    def _cleanup_cache(self):
        """Régi cache bejegyzések törlése"""
        now = time.time()
        to_delete = []
        for key, (timestamp, _) in self.context_cache.items():
            if now - timestamp > self.cache_ttl:
                to_delete.append(key)
        for key in to_delete:
            del self.context_cache[key]
    
    def _build_prompt(self, intent_packet: Dict, rag_context: Dict = None) -> str:
        """
        Prompt összeállítása az intent packetből és RAG kontextusból.
        A prompt tömör, csak az aktuális üzenet + releváns kontextus.
        """
        payload = intent_packet.get('payload', {})
        if not isinstance(payload, dict):
            payload = {}
        
        text = payload.get('text', '')
        if not isinstance(text, str):
            text = str(text)
        
        # Felhasználó neve
        user_name = self.scratchpad.get_state('user_name', 'user')
        
        # Nyelv
        language = self.scratchpad.get_state('user_language', 'en')
        if self.translator:
            self.translator.set_language(language)
        
        # Stílus alapú prompt építés
        style = self.identity.get('style', 'default')
        
        # Prompt részek
        prompt_parts = []
        
        # Instrukció a modellnek, hogy ne ismételje vissza a felhasználó üzenetét
        if language == 'hu':
            prompt_parts.append("Figyelem: Csak a saját válaszodat írd le, ne ismételd vissza a felhasználó üzenetét!")
            prompt_parts.append("Ne írd ki, hogy 'User:' vagy 'Assistant:'!")
        else:
            prompt_parts.append("Note: Only write your own response, do not repeat the user's message!")
            prompt_parts.append("Do not write 'User:' or 'Assistant:'!")
        
        # Stílus prefix
        style_prefix = self._get_style_prefix(style, language)
        if style_prefix:
            prompt_parts.append(style_prefix)
        
        # ========== RAG KONTEXTUS BEÉPÍTÉSE ==========
        if rag_context:
            # Összefoglaló
            summary = rag_context.get('summary', '')
            if summary:
                prompt_parts.append(f"\n## Összefoglaló\n{summary}")
            
            # Tények
            facts = rag_context.get('facts', [])
            if facts:
                facts_text = "\n".join([f"• {f}" for f in facts[:3]])
                prompt_parts.append(f"\n## Ismert tények\n{facts_text}")
            
            # Gráf kontextus (kapcsolatok)
            graph_context = rag_context.get('graph_context', [])
            if graph_context and isinstance(graph_context, list):
                if graph_context:
                    graph_text = "\n".join([f"• {g}" for g in graph_context[:3]])
                    prompt_parts.append(f"\n## Kapcsolatok\n{graph_text}")
            
            # Vektor kontextus (globális tudás)
            vector_context = rag_context.get('vector_context', [])
            if vector_context and isinstance(vector_context, list):
                if vector_context:
                    vector_text = "\n".join([f"• {v}" for v in vector_context[:2]])
                    prompt_parts.append(f"\n## Tudás\n{vector_text}")
            
            # Érzelmi kontextus
            emotional = rag_context.get('emotional_context', {})
            if emotional.get('recent_mood'):
                mood = emotional['recent_mood']
                if language == 'hu':
                    mood_text = {"positive": "pozitív", "negative": "negatív", "neutral": "semleges"}
                    prompt_parts.append(f"\n## Hangulat\nA beszélgetés hangulata: {mood_text.get(mood, mood)}")
                else:
                    prompt_parts.append(f"\n## Mood\nThe conversation mood is: {mood}")
        
        # Csak az aktuális üzenet
        prompt_parts.append(f"\n{user_name}: {text}")
        prompt_parts.append(f"{self.identity['name']}:")
        
        return "\n".join(prompt_parts)
    
    def _get_style_prefix(self, style: str, language: str) -> str:
        """Stílus alapú prompt előtag lekérése"""
        if language == 'hu':
            prefixes = {
                'default': '',
                'concise': 'Légy rövid és tömör.',
                'detailed': 'Magyarázz részletesen.',
                'poetic': 'Válaszolj költőien, metaforákkal.',
                'technical': 'Használj szakszerű, precíz nyelvezetet.'
            }
        else:
            prefixes = {
                'default': '',
                'concise': 'Be concise.',
                'detailed': 'Explain in detail.',
                'poetic': 'Answer poetically, with metaphors.',
                'technical': 'Use technical, precise language.'
            }
        
        return prefixes.get(style, '')
    
    def _generate_response(self, prompt: str) -> str:
        """Válasz generálása - modell hívás timeout-tal"""
        
        # Ha van modell és be van töltve
        if self.model and self.state.get('model_loaded'):
            try:
                import queue
                result_queue = queue.Queue()
                
                def generate_thread():
                    try:
                        response = self.model.generate(
                            prompt=prompt,
                            max_tokens=self.generation_params.get('max_tokens', 256),
                            temperature=self.generation_params.get('temperature', 0.7),
                            top_p=self.generation_params.get('top_p', 0.9),
                            top_k=self.generation_params.get('top_k', 40),
                            repeat_penalty=self.generation_params.get('repeat_penalty', 1.1),
                            stop=None,
                            stream=False
                        )
                        result_queue.put(('success', response))
                    except Exception as e:
                        result_queue.put(('error', str(e)))
                
                thread = threading.Thread(target=generate_thread)
                thread.daemon = True
                thread.start()
                thread.join(timeout=30)  # 30 másodperc timeout
                
                if thread.is_alive():
                    self.state['errors'].append("Generation timeout")
                    return self._get_timeout_message()
                
                try:
                    status, result = result_queue.get_nowait()
                    if status == 'success':
                        response = result
                        
                        # Naplózás
                        self.scratchpad.write(self.name, 
                            {'response': response[:100], 'tokens': len(response.split())},
                            'generation'
                        )
                        
                        return response
                    else:
                        return self._get_error_message(result)
                        
                except queue.Empty:
                    return self._get_error_message("Unknown error")
                
            except Exception as e:
                self.state['errors'].append(f"Generation error: {e}")
                return self._get_error_message(str(e))
        
        # Ha van modell, de még tölt
        elif self.model and not self.state.get('model_loaded'):
            return self._get_loading_message()
        
        # Dummy mód (nincs modell)
        else:
            return self._get_dummy_response(prompt)
    
    def _get_timeout_message(self) -> str:
        """Időtúllépés üzenet"""
        if self.translator:
            return self.translator.get('prompts.king.timeout')
        return "⏳ I'm thinking deeply... please wait."
    
    def _get_error_message(self, error: str) -> str:
        """Hibaüzenet"""
        if self.translator:
            return self.translator.get('prompts.king.error', error=error)
        return f"😞 Sorry, I encountered an error: {error}"
    
    def _get_loading_message(self) -> str:
        """Modell töltés üzenet"""
        if self.translator:
            return self.translator.get('prompts.king.loading')
        return "🤔 I'm awakening..."
    
    def _get_dummy_response(self, prompt: str) -> str:
        """Dummy válasz (ha nincs modell)"""
        prompt_lower = prompt.lower()
        user_name = self.scratchpad.get_state('user_name', 'user')
        
        if "hello" in prompt_lower or "hi" in prompt_lower or "szia" in prompt_lower:
            if self.translator:
                return self.translator.get('prompts.king.greeting', user=user_name)
            return f"Hello {user_name}!"
        elif "?" in prompt:
            if self.translator:
                return self.translator.get('prompts.king.thinking')
            return "Interesting question. Let me think..."
        else:
            if self.translator:
                return self.translator.get('prompts.king.acknowledge')
            return "I understand."
    
    def _calculate_confidence(self, intent_packet: Dict) -> float:
        """Bizonyossági szint számítása"""
        base = 0.95
        
        # Ha van modell és be van töltve
        if not (self.model and self.state.get('model_loaded')):
            base *= 0.5
        
        # Ha vannak hibák
        if self.state['errors']:
            base *= max(0.5, 1.0 - (len(self.state['errors']) * 0.1))
        
        # RAG használat növeli a bizalmat
        if self.state.get('rag_used'):
            base += 0.03
        
        # Ha van Valet
        if hasattr(self, 'valet') and self.valet is not None:
            base += 0.02
        
        # Ha van Queen
        if hasattr(self, 'queen') and self.queen is not None:
            base += 0.03
        
        return min(0.99, max(0.1, base))
    
    def _get_current_mood(self) -> str:
        """Aktuális hangulat lekérése"""
        if self.state['average_response_time'] > 10:
            mood = "tired"
        elif self.state['average_response_time'] > 5:
            mood = "thoughtful"
        elif self.state['average_response_time'] > 2:
            mood = "calm"
        else:
            mood = "lively"
        
        self.state['last_mood'] = mood
        return mood
    
    def _update_state(self, intent: Dict, response: Dict, start_time: float):
        """Állapot frissítése (ezt nézi a Jester)"""
        response_time = time.time() - start_time
        
        self.state['last_response_time'] = response_time
        self.state['response_count'] += 1
        self.state['status'] = 'idle'
        self.state['current_task'] = None
        self.state['last_mood'] = self._get_current_mood()
        
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
            return {
                **self.state,
                'average_tokens_per_second': self._calculate_tokens_per_second(),
                'mood': self._get_current_mood()
            }
        return {
            'status': 'error',
            'last_response_time': None,
            'response_count': 0,
            'average_response_time': 0,
            'errors': [f"Invalid state: {type(self.state)}"],
            'current_task': None,
            'model_loaded': False,
            'mood': 'error'
        }
    
    def _calculate_tokens_per_second(self) -> float:
        """Átlagos token/másodperc számítás"""
        if self.state['total_processing_time'] == 0:
            return 0
        return self.state['total_tokens_generated'] / self.state['total_processing_time']
    
    def get_mood(self) -> str:
        """Aktuális hangulat (UI-nak)"""
        return self._get_current_mood()
    
    def get_metrics(self) -> Dict:
        """Részletes metrikák lekérése"""
        return {
            'response_count': self.state['response_count'],
            'average_response_time': round(self.state['average_response_time'] * 1000, 2),
            'total_tokens': self.state['total_tokens_generated'],
            'average_tokens_per_second': round(self._calculate_tokens_per_second(), 2),
            'errors': len(self.state['errors']),
            'model_loaded': self.state['model_loaded'],
            'mood': self._get_current_mood(),
            'style': self.identity.get('style', 'default'),
            'rag_used': self.state.get('rag_used', False)
        }


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    s.set_state('user_name', 'user')
    s.write_note('king', 'personality', 'curious, helpful, witty')
    
    king = King(s)
    
    # Új metódus tesztelése
    response = king.generate_response("Hello, how are you?")
    print(f"Response: {response}")
    
    # Teszt RAG kontextussal
    rag_context = {
        'summary': 'User asked about the weather yesterday',
        'facts': ['Weather was sunny', 'Temperature was 25°C'],
        'graph_context': ['User likes sunny weather'],
        'vector_context': ['Climate data shows summer approaching'],
        'emotional_context': {'recent_mood': 'positive'}
    }
    
    response_with_rag = king.generate_response(
        "What's the weather like?",
        rag_context=rag_context
    )
    print(f"\nResponse with RAG: {response_with_rag}")
    
    # Régi process metódus tesztelése
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
            'text': 'Hello!',
            'rag_context': rag_context
        }
    }
    
    response_packet = king.process(test_intent)
    print(json.dumps(response_packet, indent=2))
    print("\nKing state:", king.get_state())
    print("King mood:", king.get_mood())
    print("King metrics:", king.get_metrics())