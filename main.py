"""Daily Hydrate main entry."""

import argparse
import logging
import sys
from pathlib import Path

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
    return parser.parse_args()


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
