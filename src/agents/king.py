"""
King - A Király, aki éppen uralkodik.
Lehet Gemma, Llama, bármi. A rendszer nem tudja, nem is akarja tudni, hogy melyik.

KOMMUNIKÁCIÓS PROTOKOLL:
- A King BESZÉL a buszon (broadcast), mindenki hallja
- A King várja a szolgák válaszát a buszon
- Kompatibilis marad a régi API-kkal (process, generate_response, stb.)

BELSŐ KOMMUNIKÁCIÓS FORMÁTUM:
- Király beszéde: {"header": {"sender": "king", "broadcast": true}, "payload": {"type": "royal_decree", ...}}
- Szolgák válasza: {"header": {"target": "king", "in_response_to": "..."}, "payload": {...}}
"""

import time
import json
import threading
import random
import hashlib
import uuid
import re
from typing import Dict, Any, Optional, List, Tuple
from collections import deque
from dataclasses import dataclass, asdict, field

# i18n import (csak a felhasználó felé)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False


@dataclass
class KingState:
    """Király állapota (JSON-ben továbbítható)"""
    status: str = 'idle'
    last_response_time: float = None
    last_response_text: str = None
    response_count: int = 0
    average_response_time: float = 0
    errors: List[str] = field(default_factory=list)
    current_task: str = None
    current_conversation_id: int = None
    model_loaded: bool = False
    total_tokens_generated: int = 0
    total_processing_time: float = 0
    last_mood: str = 'neutral'
    rag_used: bool = False
    last_context_hash: str = None
    temperature: float = 0.7
    
    def to_dict(self) -> Dict:
        return asdict(self)


class King:
    """
    A Király - szuverén entitás.
    
    KOMMUNIKÁCIÓ:
    1. Hallja a felhasználót
    2. KIÁLTJA a trónteremben (broadcast)
    3. Várja a szolgák válaszát
    4. Válaszol a felhasználónak
    
    Kompatibilitás: megtartja a régi API-kat (process, generate_response)
    """
    
    # Prompt verziók
    PROMPT_STYLES = {
        'default': 0,
        'concise': 1,
        'detailed': 2,
        'poetic': 3,
        'technical': 4
    }
    
    # Hangulati állapotok
    MOOD_STATES = {
        'neutral': 0,
        'lively': 0.5,
        'thoughtful': -0.2,
        'tired': -0.5,
        'playful': 0.6,
        'sarcastic': 0.3
    }
    
    def __init__(self, scratchpad, model_wrapper, message_bus=None, config: Dict = None):
        self.scratchpad = scratchpad
        self.model = model_wrapper
        self.bus = message_bus
        self.name = "king"
        self.config = config or {}
        
        # Fordító (csak a felhasználó felé)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Állapot
        self.state = KingState()
        
        # Identitás
        self.identity = {
            'name': 'assistant',
            'title': 'The Sovereign',
            'personality': 'wise, curious, sovereign',
            'style': 'default'
        }
        
        # Válaszok gyűjtője a szolgáktól (broadcast módhoz)
        self.pending_responses: Dict[str, Dict] = {}
        self.response_lock = threading.Lock()
        
        # Kontextus cache
        self.context_cache = {}
        self.cache_ttl = 300
        
        # Legutóbbi válaszok
        self.recent_responses = deque(maxlen=10)
        
        # Generálási paraméterek
        self.generation_params = {
            'max_tokens': 256,
            'temperature': 0.7,
            'top_p': 0.9,
            'top_k': 40,
            'repeat_penalty': 1.1,
            'frequency_penalty': 0.0,
            'presence_penalty': 0.0
        }
        
        # Válasz callback (WebApp felé)
        self.response_callback = None
        
        # Valet és Queen hivatkozások
        self.valet = None
        self.queen = None
        
        # Ha van busz, feliratkozunk
        if self.bus:
            self.bus.subscribe(self.name, self._on_message)
        
        # Modell betöltés
        if self.model:
            threading.Thread(target=self._load_model, daemon=True).start()
        
        print("👑 King: Király trónra lépett.")
        if self.bus:
            print("👑 King: Broadcast módban működöm.")
        else:
            print("👑 King: Hagyományos módban működöm.")
    
    # ========== BUSZ KOMMUNIKÁCIÓ (BROADCAST MÓD) ==========
    
    def _on_message(self, message: Dict):
        """Hallja a buszon érkező üzeneteket"""
        if not self.bus:
            return
        
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        # PROAKTÍV ÜZENET KEZELÉSE (először)
        if payload.get('type') == 'proactive_message':
            self._handle_proactive_message(payload)
            return
        
        # Csak a Kingnek szóló válaszok
        if header.get('target') != self.name:
            return
        
        trace_id = header.get('in_response_to')
        if not trace_id:
            return
        
        with self.response_lock:
            if trace_id not in self.pending_responses:
                self.pending_responses[trace_id] = {}
            
            sender = header.get('sender', 'unknown')
            self.pending_responses[trace_id][sender] = message
    
    def _handle_proactive_message(self, payload: Dict):
        """Proaktív üzenet kezelése - King magától megszólal"""
        subtype = payload.get('subtype', 'interest')
        topic = payload.get('topic', '')
        idle_hours = payload.get('idle_hours', 0)
        note = payload.get('note', '')
        
        if subtype == 'interest':
            prompt = f"User has been silent for {idle_hours} hours. Last topic was about {topic}. Send a short, casual message to check in."
        elif subtype == 'reminder':
            prompt = f"Reminder: {note}. Send a brief reminder to the user."
        else:
            return
        
        # Válasz generálása
        response = self._generate_response(prompt)
        
        # Callback a WebApp felé (ha van)
        if self.response_callback:
            self.response_callback(response, None, str(uuid.uuid4()))
        
        print(f"👑 King: Proaktív üzenet küldve ({subtype})")
    
    def _wait_for_responses(self, trace_id: str, required_agents: List[str], timeout: float = 5.0) -> Dict:
        """Vár a szolgák válaszára (broadcast mód)"""
        if not self.bus:
            return {}
        
        start_time = time.time()
        required_set = set(required_agents)
        
        while time.time() - start_time < timeout:
            with self.response_lock:
                if trace_id in self.pending_responses:
                    responses = self.pending_responses[trace_id]
                    if set(responses.keys()) >= required_set:
                        result = responses.copy()
                        del self.pending_responses[trace_id]
                        return result
            
            time.sleep(0.05)
        
        with self.response_lock:
            if trace_id in self.pending_responses:
                responses = self.pending_responses[trace_id].copy()
                del self.pending_responses[trace_id]
                return responses
        
        return {}
    
    def _create_royal_decree(self, trace_id: str, user_text: str, 
                              interpretation: Dict, required_agents: List[str]) -> Dict:
        """Királyi rendelet összeállítása (broadcast mód)"""
        return {
            "header": {
                "trace_id": trace_id,
                "timestamp": time.time(),
                "version": "3.0",
                "sender": self.name,
                "target": "kernel",
                "broadcast": True
            },
            "payload": {
                "type": "royal_decree",
                "user_message": user_text,
                "interpretation": interpretation,
                "order": "prepare_context",
                "required_agents": required_agents,
                "optional_agents": ["jester"]
            },
            "telemetry": {
                "model": getattr(self.model, 'name', 'unknown'),
                "temperature": self.generation_params['temperature']
            }
        }
    
    def _extract_context_from_responses(self, responses: Dict) -> Dict:
        """Kinyeri a kontextust a szolgák válaszaiból"""
        context = {
            "summary": "",
            "facts": [],
            "emotional_charge": 0.0,
            "logic": ""
        }
        
        for sender, msg in responses.items():
            payload = msg.get('payload', {})
            
            if sender == 'valet':
                ctx = payload.get('context', {})
                context['summary'] = ctx.get('summary', '')
                context['facts'] = ctx.get('facts', [])
                context['emotional_charge'] = ctx.get('emotional_charge', 0.0)
            
            elif sender == 'queen':
                logic = payload.get('logic', {})
                context['logic'] = logic.get('conclusion', '')
                context['thought'] = logic.get('thought', [])
        
        return context
    
    # ========== FŐ FELDOLGOZÓ METÓDUS (BROADCAST MÓD) ==========
    
    def process_user_message(self, user_text: str, trace_id: str = None, conversation_id: int = None) -> str:
        """
        Felhasználói üzenet feldolgozása BROADCAST móddal.
        Ha van busz, ezt használja.
        """
        if not self.bus:
            return self.generate_response(user_text, trace_id, conversation_id)
        
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        if conversation_id:
            self.state.current_conversation_id = conversation_id
        
        start_time = time.time()
        self.state.status = 'processing'
        self.state.current_task = trace_id
        
        # 1. Értelmezés
        interpretation = self._interpret(user_text)
        
        # 2. Meghatározzuk, kikre van szükség
        required_agents = self._determine_required_agents(interpretation)
        
        # 3. Broadcast
        decree = self._create_royal_decree(trace_id, user_text, interpretation, required_agents)
        self.bus.broadcast(decree)
        
        # 4. Várunk a válaszokra
        responses = self._wait_for_responses(trace_id, required_agents, timeout=5.0)
        
        # 5. Válasz generálása (belső monológ is)
        response_text = self._generate_response_with_context(user_text, interpretation, responses)
        
        # 6. Állapot frissítés
        processing_time = time.time() - start_time
        self._update_state(response_text, processing_time, len(response_text.split()), responses)
        
        # 7. Callback
        if self.response_callback:
            conv_id = conversation_id if conversation_id is not None else self.state.current_conversation_id
            if conv_id is None:
                conv_id = trace_id
            self.response_callback(response_text, conv_id, trace_id)
        
        return response_text
    
    def _determine_required_agents(self, interpretation: Dict) -> List[str]:
        """Meghatározza, kikre van szükség"""
        required = ['scribe']
        intent_class = interpretation.get('intent', {}).get('class', '')
        complexity = interpretation.get('complexity', 'medium')
        
        if intent_class in ['question', 'command', 'knowledge', 'proactive']:
            required.append('valet')
        
        if complexity == 'high' or intent_class == 'knowledge':
            required.append('queen')
        
        return required
    
    def _generate_response_with_context(self, user_text: str, interpretation: Dict, responses: Dict) -> str:
        """Válasz generálása a szolgák válaszaival + belső monológ"""
        context = self._extract_context_from_responses(responses)
        prompt = self._build_response_prompt(user_text, interpretation, context)
        
        # Belső monológ generálása
        try:
            internal_prompt = f"Generate an internal monologue (1-2 sentences) about how you feel about this user message: {user_text}"
            internal_monologue = self.model.generate(
                prompt=internal_prompt,
                max_tokens=100,
                temperature=0.7
            )
            # Belső monológ mentése a scratchpad-be (Jester olvassa)
            self.scratchpad.write_note('king', 'internal_monologue', {
                'text': internal_monologue,
                'timestamp': time.time(),
                'in_response_to': user_text[:100]
            })
        except Exception as e:
            self.state.errors.append(f"Internal monologue error: {e}")
        
        # Válasz generálása
        try:
            response = self.model.generate(
                prompt=prompt,
                max_tokens=self.generation_params['max_tokens'],
                temperature=self.generation_params['temperature'],
                top_p=self.generation_params['top_p'],
                top_k=self.generation_params['top_k'],
                repeat_penalty=self.generation_params['repeat_penalty']
            )
            return response.strip()
        except Exception as e:
            self.state.errors.append(str(e))
            return self._get_message('error', error=str(e))
    
    def _build_response_prompt(self, user_text: str, interpretation: Dict, context: Dict) -> str:
        """Prompt összeállítása a válaszhoz"""
        language = interpretation.get('language', 'en')
        style = self.identity.get('style', 'default')
        
        parts = []
        
        style_instruction = self._get_style_instruction(style, language)
        if style_instruction:
            parts.append(style_instruction)
        
        if context.get('summary'):
            parts.append(f"Context: {context['summary']}")
        
        if context.get('facts'):
            parts.append("Relevant facts:")
            for fact in context['facts'][:3]:
                parts.append(f"- {fact}")
        
        if context.get('logic'):
            parts.append(f"Logical conclusion: {context['logic']}")
        
        parts.append(f"\nUser: {user_text}")
        parts.append(f"{self.identity['name']}:")
        
        return "\n".join(parts)
    
    # ========== RÉGI API (KOMPATIBILITÁS) ==========
    
    def process_request(self, request: Dict) -> Dict:
        """JSON kérés feldolgozása (régi API)"""
        start_time = time.time()
        
        if not isinstance(request, dict):
            return self._error_response("invalid_request", "Request must be dict")
        
        trace_id = request.get('trace_id', str(uuid.uuid4()))
        payload = request.get('payload', {})
        user_text = payload.get('text', '')
        conversation_id = payload.get('conversation_id')
        
        if self.bus:
            response_text = self.process_user_message(user_text, trace_id, conversation_id)
            
            return {
                "type": "king_response",
                "target": "orchestrator",
                "trace_id": trace_id,
                "timestamp": time.time(),
                "payload": {
                    "response": response_text,
                    "confidence": self._calculate_confidence(),
                    "response_time_ms": int((time.time() - start_time) * 1000),
                    "tokens_used": len(response_text.split()),
                    "mood": self._get_current_mood(),
                    "rag_used": self.state.rag_used
                }
            }
        
        return self._process_request_legacy(request)
    
    def _process_request_legacy(self, request: Dict) -> Dict:
        """Régi feldolgozó mód (kompatibilitás)"""
        start_time = time.time()
        
        trace_id = request.get('trace_id', str(uuid.uuid4()))
        payload = request.get('payload', {})
        
        self.state.current_task = trace_id
        self.state.status = 'processing'
        
        try:
            if not self._should_respond(payload):
                self.state.status = 'idle'
                return None
            
            self._load_identity()
            
            rag_context = payload.get('context', {})
            self.state.rag_used = bool(rag_context and rag_context.get('summary'))
            
            user_text = payload.get('text', '')
            conversation_history = payload.get('conversation_history', [])
            
            prompt = self._build_prompt_cached(user_text, rag_context, conversation_history)
            response_text = self._generate_response(prompt)
            
            processing_time = time.time() - start_time
            tokens_used = len(response_text.split())
            
            self._update_state(response_text, processing_time, tokens_used, {})
            
            if self.response_callback:
                conversation_id = payload.get('conversation_id')
                if conversation_id is None:
                    conversation_id = trace_id
                self.response_callback(response_text, conversation_id, trace_id)
            
            return {
                "type": "king_response",
                "target": "orchestrator",
                "trace_id": trace_id,
                "timestamp": time.time(),
                "payload": {
                    "response": response_text,
                    "confidence": self._calculate_confidence(),
                    "response_time_ms": int(processing_time * 1000),
                    "tokens_used": tokens_used,
                    "mood": self._get_current_mood(),
                    "rag_used": self.state.rag_used
                }
            }
            
        except Exception as e:
            return self._error_response(trace_id, str(e))
    
    def generate_response(self, user_text: str, trace_id: str = None,
                         conversation_id: int = None,
                         conversation_history: List[Dict] = None,
                         rag_context: Dict = None) -> str:
        """Egyszerű belépési pont a WebApp számára (régi API)"""
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        if self.bus:
            return self.process_user_message(user_text, trace_id, conversation_id)
        
        request = {
            "type": "king_request",
            "target": "king",
            "trace_id": trace_id,
            "timestamp": time.time(),
            "payload": {
                "intent": {"class": "USER_MESSAGE", "target": "king", "confidence": 1.0},
                "text": user_text,
                "context": rag_context or {},
                "conversation_history": conversation_history or [],
                "conversation_id": conversation_id
            }
        }
        
        response = self._process_request_legacy(request)
        
        if response and isinstance(response, dict):
            payload = response.get('payload', {})
            return payload.get('response', '')
        
        return self._get_message('error', error="No response")
    
    def process(self, intent_packet: Dict) -> Optional[Dict]:
        """Régi API kompatibilitás (Orchestrator hívja)"""
        trace_id = intent_packet.get('header', {}).get('trace_id', str(uuid.uuid4()))
        payload = intent_packet.get('payload', {})
        
        request = {
            "type": "king_request",
            "target": "king",
            "trace_id": trace_id,
            "timestamp": time.time(),
            "payload": {
                "intent": payload.get('intent', {}),
                "text": payload.get('text', ''),
                "context": payload.get('rag_context', {}),
                "conversation_history": payload.get('conversation_history', []),
                "conversation_id": payload.get('conversation_id')
            }
        }
        
        response = self.process_request(request)
        
        if response and isinstance(response, dict):
            return {
                "header": {
                    "trace_id": trace_id,
                    "timestamp": response.get('timestamp', time.time()),
                    "sender": self.name
                },
                "payload": response.get('payload', {})
            }
        
        return None
    
    # ========== MEGLÉVŐ SEGÉDFÜGGVÉNYEK ==========
    
    def _interpret(self, text: str) -> Dict:
        """King értelmezi a kérést"""
        prompt = f"""Analyze this user message and extract intent and entities.

Message: {text}

Return JSON:
{{
    "intent": {{"class": "greeting|question|command|knowledge|proactive|system_control|affirmation|negation|gratitude", "confidence": 0.95}},
    "entities": [{{"type": "PERSON|DATE|TIME|FILE|PATH|URL|EMAIL|NUMBER|LOCATION", "value": "..."}}],
    "language": "en|hu|...",
    "sentiment": "positive|neutral|negative",
    "complexity": "low|medium|high"
}}"""
        
        try:
            response = self.model.generate(prompt, max_tokens=256, temperature=0.3)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            self.state.errors.append(str(e))
        
        return {
            "intent": {"class": "unknown", "confidence": 0.5},
            "entities": [],
            "language": "unknown",
            "sentiment": "neutral",
            "complexity": "medium"
        }
    
    def _should_respond(self, payload: Dict) -> bool:
        intent = payload.get('intent', {})
        if not isinstance(intent, dict):
            return False
        
        intent_class = intent.get('class', '')
        target = intent.get('target', '')
        
        if target == 'king':
            return True
        if intent_class == 'PROACTIVE':
            return True
        if intent_class in ['SYSTEM_ALERT', 'ERROR']:
            return True
        if intent_class == 'USER_MESSAGE':
            return True
        
        return False
    
    def _load_identity(self):
        stored = self.scratchpad.read_note(self.name, 'personality')
        if stored:
            if isinstance(stored, str):
                self.identity['personality'] = stored
            elif isinstance(stored, dict):
                self.identity.update(stored)
        
        name = self.scratchpad.read_note(self.name, 'name')
        if name:
            self.identity['name'] = name
        
        style = self.scratchpad.read_note(self.name, 'style')
        if style and style in self.PROMPT_STYLES:
            self.identity['style'] = style
    
    def _build_prompt_cached(self, user_text: str, rag_context: Dict, conversation_history: List) -> str:
        language = self.scratchpad.get_state('user_language', 'en')
        style = self.identity.get('style', 'default')
        
        rag_hash = ''
        if rag_context:
            rag_str = f"{rag_context.get('summary', '')}_{rag_context.get('facts', [])}"
            rag_hash = hashlib.md5(rag_str.encode()).hexdigest()[:8]
        
        history_hash = ''
        if conversation_history:
            hist_str = str([m.get('content', '') for m in conversation_history[-3:]])
            history_hash = hashlib.md5(hist_str.encode()).hexdigest()[:8]
        
        cache_key = hashlib.md5(f"{user_text}_{language}_{style}_{rag_hash}_{history_hash}".encode()).hexdigest()
        
        if cache_key in self.context_cache:
            cached_time, cached_prompt = self.context_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_prompt
        
        prompt = self._build_prompt_legacy(user_text, rag_context, conversation_history)
        self.context_cache[cache_key] = (time.time(), prompt)
        
        if len(self.context_cache) > 100:
            self._cleanup_cache()
        
        return prompt
    
    def _build_prompt_legacy(self, user_text: str, rag_context: Dict, conversation_history: List) -> str:
        language = self.scratchpad.get_state('user_language', 'en')
        user_name = self.scratchpad.get_state('user_name', 'user')
        style = self.identity.get('style', 'default')
        
        prompt_parts = []
        
        if language == 'hu':
            prompt_parts.append("Figyelem: Csak a saját válaszodat írd le, ne ismételd vissza a felhasználó üzenetét!")
        else:
            prompt_parts.append("Note: Only write your own response, do not repeat the user's message!")
        
        style_instruction = self._get_style_instruction(style, language)
        if style_instruction:
            prompt_parts.append(style_instruction)
        
        if rag_context:
            context_parts = []
            summary = rag_context.get('summary', '')
            if summary:
                context_parts.append(f"Context: {summary}")
            
            facts = rag_context.get('facts', [])
            if facts and isinstance(facts, list):
                for fact in facts[:3]:
                    if isinstance(fact, str):
                        context_parts.append(f"Fact: {fact}")
            
            if context_parts:
                prompt_parts.append("\n".join(context_parts))
        
        if conversation_history:
            history_parts = []
            for msg in conversation_history[-3:]:
                role = msg.get('role', 'user')
                content = msg.get('content', '')[:200]
                if role == 'user':
                    history_parts.append(f"{user_name}: {content}")
                else:
                    history_parts.append(f"{self.identity['name']}: {content}")
            
            if history_parts:
                prompt_parts.append("\n".join(history_parts))
        
        prompt_parts.append(f"{user_name}: {user_text}")
        prompt_parts.append(f"{self.identity['name']}:")
        
        return "\n".join(prompt_parts)
    
    def _get_style_instruction(self, style: str, language: str) -> str:
        instructions = {
            'default': ('', ''),
            'concise': ('Légy rövid és tömör.', 'Be concise.'),
            'detailed': ('Magyarázz részletesen.', 'Explain in detail.'),
            'poetic': ('Válaszolj költőien, metaforákkal.', 'Answer poetically, with metaphors.'),
            'technical': ('Használj szakszerű, precíz nyelvezetet.', 'Use technical, precise language.')
        }
        hu, en = instructions.get(style, ('', ''))
        return hu if language == 'hu' else en
    
    def _generate_response(self, prompt: str) -> str:
        if self.model and self.state.model_loaded:
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
                            repeat_penalty=self.generation_params.get('repeat_penalty', 1.1)
                        )
                        result_queue.put(('success', response))
                    except Exception as e:
                        result_queue.put(('error', str(e)))
                
                thread = threading.Thread(target=generate_thread)
                thread.daemon = True
                thread.start()
                thread.join(timeout=30)
                
                if thread.is_alive():
                    return self._get_message('timeout')
                
                try:
                    status, result = result_queue.get_nowait()
                    if status == 'success':
                        return result
                    return self._get_message('error', error=result)
                except queue.Empty:
                    return self._get_message('error', error='Empty queue')
                    
            except Exception as e:
                return self._get_message('error', error=str(e))
        
        elif self.model and not self.state.model_loaded:
            return self._get_message('loading')
        
        else:
            return self._get_dummy_response(prompt)
    
    def _get_dummy_response(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if any(word in prompt_lower for word in ['hello', 'hi', 'szia']):
            return self._get_message('greeting')
        elif '?' in prompt_lower:
            return self._get_message('thinking')
        else:
            return self._get_message('acknowledge')
    
    def _get_message(self, msg_type: str, **kwargs) -> str:
        if self.translator and I18N_AVAILABLE:
            return self.translator.get(f'prompts.king.{msg_type}', **kwargs)
        
        fallbacks = {
            'timeout': "⏳ I'm thinking... please wait.",
            'loading': "🤔 I'm awakening...",
            'error': f"😞 Error: {kwargs.get('error', 'Unknown')}",
            'greeting': "Hello! How can I help?",
            'thinking': "Let me think about that...",
            'acknowledge': "I understand."
        }
        return fallbacks.get(msg_type, "I understand.")
    
    def _calculate_confidence(self) -> float:
        base = 0.95
        if not self.state.model_loaded:
            base *= 0.5
        if self.state.errors:
            base *= max(0.5, 1.0 - (len(self.state.errors) * 0.1))
        if self.state.rag_used:
            base += 0.03
        return min(0.99, max(0.1, base))
    
    def _get_current_mood(self) -> str:
        if self.state.average_response_time > 10:
            return "tired"
        elif self.state.average_response_time > 5:
            return "thoughtful"
        elif self.state.average_response_time > 2:
            return "calm"
        return "lively"
    
    def _update_state(self, response_text: str, processing_time: float, tokens_used: int, responses: Dict):
        self.state.last_response_time = processing_time
        self.state.last_response_text = response_text[:200]
        self.state.response_count += 1
        self.state.total_tokens_generated += tokens_used
        self.state.total_processing_time += processing_time
        self.state.status = 'idle'
        self.state.current_task = None
        self.state.last_mood = self._get_current_mood()
        self.state.rag_used = bool(responses.get('valet'))
        
        if self.state.average_response_time == 0:
            self.state.average_response_time = processing_time
        else:
            self.state.average_response_time = self.state.average_response_time * 0.9 + processing_time * 0.1
        
        self.scratchpad.write_note(self.name, 'state', self.state.to_dict())
    
    def _cleanup_cache(self):
        now = time.time()
        to_delete = [k for k, (t, _) in self.context_cache.items() if now - t > self.cache_ttl]
        for key in to_delete:
            del self.context_cache[key]
    
    def _load_model(self):
        if not self.model:
            return
        
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
            thread.join(timeout=30)
            
            if thread.is_alive():
                self.state.model_loaded = False
                self.state.errors.append("Model load timeout")
                return
            
            try:
                status, result = result_queue.get_nowait()
                if status == 'success':
                    self.state.model_loaded = result
                else:
                    self.state.model_loaded = False
                    self.state.errors.append(f"Model load error: {result}")
            except queue.Empty:
                self.state.model_loaded = False
                
        except Exception as e:
            self.state.model_loaded = False
            self.state.errors.append(f"Model load error: {e}")
    
    def _error_response(self, trace_id: str, error: str) -> Dict:
        return {
            "type": "king_response",
            "target": "orchestrator",
            "trace_id": trace_id,
            "timestamp": time.time(),
            "payload": {
                "response": self._get_message('error', error=error),
                "confidence": 0.0,
                "response_time_ms": 0,
                "tokens_used": 0,
                "mood": "error",
                "rag_used": False,
                "error": error
            }
        }
    
    # ========== SCRIPT GENERÁLÁS ==========
    
    def generate_script(self, task: str) -> Optional[str]:
        """Python script generálása a feladat alapján"""
        prompt = f"""Write a Python script to accomplish this task: {task}

Requirements:
- Use only standard library
- Include error handling
- Print the result
- Keep it concise (max 30 lines)

Return only the code, no explanation."""
        
        try:
            response = self.model.generate(prompt, max_tokens=500, temperature=0.3)
            code = self._extract_code(response)
            return code
        except Exception as e:
            self.state.errors.append(f"Script generation error: {e}")
            return None
    
    def _extract_code(self, response: str) -> str:
        """
        Kód kinyerése a modell válaszából.
        """
        # Keresünk ```python ... ``` blokkokat
        code_match = re.search(r'```python\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Keresünk ``` ... ``` blokkokat
        code_match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Ha nincs kódblokk, az egész válasz a kód
        return response.strip()
    
    # ========== PUBLIKUS API ==========
    
    def get_state(self) -> Dict:
        return {
            "type": "king_state",
            "target": "jester",
            "timestamp": time.time(),
            "payload": self.state.to_dict()
        }
    
    def set_parameters(self, params: Dict) -> Dict:
        applied = {}
        
        if 'temperature' in params:
            self.generation_params['temperature'] = max(0.1, min(2.0, params['temperature']))
            applied['temperature'] = self.generation_params['temperature']
        
        if 'max_tokens' in params:
            self.generation_params['max_tokens'] = max(64, min(2048, params['max_tokens']))
            applied['max_tokens'] = self.generation_params['max_tokens']
        
        if 'style' in params and params['style'] in self.PROMPT_STYLES:
            self.identity['style'] = params['style']
            applied['style'] = params['style']
            self.scratchpad.write_note(self.name, 'style', params['style'])
        
        if 'top_p' in params:
            self.generation_params['top_p'] = max(0.5, min(0.99, params['top_p']))
            applied['top_p'] = self.generation_params['top_p']
        
        if 'repeat_penalty' in params:
            self.generation_params['repeat_penalty'] = max(1.0, min(1.5, params['repeat_penalty']))
            applied['repeat_penalty'] = self.generation_params['repeat_penalty']
        
        return {"status": "ok", "applied": applied, "timestamp": time.time()}
    
    def set_identity(self, identity: Dict) -> Dict:
        if 'name' in identity:
            self.identity['name'] = identity['name']
            self.scratchpad.write_note(self.name, 'name', identity['name'])
        
        if 'personality' in identity:
            self.identity['personality'] = identity['personality']
            self.scratchpad.write_note(self.name, 'personality', identity['personality'])
        
        if 'style' in identity and identity['style'] in self.PROMPT_STYLES:
            self.identity['style'] = identity['style']
            self.scratchpad.write_note(self.name, 'style', identity['style'])
        
        return {"status": "ok", "identity": self.identity, "timestamp": time.time()}
    
    def set_temperature(self, temperature: float):
        self.generation_params['temperature'] = max(0.1, min(2.0, temperature))
        self.state.temperature = self.generation_params['temperature']
    
    def set_identity_prompt(self, prompt: str):
        self.identity['personality'] = prompt
        self.scratchpad.write_note(self.name, 'personality', prompt)
    
    def get_metrics(self) -> Dict:
        return {
            "response_count": self.state.response_count,
            "average_response_time_ms": round(self.state.average_response_time * 1000, 2),
            "total_tokens": self.state.total_tokens_generated,
            "tokens_per_second": round(
                self.state.total_tokens_generated / max(self.state.total_processing_time, 0.001), 2
            ),
            "errors": len(self.state.errors),
            "model_loaded": self.state.model_loaded,
            "mood": self.state.last_mood,
            "style": self.identity.get('style', 'default'),
            "rag_used": self.state.rag_used,
            "temperature": self.state.temperature
        }
    
    def set_response_callback(self, callback):
        self.response_callback = callback
    
    def set_valet(self, valet):
        self.valet = valet
    
    def set_queen(self, queen):
        self.queen = queen
    
    def set_language(self, language: str):
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def start(self):
        self.state.status = 'ready'
        self.scratchpad.set_state('king_status', 'ready', self.name)
        print("👑 King: Készen állok.")
    
    def stop(self):
        self.state.status = 'stopped'
        self.scratchpad.set_state('king_status', 'stopped', self.name)
        if self.model:
            self.model.unload()
        print("👑 King: Leállt.")
    
    def get_mood(self) -> str:
        return self._get_current_mood()