#!/usr/bin/env python3
"""
MCP Auto-Configuration for WC Optimizer
========================================
Automatically configures Claude Desktop and Cursor IDE to connect to the
WC Optimizer MCP server running inside Docker.

Usage:
    python scripts/setup_mcp.py              # Install MCP config
    python scripts/setup_mcp.py --uninstall  # Remove MCP config
    python scripts/setup_mcp.py --check      # Check current status
    python scripts/setup_mcp.py --help       # Show help

Works on Windows, macOS, and Linux. No pip dependencies required.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

MCP_SERVER_NAME = "wc-optimizer"
CONTAINER_NAME = "wc-optimizer-mcp-sse-1"

MCP_CONFIG = {
    "command": "docker",
    "args": [
        "exec",
        "-i",
        CONTAINER_NAME,
        "python3",
        "/app/mcp_servers/stdio_server.py"
    ]
}

# ─── Utilities ────────────────────────────────────────────────────────────────

class Colors:
    """ANSI color codes (disabled on Windows cmd without ANSI support)."""
    if sys.platform == "win32":
        # Enable ANSI on Windows 10+
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            BOLD = "\033[1m"
            GREEN = "\033[92m"
            YELLOW = "\033[93m"
            RED = "\033[91m"
            CYAN = "\033[96m"
            RESET = "\033[0m"
        except Exception:
            BOLD = GREEN = YELLOW = RED = CYAN = RESET = ""
    else:
        BOLD = "\033[1m"
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        RED = "\033[91m"
        CYAN = "\033[96m"
        RESET = "\033[0m"


def ok(msg):
    print(f"  {Colors.GREEN}✅ {msg}{Colors.RESET}")

def warn(msg):
    print(f"  {Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def fail(msg):
    print(f"  {Colors.RED}❌ {msg}{Colors.RESET}")

def info(msg):
    print(f"  {Colors.CYAN}ℹ️  {msg}{Colors.RESET}")

def header(msg):
    print(f"\n{Colors.BOLD}{msg}{Colors.RESET}")


# ─── Config Path Detection ───────────────────────────────────────────────────

def get_claude_config_path() -> Path | None:
    """Return the Claude Desktop config file path for the current OS."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        # Some Linux users use Claude Desktop via unofficial builds
        xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg) / "Claude" / "claude_desktop_config.json"
    return None


def get_cursor_config_path() -> Path | None:
    """Return the Cursor IDE MCP config file path for the current OS."""
    system = platform.system()
    if system == "Windows":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            return Path(userprofile) / ".cursor" / "mcp.json"
    elif system in ("Darwin", "Linux"):
        return Path.home() / ".cursor" / "mcp.json"
    return None


# ─── Docker Check ────────────────────────────────────────────────────────────

def check_docker() -> dict:
    """Check if Docker is available and the MCP container is running."""
    result = {"docker_available": False, "container_running": False}

    # Check docker CLI
    try:
        subprocess.run(
            ["docker", "--version"],
            capture_output=True, timeout=10
        )
        result["docker_available"] = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return result

    # Check container
    try:
        proc = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER_NAME],
            capture_output=True, text=True, timeout=10
        )
        result["container_running"] = proc.stdout.strip().lower() == "true"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return result


# ─── Config Read/Write ───────────────────────────────────────────────────────

def read_config(path: Path) -> dict:
    """Read a JSON config file, returning empty dict if missing or invalid."""
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)
    except (json.JSONDecodeError, OSError) as e:
        warn(f"Could not parse {path}: {e}")
        return {}


def write_config(path: Path, data: dict) -> bool:
    """Write JSON config to a file, creating parent dirs as needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2) + "\n",
            encoding="utf-8"
        )
        return True
    except OSError as e:
        fail(f"Could not write {path}: {e}")
        return False


def backup_config(path: Path) -> Path | None:
    """Create a timestamped backup of a config file."""
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(f".{ts}.bak")
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError as e:
        warn(f"Could not create backup: {e}")
        return None


# ─── Install / Uninstall Logic ───────────────────────────────────────────────

def is_configured(config: dict) -> bool:
    """Check if the wc-optimizer MCP server is already configured."""
    return MCP_SERVER_NAME in config.get("mcpServers", {})


def install_config(path: Path, client_name: str) -> bool:
    """Install the MCP config entry into a config file."""
    config = read_config(path)

    if is_configured(config):
        ok(f"{client_name}: Already configured — no changes needed")
        return True

    # Backup existing file
    if path.exists():
        bak = backup_config(path)
        if bak:
            info(f"Backup saved: {bak.name}")

    # Merge: add our server entry, keep everything else
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"][MCP_SERVER_NAME] = MCP_CONFIG

    if write_config(path, config):
        ok(f"{client_name}: Configured successfully")
        info(f"Config file: {path}")
        return True
    return False


def uninstall_config(path: Path, client_name: str) -> bool:
    """Remove the MCP config entry from a config file."""
    config = read_config(path)

    if not is_configured(config):
        info(f"{client_name}: Not configured — nothing to remove")
        return True

    # Backup before removal
    bak = backup_config(path)
    if bak:
        info(f"Backup saved: {bak.name}")

    del config["mcpServers"][MCP_SERVER_NAME]

    # Clean up empty mcpServers key
    if not config["mcpServers"]:
        del config["mcpServers"]

    if write_config(path, config):
        ok(f"{client_name}: Configuration removed")
        return True
    return False


# ─── Main Commands ───────────────────────────────────────────────────────────

def cmd_install():
    """Install MCP config into Claude Desktop and Cursor IDE."""
    header("🔧 WC Optimizer — MCP Auto-Configuration")
    print(f"  Platform: {platform.system()} {platform.release()}")
    print()

    # Docker check
    header("Step 1: Checking Docker...")
    docker = check_docker()

    if not docker["docker_available"]:
        fail("Docker is not installed or not in PATH")
        print(f"\n  Please install Docker Desktop from: https://www.docker.com/products/docker-desktop")
        sys.exit(1)
    else:
        ok("Docker CLI found")

    if not docker["container_running"]:
        warn(f"Container '{CONTAINER_NAME}' is not running")
        info("Run 'docker compose up -d' first, or the config will be installed for when you start it later")
        print()
    else:
        ok(f"Container '{CONTAINER_NAME}' is running")

    # Configure clients
    header("Step 2: Configuring AI Clients...")
    print()

    success_count = 0
    skip_count = 0

    # Claude Desktop
    claude_path = get_claude_config_path()
    if claude_path:
        print(f"  {Colors.BOLD}Claude Desktop:{Colors.RESET}")
        if install_config(claude_path, "Claude Desktop"):
            success_count += 1
        print()
    else:
        warn("Could not determine Claude Desktop config path for this OS")
        skip_count += 1
        print()

    # Cursor IDE
    cursor_path = get_cursor_config_path()
    if cursor_path:
        print(f"  {Colors.BOLD}Cursor IDE:{Colors.RESET}")
        if install_config(cursor_path, "Cursor IDE"):
            success_count += 1
        print()
    else:
        warn("Could not determine Cursor IDE config path for this OS")
        skip_count += 1
        print()

    # Summary
    header("Step 3: Post-Setup")
    print()
    if success_count > 0:
        ok("Configuration complete!")
        print()
        info("Next steps:")
        print("    1. If Claude Desktop is open → Fully quit it (Cmd+Q / Alt+F4) → Reopen")
        print("    2. If Cursor IDE is open → Restart it")
        print("    3. Make sure Docker containers are running: docker compose up -d")
        print("    4. Start asking questions about your supply chain data!")
    else:
        warn("No clients were configured. Install Claude Desktop or Cursor IDE first.")

    print()


def cmd_uninstall():
    """Remove MCP config from Claude Desktop and Cursor IDE."""
    header("🧹 WC Optimizer — Remove MCP Configuration")
    print()

    claude_path = get_claude_config_path()
    if claude_path and claude_path.exists():
        print(f"  {Colors.BOLD}Claude Desktop:{Colors.RESET}")
        uninstall_config(claude_path, "Claude Desktop")
        print()

    cursor_path = get_cursor_config_path()
    if cursor_path and cursor_path.exists():
        print(f"  {Colors.BOLD}Cursor IDE:{Colors.RESET}")
        uninstall_config(cursor_path, "Cursor IDE")
        print()

    ok("Done. Restart Claude Desktop / Cursor IDE to apply changes.")
    print()


def cmd_check():
    """Check current configuration status."""
    header("🔍 WC Optimizer — Configuration Status")
    print()

    # Docker
    docker = check_docker()
    print(f"  {Colors.BOLD}Docker:{Colors.RESET}")
    if docker["docker_available"]:
        ok("Docker CLI available")
    else:
        fail("Docker CLI not found")
    if docker["container_running"]:
        ok(f"Container '{CONTAINER_NAME}' is running")
    else:
        warn(f"Container '{CONTAINER_NAME}' is not running")
    print()

    # Claude Desktop
    claude_path = get_claude_config_path()
    print(f"  {Colors.BOLD}Claude Desktop:{Colors.RESET}")
    if claude_path:
        info(f"Config path: {claude_path}")
        if claude_path.exists():
            config = read_config(claude_path)
            if is_configured(config):
                ok("wc-optimizer MCP server is configured")
            else:
                warn("Config file exists but wc-optimizer is not configured")
        else:
            info("Config file does not exist yet")
    else:
        warn("Config path not detected for this OS")
    print()

    # Cursor IDE
    cursor_path = get_cursor_config_path()
    print(f"  {Colors.BOLD}Cursor IDE:{Colors.RESET}")
    if cursor_path:
        info(f"Config path: {cursor_path}")
        if cursor_path.exists():
            config = read_config(cursor_path)
            if is_configured(config):
                ok("wc-optimizer MCP server is configured")
            else:
                warn("Config file exists but wc-optimizer is not configured")
        else:
            info("Config file does not exist yet")
    else:
        warn("Config path not detected for this OS")
    print()


def cmd_help():
    """Print usage help."""
    print(__doc__)
    print("Commands:")
    print("  (no args)     Install MCP config into Claude Desktop & Cursor IDE")
    print("  --uninstall   Remove MCP config from Claude Desktop & Cursor IDE")
    print("  --check       Check current configuration status")
    print("  --help        Show this help message")
    print()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        cmd_help()
    elif "--uninstall" in args:
        cmd_uninstall()
    elif "--check" in args:
        cmd_check()
    else:
        cmd_install()


if __name__ == "__main__":
    main()
