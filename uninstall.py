#!/usr/bin/env python3
"""
Ollama Discord Rich Presence - Uninstaller
Removes all traces of the service
"""

import os
import sys
import subprocess
import platform
import psutil
from pathlib import Path
import shutil

def kill_ollama_presence():
    """Kill any running ollama_presence processes."""
    print("🔄 Stopping Ollama Discord Rich Presence...")
    
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if it's our process
            if proc.info['cmdline']:
                cmdline_str = ' '.join(proc.info['cmdline'])
                if 'ollama_presence.py' in cmdline_str or 'ollama_discord_service' in cmdline_str:
                    print(f"  Killing process: {proc.info['pid']}")
                    proc.kill()
                    killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if killed > 0:
        print(f"✅ Stopped {killed} process(es)")
    else:
        print("✅ No running processes found")

def remove_windows_service():
    """Remove Windows startup entries."""
    print("🔧 Removing Windows startup entries...")
    
    startup_folder = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    vbs_file = startup_folder / "ollama_discord_service.vbs"
    
    if vbs_file.exists():
        try:
            vbs_file.unlink()
            print("  ✅ Removed startup VBS file")
        except Exception as e:
            print(f"  ❌ Failed to remove VBS file: {e}")
    
    # Also check current directory
    current_dir = Path.cwd()
    for file in ["ollama_discord_service.bat", "ollama_discord_service.vbs"]:
        file_path = current_dir / file
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"  ✅ Removed {file}")
            except Exception as e:
                print(f"  ❌ Failed to remove {file}: {e}")

def remove_linux_service():
    """Remove Linux systemd service."""
    print("🔧 Removing Linux systemd service...")
    
    try:
        # Stop and disable service
        subprocess.run(["sudo", "systemctl", "stop", "ollama-discord.service"], 
                      capture_output=True)
        subprocess.run(["sudo", "systemctl", "disable", "ollama-discord.service"], 
                      capture_output=True)
        
        # Remove service file
        service_file = Path("/etc/systemd/system/ollama-discord.service")
        if service_file.exists():
            subprocess.run(["sudo", "rm", str(service_file)], capture_output=True)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True)
            print("  ✅ Removed systemd service")
        
        # Remove local service file
        local_service = Path.cwd() / "ollama-discord.service"
        if local_service.exists():
            local_service.unlink()
            print("  ✅ Removed local service file")
            
    except Exception as e:
        print(f"  ❌ Error removing systemd service: {e}")

def remove_macos_service():
    """Remove macOS LaunchAgent."""
    print("🔧 Removing macOS LaunchAgent...")
    
    try:
        launch_agents_dir = Path.home() / "Library/LaunchAgents"
        plist_file = launch_agents_dir / "com.ollama.discord.presence.plist"
        
        if plist_file.exists():
            # Unload the service
            subprocess.run(["launchctl", "unload", str(plist_file)], 
                          capture_output=True)
            
            # Remove the plist file
            plist_file.unlink()
            print("  ✅ Removed LaunchAgent")
            
    except Exception as e:
        print(f"  ❌ Error removing LaunchAgent: {e}")

def remove_files():
    """Remove application files."""
    print("🗑️  Removing application files...")
    
    current_dir = Path.cwd()
    files_to_remove = [
        "ollama_presence.py",
        "config.json",
        "install.py"
    ]
    
    removed = 0
    for file in files_to_remove:
        file_path = current_dir / file
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"  ✅ Removed {file}")
                removed += 1
            except Exception as e:
                print(f"  ❌ Failed to remove {file}: {e}")
    
    if removed == 0:
        print("  ℹ️  No application files found")

def remove_logs():
    """Remove log files."""
    print("📝 Removing log files...")
    
    try:
        home_dir = Path.home()
        log_dir = home_dir / '.ollama' / 'discord'
        
        if log_dir.exists():
            shutil.rmtree(log_dir)
            print("  ✅ Removed log directory")
            
            # Remove .ollama directory if empty
            ollama_dir = home_dir / '.ollama'
            if ollama_dir.exists() and not any(ollama_dir.iterdir()):
                ollama_dir.rmdir()
                print("  ✅ Removed empty .ollama directory")
        else:
            print("  ℹ️  No log files found")
            
    except Exception as e:
        print(f"  ❌ Error removing logs: {e}")

def main():
    print("🗑️  Ollama Discord Rich Presence - Uninstaller")
    print("=" * 45)
    print()
    
    # Confirm uninstallation
    response = input("Are you sure you want to completely remove Ollama Discord Rich Presence? (y/N): ")
    if not response.lower().startswith('y'):
        print("❌ Uninstallation cancelled")
        return
    
    print()
    
    # Kill running processes
    kill_ollama_presence()
    
    # Remove platform-specific services
    system = platform.system()
    if system == "Windows":
        remove_windows_service()
    elif system == "Linux":
        remove_linux_service()
    elif system == "Darwin":
        remove_macos_service()
    
    # Remove files and logs
    remove_files()
    remove_logs()
    
    print()
    print("🎉 Uninstallation complete!")
    

if __name__ == "__main__":
    main()
