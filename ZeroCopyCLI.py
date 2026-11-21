import requests
import time
import os
import re
import glob
import base64
import sys
from datetime import datetime

API = "https://discord.com/api/v9"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_RETRIES = 5
TIMEOUT = 15

def cprint(text, color="white"):
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "cyan": "\033[96m",
        "white": "\033[0m"
    }
    print(f"{colors.get(color, '')}{text}{colors['white']}")
    sys.stdout.flush()

def log(msg, color="white"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    cprint(f"[{timestamp}] {msg}", color)

def find_token():
    appdata = os.getenv("APPDATA", "")
    localappdata = os.getenv("LOCALAPPDATA", "")
    paths = [
        os.path.join(appdata, "discord", "Local Storage", "leveldb"),
        os.path.join(appdata, "discordptb", "Local Storage", "leveldb"),
        os.path.join(appdata, "discordcanary", "Local Storage", "leveldb"),
        os.path.join(localappdata, "Google", "Chrome", "User Data", "Default", "Local Storage", "leveldb"),
        os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default", "Local Storage", "leveldb"),
    ]
    token_regex = re.compile(r"[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}|mfa\.[\w-]{80,95}")
    for path in paths:
        if not os.path.exists(path): continue
        for file in glob.glob(os.path.join(path, "*.ldb")) + glob.glob(os.path.join(path, "*.log")):
            try:
                with open(file, "r", encoding="utf-8", errors="ignore") as f:
                    matches = token_regex.findall(f.read())
                    if matches: return matches[0]
            except: pass
    return None

class ZeroCopyCLI:
    def __init__(self):
        self.headers = {}
        self.role_map = {}
        self.stats = {"success": 0, "failed": 0}

    def start(self):
        os.system("cls")
        cprint("=" * 60, "cyan")
        cprint("  Zero Copy - Advanced Server Cloner (v10)", "cyan")
        cprint("=" * 60, "cyan")
        print()

        cprint("[*] Token Setup", "yellow")
        cprint("  1. Paste Token manually", "white")
        cprint("  2. Auto-extract from Discord", "white")
        choice = input("  Select (1/2): ").strip()

        if choice == "2":
            log("Searching for token...", "cyan")
            token = find_token()
            if not token:
                log("Token not found.", "red")
                return
            log("Token found automatically.", "green")
        else:
            token = input("  Paste Token: ").strip()

        if not token:
            log("Token is required.", "red")
            return

        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_UA
        }

        me = self.api_request("GET", "/users/@me")
        if not me:
            log("Invalid Token.", "red")
            return
        log(f"Logged in as: {me.get('username')}", "green")
        print()

        cprint("[*] Server Setup", "yellow")
        src = input("  Source Server ID (Copy FROM): ").strip()
        tgt = input("  Target Server ID (Copy TO):   ").strip()
        if not src or not tgt:
            log("IDs are required.", "red")
            return

        cprint("[*] Fetching Source Data (This may take a moment)...", "cyan")
        src_roles = self.api_request("GET", f"/guilds/{src}/roles")
        src_channels = self.api_request("GET", f"/guilds/{src}/channels")
        src_emojis = self.api_request("GET", f"/guilds/{src}/emojis")

        if src_roles is None or src_channels is None:
            log("Failed to fetch Source Server data. Ensure you have access.", "red")
            return
        
        src_roles = [r for r in src_roles if r["name"] != "@everyone" and not r.get("managed")]
        src_emojis = [e for e in (src_emojis or []) if e.get("available")]
        
        log(f"Source Data Loaded: {len(src_roles)} Roles, {len(src_channels)} Channels, {len(src_emojis)} Emojis", "green")
        print()

        tgt_guild = self.api_request("GET", f"/guilds/{tgt}")
        if not tgt_guild:
            log("Cannot access Target Server.", "red")
            return
        log(f"Target Server: {tgt_guild.get('name')}", "green")
        print()

        cprint("[!] WARNING: This will DELETE ALL channels, roles, and emojis in the Target Server.", "red")
        confirm = input("  Type 'YES' to confirm: ").strip().upper()
        if confirm != "YES":
            log("Cancelled.", "red")
            return

        self.stats = {"success": 0, "failed": 0}
        self.wipe_target(tgt)
        print()
        
        self.stats = {"success": 0, "failed": 0}
        self.clone_roles(src_roles, tgt)
        self.clone_channels(src_channels, tgt)
        self.clone_emojis(src_emojis, tgt)
        self.fix_role_positions(src_roles, tgt)
        print()

        cprint("=" * 60, "cyan")
        cprint(f"  CLONE FINISHED: {self.stats['success']} Success, {self.stats['failed']} Failed", "green" if self.stats['failed'] == 0 else "yellow")
        cprint("=" * 60, "cyan")

    def wipe_target(self, tgt):
        log("Wiping Target Server...", "red")
        
        channels = self.api_request("GET", f"/guilds/{tgt}/channels")
        if channels:
            log(f"Deleting {len(channels)} channels...", "yellow")
            for c in channels:
                self.api_request("DELETE", f"/channels/{c['id']}", item=f"Channel: {c['name']}")
                time.sleep(0.8)
        
        roles = self.api_request("GET", f"/guilds/{tgt}/roles")
        if roles:
            log(f"Deleting {len(roles)} roles...", "yellow")
            for r in roles:
                if r["name"] == "@everyone" or r.get("managed"): continue
                self.api_request("DELETE", f"/guilds/{tgt}/roles/{r['id']}", item=f"Role: {r['name']}")
                time.sleep(0.8)
        
        emojis = self.api_request("GET", f"/guilds/{tgt}/emojis")
        if emojis:
            log(f"Deleting {len(emojis)} emojis...", "yellow")
            for e in emojis:
                self.api_request("DELETE", f"/guilds/{tgt}/emojis/{e['id']}", item=f"Emoji: {e['name']}")
                time.sleep(0.8)
        
        log("Wipe Complete.", "green")

    def clone_roles(self, src_roles, tgt):
        log(f"Cloning {len(src_roles)} roles...", "yellow")
        for r in sorted(src_roles, key=lambda x: x["position"]):
            payload = {
                "name": r["name"],
                "permissions": r["permissions"],
                "color": r["color"],
                "hoist": r["hoist"],
                "mentionable": r["mentionable"]
            }
            new_r = self.api_request("POST", f"/guilds/{tgt}/roles", payload=payload, item=f"Role: {r['name']}")
            if new_r:
                self.role_map[r["id"]] = new_r["id"]
                self.stats["success"] += 1
            else:
                self.stats["failed"] += 1
            time.sleep(1.0)

    def fix_role_positions(self, src_roles, tgt):
        if not self.role_map: return
        log("Fixing role hierarchy...", "yellow")
        positions = []
        for r in sorted(src_roles, key=lambda x: x["position"], reverse=True):
            if r["id"] in self.role_map:
                positions.append({"id": self.role_map[r["id"]], "position": r["position"]})
        
        if positions:
            self.api_request("PATCH", f"/guilds/{tgt}/roles", payload={"positions": positions}, item="Role Positions")
            time.sleep(1.0)

    def clone_channels(self, src_channels, tgt):
        log(f"Cloning {len(src_channels)} channels...", "yellow")
        cat_map = {}
        categories = [c for c in src_channels if c["type"] == 4]
        others = [c for c in src_channels if c["type"] != 4]
        
        for c in sorted(categories, key=lambda x: x.get("position", 0)):
            payload = {"name": c["name"], "type": 4}
            if c.get("permission_overwrites"):
                payload["permission_overwrites"] = self.remap_overwrites(c["permission_overwrites"])
            
            new_c = self.api_request("POST", f"/guilds/{tgt}/channels", payload=payload, item=f"Category: {c['name']}")
            if new_c:
                cat_map[c["id"]] = new_c["id"]
                self.stats["success"] += 1
            else:
                self.stats["failed"] += 1
            time.sleep(1.0)

        for c in sorted(others, key=lambda x: x.get("position", 0)):
            if c["type"] not in (0, 2, 5, 13, 15): continue
            
            payload = {
                "name": c["name"],
                "type": c["type"],
                "topic": c.get("topic") or "",
                "nsfw": c.get("nsfw", False),
                "rate_limit_per_user": c.get("rate_limit_per_user", 0),
                "position": c.get("position", 0),
                "default_auto_archive_duration": c.get("default_auto_archive_duration", 1440)
            }
            if c["type"] == 2:
                payload["bitrate"] = c.get("bitrate", 64000)
                payload["user_limit"] = c.get("user_limit", 0)
                payload["video_quality_mode"] = c.get("video_quality_mode", 1)
            if c.get("parent_id") and c["parent_id"] in cat_map:
                payload["parent_id"] = cat_map[c["parent_id"]]
            if c.get("permission_overwrites"):
                payload["permission_overwrites"] = self.remap_overwrites(c["permission_overwrites"])
            
            new_c = self.api_request("POST", f"/guilds/{tgt}/channels", payload=payload, item=f"Channel: {c['name']}")
            if new_c:
                self.stats["success"] += 1
            else:
                self.stats["failed"] += 1
            time.sleep(1.0)

    def clone_emojis(self, src_emojis, tgt):
        log(f"Cloning {len(src_emojis)} emojis...", "yellow")
        for e in src_emojis:
            img_url = f"https://cdn.discordapp.com/emojis/{e['id']}.{'gif' if e['animated'] else 'png'}"
            try:
                img_resp = requests.get(img_url, timeout=TIMEOUT)
                if img_resp.status_code == 200:
                    b64 = base64.b64encode(img_resp.content).decode()
                    mime = "image/gif" if e["animated"] else "image/png"
                    payload = {"name": e["name"], "image": f"data:{mime};base64,{b64}"}
                    new_e = self.api_request("POST", f"/guilds/{tgt}/emojis", payload=payload, item=f"Emoji: {e['name']}")
                    if new_e:
                        self.stats["success"] += 1
                    else:
                        self.stats["failed"] += 1
                else:
                    log(f"Failed to download emoji: {e['name']} (HTTP {img_resp.status_code})", "red")
                    self.stats["failed"] += 1
                time.sleep(1.2)
            except Exception as ex:
                log(f"Error downloading emoji {e['name']}: {ex}", "red")
                self.stats["failed"] += 1

    def remap_overwrites(self, overwrites):
        out = []
        for ow in overwrites:
            if ow["type"] == 0:
                if ow["id"] in self.role_map:
                    out.append({
                        "id": self.role_map[ow["id"]],
                        "type": 0,
                        "allow": ow["allow"],
                        "deny": ow["deny"]
                    })
        return out

    def api_request(self, method, endpoint, payload=None, item="Item"):
        url = f"{API}{endpoint}"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if method == "GET":
                    r = requests.get(url, headers=self.headers, timeout=TIMEOUT)
                elif method == "POST":
                    r = requests.post(url, headers=self.headers, json=payload, timeout=TIMEOUT)
                elif method == "DELETE":
                    r = requests.delete(url, headers=self.headers, timeout=TIMEOUT)
                elif method == "PATCH":
                    r = requests.patch(url, headers=self.headers, json=payload, timeout=TIMEOUT)

                if r.status_code == 429:
                    retry_after = r.json().get("retry_after", 5)
                    log(f"Rate Limited (Attempt {attempt}/{MAX_RETRIES}). Waiting {retry_after}s...", "yellow")
                    time.sleep(retry_after)
                    continue
                
                if r.status_code in (200, 201, 204):
                    if method in ("POST", "DELETE", "PATCH"):
                        prefix = "+" if method != "DELETE" else "-"
                        log(f"{prefix} {item}", "green" if method != "DELETE" else "red")
                    if "application/json" in r.headers.get("Content-Type", ""):
                        return r.json()
                    return {}
                
                try:
                    error_data = r.json()
                    error_msg = error_data.get("message", "Unknown Error")
                except:
                    error_msg = r.text[:100]
                
                log(f"Failed: {item} -> {r.status_code} ({error_msg})", "red")
                return None

            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES:
                    log(f"Network Error (Attempt {attempt}/{MAX_RETRIES}): {e}. Retrying...", "yellow")
                    time.sleep(2)
                else:
                    log(f"Network Error: {item} -> {e}", "red")
                    return None
        return None

if __name__ == "__main__":
    app = ZeroCopyCLI()
    app.start()