"""
每日喝水提醒 - 主程序入口
Daily Hydrate - Main Entry Point

功能：
1. 自定义每日喝水量目标
2. 添加喝水计划（自定义杯容量）
3. Windows系统弹窗提醒

作者：DailyHydrate
版本：1.0.0
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from src.config_manager import ConfigManager
from src.reminder import ReminderManager
from src.gui import DailyHydrateGUI

def check_dependencies():
    """检查依赖是否安装"""
    missing_deps = []

    try:
        import winotify
    except ImportError:
        missing_deps.append("winotify")

    if missing_deps:
        print("=" * 50)
        print("缺少必要的依赖库！")
        print("=" * 50)
        print("\n请运行以下命令安装依赖：")
        print("pip install -r requirements.txt")
        print("\n或者单独安装：")
        for dep in missing_deps:
            print(f"pip install {dep}")
        print("\n提示：如果不安装winotify，程序将使用tkinter弹窗作为备选方案。")
        print("=" * 50)
        print()

def main():
    """主函数"""
    print("=" * 50)
    print("💧 每日喝水提醒 - Daily Hydrate")
    print("=" * 50)
    print()

    # 检查依赖（不强制要求）
    check_dependencies()

    # 获取配置文件路径
    if getattr(sys, 'frozen', False):
        # 打包后的exe运行环境
        config_path = os.path.join(os.path.dirname(sys.executable), "config.json")
    else:
        # 开发环境
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

    # 初始化管理器
    config_manager = ConfigManager(config_path)
    reminder_manager = ReminderManager(config_manager)

    # 启动GUI
    try:
        app = DailyHydrateGUI(config_manager, reminder_manager)
        app.run()
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        # 仅在有控制台时等待用户输入
        if sys.stdin is not None:
            input("按回车键退出...")

if __name__ == "__main__":
    main()
