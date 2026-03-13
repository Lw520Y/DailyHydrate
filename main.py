"""Daily Hydrate main entry."""

import argparse
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

# Keep import path stable for both source run and bundled run.
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from src.config_manager import ConfigManager
from src.reminder import ReminderManager
from src.gui import DailyHydrateGUI


def resolve_runtime_dir() -> Path:
    """Return writable runtime directory for config/log files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_DIR


def setup_logging(runtime_dir: Path) -> logging.Logger:
    """Configure app logging to file and console."""
    log_file = runtime_dir / "dailyhydrate.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger("dailyhydrate")
    logger.info("Log initialized: %s", log_file)
    return logger


def parse_args():
    parser = argparse.ArgumentParser(description="Daily Hydrate")
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start minimized to tray for this launch.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Force show main window on startup for this launch.",
    )
    parser.add_argument(
        "--action-url",
        type=str,
        help="Handle deep-link action (internal use).",
    )
    return parser.parse_args()


def ensure_url_protocol(logger: logging.Logger):
    """Register dailyhydrate:// protocol under HKCU for toast action callbacks."""
    if sys.platform != "win32":
        return
    try:
        import winreg
    except Exception:
        return

    protocol = "dailyhydrate"
    root = winreg.HKEY_CURRENT_USER
    base = fr"Software\Classes\{protocol}"
    command_key = fr"{base}\shell\open\command"

    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}" --action-url "%1"'
    else:
        cmd = f'"{sys.executable}" "{Path(__file__).resolve()}" --action-url "%1"'

    try:
        key = winreg.CreateKey(root, base)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:DailyHydrate Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)

        key_cmd = winreg.CreateKey(root, command_key)
        winreg.SetValueEx(key_cmd, "", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key_cmd)
        logger.info("Registered URL protocol: %s://", protocol)
    except Exception:
        logger.exception("Failed to register URL protocol")


def handle_action_url(action_url: str, config: ConfigManager, logger: logging.Logger):
    """Handle deep-link actions and exit."""
    try:
        parsed = urlparse(action_url)
        host = (parsed.netloc or "").lower()
        path_parts = [p for p in parsed.path.split("/") if p]

        # dailyhydrate://drink/250
        if host == "drink" and path_parts:
            amount = int(path_parts[0])
            if amount > 0:
                config.add_record(amount)
                config.set_snooze_until(None)
                logger.info("Action handled: drink %s ml", amount)
                return True

        # dailyhydrate://snooze/10
        if host == "snooze" and path_parts:
            minutes = int(path_parts[0])
            if minutes > 0:
                config.set_snooze_until(time.time() + minutes * 60)
                logger.info("Action handled: snooze %s min", minutes)
                return True

        logger.warning("Unsupported action url: %s", action_url)
        return False
    except Exception:
        logger.exception("Failed to handle action url: %s", action_url)
        return False


def check_dependencies(logger: logging.Logger):
    """Non-blocking dependency check for optional backends."""
    missing = []
    try:
        import winotify  # noqa: F401
    except ImportError:
        missing.append("winotify")

    try:
        import pystray  # noqa: F401
    except ImportError:
        missing.append("pystray")

    if missing:
        logger.warning("Optional dependencies missing: %s", ", ".join(missing))
        logger.warning("Install with: pip install -r requirements.txt")


def main():
    args = parse_args()
    runtime_dir = resolve_runtime_dir()
    logger = setup_logging(runtime_dir)

    logger.info("Daily Hydrate starting")
    check_dependencies(logger)

    config_path = runtime_dir / "config.json"
    logger.info("Using config: %s", config_path)

    config_manager = ConfigManager(str(config_path))

    ensure_url_protocol(logger)
    if args.action_url:
        handle_action_url(args.action_url, config_manager, logger)
        return

    reminder_manager = ReminderManager(config_manager)

    # Startup mode priority: CLI override > config default
    start_minimized = config_manager.is_start_minimized()
    if args.minimized:
        start_minimized = True
    if args.show:
        start_minimized = False

    try:
        app = DailyHydrateGUI(config_manager, reminder_manager)
        app.run(start_minimized=start_minimized)
    except Exception:
        logger.exception("Application crashed")
        if sys.stdin is not None and not getattr(sys, "frozen", False):
            input("Press Enter to exit...")


if __name__ == "__main__":
    main()
