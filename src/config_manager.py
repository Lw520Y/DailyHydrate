"""
配置管理模块 - 负责加载和保存用户配置
"""
import json
import os
import threading
import tempfile
from datetime import datetime, timedelta


class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self._lock = threading.RLock()
        self.config = self.load_config()

    def load_config(self):
        """加载配置文件"""
        default_config = {
            "daily_goal": 2000,
            "cup_size": 250,
            "remind_interval": 30,
            "remind_enabled": True,
            "sound_enabled": True,
            "records": [],
            "last_date": None,
            "history": {},
            "sedentary_interval": 45,
            "sedentary_enabled": True,
            "start_minimized": False,
            "quiet_hours_enabled": False,
            "quiet_start": "23:00",
            "quiet_end": "07:00",
            "snooze_until": None,
        }

        with self._lock:
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        loaded_config = json.load(f)

                    # 合并缺失字段，保持向后兼容
                    for key, value in default_config.items():
                        loaded_config.setdefault(key, value)
                    self._migrate_history(loaded_config)
                    return loaded_config
                except (json.JSONDecodeError, IOError):
                    return default_config

            return default_config

    def _migrate_history(self, cfg):
        """迁移并清理历史数据，兼容旧版本配置。"""
        history = cfg.get("history")
        if not isinstance(history, dict):
            history = {}

        # 旧版本只有 records/last_date：将当日汇总写入 history。
        last_date = cfg.get("last_date")
        if last_date and isinstance(cfg.get("records"), list):
            total = sum(record.get("amount", 0) for record in cfg.get("records", []))
            if total > 0 and last_date not in history:
                history[last_date] = total

        # 仅保留最近 90 天，避免配置无限增长。
        cleaned = {}
        for i in range(90):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            cleaned[day] = int(history.get(day, 0))

        cfg["history"] = cleaned

    def save_config(self):
        """保存配置文件"""
        with self._lock:
            try:
                config_dir = os.path.dirname(os.path.abspath(self.config_file)) or "."
                fd, temp_path = tempfile.mkstemp(prefix=".config.", suffix=".tmp", dir=config_dir)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, ensure_ascii=False, indent=4)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp_path, self.config_file)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                return True
            except IOError:
                return False

    def get_daily_goal(self):
        with self._lock:
            return self.config.get("daily_goal", 2000)

    def set_daily_goal(self, goal):
        with self._lock:
            self.config["daily_goal"] = goal
            self.save_config()

    def get_cup_size(self):
        with self._lock:
            return self.config.get("cup_size", 250)

    def set_cup_size(self, size):
        with self._lock:
            self.config["cup_size"] = size
            self.save_config()

    def get_remind_interval(self):
        with self._lock:
            return self.config.get("remind_interval", 30)

    def set_remind_interval(self, interval):
        with self._lock:
            self.config["remind_interval"] = interval
            self.save_config()

    def is_remind_enabled(self):
        with self._lock:
            return self.config.get("remind_enabled", True)

    def set_remind_enabled(self, enabled):
        with self._lock:
            self.config["remind_enabled"] = enabled
            self.save_config()

    def is_sound_enabled(self):
        with self._lock:
            return self.config.get("sound_enabled", True)

    def set_sound_enabled(self, enabled):
        with self._lock:
            self.config["sound_enabled"] = enabled
            self.save_config()

    def get_records(self):
        with self._lock:
            return list(self.config.get("records", []))

    def add_record(self, amount):
        """添加喝水记录"""
        with self._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.now().strftime("%H:%M:%S")

            # 跨天时自动清空旧记录
            if self.config.get("last_date") != today:
                self.config["records"] = []
                self.config["last_date"] = today

            self.config["records"].append({"time": current_time, "amount": amount})
            self.config.setdefault("history", {})
            self.config["history"][today] = int(self.config["history"].get(today, 0)) + int(amount)
            self.save_config()

    def get_today_total(self):
        """获取今日总喝水量"""
        with self._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            if self.config.get("last_date") != today:
                return 0

            return sum(record.get("amount", 0) for record in self.config.get("records", []))

    def clear_today_records(self):
        """清空今日记录"""
        with self._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            self.config["records"] = []
            self.config["last_date"] = today
            self.config.setdefault("history", {})
            self.config["history"][today] = 0
            self.save_config()

    # 久坐提醒相关方法
    def get_sedentary_interval(self):
        """获取久坐提醒间隔（分钟）"""
        with self._lock:
            return self.config.get("sedentary_interval", 45)

    def set_sedentary_interval(self, interval):
        """设置久坐提醒间隔（分钟）"""
        with self._lock:
            self.config["sedentary_interval"] = interval
            self.save_config()

    def is_sedentary_enabled(self):
        """是否启用久坐提醒"""
        with self._lock:
            return self.config.get("sedentary_enabled", True)

    def set_sedentary_enabled(self, enabled):
        """设置久坐提醒开关"""
        with self._lock:
            self.config["sedentary_enabled"] = enabled
            self.save_config()

    def is_start_minimized(self):
        """是否启动时最小化到托盘"""
        with self._lock:
            return self.config.get("start_minimized", False)

    def set_start_minimized(self, enabled):
        """设置启动时最小化开关"""
        with self._lock:
            self.config["start_minimized"] = enabled
            self.save_config()

    def is_quiet_hours_enabled(self):
        with self._lock:
            return self.config.get("quiet_hours_enabled", False)

    def set_quiet_hours_enabled(self, enabled):
        with self._lock:
            self.config["quiet_hours_enabled"] = enabled
            self.save_config()

    def get_quiet_start(self):
        with self._lock:
            return self.config.get("quiet_start", "23:00")

    def set_quiet_start(self, time_str):
        with self._lock:
            self.config["quiet_start"] = time_str
            self.save_config()

    def get_quiet_end(self):
        with self._lock:
            return self.config.get("quiet_end", "07:00")

    def set_quiet_end(self, time_str):
        with self._lock:
            self.config["quiet_end"] = time_str
            self.save_config()

    def get_recent_history(self, days=7):
        """返回最近 N 天饮水总量（含今天）。"""
        with self._lock:
            history = self.config.get("history", {})
            result = []
            for i in range(days - 1, -1, -1):
                day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                result.append({"date": day, "total": int(history.get(day, 0))})
            return result

    def get_snooze_until(self):
        with self._lock:
            value = self.config.get("snooze_until")
            return float(value) if value else None

    def set_snooze_until(self, timestamp):
        with self._lock:
            self.config["snooze_until"] = float(timestamp) if timestamp else None
            self.save_config()
