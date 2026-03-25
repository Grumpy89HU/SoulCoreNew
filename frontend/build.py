#!/usr/bin/env python3
"""
SoulCore Frontend Build Script
Elvégzi a Svelte/Vite build-et és a fájlokat a web mappába másolja.
"""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime

class FrontendBuilder:
    """Frontend build kezelő"""
    
    def __init__(self):
        self.root = Path(__file__).parent
        self.web_root = self.root.parent / 'web'
        self.dist_root = self.root / 'dist'
        
        # Színek a konzolhoz
        self.colors = {
            'green': '\033[92m',
            'yellow': '\033[93m',
            'red': '\033[91m',
            'blue': '\033[94m',
            'reset': '\033[0m'
        }
    
    def print_color(self, text, color='reset'):
        """Színes kiírás"""
        print(f"{self.colors.get(color, '')}{text}{self.colors['reset']}")
    
    def run_command(self, cmd, cwd=None):
        """Parancs futtatása"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd or self.root,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(result.stderr)
                return False
            return True
        except Exception as e:
            print(f"Hiba: {e}")
            return False
    
    def check_node_npm(self):
        """Node.js és npm ellenőrzése"""
        self.print_color("📦 1. Node.js és npm ellenőrzése...", 'blue')
        
        # Node.js ellenőrzés
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            self.print_color("❌ Node.js nincs telepítve!", 'red')
            self.print_color("   Telepítsd: https://nodejs.org/", 'yellow')
            return False
        
        node_version = result.stdout.strip()
        self.print_color(f"   ✅ Node.js: {node_version}", 'green')
        
        # npm ellenőrzés
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            self.print_color("❌ npm nincs telepítve!", 'red')
            return False
        
        npm_version = result.stdout.strip()
        self.print_color(f"   ✅ npm: {npm_version}", 'green')
        
        return True
    
    def check_package_json(self):
        """package.json ellenőrzése"""
        self.print_color("📦 2. package.json ellenőrzése...", 'blue')
        
        package_json = self.root / 'package.json'
        if not package_json.exists():
            self.print_color("❌ package.json nem található!", 'red')
            return False
        
        self.print_color("   ✅ package.json megtalálható", 'green')
        return True
    
    def install_dependencies(self):
        """Függőségek telepítése"""
        self.print_color("📦 3. Függőségek telepítése...", 'blue')
        
        # Ellenőrizzük, hogy van-e node_modules
        node_modules = self.root / 'node_modules'
        if node_modules.exists():
            self.print_color("   ⚠️ node_modules már létezik, frissítés...", 'yellow')
        
        if not self.run_command('npm install'):
            self.print_color("❌ Függőségek telepítése sikertelen!", 'red')
            return False
        
        self.print_color("   ✅ Függőségek telepítve", 'green')
        return True
    
    def run_build(self):
        """Build futtatása"""
        self.print_color("🔨 4. Build futtatása...", 'blue')
        
        if not self.run_command('npm run build'):
            self.print_color("❌ Build sikertelen!", 'red')
            return False
        
        self.print_color("   ✅ Build sikeres", 'green')
        return True
    
    def check_dist(self):
        """dist mappa ellenőrzése"""
        self.print_color("📁 5. dist mappa ellenőrzése...", 'blue')
        
        if not self.dist_root.exists():
            self.print_color("❌ dist mappa nem jött létre!", 'red')
            return False
        
        # Ellenőrizzük a fájlokat
        index_html = self.dist_root / 'index.html'
        if not index_html.exists():
            self.print_color("❌ index.html nem található a dist-ben!", 'red')
            return False
        
        assets_dir = self.dist_root / 'assets'
        if not assets_dir.exists() or not any(assets_dir.iterdir()):
            self.print_color("⚠️ assets mappa üres vagy nem létezik", 'yellow')
        
        self.print_color("   ✅ dist mappa rendben", 'green')
        return True
    
    def backup_web(self):
        """web mappa biztonsági mentése"""
        self.print_color("💾 6. Web mappa biztonsági mentése...", 'blue')
        
        if not self.web_root.exists():
            self.print_color("   ⚠️ web mappa nem létezik, létrehozom...", 'yellow')
            self.web_root.mkdir(parents=True, exist_ok=True)
            return True
        
        backup_dir = self.web_root.parent / f"web_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copytree(self.web_root, backup_dir)
            self.print_color(f"   ✅ Mentés: {backup_dir}", 'green')
        except Exception as e:
            self.print_color(f"   ⚠️ Mentés sikertelen: {e}", 'yellow')
        
        return True
    
    def clean_web(self):
        """web mappa tisztítása"""
        self.print_color("🧹 7. Web mappa tisztítása...", 'blue')
        
        if not self.web_root.exists():
            return True
        
        try:
            for item in self.web_root.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            self.print_color("   ✅ Web mappa kitakarítva", 'green')
        except Exception as e:
            self.print_color(f"   ❌ Tisztítás sikertelen: {e}", 'red')
            return False
        
        return True
    
    def copy_dist_to_web(self):
        """dist tartalom másolása web mappába"""
        self.print_color("📋 8. Fájlok másolása web mappába...", 'blue')
        
        try:
            for item in self.dist_root.iterdir():
                dest = self.web_root / item.name
                if item.is_file():
                    shutil.copy2(item, dest)
                elif item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
            
            self.print_color("   ✅ Fájlok másolva", 'green')
            return True
        except Exception as e:
            self.print_color(f"   ❌ Másolás sikertelen: {e}", 'red')
            return False
    
    def create_info_file(self):
        """info.json fájl létrehozása a web mappában"""
        self.print_color("📄 9. Info fájl létrehozása...", 'blue')
        
        info = {
            'build_date': datetime.now().isoformat(),
            'version': '3.0',
            'source': 'frontend/build.py',
            'files': []
        }
        
        for item in self.web_root.iterdir():
            if item.is_file():
                info['files'].append({
                    'name': item.name,
                    'size': item.stat().st_size,
                    'type': 'file'
                })
            elif item.is_dir():
                info['files'].append({
                    'name': item.name,
                    'size': sum(f.stat().st_size for f in item.rglob('*') if f.is_file()),
                    'type': 'directory'
                })
        
        info_file = self.web_root / 'build_info.json'
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        
        self.print_color("   ✅ build_info.json létrehozva", 'green')
        return True
    
    def print_summary(self):
        """Összefoglaló kiírása"""
        self.print_color("\n" + "=" * 50, 'green')
        self.print_color("🏰 SOULCORE FRONTEND BUILD", 'green')
        self.print_color("=" * 50, 'green')
        
        # Web mappa mérete
        if self.web_root.exists():
            total_size = sum(f.stat().st_size for f in self.web_root.rglob('*') if f.is_file())
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            else:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"
            
            self.print_color(f"\n📁 Web mappa: {self.web_root}", 'green')
            self.print_color(f"   Méret: {size_str}", 'green')
            
            # Fájlok listája
            self.print_color("\n📄 Fájlok:", 'green')
            for item in sorted(self.web_root.iterdir()):
                if item.is_file():
                    self.print_color(f"   ├─ {item.name}", 'green')
            for item in sorted(self.web_root.iterdir()):
                if item.is_dir():
                    self.print_color(f"   ├─ {item.name}/", 'green')
        
        self.print_color("\n✅ Build sikeresen befejeződött!", 'green')
        self.print_color(f"🌐 Web elérhető: http://localhost:8000", 'green')
        self.print_color("=" * 50, 'green')
    
    def build(self):
        """Teljes build folyamat"""
        self.print_color("\n🏗️ SoulCore Frontend Build\n", 'blue')
        
        steps = [
            ('Node.js ellenőrzés', self.check_node_npm),
            ('package.json ellenőrzés', self.check_package_json),
            ('Függőségek telepítése', self.install_dependencies),
            ('Build futtatása', self.run_build),
            ('dist mappa ellenőrzés', self.check_dist),
            ('Web mappa biztonsági mentés', self.backup_web),
            ('Web mappa tisztítás', self.clean_web),
            ('Fájlok másolás', self.copy_dist_to_web),
            ('Info fájl létrehozás', self.create_info_file)
        ]
        
        for step_name, step_func in steps:
            if not step_func():
                self.print_color(f"\n❌ Build megszakítva a következő lépésnél: {step_name}", 'red')
                return False
        
        self.print_summary()
        return True
    
    def clean(self):
        """Build utáni takarítás"""
        self.print_color("🧹 Takarítás...", 'blue')
        
        # dist mappa törlése
        if self.dist_root.exists():
            shutil.rmtree(self.dist_root)
            self.print_color("   ✅ dist mappa törölve", 'green')
        
        # node_modules törlése (opcionális)
        node_modules = self.root / 'node_modules'
        if node_modules.exists():
            response = input("   Töröljem a node_modules mappát is? (i/n): ")
            if response.lower() == 'i':
                shutil.rmtree(node_modules)
                self.print_color("   ✅ node_modules törölve", 'green')
        
        self.print_color("✅ Takarítás kész", 'green')


def main():
    """Fő belépési pont"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SoulCore Frontend Build')
    parser.add_argument('--clean', action='store_true', help='Takarítás build után')
    parser.add_argument('--no-install', action='store_true', help='Függőségek telepítésének kihagyása')
    args = parser.parse_args()
    
    builder = FrontendBuilder()
    
    if args.clean:
        builder.clean()
    else:
        success = builder.build()
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
