#!/usr/bin/env python3

import os
import sys
import subprocess
import platform
import json
import shutil
from pathlib import Path

def run_command(cmd, check=True):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"Error executing: {cmd}")
            print(f"Error: {result.stderr}")
            return False
        return result.stdout.strip() if result.stdout else True
    except Exception as e:
        print(f"Failed to execute: {cmd} - {e}")
        return False

def check_python():
    if sys.version_info < (3, 7):
        print("Python 3.7+ required!")
        sys.exit(1)
    print("Python version OK")

def install_dependencies():
    print("Installing dependencies...")
    packages = ["pypresence", "psutil"]
    
    for package in packages:
        print(f"  Installing {package}...")
        if not run_command(f"{sys.executable} -m pip install {package}"):
            print(f"Failed to install {package}")
            sys.exit(1)
    
    print("Dependencies installed")

def download_service_file():
    print("Creating service file...")
    
    service_content = '''import json
import os
import time
import subprocess
import psutil
import platform
import signal
import sys
import logging
from pathlib import Path
from pypresence import Presence

class OllamaDiscordService:
    def __init__(self):
        self.setup_logging()
        self.config = self.load_config()
        self.client_id = self.config.get('clientId', '1408133296000466945')
        
        self.poll_interval = 5  # Check every 5 seconds
        self.auto_start = self.config.get('autoStart', True)
        self.auto_exit = self.config.get('autoExit', True)
        self.ollama_cmd = self.config.get('ollamaCmd', 'ollama ps')
        
        self.gpu_info = None
        self.ram_info = None
        self.ollama_version = None
        self.presence_active = False
        self.was_running = None
        self.rpc = None
        
    def setup_logging(self):
        home_dir = Path.home()
        log_dir = home_dir / '.ollama' / 'discord'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / 'logs.txt'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler() if '--debug' in sys.argv else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        config_path = Path(__file__).parent / 'config.json'
        default_config = {
            "clientId": "1408133296000466945",
            "largeImageKey": "ollama",
            "autoStart": True,
            "autoExit": True,
            "ollamaCmd": "ollama ps"
        }
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {**default_config, **config}
        except FileNotFoundError:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            return default_config

    def run_command(self, cmd, timeout=10):
        try:
            if platform.system() == 'Windows':
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            else:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=timeout
                )
            
            return {
                'ok': result.returncode == 0,
                'stdout': result.stdout.strip() if result.stdout else '',
                'stderr': result.stderr.strip() if result.stderr else ''
            }
        except subprocess.TimeoutExpired:
            return {'ok': False, 'stdout': '', 'stderr': 'Command timeout'}
        except Exception as e:
            return {'ok': False, 'stdout': '', 'stderr': str(e)}

    def is_ollama_running(self):
        """Check if Ollama process is running."""
        try:
            self.logger.info("Checking Ollama processes...")
            
            # Method 1: Process detection via psutil
            ollama_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info.get('name', '').lower()
                    proc_exe = proc_info.get('exe', '').lower() if proc_info.get('exe') else ''
                    
                    if ('ollama' in proc_name or 'ollama' in proc_exe):
                        ollama_processes.append({
                            'pid': proc_info['pid'],
                            'name': proc_name,
                            'exe': proc_exe
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if ollama_processes:
                self.logger.info(f"Found {len(ollama_processes)} Ollama process(es)")
                for proc in ollama_processes:
                    self.logger.info(f"   PID: {proc['pid']}, Name: {proc['name']}")
                return True
            
            # Method 2: Port check as fallback
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', 11434))
                sock.close()
                if result == 0:
                    self.logger.info("Ollama port 11434 is open")
                    return True
                else:
                    self.logger.info("Ollama port 11434 is closed")
            except Exception as e:
                self.logger.info(f"Port check failed: {e}")
            
            self.logger.info("No Ollama process found")
            return False
            
        except Exception as e:
            self.logger.error(f"Exception checking Ollama: {e}")
            return False

    def get_gpu_info(self):
        result = self.run_command('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits')
        if result['ok'] and result['stdout'].strip():
            lines = result['stdout'].strip().split('\\n')
            if lines:
                parts = [p.strip() for p in lines[0].split(',')]
                if len(parts) >= 2:
                    try:
                        vram_mib = int(''.join(filter(str.isdigit, parts[1])))
                        return {
                            'name': parts[0],
                            'vram_mib': vram_mib,
                            'vram_str': f"{vram_mib}MiB"
                        }
                    except:
                        pass
                return {'name': parts[0], 'vram_mib': None, 'vram_str': None}
        
        if platform.system() == 'Windows':
            result = self.run_command('wmic path win32_VideoController get Name,AdapterRAM /format:list')
            if result['ok'] and result['stdout']:
                lines = [l.strip() for l in result['stdout'].split('\\n') if l.strip()]
                name = None
                adapter_ram = None
                for line in lines:
                    if line.startswith('Name='):
                        name = line.split('=', 1)[1]
                    elif line.startswith('AdapterRAM='):
                        try:
                            adapter_ram = int(line.split('=', 1)[1])
                        except:
                            pass
                
                vram_mib = round(adapter_ram / 1024 / 1024) if adapter_ram else None
                return {
                    'name': name,
                    'vram_mib': vram_mib,
                    'vram_str': f"{vram_mib}MiB" if vram_mib else None
                }
        
        return {'name': None, 'vram_mib': None, 'vram_str': None}

    def get_ram_info(self):
        try:
            memory = psutil.virtual_memory()
            total_gb = round(memory.total / 1024 / 1024 / 1024)
            return {'total_gb': total_gb}
        except:
            return {'total_gb': None}

    def get_gpu_brand(self):
        if not self.gpu_info or not self.gpu_info.get('name'):
            return 'gpu'
        
        gpu_name = self.gpu_info['name'].lower()
        
        if any(keyword in gpu_name for keyword in ['nvidia', 'geforce', 'rtx', 'gtx']):
            return 'nvidia'
        elif any(keyword in gpu_name for keyword in ['amd', 'radeon', 'rx']):
            return 'amd'
        elif any(keyword in gpu_name for keyword in ['intel', 'iris', 'uhd']):
            return 'intel'
        else:
            return 'gpu'

    def get_ollama_model(self):
        result = self.run_command(self.ollama_cmd)
        if not result['ok'] or not result['stdout']:
            return None
        
        lines = [l.strip() for l in result['stdout'].split('\\n') if l.strip()]
        if len(lines) < 2:
            return None
        
        data_line = lines[1]
        cols = [c.strip() for c in data_line.split() if c.strip()]
        if not cols:
            return None
        
        return {'model': cols[0]}

    def get_ollama_version(self):
        result = self.run_command('ollama --version')
        if not result['ok'] or not result['stdout']:
            return None
        
        import re
        stdout = result['stdout'].strip()
        
        patterns = [
            r'ollama version is (.+)',
            r'version (.+)',
            r'v?(\\d+\\.\\d+\\.\\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, stdout, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return stdout.split('\\n')[0] if stdout else 'unknown'

    def start_ollama(self):
        if self.auto_start:
            try:
                subprocess.Popen(['ollama', 'serve'], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                time.sleep(3)
                self.logger.info("Started Ollama")
            except Exception as e:
                self.logger.error(f"Failed to start Ollama: {e}")

    def refresh_hardware_info(self):
        """Refresh hardware info - only call GPU/RAM detection, get Ollama version only if running."""
        self.gpu_info = self.get_gpu_info()
        self.ram_info = self.get_ram_info()
        
        # Only get Ollama version if we know Ollama is running (to avoid auto-starting it)
        if self.is_ollama_running():
            self.ollama_version = self.get_ollama_version()
        else:
            self.ollama_version = 'unknown'
            
        gpu_name = self.gpu_info.get('name', 'unknown') if self.gpu_info else 'unknown'
        ram_gb = self.ram_info.get('total_gb', 'unknown') if self.ram_info else 'unknown'
        self.logger.info(f"Hardware refreshed: GPU={gpu_name}, RAM={ram_gb}GB, Version={self.ollama_version}")

    def get_gpu_info(self):
        """Get GPU info - safe, doesn't interact with Ollama."""
        result = self.run_command('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits')
        if result['ok'] and result['stdout'].strip():
            lines = result['stdout'].strip().split('\\n')
            if lines:
                parts = [p.strip() for p in lines[0].split(',')]
                if len(parts) >= 2:
                    try:
                        vram_mib = int(''.join(filter(str.isdigit, parts[1])))
                        return {
                            'name': parts[0],
                            'vram_mib': vram_mib,
                            'vram_str': f"{vram_mib}MiB"
                        }
                    except:
                        pass
                return {'name': parts[0], 'vram_mib': None, 'vram_str': None}
        
        if platform.system() == 'Windows':
            result = self.run_command('wmic path win32_VideoController get Name,AdapterRAM /format:list')
            if result['ok'] and result['stdout']:
                lines = [l.strip() for l in result['stdout'].split('\\n') if l.strip()]
                name = None
                adapter_ram = None
                for line in lines:
                    if line.startswith('Name='):
                        name = line.split('=', 1)[1]
                    elif line.startswith('AdapterRAM='):
                        try:
                            adapter_ram = int(line.split('=', 1)[1])
                        except:
                            pass
                
                vram_mib = round(adapter_ram / 1024 / 1024) if adapter_ram else None
                return {
                    'name': name,
                    'vram_mib': vram_mib,
                    'vram_str': f"{vram_mib}MiB" if vram_mib else None
                }
        
        return {'name': None, 'vram_mib': None, 'vram_str': None}

    def get_ram_info(self):
        """Get RAM info - safe, doesn't interact with Ollama."""
        try:
            memory = psutil.virtual_memory()
            total_gb = round(memory.total / 1024 / 1024 / 1024)
            return {'total_gb': total_gb}
        except:
            return {'total_gb': None}

    def get_gpu_brand(self):
        """Get GPU brand - safe, doesn't interact with Ollama."""
        if not self.gpu_info or not self.gpu_info.get('name'):
            return 'gpu'
        
        gpu_name = self.gpu_info['name'].lower()
        
        if any(keyword in gpu_name for keyword in ['nvidia', 'geforce', 'rtx', 'gtx']):
            return 'nvidia'
        elif any(keyword in gpu_name for keyword in ['amd', 'radeon', 'rx']):
            return 'amd'
        elif any(keyword in gpu_name for keyword in ['intel', 'iris', 'uhd']):
            return 'intel'
        else:
            return 'gpu'

    def set_presence(self, model_obj):
        if not self.rpc:
            return
        
        model_name = model_obj.get('model', 'none') if model_obj else 'none'
        version = self.ollama_version or 'unknown'
        ram_text = f"{self.ram_info['total_gb']}GB" if self.ram_info and self.ram_info.get('total_gb') else 'unknown'
        card_name = self.gpu_info.get('name', 'unknown') if self.gpu_info else 'unknown'
        vram_text = self.gpu_info.get('vram_str', 'unknown') if self.gpu_info else 'unknown'
        gpu_brand = self.get_gpu_brand()
        
        try:
            start_time = int(time.time()) if model_obj else None
            
            self.rpc.update(
                details=f"MODEL: {model_name}",
                state=f"RAM: {ram_text} | VRAM: {vram_text}",
                large_image=self.config.get('largeImageKey', 'ollama'),
                large_text=f"VERSION: {version}",
                small_image=gpu_brand,
                small_text=f"{card_name}",
                start=start_time
            )
            
            if not self.presence_active:
                self.logger.info(f"Rich Presence SET: {model_name}")
            self.presence_active = True
            
        except Exception as e:
            self.logger.error(f"Failed to set presence: {e}")
            self.presence_active = False

    def clear_presence(self):
        if not self.rpc:
            return
            
        try:
            self.rpc.clear()
            self.presence_active = False
            self.logger.info("Rich Presence CLEARED")
        except Exception as e:
            self.logger.error(f"Failed to clear presence: {e}")
            self.presence_active = False

    def main_loop(self):
        running = self.is_ollama_running()
        
        status_text = "RUNNING" if running else "STOPPED"
        self.logger.info(f"DETECTION RESULT: Ollama is {status_text}")
        
        if self.was_running is None:
            self.was_running = running
            if running:
                self.logger.info("INITIAL STATE: Ollama already running -> Showing Rich Presence")
                self.refresh_hardware_info()
            else:
                self.logger.info("INITIAL STATE: Ollama not running")
        elif running != self.was_running:
            if running:
                self.logger.info("STATE CHANGE: Ollama STARTED -> Showing Rich Presence")
                self.was_running = True
                self.refresh_hardware_info()
            else:
                self.logger.info("STATE CHANGE: Ollama STOPPED -> Hiding Rich Presence")
                self.was_running = False
                self.clear_presence()
                return
        
        if running:
            if not self.gpu_info or not self.ram_info or not self.ollama_version:
                self.refresh_hardware_info()
            
            model = self.get_ollama_model()
            if model:
                self.logger.info(f"Showing presence with model: {model.get('model', 'none')}")
            self.set_presence(model)
        else:
            if self.presence_active:
                self.logger.info("Hiding presence - Ollama confirmed stopped")
                self.clear_presence()

    def signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.cleanup_and_exit()

    def cleanup_and_exit(self):
        if self.presence_active:
            self.clear_presence()
        
        if self.rpc:
            try:
                self.rpc.close()
            except:
                pass
        
        self.logger.info("Service stopped")
        sys.exit(0)

    def run(self):
        self.logger.info("Starting Ollama Discord Rich Presence Service")
        self.logger.info(f"Auto-start Ollama: {self.auto_start}")
        self.logger.info(f"Auto-exit: {self.auto_exit}")
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.logger.info("Connected to Discord")
        except Exception as e:
            self.logger.error(f"Failed to connect to Discord: {e}")
            sys.exit(1)
        
        self.refresh_hardware_info()
        
        ollama_stopped_count = 0
        
        try:
            while True:
                self.main_loop()
                
                if self.auto_exit:
                    if not self.is_ollama_running():
                        ollama_stopped_count += 1
                        if ollama_stopped_count >= 12:  # 60 seconds (12 * 5s intervals)
                            self.logger.info("Ollama stopped for 60 seconds, exiting...")
                            break
                    else:
                        ollama_stopped_count = 0
                
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup_and_exit()

if __name__ == "__main__":
    service = OllamaDiscordService()
    service.run()
'''
    
    with open("ollama_presence.py", "w", encoding='utf-8') as f:
        f.write(service_content)
    
    print("Service file created successfully")

def create_config():
    print("Creating configuration...")
    
    config = {
        "clientId": "1408133296000466945",
        "largeImageKey": "ollama",
        "autoStart": True,
        "autoExit": True,
        "ollamaCmd": "ollama ps"
    }
    
    with open("config.json", "w", encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print("Configuration created with pre-configured Discord App")

def setup_windows_service():
    print("Setting up Windows service...")
    
    current_dir = os.getcwd()
    python_exe = sys.executable
    
    batch_content = f'''@echo off
cd /d "{current_dir}"
"{python_exe}" ollama_presence.py
'''
    
    with open("ollama_discord_service.bat", "w", encoding='utf-8') as f:
        f.write(batch_content)
    
    vbs_content = f'''Set oShell = CreateObject ("Wscript.Shell") 
Dim strArgs
strArgs = "cmd /c {current_dir}\\ollama_discord_service.bat"
oShell.Run strArgs, 0, false
'''
    
    with open("ollama_discord_service.vbs", "w", encoding='utf-8') as f:
        f.write(vbs_content)
    
    startup_folder = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    if startup_folder.exists():
        try:
            shutil.copy2("ollama_discord_service.vbs", startup_folder / "ollama_discord_service.vbs")
            print("Added to Windows startup")
        except Exception as e:
            print(f"Could not add to startup automatically: {e}")
            print(f"Please manually copy 'ollama_discord_service.vbs' to:")
            print(f"   {startup_folder}")
    
    print("Windows service setup complete")

def main():
    print("Ollama Discord Rich Presence - One-Click Installer")
    print("=" * 50)
    
    check_python()
    install_dependencies()
    download_service_file()
    create_config()
    
    system = platform.system()
    if system == "Windows":
        setup_windows_service()
    
    print("\nInstallation complete!")
    print("Ready to use with pre-configured Discord App!")
    
    print("\nStarting service...")
    try:
        if system == "Windows":
            subprocess.Popen([sys.executable, "ollama_presence.py"], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen([sys.executable, "ollama_presence.py"], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Service started and running in background!")
    except Exception as e:
        print(f"Failed to start service: {e}")

if __name__ == "__main__":
    main()