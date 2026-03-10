"""
GUI模块 - 负责用户界面
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading
import os
import sys

class DailyHydrateGUI:
    def __init__(self, config_manager, reminder_manager):
        self.config = config_manager
        self.reminder = reminder_manager

        # 设置提醒回调
        self.reminder.on_remind_callback = self.on_remind
        self.reminder.on_notification_click = self.show_window
        self.reminder.on_sedentary_callback = self.on_sedentary_remind

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("每日喝水提醒")
        self.root.geometry("420x720")
        self.root.resizable(False, False)

        # 设置窗口图标
        self.icon_path = self._get_icon_path()
        try:
            self.root.iconbitmap(self.icon_path)
        except:
            pass

        # 设置样式
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # 系统托盘（可选）- 必须在 create_widgets 和 update_display 之前初始化
        self.tray_icon = None
        self.is_hidden = False

        self.create_widgets()
        self.update_display()

        self._setup_tray()

        # 启动提醒服务
        self.reminder.start()

        # 定时更新显示
        self.schedule_update()

    def _get_icon_path(self):
        """获取图标路径"""
        possible_paths = [
            "icon.ico",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico"),
        ]
        if hasattr(sys, '_MEIPASS'):
            possible_paths.insert(0, os.path.join(sys._MEIPASS, "icon.ico"))

        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def _setup_tray(self):
        """设置系统托盘（如果可用）"""
        try:
            import pystray
            from PIL import Image

            icon_image = None
            if self.icon_path and os.path.exists(self.icon_path):
                try:
                    icon_image = Image.open(self.icon_path)
                except:
                    pass

            if icon_image is None:
                icon_image = Image.new('RGBA', (64, 64), color=(0, 120, 215, 255))

            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", self.show_window, default=True),
                pystray.MenuItem("喝水 250ml", lambda: self._tray_add_water(250)),
                pystray.MenuItem("喝水 500ml", lambda: self._tray_add_water(500)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("重置久坐计时", self._tray_reset_sedentary),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self.quit_app)
            )

            self.tray_icon = pystray.Icon("DailyHydrate", icon_image, "每日喝水提醒", menu)
            tray_thread = threading.Thread(target=self._run_tray, daemon=True)
            tray_thread.start()

        except ImportError:
            print("pystray not installed, tray icon disabled")
        except Exception as e:
            print(f"Failed to setup tray: {e}")

    def _run_tray(self):
        if self.tray_icon:
            self.tray_icon.run()

    def _tray_add_water(self, amount):
        self.config.add_record(amount)
        self.reminder.reset_timer()
        self.root.after(0, self.update_display)

    def _tray_reset_sedentary(self):
        """从托盘重置久坐计时器"""
        self.reminder.reset_sedentary_timer()
        self.root.after(0, self.update_sedentary_countdown)

    def show_window(self):
        """显示窗口（从托盘或通知点击唤醒）"""
        def _show():
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.attributes("-topmost", True)
            self.root.after(100, lambda: self.root.attributes("-topmost", False))
            self.is_hidden = False
        self.root.after(0, _show)

    def hide_window(self):
        """隐藏窗口到托盘"""
        if self.tray_icon:
            self.root.withdraw()
            self.is_hidden = True
        else:
            # 没有托盘时，最小化窗口
            self.root.iconify()

    def quit_app(self):
        """退出应用"""
        self.reminder.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(
            main_frame,
            text="每日喝水提醒",
            font=("Microsoft YaHei UI", 18, "bold")
        )
        title_label.pack(pady=(0, 20))

        # 进度区域
        progress_frame = ttk.LabelFrame(main_frame, text="今日进度", padding="15")
        progress_frame.pack(fill=tk.X, pady=(0, 15))

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=300,
            mode='determinate'
        )
        self.progress_bar.pack(pady=(0, 10))

        # 进度文本
        self.progress_label = ttk.Label(
            progress_frame,
            text="0 / 2000 ml",
            font=("Microsoft YaHei UI", 14, "bold")
        )
        self.progress_label.pack()

        # 百分比标签
        self.percent_label = ttk.Label(
            progress_frame,
            text="0%",
            font=("Microsoft YaHei UI", 12)
        )
        self.percent_label.pack()

        # 倒计时标签
        self.countdown_label = ttk.Label(
            progress_frame,
            text="下次提醒: --:--",
            font=("Microsoft YaHei UI", 11)
        )
        self.countdown_label.pack(pady=(5, 0))

        # 久坐提醒倒计时标签
        self.sedentary_countdown_label = ttk.Label(
            progress_frame,
            text="久坐提醒: --:--",
            font=("Microsoft YaHei UI", 11)
        )
        self.sedentary_countdown_label.pack(pady=(5, 0))

        # 喝水按钮区域
        drink_frame = ttk.LabelFrame(main_frame, text="记录喝水", padding="15")
        drink_frame.pack(fill=tk.X, pady=(0, 15))

        # 快捷按钮
        button_frame = ttk.Frame(drink_frame)
        button_frame.pack(pady=(0, 10))

        ttk.Button(
            button_frame,
            text="一杯\n(250ml)",
            command=lambda: self.add_water(250),
            width=10
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="半杯\n(125ml)",
            command=lambda: self.add_water(125),
            width=10
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="大杯\n(500ml)",
            command=lambda: self.add_water(500),
            width=10
        ).pack(side=tk.LEFT, padx=5)

        # 自定义水量
        custom_frame = ttk.Frame(drink_frame)
        custom_frame.pack()

        ttk.Label(custom_frame, text="自定义:").pack(side=tk.LEFT, padx=(0, 5))

        self.custom_amount = ttk.Entry(custom_frame, width=8)
        self.custom_amount.pack(side=tk.LEFT, padx=5)
        self.custom_amount.insert(0, str(self.config.get_cup_size()))

        ttk.Label(custom_frame, text="ml").pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            custom_frame,
            text="添加",
            command=self.add_custom_water,
            width=6
        ).pack(side=tk.LEFT, padx=5)

        # 计划设置区域
        settings_frame = ttk.LabelFrame(main_frame, text="设置", padding="15")
        settings_frame.pack(fill=tk.X, pady=(0, 15))

        settings_frame.columnconfigure(0, minsize=80)
        settings_frame.columnconfigure(1, minsize=100)
        settings_frame.columnconfigure(2, minsize=50)
        settings_frame.columnconfigure(3, weight=1)

        # 每日目标
        ttk.Label(settings_frame, text="每日目标:").grid(row=0, column=0, sticky="e", pady=5)
        self.goal_entry = ttk.Entry(settings_frame, width=10)
        self.goal_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.goal_entry.insert(0, str(self.config.get_daily_goal()))
        ttk.Label(settings_frame, text="ml").grid(row=0, column=2, sticky="w", pady=5)
        ttk.Button(settings_frame, text="保存", command=self.save_goal, width=6).grid(row=0, column=3, sticky="e", pady=5)

        # 提醒间隔
        ttk.Label(settings_frame, text="提醒间隔:").grid(row=1, column=0, sticky="e", pady=5)
        self.interval_entry = ttk.Entry(settings_frame, width=10)
        self.interval_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.interval_entry.insert(0, str(self.config.get_remind_interval()))
        ttk.Label(settings_frame, text="分钟").grid(row=1, column=2, sticky="w", pady=5)
        ttk.Button(settings_frame, text="保存", command=self.save_interval, width=6).grid(row=1, column=3, sticky="e", pady=5)

        # 提醒开关
        self.remind_var = tk.BooleanVar(value=self.config.is_remind_enabled())
        ttk.Checkbutton(
            settings_frame,
            text="开启提醒",
            variable=self.remind_var,
            command=self.toggle_remind
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

        self.sound_var = tk.BooleanVar(value=self.config.is_sound_enabled())
        ttk.Checkbutton(
            settings_frame,
            text="声音",
            variable=self.sound_var,
            command=self.toggle_sound
        ).grid(row=2, column=2, columnspan=2, sticky="w", pady=5)

        # 久坐提醒设置
        ttk.Label(settings_frame, text="久坐提醒:").grid(row=3, column=0, sticky="e", pady=5)
        self.sedentary_entry = ttk.Entry(settings_frame, width=10)
        self.sedentary_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.sedentary_entry.insert(0, str(self.config.get_sedentary_interval()))
        ttk.Label(settings_frame, text="分钟").grid(row=3, column=2, sticky="w", pady=5)
        ttk.Button(settings_frame, text="保存", command=self.save_sedentary_interval, width=6).grid(row=3, column=3, sticky="e", pady=5)

        # 久坐提醒开关
        self.sedentary_var = tk.BooleanVar(value=self.config.is_sedentary_enabled())
        ttk.Checkbutton(
            settings_frame,
            text="开启久坐提醒",
            variable=self.sedentary_var,
            command=self.toggle_sedentary
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=5)

        # 底部按钮
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            bottom_frame,
            text="清空记录",
            command=self.clear_records
        ).pack(side=tk.LEFT)

        ttk.Button(
            bottom_frame,
            text="测试提醒",
            command=self.test_remind
        ).pack(side=tk.RIGHT)

    def add_water(self, amount):
        self.config.add_record(amount)
        self.update_display()
        self.reminder.reset_timer()

        total = self.config.get_today_total()
        goal = self.config.get_daily_goal()
        if total >= goal:
            messagebox.showinfo("恭喜!", f"目标已达成!\n当前: {total}ml / {goal}ml")

    def add_custom_water(self):
        try:
            amount = int(self.custom_amount.get())
            if amount <= 0:
                raise ValueError("水量必须大于0")
            if amount > 5000:
                raise ValueError("水量不能超过5000ml")
            self.config.set_cup_size(amount)
            self.add_water(amount)
        except ValueError as e:
            messagebox.showerror("错误", f"无效的数量\n{str(e)}")

    def save_goal(self):
        try:
            goal = int(self.goal_entry.get())
            if goal < 500:
                raise ValueError("每日目标不能少于500ml")
            if goal > 10000:
                raise ValueError("每日目标不能超过10000ml")
            self.config.set_daily_goal(goal)
            self.update_display()
            messagebox.showinfo("成功", f"每日目标已设置为 {goal}ml")
        except ValueError as e:
            messagebox.showerror("错误", f"无效的数值\n{str(e)}")

    def save_interval(self):
        try:
            interval = int(self.interval_entry.get())
            if interval < 0:
                raise ValueError("提醒间隔不能小于0分钟")
            if interval > 180:
                raise ValueError("提醒间隔不能超过180分钟")
            self.config.set_remind_interval(interval)
            messagebox.showinfo("成功", f"提醒间隔已设置为 {interval} 分钟")
        except ValueError as e:
            messagebox.showerror("错误", f"无效的数值\n{str(e)}")

    def toggle_remind(self):
        self.config.set_remind_enabled(self.remind_var.get())

    def toggle_sound(self):
        self.config.set_sound_enabled(self.sound_var.get())

    def save_sedentary_interval(self):
        try:
            interval = int(self.sedentary_entry.get())
            if interval < 5:
                raise ValueError("久坐提醒间隔不能少于5分钟")
            if interval > 180:
                raise ValueError("久坐提醒间隔不能超过180分钟")
            self.config.set_sedentary_interval(interval)
            messagebox.showinfo("成功", f"久坐提醒间隔已设置为 {interval} 分钟")
        except ValueError as e:
            messagebox.showerror("错误", f"无效的数值\n{str(e)}")

    def toggle_sedentary(self):
        self.config.set_sedentary_enabled(self.sedentary_var.get())

    def clear_records(self):
        if messagebox.askyesno("确认", "确定清空今日所有记录?"):
            self.config.clear_today_records()
            self.update_display()

    def test_remind(self):
        self.on_remind()

    def update_display(self):
        total = self.config.get_today_total()
        goal = self.config.get_daily_goal()

        percent = min(100, (total / goal) * 100) if goal > 0 else 0
        self.progress_var.set(percent)
        self.progress_label.config(text=f"{total} / {goal} ml")
        self.percent_label.config(text=f"{percent:.1f}%")

        if percent >= 100:
            self.percent_label.config(foreground="green")
        elif percent >= 50:
            self.percent_label.config(foreground="orange")
        else:
            self.percent_label.config(foreground="black")

        self._update_tray_tooltip(total, goal)

    def _update_tray_tooltip(self, total, goal):
        if self.tray_icon:
            percent = min(100, (total / goal) * 100) if goal > 0 else 0
            self.tray_icon.title = f"每日喝水: {total}/{goal}ml ({percent:.0f}%)"

    def on_remind(self):
        total = self.config.get_today_total()
        goal = self.config.get_daily_goal()
        remaining = max(0, goal - total)

        if remaining > 0:
            message = (
                f"该喝水了!\n\n"
                f"今日已喝: {total}ml\n"
                f"还需: {remaining}ml\n\n"
                f"保持健康!"
            )
        else:
            message = (
                f"太棒了!\n\n"
                f"今日已喝: {total}ml\n"
                f"目标已达成!\n\n"
                f"继续保持!"
            )

        self.reminder.send_notification("喝水提醒", message)
        self.root.after(0, self.update_display)

    def on_sedentary_remind(self):
        """久坐提醒回调"""
        self.reminder.send_sedentary_notification()
        self.root.after(0, self.update_sedentary_countdown)

    def schedule_update(self):
        self.update_display()
        self.update_countdown()
        self.update_sedentary_countdown()
        self.root.after(60000, self.schedule_update)

    def update_countdown(self):
        remaining = self.reminder.get_remaining_time_str()

        if remaining == "--:--":
            self.countdown_label.config(text="提醒已关闭", foreground="gray")
        else:
            self.countdown_label.config(text=f"下次提醒: {remaining}", foreground="blue")

        self.root.after(1000, self.update_countdown)

    def update_sedentary_countdown(self):
        """更新久坐提醒倒计时"""
        remaining = self.reminder.get_sedentary_remaining_time_str()

        if remaining == "--:--":
            self.sedentary_countdown_label.config(text="久坐提醒已关闭", foreground="gray")
        else:
            self.sedentary_countdown_label.config(text=f"久坐提醒: {remaining}", foreground="orange")

        self.root.after(1000, self.update_sedentary_countdown)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()
