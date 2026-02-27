#!/usr/bin/env python3
"""
Discord Orb Quest Faker

EDUCATIONAL PURPOSES ONLY - This tool is provided for educational and research
purposes only. The developers do not condone or encourage any misuse of this
software. Users are solely responsible for their actions and must comply with
all applicable laws and terms of service.

Automatically creates fake game processes for Discord Orb quests.
Developed by Strykey
"""

import os
import sys
import shutil
import requests
import subprocess
import time
from pathlib import Path
import tempfile
import zipfile
import hashlib
from datetime import datetime, timezone


class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'


def print_color(text, color=Colors.WHITE, bold=False):
    """Print colored text"""
    style = Colors.BOLD if bold else ''
    print(f"{style}{color}{text}{Colors.RESET}")


def print_boxed_title(title, width=50, color=Colors.CYAN):
    """Print a boxed title with ASCII borders"""
    border = f"{Colors.BOLD}{color}{'+' + '-' * (width - 2) + '+'}{Colors.RESET}"
    title_padding = (width - len(title) - 4) // 2
    extra_space = (width - len(title) - 4) % 2
    title_line = f"{Colors.BOLD}{color}|{Colors.RESET}{' ' * title_padding}{Colors.BOLD}{title}{Colors.RESET}{' ' * (title_padding + extra_space)}{Colors.BOLD}{color}|{Colors.RESET}"
    print(f"\n{border}")
    print(title_line)
    print(f"{border}\n")


def print_banner():
    """Display ASCII banner"""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
                                                                
 _____ _____ _____ _____    _____ _____ _____ _____ _____ _____ 
|     | __  | __  |   __|  |  |  |  _  |     |  |  |   __| __  |
|  |  |    -| __ -|__   |  |     |     |   --|    -|   __|    -|
|_____|__|__|_____|_____|  |__|__|__|__|_____|__|__|_____|__|__|
                                                                
{Colors.RESET}
    {Colors.GRAY}Developer: {Colors.CYAN}Strykey{Colors.RESET}
    {Colors.GRAY}Version: {Colors.WHITE}2.1.0{Colors.RESET}
    {Colors.GRAY}Database: {Colors.GREEN}Discord Official API + GitHub Archive{Colors.RESET}
"""
    print(banner)


def loading_animation(text, duration=1.5):
    """Display loading animation"""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + duration
    i = 0
    
    while time.time() < end_time:
        sys.stdout.write(f"\r{Colors.CYAN}{frames[i % len(frames)]}{Colors.RESET} {text}")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    
    sys.stdout.write("\r" + " " * (len(text) + 5) + "\r")
    sys.stdout.flush()


# ─────────────────────────────────────────────
#  STEAM QUEST MODE  –  helpers
# ─────────────────────────────────────────────

def get_steam_path():
    """Read Steam installation path from Windows registry."""
    if sys.platform != 'win32':
        return None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        value, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        return Path(value)
    except Exception:
        # Fallback to common default
        fallback = Path("C:/Program Files (x86)/Steam")
        return fallback if fallback.exists() else None


def get_steam_user_id():
    """Read the currently logged-in Steam user ID from registry."""
    if sys.platform != 'win32':
        return "0"
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess")
        value, _ = winreg.QueryValueEx(key, "ActiveUser")
        winreg.CloseKey(key)
        # Convert 32-bit accountid to 64-bit SteamID
        steam_id_64 = int(value) + 76561197960265728
        return str(steam_id_64)
    except Exception:
        return "0"


def fetch_steam_app_info(appid):
    """
    Fetch app info from SteamCMD public API.
    Returns dict with keys: name, installdir, executable  (or None on failure)
    """
    url = f"https://api.steamcmd.net/v1/info/{appid}"
    try:
        loading_animation(f"Fetching Steam app info for {appid}", 1.2)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        app_data = data.get("data", {}).get(str(appid), {})
        common  = app_data.get("common", {})
        config  = app_data.get("config", {})

        name       = common.get("name", f"App {appid}")
        installdir = config.get("installdir", name)

        # Try to find first Windows launch executable
        launch = config.get("launch", {})
        executable = None
        for key in sorted(launch.keys()):
            entry = launch[key]
            cfg   = entry.get("config", {})
            oslist = cfg.get("oslist", "windows")
            if "windows" in oslist or oslist == "":
                exe = entry.get("executable", "")
                if exe.endswith(".exe"):
                    executable = exe.replace("\\", "/")
                    break

        # Last resort: just use installdir name as exe
        if not executable:
            executable = installdir.split("/")[-1] + ".exe"

        # Try to get first depot id for StagedDepots
        depots = app_data.get("depots", {})
        depot_id = None
        for k, v in depots.items():
            if k.isdigit() and isinstance(v, dict):
                depot_id = k
                break

        return {"name": name, "installdir": installdir, "executable": executable, "depot_id": depot_id}

    except Exception as e:
        print_color(f"[!] SteamCMD API error: {e}", Colors.YELLOW)
        return None


def generate_appmanifest(appid, name, installdir, steam_path, depot_id=None):
    """
    Generate a realistic appmanifest_<appid>.acf matching what Steam creates
    during an active download (StateFlags 1026 = downloading).
    """
    steam_exe = str(steam_path / "steam.exe").replace("/", "\\\\")
    owner_id  = get_steam_user_id()

    staged_depots_block = ""
    if depot_id:
        staged_depots_block = f'''
\t\t"{depot_id}"
\t\t{{
\t\t\t"manifest"\t\t"0"
\t\t\t"size"\t\t"1073741824"
\t\t\t"dlcappid"\t\t"0"
\t\t}}'''

    acf_content = f'''"AppState"
{{
\t"appid"\t\t"{appid}"
\t"universe"\t\t"1"
\t"LauncherPath"\t\t"{steam_exe}"
\t"name"\t\t"{name}"
\t"StateFlags"\t\t"1026"
\t"installdir"\t\t"{installdir}"
\t"LastUpdated"\t\t"0"
\t"LastPlayed"\t\t"0"
\t"SizeOnDisk"\t\t"0"
\t"StagingSize"\t\t"1073741824"
\t"buildid"\t\t"0"
\t"LastOwner"\t\t"{owner_id}"
\t"DownloadType"\t\t"1"
\t"UpdateResult"\t\t"4"
\t"BytesToDownload"\t\t"1073741824"
\t"BytesDownloaded"\t\t"27262976"
\t"BytesToStage"\t\t"1073741824"
\t"BytesStaged"\t\t"27262976"
\t"TargetBuildID"\t\t"0"
\t"AutoUpdateBehavior"\t\t"0"
\t"AllowOtherDownloadsWhileRunning"\t\t"0"
\t"ScheduledAutoUpdate"\t\t"0"
\t"InstalledDepots"
\t{{
\t}}
\t"StagedDepots"
\t{{{staged_depots_block}
\t}}
\t"UserConfig"
\t{{
\t}}
\t"MountedConfig"
\t{{
\t}}
}}
'''
    acf_path = steam_path / "steamapps" / f"appmanifest_{appid}.acf"
    try:
        acf_path.parent.mkdir(parents=True, exist_ok=True)
        with open(acf_path, "w", encoding="utf-8") as f:
            f.write(acf_content)
        print_color(f"[OK] Created appmanifest: {acf_path}", Colors.GREEN, bold=True)
        return acf_path
    except Exception as e:
        print_color(f"[ERROR] Failed to write appmanifest: {e}", Colors.RED, bold=True)
        return None


def search_steam_games(query):
    """Search Steam store for games matching query. Returns list of {id, name} dicts."""
    try:
        loading_animation(f"Searching Steam for '{query}'", 1.0)
        resp = requests.get(
            "https://store.steampowered.com/api/storesearch",
            params={"term": query, "l": "english", "cc": "US"},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        print_color(f"[!] Steam search error: {e}", Colors.YELLOW)
        return []


def steam_quest_mode(faker):
    """Steam Quest Mode – generates appmanifest + fake exe for any Steam appid."""
    print_boxed_title("STEAM QUEST MODE", width=55, color=Colors.CYAN)

    print_color("[*] This mode generates a fake Steam appmanifest + exe", Colors.CYAN)
    print_color("[*] Required for games that verify Steam ownership (Marathon, Toxic Commando…)", Colors.GRAY)
    print_color("[*] Search by game name — demos and DLCs are listed separately, pick the right one!", Colors.YELLOW)
    print_color("[*] TIP: If the quest targets a Demo, search 'Toxic Commando Demo' not just 'Toxic Commando'", Colors.GRAY)
    print()

    # ── locate Steam ──────────────────────────────────────────────────
    steam_path = get_steam_path()
    if not steam_path or not steam_path.exists():
        print_color("[!] Could not locate Steam automatically.", Colors.YELLOW)
        manual_steam = input(f"{Colors.BOLD}Enter Steam path manually{Colors.RESET} (e.g. C:/Program Files (x86)/Steam): ").strip()
        if not manual_steam:
            print_color("[!] No Steam path provided. Aborting.", Colors.RED)
            return
        steam_path = Path(manual_steam)

    print_color(f"[OK] Steam found at: {steam_path}", Colors.GREEN)

    # ── search game ───────────────────────────────────────────────────
    query = input(f"\n{Colors.BOLD}Search game{Colors.RESET} (or 'back'): ").strip()
    if query.lower() in ['back', 'b', '']:
        return

    results = search_steam_games(query)

    if not results:
        print_color(f"\n[ERROR] No results found for '{query}'", Colors.RED)
        print_color("[!] Try a different search term", Colors.YELLOW)
        time.sleep(2)
        return

    print(f"\n{Colors.BOLD}{Colors.GREEN}Found {len(results)} result(s):{Colors.RESET}\n")
    print(f"{Colors.GRAY}{'─' * 60}{Colors.RESET}")
    for idx, game in enumerate(results, 1):
        print(f"  {Colors.BOLD}{Colors.CYAN}{idx:2d}.{Colors.RESET} {Colors.WHITE}{game['name']}{Colors.RESET}  {Colors.GRAY}(AppID: {game['id']}){Colors.RESET}")
        if idx < len(results):
            print(f"{Colors.GRAY}{'─' * 60}{Colors.RESET}")
    print()

    choice = input(f"{Colors.BOLD}Select [1-{len(results)}]{Colors.RESET} (or 'back'): ").strip()
    if choice.lower() in ['back', 'b', '']:
        return
    try:
        choice = int(choice)
        if choice < 1 or choice > len(results):
            raise ValueError
    except ValueError:
        print_color("[ERROR] Invalid selection.", Colors.RED)
        time.sleep(1.5)
        return

    selected = results[choice - 1]
    appid    = int(selected['id'])
    print_color(f"\n[OK] Selected: {selected['name']} (AppID: {appid})", Colors.GREEN, bold=True)

    # ── fetch info from SteamCMD API ──────────────────────────────────
    info = fetch_steam_app_info(appid)
    if not info:
        print_color("[!] Could not fetch app info automatically.", Colors.YELLOW)
        print_color("[*] You can enter the details manually:", Colors.CYAN)
        info = {
            "name":       input(f"  {Colors.BOLD}Game name{Colors.RESET}: ").strip() or f"App {appid}",
            "installdir": input(f"  {Colors.BOLD}Install dir{Colors.RESET} (folder name in steamapps/common): ").strip() or f"App{appid}",
            "executable": input(f"  {Colors.BOLD}Executable{Colors.RESET} (relative path, e.g. Bin/Game.exe): ").strip() or "Game.exe",
        }

    print(f"\n{Colors.BOLD}Detected info:{Colors.RESET}")
    print(f"  Name:        {Colors.CYAN}{info['name']}{Colors.RESET}")
    print(f"  Install dir: {Colors.CYAN}{info['installdir']}{Colors.RESET}")
    print(f"  Executable:  {Colors.CYAN}{info['executable']}{Colors.RESET}")

    # Allow override
    override = input(f"\n{Colors.BOLD}Override executable path?{Colors.RESET} [leave empty to keep]: ").strip()
    if override:
        info['executable'] = override.replace("\\", "/")

    exe_full_path = f"{info['installdir']}/{info['executable']}"
    fake_exe_path = steam_path / "steamapps" / "common" / exe_full_path.replace("/", os.sep)

    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  AppManifest: {Colors.GRAY}{steam_path / 'steamapps' / f'appmanifest_{appid}.acf'}{Colors.RESET}")
    print(f"  Fake exe:    {Colors.GRAY}{fake_exe_path}{Colors.RESET}")

    confirm = input(f"\n{Colors.BOLD}Create and launch?{Colors.RESET} [Y/n]: ").strip().lower()
    if confirm not in ['', 'y', 'yes']:
        print_color("\n[!] Operation cancelled.", Colors.YELLOW)
        time.sleep(1)
        return

    # ── generate appmanifest ──────────────────────────────────────────
    acf = generate_appmanifest(appid, info['name'], info['installdir'], steam_path, depot_id=info.get('depot_id'))
    if not acf:
        print_color("[ERROR] Failed to create appmanifest. Aborting.", Colors.RED)
        time.sleep(1.5)
        return

    # ── create fake exe ───────────────────────────────────────────────
    fake_exe_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        loading_animation(f"Creating {info['executable'].split('/')[-1]}", 0.8)
        shutil.copy2(faker.exe_source, fake_exe_path)
        print_color(f"[OK] Created: {fake_exe_path}", Colors.GREEN, bold=True)
    except Exception as e:
        print_color(f"[ERROR] Failed to copy exe: {e}", Colors.RED, bold=True)
        time.sleep(1.5)
        return

    # ── launch ────────────────────────────────────────────────────────
    print()
    faker.launch_executable(fake_exe_path)

    print_color("\n[OK] Steam Quest setup complete!", Colors.GREEN, bold=True)
    print_color("[!] Discord MUST be running for detection to work.", Colors.YELLOW)
    print_color("[*] Keep the process running until the quest is done.", Colors.CYAN)
    print_color("[*] When done, you can delete the appmanifest and the fake exe.", Colors.GRAY)

    input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")


# ─────────────────────────────────────────────


class DiscordGamesDB:
    DISCORD_API_URL = "https://discord.com/api/v9/applications/detectable"
    GITHUB_BACKUP_URL = "https://gist.githubusercontent.com/Cynosphere/c1e77f77f0e565ddaac2822977961e76/raw/gameslist.json"
    
    def __init__(self):
        self.games = []
        self.source = None
        self.load_games_list()
    
    def load_games_list(self):
        """Load games from Discord API or GitHub backup"""
        print_color("\n[*] Loading games database...", Colors.YELLOW)
        
        if self._load_from_discord_api():
            return
        
        print_color("[!] Discord API unavailable, using GitHub backup...", Colors.YELLOW)
        if self._load_from_github():
            return
        
        print_color("[ERROR] Failed to load any database!", Colors.RED, bold=True)
        sys.exit(1)
    
    def _load_from_discord_api(self):
        """Load from Discord's official API"""
        try:
            loading_animation("Connecting to Discord API", 1.0)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://discord.com/',
                'Origin': 'https://discord.com'
            }
            
            response = requests.get(self.DISCORD_API_URL, headers=headers, timeout=10)
            
            if response.status_code == 200:
                self.games = response.json()
                self.source = "Discord Official API"
                print_color(f"[OK] Loaded {len(self.games)} games from Discord API", Colors.GREEN, bold=True)
                print_color(f"[*] Using LIVE database (fresh from Discord's servers)", Colors.CYAN)
                return True
            else:
                return False
                
        except Exception as e:
            print_color(f"[!] Discord API error: {e}", Colors.YELLOW)
            return False
    
    def _load_from_github(self):
        """Load from GitHub backup"""
        try:
            loading_animation("Fetching GitHub backup", 1.0)
            
            response = requests.get(self.GITHUB_BACKUP_URL, timeout=15)
            response.raise_for_status()
            self.games = response.json()
            self.source = "GitHub Backup"
            print_color(f"[OK] Loaded {len(self.games)} games from GitHub", Colors.GREEN, bold=True)
            return True
            
        except Exception as e:
            print_color(f"[ERROR] GitHub backup failed: {e}", Colors.RED)
            return False
    
    def search_games(self, query):
        """Search for games by name or alias"""
        query_lower = query.lower()
        matches = []
        
        for game in self.games:
            name = game.get('name', '').lower()
            aliases = [a.lower() for a in game.get('aliases', [])]
            
            if query_lower == name or query_lower in aliases:
                matches.insert(0, game)
            elif query_lower in name or any(query_lower in alias for alias in aliases):
                matches.append(game)
        
        seen = set()
        unique_matches = []
        for game in matches:
            game_id = game.get('id')
            if game_id not in seen:
                seen.add(game_id)
                unique_matches.append(game)
        
        return unique_matches[:20]
    
    def get_win32_executable(self, game):
        """Extract primary Windows executable from game data (with full path)"""
        executables = game.get('executables', [])
        candidates = []
        
        for exe in executables:
            if exe.get('os') != 'win32':
                continue
            
            name = exe.get('name', '')
            if name.startswith('>'):
                name = name[1:]
            
            name = name.replace('\\', '/')
            name_lower = name.lower()
            skip_patterns = ['_be.exe', '_eac.exe', 'launcher', 'unins', 'crash', 'report', 'update', 'setup', 'install']
            
            if any(skip in name_lower for skip in skip_patterns):
                continue
            
            candidates.append(name)
        
        return candidates[0] if candidates else None
    
    def get_all_executables(self, game):
        """Get all Windows executables for a game (with full paths)"""
        executables = game.get('executables', [])
        all_exes = []
        
        for exe in executables:
            if exe.get('os') != 'win32':
                continue
            
            name = exe.get('name', '')
            if name.startswith('>'):
                name = name[1:]
            
            name = name.replace('\\', '/')
            
            if name and name not in all_exes:
                all_exes.append(name)
        
        return all_exes


class GameFaker:
    def __init__(self, exe_source="exe.exe"):
        self.exe_source = Path(exe_source)
        self.desktop_path = Path.home() / "Desktop"
        
        if not self.exe_source.exists():
            print_color(f"\n[ERROR] Source executable not found: {self.exe_source}", Colors.RED, bold=True)
            print_color(f"[!] Please place 'exe.exe' in: {Path.cwd()}", Colors.YELLOW)
            print_color("[*] We can't fake games without the base executable, you know", Colors.GRAY)
            sys.exit(1)
    
    def create_fake_game(self, exe_name):
        """Create fake game executable with full directory structure"""
        if not exe_name.lower().endswith('.exe'):
            exe_name += '.exe'
        
        exe_name = exe_name.replace('\\', '/')
        target_path = self.desktop_path / "Win64" / exe_name
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            filename = exe_name.split('/')[-1]
            loading_animation(f"Creating {filename}", 0.8)
            shutil.copy2(self.exe_source, target_path)
            print_color(f"[OK] Created: {target_path}", Colors.GREEN, bold=True)
            return target_path
        except Exception as e:
            print_color(f"[ERROR] Failed to create executable: {e}", Colors.RED, bold=True)
            print_color("[!] Check file permissions or disk space", Colors.YELLOW)
            return None
    
    def launch_executable(self, exe_path):
        """Launch executable in background - Educational purposes only"""
        try:
            loading_animation("Launching process", 0.8)
            
            if sys.platform == 'win32':
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(
                    [str(exe_path)],
                    creationflags=DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    [str(exe_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            print_color("[OK] Process launched in background", Colors.GREEN, bold=True)
            print_color("[*] Discord should now detect the game (if Discord is running)", Colors.CYAN)
            print_color("[!] IMPORTANT: Discord MUST be running for the spoofing to work", Colors.YELLOW)
            print_color("[*] Wait a few seconds for Discord to scan processes", Colors.GRAY)
            print_color("[*] If it doesn't work, make sure Discord is actually open", Colors.GRAY)
            print_color(f"[*] TIP: You can run this tool multiple times to emulate multiple games!", Colors.MAGENTA)
            return True
        except Exception as e:
            print_color(f"[!] Failed to auto-launch: {e}", Colors.YELLOW)
            print_color(f"[*] You can manually run: {exe_path}", Colors.CYAN)
            print_color("[*] Or try running it as administrator", Colors.GRAY)
            return False


def print_menu():
    """Display main menu"""
    print_boxed_title("MAIN MENU", width=50, color=Colors.CYAN)
    
    print(f"  {Colors.BOLD}{Colors.GREEN}1.{Colors.RESET} Search Discord database (Official API)")
    print(f"  {Colors.BOLD}{Colors.GREEN}2.{Colors.RESET} Manual mode (custom executable)")
    print(f"  {Colors.BOLD}{Colors.YELLOW}3.{Colors.RESET} Steam Quest Mode  {Colors.YELLOW}[NEW - for Marathon, Toxic Commando…]{Colors.RESET}")
    print(f"  {Colors.BOLD}{Colors.GREEN}4.{Colors.RESET} Credits & Info")
    print(f"  {Colors.BOLD}{Colors.RED}5.{Colors.RESET} Exit\n")


def show_credits():
    """Display credits"""
    print_boxed_title("CREDITS", width=65, color=Colors.CYAN)
    credits = f"""
    {Colors.BOLD}Developer:{Colors.RESET} {Colors.CYAN}Strykey{Colors.RESET}
    {Colors.BOLD}Version:{Colors.RESET} {Colors.WHITE}2.1.0{Colors.RESET}
    
    {Colors.BOLD}Description:{Colors.RESET}
    This tool works as a game process spoofer. It tricks Discord into
    thinking you're running a game by creating fake processes with the
    exact names Discord expects.
    
    {Colors.BOLD}IMPORTANT:{Colors.RESET} {Colors.RED}Discord MUST be running for this to work!{Colors.RESET}
    
    {Colors.BOLD}How it works (Game Spoofing):{Colors.RESET}
    1. Connects to Discord's official API to get the latest game list
    2. Finds the exact process name Discord expects for each game
    3. Copies exe.exe to Desktop/Win64/ and renames it to match
    4. Launches the fake process in background
    5. Discord scans running processes and detects the fake process name
    6. Discord thinks you're playing the game (process name match)
    7. The fake process must stay running for Discord to keep detecting it
    
    {Colors.BOLD}Steam Quest Mode (NEW):{Colors.RESET}
    Some games (Marathon, Toxic Commando…) require Discord to verify
    that Steam has at least partially downloaded them.
    Steam Quest Mode bypasses this by:
    1. Fetching app info automatically from SteamCMD public API
    2. Generating a fake appmanifest_<appid>.acf in your steamapps/ folder
       (StateFlags=4 → paused download, exactly what Steam creates)
    3. Placing the fake exe directly in steamapps/common/<installdir>/
    Discord then sees a valid Steam manifest + a running process = quest detected.
    No actual download required.
    
    {Colors.BOLD}Database Sources:{Colors.RESET}
    • Primary: Discord Official API
    • Backup:  GitHub Archive by Cynosphere
    
    {Colors.BOLD}Pro Tips:{Colors.RESET}
    • Use Steam Quest Mode for any game that wasn't detected by modes 1 or 2
    • Find AppIDs at https://steamdb.info
    • Discord MUST be running - the tool won't work otherwise
    • The fake process must stay running for Discord to detect it
    • Close the fake exe after completing the quest
    
    {Colors.BOLD}{Colors.GREEN}Multi-Game Emulation:{Colors.RESET}
    • Run this tool multiple times to emulate multiple games at once
    • Complete ALL orb quests simultaneously in just 15 minutes
    
    {Colors.BOLD}{Colors.RED}WARNING - EDUCATIONAL PURPOSES ONLY{Colors.RESET}
    • Users are SOLELY responsible for compliance with Discord ToS
    • The developers are NOT responsible for any consequences
    • Use at your own risk
    
    {Colors.GRAY}Made by Strykey{Colors.RESET}
    {Colors.GRAY}Press Enter to return to menu...{Colors.RESET}
"""
    print(credits)
    input()


def manual_mode(faker):
    """Manual mode for custom executable names"""
    print_boxed_title("MANUAL MODE", width=50, color=Colors.CYAN)
    
    print_color("[*] Enter the exact process name Discord expects", Colors.CYAN)
    print_color("[*] Examples:", Colors.GRAY)
    print_color("    • TslGame.exe (PUBG)", Colors.GRAY)
    print_color("    • League of Legends.exe (LoL)", Colors.GRAY)
    print_color("    • Overwatch.exe", Colors.GRAY)
    print_color("[*] Make sure the name matches exactly (case-sensitive on some systems)", Colors.GRAY)
    print()
    
    exe_name = input(f"{Colors.BOLD}Executable name{Colors.RESET} (or 'back'): ").strip()
    
    if exe_name.lower() in ['back', 'b', '']:
        return
    
    if not exe_name:
        print_color("\n[ERROR] Invalid executable name", Colors.RED)
        print_color("[!] You need to enter something, you know", Colors.YELLOW)
        time.sleep(1.5)
        return
    
    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Executable: {Colors.CYAN}{exe_name}{Colors.RESET}")
    print(f"  Path: {Colors.GRAY}{faker.desktop_path / 'Win64' / exe_name}{Colors.RESET}")

    confirm = input(f"\n{Colors.BOLD}Create and launch?{Colors.RESET} [Y/n]: ").strip().lower()

    if confirm not in ['', 'y', 'yes']:
        print_color("\n[!] Operation cancelled", Colors.YELLOW)
        print_color("[*] No fake games were created (this time)", Colors.GRAY)
        time.sleep(1.5)
        return

    result = faker.create_fake_game(exe_name)
    
    if result:
        print()
        faker.launch_executable(result)
        print_color("\n[OK] Setup complete!", Colors.GREEN, bold=True)
        print_color("[!] IMPORTANT: Discord MUST be running for the spoofing to work", Colors.YELLOW)
        print_color("[*] Process is running in the background", Colors.GRAY)
        print_color("[*] Discord should detect it by scanning process names", Colors.GRAY)
    
    input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")


def database_mode(db, faker):
    """Database search mode"""
    print_boxed_title("DATABASE SEARCH", width=50, color=Colors.CYAN)
    
    print_color(f"[*] Database: {db.source}", Colors.CYAN)
    print_color(f"[*] Total games available: {len(db.games)}", Colors.GRAY)
    print_color("\n[*] Search by name or abbreviation", Colors.CYAN)
    print_color("[*] Examples: PUBG, Fortnite, League, Valorant, Minecraft", Colors.GRAY)
    print()
    
    query = input(f"{Colors.BOLD}Search{Colors.RESET} (or 'back'): ").strip()
    
    if query.lower() in ['back', 'b', '']:
        return
    
    loading_animation(f"Searching for '{query}'", 0.8)
    matches = db.search_games(query)

    if not matches:
        print_color(f"\n[ERROR] No games found for '{query}'", Colors.RED)
        print_color("[!] Try a different search term or abbreviation", Colors.YELLOW)
        print_color("[*] Pro tip: Try searching 'Minecraft' instead of 'minecraft.exe'", Colors.GRAY)
        time.sleep(2)
        return
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}Found {len(matches)} game(s):{Colors.RESET}\n")
    print(f"{Colors.GRAY}{'─' * 75}{Colors.RESET}")
    
    for idx, game in enumerate(matches, 1):
        name = game.get('name', 'Unknown')
        game_id = game.get('id', 'N/A')
        aliases = game.get('aliases', [])
        
        print(f"{Colors.BOLD}{Colors.CYAN}{idx:2d}.{Colors.RESET} {Colors.WHITE}{name}{Colors.RESET}")
        if aliases:
            alias_str = ', '.join(aliases[:3])
            if len(aliases) > 3:
                alias_str += f" (+{len(aliases)-3} more)"
            print(f"    {Colors.GRAY}Aliases: {alias_str}{Colors.RESET}")
        print(f"    {Colors.GRAY}ID: {game_id}{Colors.RESET}")
        
        if idx < len(matches):
            print(f"{Colors.GRAY}{'─' * 75}{Colors.RESET}")
    
    print()
    choice = input(f"{Colors.BOLD}Select [1-{len(matches)}]{Colors.RESET} (or 'back'): ").strip()
    
    if choice.lower() in ['back', 'b', '']:
        return
    
    try:
        choice = int(choice)
        if choice < 1 or choice > len(matches):
            print_color("\n[ERROR] Invalid selection", Colors.RED)
            time.sleep(1)
            return
    except ValueError:
        print_color("\n[ERROR] Enter a number", Colors.RED)
        time.sleep(1)
        return
    
    selected = matches[choice - 1]
    
    loading_animation("Analyzing game data", 0.8)
    exe_name = db.get_win32_executable(selected)
    all_exes = db.get_all_executables(selected)

    if not exe_name:
        print_color("\n[ERROR] No Windows executable found for this game", Colors.RED)
        print_color("[!] This game might not have a Windows version or executable data", Colors.YELLOW)
        manual = input(f"{Colors.YELLOW}Enter executable name manually?{Colors.RESET} [Y/n]: ").strip().lower()
        
        if manual in ['', 'y', 'yes']:
            exe_name = input(f"{Colors.BOLD}Executable name:{Colors.RESET} ").strip()
            if not exe_name:
                print_color("\n[!] Operation cancelled", Colors.YELLOW)
                time.sleep(1.5)
                return
        else:
            return
    
    print(f"\n{Colors.BOLD}Game Information:{Colors.RESET}")
    print(f"  Name: {Colors.CYAN}{selected.get('name')}{Colors.RESET}")
    print(f"  ID: {Colors.GRAY}{selected.get('id')}{Colors.RESET}")
    print(f"  Primary Executable: {Colors.GREEN}{exe_name}{Colors.RESET}")

    if len(all_exes) > 1:
        print(f"  {Colors.GRAY}Other executables: {', '.join(all_exes[1:3])}{Colors.RESET}")
        if len(all_exes) > 3:
            print(f"  {Colors.GRAY}(+{len(all_exes)-3} more executables available){Colors.RESET}")

    print(f"  Path: {Colors.GRAY}{faker.desktop_path / 'Win64' / exe_name}{Colors.RESET}")

    confirm = input(f"\n{Colors.BOLD}Create and launch?{Colors.RESET} [Y/n]: ").strip().lower()

    if confirm not in ['', 'y', 'yes']:
        print_color("\n[!] Operation cancelled", Colors.YELLOW)
        print_color("[*] Returning to main menu...", Colors.GRAY)
        time.sleep(1.5)
        return
    
    result = faker.create_fake_game(exe_name)
    
    if result:
        print()
        faker.launch_executable(result)
        print_color("\n[OK] Setup complete! Discord should detect the game.", Colors.GREEN, bold=True)
        print_color(f"[!] IMPORTANT: Discord MUST be running for the spoofing to work", Colors.YELLOW)
        print_color(f"[*] Keep the process running until quest is complete", Colors.CYAN)
        print_color("[*] Don't close this window or the process will stop", Colors.GRAY)
        print_color("[*] The game spoofer works by matching process names", Colors.GRAY)
        print_color(f"[*] TIP: Run this tool again to emulate another game simultaneously!", Colors.MAGENTA)
        print_color(f"[*] You can complete ALL orb quests at once in 15 minutes!", Colors.MAGENTA)
    
    input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")


def auto_update_from_github(repo_url, dry_run=False):
    """Download repo ZIP from GitHub, compare files and update local files if different.

    - Only adds/updates files (will not delete local files).
    - Makes backups into `.backups/<timestamp>/...` before overwriting.
    - Silently continues on network errors.
    """
    # small UX: show checking animation
    try:
        loading_animation("Checking for updates", 1.2)
    except Exception:
        pass

    try:
        base_dir = Path(__file__).resolve().parent
    except Exception:
        return []

    def _download_repo_zip(url):
        resp = requests.get(url, stream=True, timeout=20)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        with open(tmp.name, 'wb') as fh:
            for chunk in resp.iter_content(1024 * 8):
                if chunk:
                    fh.write(chunk)
        return tmp.name

    def _extract_zip_to_temp(zip_path):
        td = tempfile.mkdtemp()
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(td)
        return Path(td)

    def _sha256(path):
        h = hashlib.sha256()
        with open(path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def _sync_dirs(src_dir, dst_dir, dry_run=False):
        updated = []
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup_base = dst_dir / '.backups' / timestamp

        for src in src_dir.rglob('*'):
            if src.is_dir():
                continue
            rel = src.relative_to(src_dir)
            if any(part.startswith('.git') for part in rel.parts):
                continue

            dst = dst_dir / rel
            if dst.exists():
                try:
                    if _sha256(src) == _sha256(dst):
                        continue
                except Exception:
                    pass

                backup_target = backup_base / rel
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                if not dry_run:
                    shutil.copy2(dst, backup_target)

                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dry_run:
                    shutil.copy2(src, dst)
                updated.append(str(rel))
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dry_run:
                    shutil.copy2(src, dst)
                updated.append(str(rel))

        return updated

    branches = ['main', 'master']
    for branch in branches:
        try:
            zip_url = f"{repo_url.rstrip('/')}/archive/refs/heads/{branch}.zip"
            zip_path = _download_repo_zip(zip_url)
            extracted = _extract_zip_to_temp(zip_path)

            entries = [p for p in extracted.iterdir() if p.is_dir()]
            repo_root = entries[0] if entries else extracted

            updated_files = _sync_dirs(repo_root, base_dir, dry_run=dry_run)

            if updated_files:
                print_color(f"[UPDATE] Applied {len(updated_files)} updated/new files", Colors.GREEN)
            else:
                print_color("[UPDATE] No changes detected", Colors.CYAN)

            try:
                os.unlink(zip_path)
            except Exception:
                pass

            return updated_files

        except Exception:
            continue

    return []


def main():
    """Main application loop"""
    try:
        repo_url = "https://github.com/strykey/orbshacker"
        auto_update_from_github(repo_url, dry_run=False)
    except Exception:
        pass

    print_banner()
    
    print_color("Initializing Discord Orb Quest Faker...", Colors.CYAN)
    print_color("[*] Connecting to Discord API...", Colors.GRAY)
    db = DiscordGamesDB()
    faker = GameFaker()
    print_color("[OK] Ready to fake some games!", Colors.GREEN)
    time.sleep(0.5)
    
    while True:
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
            print_banner()
            
            if db.source:
                print_color(f"   Active Database: {db.source} ({len(db.games)} games)", Colors.GRAY)
            
            print_menu()
            
            choice = input(f"{Colors.BOLD}Select option{Colors.RESET} [1-5]: ").strip()
            
            if choice == '1':
                database_mode(db, faker)
            elif choice == '2':
                manual_mode(faker)
            elif choice == '3':
                steam_quest_mode(faker)
            elif choice == '4':
                show_credits()
            elif choice == '5':
                print_color("\n[*] Thanks for using Orb Quest Faker!", Colors.CYAN, bold=True)
                print_color("[*] Developed by Strykey", Colors.GRAY)
                print_color("\n[*] May your orbs be plentiful!", Colors.MAGENTA)
                print_color("[*] Remember: With great power comes great responsibility\n", Colors.GRAY)
                break
            else:
                print_color("\n[ERROR] Invalid option - try 1, 2, 3, 4 or 5", Colors.RED)
                time.sleep(1.5)
                
        except KeyboardInterrupt:
            print_color("\n\n[!] Interrupted by user", Colors.YELLOW)
            print_color("[*] Exiting gracefully...", Colors.GRAY)
            print_color("[*] Thanks for using Orb Quest Faker!\n", Colors.CYAN)
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_color("\n\n[!] Interrupted", Colors.YELLOW)
        sys.exit(0)
    except Exception as e:
        print_color(f"\n[ERROR] Fatal error: {e}", Colors.RED, bold=True)
        print_color("[!] This shouldn't happen. Please report this issue.", Colors.YELLOW)
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
