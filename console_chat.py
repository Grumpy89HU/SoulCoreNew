#!/usr/bin/env python3
"""
SoulCore 3.0 - Konzol Chat Kliens
Csatlakozik a futó SoulCore API-hoz és beszélget a Királlyal.
"""

import json
import sys
import time
import signal
import readline
import atexit
import logging
import requests
from pathlib import Path

# Logging beállítása (hogy ne zavarja a konzolt)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Színek a konzolhoz
class Colors:
    HEADER = '\033[95m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


class SoulCoreConsole:
    """
    Konzol chat kliens a futó SoulCore API-hoz.
    """
    
    def __init__(self, host: str = 'localhost', port: int = 5001):
        self.base_url = f"http://{host}:{port}"
        self.api_url = f"{self.base_url}/api"
        self.conversation_id = None
        self.running = True
        self.history = []
        
        # Signal kezelés
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Readline történet
        hist_file = Path.home() / '.soulcore_history'
        try:
            readline.read_history_file(str(hist_file))
        except FileNotFoundError:
            pass
        atexit.register(readline.write_history_file, str(hist_file))
        
        # Kapcsolat teszt
        self._check_connection()
        
        # Új beszélgetés indítása
        self._new_conversation()
        
        self._show_welcome()
    
    def _check_connection(self):
        """API kapcsolat ellenőrzése"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            if response.status_code == 200:
                print(f"{Colors.GREEN}✅ Kapcsolódva a SoulCore API-hoz: {self.base_url}{Colors.END}")
            else:
                print(f"{Colors.RED}❌ API válasz: {response.status_code}{Colors.END}")
                sys.exit(1)
        except requests.exceptions.ConnectionError:
            print(f"{Colors.RED}❌ Nem sikerült csatlakozni a SoulCore API-hoz!")
            print(f"   Ellenőrizd, hogy fut-e a SoulCore: python main.py{Colors.END}")
            sys.exit(1)
        except Exception as e:
            print(f"{Colors.RED}❌ Kapcsolódási hiba: {e}{Colors.END}")
            sys.exit(1)
    
    def _new_conversation(self):
        """Új beszélgetés indítása"""
        try:
            response = requests.post(f"{self.api_url}/conversations", json={}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.conversation_id = data.get('id')
                if self.conversation_id:
                    print(f"{Colors.GREEN}✨ Új beszélgetés: #{self.conversation_id}{Colors.END}")
                    return
                else:
                    print(f"{Colors.YELLOW}⚠️ API nem adott ID-t, lokális ID-t használok{Colors.END}")
            else:
                print(f"{Colors.YELLOW}⚠️ API hiba ({response.status_code}), lokális ID-t használok{Colors.END}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ Beszélgetés létrehozási hiba: {e}{Colors.END}")
        
        # Fallback: időbélyeg alapú egyedi ID (garantáltan más, mint a webes)
        import time
        self.conversation_id = int(time.time() * 1000)
        print(f"{Colors.YELLOW}⚠️ Új beszélgetés (lokális): #{self.conversation_id}{Colors.END}")
    
    def _show_welcome(self):
        """Üdvözlő üzenet"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}")
        print("=" * 50)
        print("🏰 SoulCore 3.0 - Konzol Chat Kliens")
        print("=" * 50)
        print(f"{Colors.END}")
        print(f"{Colors.DIM}💡 Parancsok: /help, /exit, /new, /clear, /status{Colors.END}")
        print(f"{Colors.DIM}   A Király válaszait a modell generálja.{Colors.END}\n")
    
    def _signal_handler(self, signum, frame):
        """Ctrl+C kezelés"""
        print(f"\n{Colors.YELLOW}👋 Kilépés...{Colors.END}")
        self.running = False
    
    def _send_message(self, text: str) -> str:
        """Üzenet küldése a Királynak"""
        try:
            response = requests.post(
                f"{self.api_url}/chat",
                json={
                    'text': text,
                    'conversation_id': self.conversation_id
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', '')
            else:
                error_data = response.json() if response.text else {}
                return f"[API hiba: {response.status_code}] {error_data.get('error', '')}"
                
        except requests.exceptions.Timeout:
            return "[Időtúllépés – a Király gondolkodik...]"
        except Exception as e:
            return f"[Hiba: {e}]"
    
    def _show_help(self):
        """Súgó megjelenítése"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}📖 Parancsok:{Colors.END}")
        print(f"  {Colors.GREEN}/help{Colors.END}      - Ez a súgó")
        print(f"  {Colors.GREEN}/exit{Colors.END}      - Kilépés")
        print(f"  {Colors.GREEN}/quit{Colors.END}      - Kilépés")
        print(f"  {Colors.GREEN}/clear{Colors.END}     - Képernyő törlés")
        print(f"  {Colors.GREEN}/new{Colors.END}       - Új beszélgetés")
        print(f"  {Colors.GREEN}/status{Colors.END}    - API állapot")
        print(f"\n{Colors.DIM}💡 Egyszerűen írd be az üzeneted, majd Enter.{Colors.END}\n")
    
    def _clear_screen(self):
        """Képernyő törlés"""
        import os
        os.system('clear' if os.name == 'posix' else 'cls')
        self._show_welcome()
    
    def _show_status(self):
        """API állapot lekérése"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"\n{Colors.CYAN}{Colors.BOLD}📊 SoulCore állapot:{Colors.END}")
                print(f"   Verzió: {data.get('version', '?')}")
                print(f"   King: {data.get('king_available', False)}")
                print(f"   Modulok: {len(data.get('modules', []))}")
                print(f"   Beszélgetés ID: {self.conversation_id}")
                print()
            else:
                print(f"{Colors.RED}⚠️ Nem sikerült lekérni az állapotot.{Colors.END}\n")
        except Exception as e:
            print(f"{Colors.RED}⚠️ Állapot lekérési hiba: {e}{Colors.END}\n")
    
    def _process_command(self, cmd: str) -> bool:
        """
        Parancs feldolgozása.
        Returns: True = folytatás, False = kilépés
        """
        cmd_lower = cmd.lower().strip()
        
        if cmd_lower in ['/exit', '/quit', 'exit', 'quit']:
            print(f"\n{Colors.YELLOW}👋 Kilépés...{Colors.END}")
            return False
        
        elif cmd_lower == '/help':
            self._show_help()
            return True
        
        elif cmd_lower == '/clear':
            self._clear_screen()
            return True
        
        elif cmd_lower == '/new':
            self._new_conversation()
            print(f"{Colors.GREEN}💬 Új beszélgetés indítva! (ID: {self.conversation_id}){Colors.END}\n")
            return True
        
        elif cmd_lower == '/status':
            self._show_status()
            return True
        
        else:
            # Ismeretlen parancs
            print(f"{Colors.YELLOW}⚠️ Ismeretlen parancs: {cmd}{Colors.END}")
            print(f"   Írd be a {Colors.GREEN}/help{Colors.END} parancsot a súgóért.\n")
            return True
    
    def _get_user_input(self) -> str:
        """Felhasználói bemenet kérése"""
        try:
            prompt = f"{Colors.CYAN}You{Colors.END}> "
            user_input = input(prompt).strip()
            return user_input
        except (EOFError, KeyboardInterrupt):
            return "/exit"
    
    def run(self):
        """Fő ciklus"""
        print(f"{Colors.GREEN}💬 Beszélgetés indítva! (ID: {self.conversation_id}){Colors.END}")
        print(f"{Colors.DIM}   Írd be az üzeneted, majd Enter.{Colors.END}\n")
        
        while self.running:
            try:
                user_input = self._get_user_input()
                
                if not user_input:
                    continue
                
                # Parancs ellenőrzés
                if user_input.startswith('/'):
                    should_continue = self._process_command(user_input)
                    if not should_continue:
                        break
                    continue
                
                # "Gondolkodás" jelzés
                print(f"{Colors.DIM}🤔 King gondolkodik...{Colors.END}", end='\r')
                sys.stdout.flush()
                
                # Üzenet küldése
                response = self._send_message(user_input)
                
                # Válasz megjelenítése
                print(f"\r{Colors.YELLOW}King{Colors.END}> {response}")
                print()
                
                # Mentés (opcionális)
                self.history.append((user_input, response))
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}👋 Kilépés...{Colors.END}")
                break
            except Exception as e:
                print(f"\n{Colors.RED}⚠️ Váratlan hiba: {e}{Colors.END}")
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}👋 Viszlát!{Colors.END}")


def main():
    """Belépési pont"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SoulCore Konzol Chat Kliens')
    parser.add_argument('--host', default='localhost', help='API szerver host')
    parser.add_argument('--port', type=int, default=5001, help='API szerver port')
    
    args = parser.parse_args()
    
    chat = SoulCoreConsole(host=args.host, port=args.port)
    chat.run()


if __name__ == "__main__":
    main()