"""
配置管理模块 - 负责加载和保存用户配置
"""
import json
import os
from datetime import datetime

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
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
            "sedentary_interval": 45,
            "sedentary_enabled": True
        }

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和加载的配置
                    for key in default_config:
                        if key not in loaded_config:
                            loaded_config[key] = default_config[key]
                    return loaded_config
            except (json.JSONDecodeError, IOError):
                return default_config

        return default_config

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except IOError:
            return False

    def get_daily_goal(self):
        return self.config.get("daily_goal", 2000)

    def set_daily_goal(self, goal):
        self.config["daily_goal"] = goal
        self.save_config()

    def get_cup_size(self):
        return self.config.get("cup_size", 250)

    def set_cup_size(self, size):
        self.config["cup_size"] = size
        self.save_config()

    def get_remind_interval(self):
        return self.config.get("remind_interval", 30)

    def set_remind_interval(self, interval):
        self.config["remind_interval"] = interval
        self.save_config()

    def is_remind_enabled(self):
        return self.config.get("remind_enabled", True)

    def set_remind_enabled(self, enabled):
        self.config["remind_enabled"] = enabled
        self.save_config()

    def is_sound_enabled(self):
        return self.config.get("sound_enabled", True)

    def set_sound_enabled(self, enabled):
        self.config["sound_enabled"] = enabled
        self.save_config()

    def get_records(self):
        return self.config.get("records", [])

    def add_record(self, amount):
        """添加喝水记录"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        # 检查是否是新的一天，如果是则清空记录
        if self.config.get("last_date") != today:
            self.config["records"] = []
            self.config["last_date"] = today

        record = {
            "time": current_time,
            "amount": amount
        }
        self.config["records"].append(record)
        self.save_config()

    def get_today_total(self):
        """获取今日总喝水量"""
        today = datetime.now().strftime("%Y-%m-%d")

        # 如果是新的一天，返回0
        if self.config.get("last_date") != today:
            return 0

        total = 0
        for record in self.config.get("records", []):
            total += record.get("amount", 0)
        return total

    def clear_today_records(self):
        """清空今日记录"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.config["records"] = []
        self.config["last_date"] = today
        self.save_config()

    # 久坐提醒相关方法
    def get_sedentary_interval(self):
        """获取久坐提醒间隔（分钟）"""
        return self.config.get("sedentary_interval", 45)

    def set_sedentary_interval(self, interval):
        """设置久坐提醒间隔（分钟）"""
        self.config["sedentary_interval"] = interval
        self.save_config()

    def is_sedentary_enabled(self):
        """是否启用久坐提醒"""
        return self.config.get("sedentary_enabled", True)

    def set_sedentary_enabled(self, enabled):
        """设置久坐提醒开关"""
        self.config["sedentary_enabled"] = enabled
        self.save_config()
