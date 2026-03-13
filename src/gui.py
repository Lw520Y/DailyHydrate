"""
GUI 模块 - 负责用户界面
"""
import os
import sys
import threading
import logging
import tkinter as tk
from tkinter import ttk, messagebox


logger = logging.getLogger(__name__)


class DailyHydrateGUI:
    def __init__(self, config_manager, reminder_manager):
        self.config = config_manager
        self.reminder = reminder_manager

        self.tray_icon = None
        self.is_hidden = False
        self.is_closing = False

        # 定时器句柄，便于退出时取消
        self.display_after_id = None
        self.countdown_after_id = None
        self.sedentary_after_id = None

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("每日喝水提醒")
        self.root.geometry("460x760")
        self.root.resizable(True, True)
        self.root.minsize(420, 640)

        # 通知回调与 UI 主线程调度
        self.reminder.on_remind_callback = self.on_remind
        self.reminder.on_notification_click = self.show_window
        self.reminder.on_sedentary_callback = self.on_sedentary_remind
        self.reminder.ui_dispatch = lambda fn: self.root.after(0, fn)

        # 设置窗口图标
        self.icon_path = self._get_icon_path()
        try:
            if self.icon_path:
                self.root.iconbitmap(self.icon_path)
        except Exception:
            pass

        # 样式
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # 可滚动内容容器，避免内容增多后显示不全
        self._setup_scrollable_container()
        self.create_widgets()
        self.update_display()

        self._setup_tray()

        # 启动提醒服务
        self.reminder.start()

        # 启动周期更新（避免重复调度）
        self.schedule_update()
        self.update_countdown()
        self.update_sedentary_countdown()

    def _setup_scrollable_container(self):
        wrapper = ttk.Frame(self.root)
        wrapper.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(wrapper, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(wrapper, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")

        self.content_frame.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_content_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if self.root.winfo_exists():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _get_icon_path(self):
        """获取图标路径"""
        possible_paths = [
            "icon.ico",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico"),
        ]
        if hasattr(sys, "_MEIPASS"):
            possible_paths.insert(0, os.path.join(sys._MEIPASS, "icon.ico"))

        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def _setup_tray(self):
        """设置系统托盘（可选）"""
        try:
            import pystray
            from PIL import Image

            icon_image = None
            if self.icon_path and os.path.exists(self.icon_path):
                try:
                    icon_image = Image.open(self.icon_path)
                except Exception:
                    pass

            if icon_image is None:
                icon_image = Image.new("RGBA", (64, 64), color=(0, 120, 215, 255))

            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", self.show_window, default=True),
                pystray.MenuItem("喝水 250ml", lambda: self._tray_add_water(250)),
                pystray.MenuItem("喝水 500ml", lambda: self._tray_add_water(500)),
                pystray.MenuItem("稍后提醒10分钟", lambda: self._tray_snooze_reminder(10)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("重置久坐计时", self._tray_reset_sedentary),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self.quit_app),
            )

            self.tray_icon = pystray.Icon("DailyHydrate", icon_image, "每日喝水提醒", menu)
            tray_thread = threading.Thread(target=self._run_tray, daemon=True)
            tray_thread.start()

        except ImportError:
            logger.warning("pystray not installed, tray icon disabled")
        except Exception as e:
            logger.warning("Failed to setup tray: %s", e)

    def _run_tray(self):
        if self.tray_icon:
            self.tray_icon.run()

    def _tray_add_water(self, amount):
        self.config.add_record(amount)
        self.reminder.reset_timer()
        self.root.after(0, self.update_display)

    def _tray_reset_sedentary(self):
        self.reminder.reset_sedentary_timer()
        self.root.after(0, self.update_sedentary_countdown)

    def _tray_snooze_reminder(self, minutes):
        self.reminder.snooze_reminder(minutes)
        self.root.after(0, self._render_countdown_label)

    def show_window(self, *args):
        """显示窗口（从托盘或通知点击唤醒）"""

        def _show():
            if self.is_closing:
                return
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
            self.root.iconify()

    def _cancel_timers(self):
        for after_id in [self.display_after_id, self.countdown_after_id, self.sedentary_after_id]:
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass

        self.display_after_id = None
        self.countdown_after_id = None
        self.sedentary_after_id = None

    def quit_app(self, *args):
        """退出应用"""
        if self.is_closing:
            return

        self.is_closing = True
        self._cancel_timers()

        self.reminder.stop()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        self.root.after(0, self.root.destroy)

    def _on_window_close(self):
        """点击窗口关闭按钮时：优先最小化到托盘"""
        if self.tray_icon:
            self.hide_window()
        else:
            self.quit_app()

    def create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.content_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="每日喝水提醒",
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        title_label.pack(pady=(0, 20))

        progress_frame = ttk.LabelFrame(main_frame, text="今日进度", padding="15")
        progress_frame.pack(fill=tk.X, pady=(0, 15))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=300,
            mode="determinate",
        )
        self.progress_bar.pack(pady=(0, 10))

        self.progress_label = ttk.Label(
            progress_frame,
            text="0 / 2000 ml",
            font=("Microsoft YaHei UI", 14, "bold"),
        )
        self.progress_label.pack()

        self.percent_label = ttk.Label(progress_frame, text="0%", font=("Microsoft YaHei UI", 12))
        self.percent_label.pack()

        self.countdown_label = ttk.Label(
            progress_frame,
            text="下次提醒: --:--",
            font=("Microsoft YaHei UI", 11),
        )
        self.countdown_label.pack(pady=(5, 0))

        self.sedentary_countdown_label = ttk.Label(
            progress_frame,
            text="久坐提醒: --:--",
            font=("Microsoft YaHei UI", 11),
        )
        self.sedentary_countdown_label.pack(pady=(5, 0))

        history_frame = ttk.LabelFrame(main_frame, text="最近7天", padding="15")
        history_frame.pack(fill=tk.X, pady=(0, 15))

        self.week_total_label = ttk.Label(history_frame, text="总饮水: 0 ml")
        self.week_total_label.pack(anchor="w")
        self.week_avg_label = ttk.Label(history_frame, text="日均饮水: 0 ml")
        self.week_avg_label.pack(anchor="w")
        self.streak_label = ttk.Label(history_frame, text="连续达标: 0 天")
        self.streak_label.pack(anchor="w")

        drink_frame = ttk.LabelFrame(main_frame, text="记录喝水", padding="15")
        drink_frame.pack(fill=tk.X, pady=(0, 15))

        button_frame = ttk.Frame(drink_frame)
        button_frame.pack(pady=(0, 10))

        ttk.Button(button_frame, text="一杯\n(250ml)", command=lambda: self.add_water(250), width=10).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="半杯\n(125ml)", command=lambda: self.add_water(125), width=10).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="大杯\n(500ml)", command=lambda: self.add_water(500), width=10).pack(
            side=tk.LEFT, padx=5
        )

        custom_frame = ttk.Frame(drink_frame)
        custom_frame.pack()

        ttk.Label(custom_frame, text="自定义:").pack(side=tk.LEFT, padx=(0, 5))
        self.custom_amount = ttk.Entry(custom_frame, width=8)
        self.custom_amount.pack(side=tk.LEFT, padx=5)
        self.custom_amount.insert(0, str(self.config.get_cup_size()))
        ttk.Label(custom_frame, text="ml").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(custom_frame, text="添加", command=self.add_custom_water, width=6).pack(side=tk.LEFT, padx=5)

        settings_frame = ttk.LabelFrame(main_frame, text="设置", padding="15")
        settings_frame.pack(fill=tk.X, pady=(0, 15))

        settings_frame.columnconfigure(0, minsize=80)
        settings_frame.columnconfigure(1, minsize=100)
        settings_frame.columnconfigure(2, minsize=50)
        settings_frame.columnconfigure(3, weight=1)

        ttk.Label(settings_frame, text="每日目标:").grid(row=0, column=0, sticky="e", pady=5)
        self.goal_entry = ttk.Entry(settings_frame, width=10)
        self.goal_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.goal_entry.insert(0, str(self.config.get_daily_goal()))
        ttk.Label(settings_frame, text="ml").grid(row=0, column=2, sticky="w", pady=5)
        ttk.Button(settings_frame, text="保存", command=self.save_goal, width=6).grid(
            row=0, column=3, sticky="e", pady=5
        )

        ttk.Label(settings_frame, text="提醒间隔:").grid(row=1, column=0, sticky="e", pady=5)
        self.interval_entry = ttk.Entry(settings_frame, width=10)
        self.interval_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.interval_entry.insert(0, str(self.config.get_remind_interval()))
        ttk.Label(settings_frame, text="分钟").grid(row=1, column=2, sticky="w", pady=5)
        ttk.Button(settings_frame, text="保存", command=self.save_interval, width=6).grid(
            row=1, column=3, sticky="e", pady=5
        )

        self.remind_var = tk.BooleanVar(value=self.config.is_remind_enabled())
        ttk.Checkbutton(
            settings_frame,
            text="开启提醒",
            variable=self.remind_var,
            command=self.toggle_remind,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

        self.sound_var = tk.BooleanVar(value=self.config.is_sound_enabled())
        ttk.Checkbutton(
            settings_frame,
            text="声音",
            variable=self.sound_var,
            command=self.toggle_sound,
        ).grid(row=2, column=2, columnspan=2, sticky="w", pady=5)

        ttk.Label(settings_frame, text="久坐提醒:").grid(row=3, column=0, sticky="e", pady=5)
        self.sedentary_entry = ttk.Entry(settings_frame, width=10)
        self.sedentary_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.sedentary_entry.insert(0, str(self.config.get_sedentary_interval()))
        ttk.Label(settings_frame, text="分钟").grid(row=3, column=2, sticky="w", pady=5)
        ttk.Button(settings_frame, text="保存", command=self.save_sedentary_interval, width=6).grid(
            row=3, column=3, sticky="e", pady=5
        )

        self.sedentary_var = tk.BooleanVar(value=self.config.is_sedentary_enabled())
        ttk.Checkbutton(
            settings_frame,
            text="开启久坐提醒",
            variable=self.sedentary_var,
            command=self.toggle_sedentary,
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=5)

        self.start_minimized_var = tk.BooleanVar(value=self.config.is_start_minimized())
        ttk.Checkbutton(
            settings_frame,
            text="启动时最小化到托盘",
            variable=self.start_minimized_var,
            command=self.toggle_start_minimized,
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=5)

        self.quiet_var = tk.BooleanVar(value=self.config.is_quiet_hours_enabled())
        ttk.Checkbutton(
            settings_frame,
            text="启用静默时段",
            variable=self.quiet_var,
            command=self.toggle_quiet_hours,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Label(settings_frame, text="静默:").grid(row=7, column=0, sticky="e", pady=5)
        self.quiet_start_entry = ttk.Entry(settings_frame, width=8)
        self.quiet_start_entry.grid(row=7, column=1, sticky="w", padx=5, pady=5)
        self.quiet_start_entry.insert(0, self.config.get_quiet_start())
        self.quiet_end_entry = ttk.Entry(settings_frame, width=8)
        self.quiet_end_entry.grid(row=7, column=2, sticky="w", padx=5, pady=5)
        self.quiet_end_entry.insert(0, self.config.get_quiet_end())
        ttk.Button(settings_frame, text="保存", command=self.save_quiet_hours, width=6).grid(
            row=7, column=3, sticky="e", pady=5
        )

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(bottom_frame, text="清空记录", command=self.clear_records).pack(side=tk.LEFT)
        ttk.Button(bottom_frame, text="稍后10分钟", command=lambda: self.snooze_reminder(10)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="测试提醒", command=self.test_remind).pack(side=tk.RIGHT)

    def add_water(self, amount):
        self.config.add_record(amount)
        self.update_display()
        self.reminder.reset_timer()

        total = self.config.get_today_total()
        goal = self.config.get_daily_goal()
        if total >= goal:
            messagebox.showinfo("恭喜", f"目标已达成\n当前: {total}ml / {goal}ml")

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
            messagebox.showerror("错误", f"无效的数值\n{str(e)}")

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
            self.reminder.reset_timer()
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
            self.reminder.reset_sedentary_timer()
            messagebox.showinfo("成功", f"久坐提醒间隔已设置为 {interval} 分钟")
        except ValueError as e:
            messagebox.showerror("错误", f"无效的数值\n{str(e)}")

    def toggle_sedentary(self):
        self.config.set_sedentary_enabled(self.sedentary_var.get())

    def toggle_start_minimized(self):
        self.config.set_start_minimized(self.start_minimized_var.get())

    def toggle_quiet_hours(self):
        self.config.set_quiet_hours_enabled(self.quiet_var.get())

    def save_quiet_hours(self):
        start = self.quiet_start_entry.get().strip()
        end = self.quiet_end_entry.get().strip()
        if not self._valid_hhmm(start) or not self._valid_hhmm(end):
            messagebox.showerror("错误", "时间格式应为 HH:MM，例如 23:00")
            return

        self.config.set_quiet_start(start)
        self.config.set_quiet_end(end)
        messagebox.showinfo("成功", f"静默时段已设置为 {start} - {end}")

    def _valid_hhmm(self, value):
        try:
            hour, minute = value.split(":", 1)
            hour = int(hour)
            minute = int(minute)
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except Exception:
            return False

    def snooze_reminder(self, minutes):
        self.reminder.snooze_reminder(minutes)
        self._render_countdown_label()
        messagebox.showinfo("已设置", f"喝水提醒已延后 {minutes} 分钟")

    def clear_records(self):
        if messagebox.askyesno("确认", "确定清空今日所有记录?"):
            self.config.clear_today_records()
            self.update_display()

    def test_remind(self):
        self.on_remind()

    def update_display(self):
        if self.is_closing:
            return

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
        self.update_history_stats()

    def update_history_stats(self):
        history = self.config.get_recent_history(7)
        week_total = sum(item["total"] for item in history)
        week_avg = int(week_total / 7) if history else 0
        streak = self._calculate_streak(history)

        self.week_total_label.config(text=f"总饮水: {week_total} ml")
        self.week_avg_label.config(text=f"日均饮水: {week_avg} ml")
        self.streak_label.config(text=f"连续达标: {streak} 天")

    def _calculate_streak(self, history):
        goal = self.config.get_daily_goal()
        streak = 0
        for item in reversed(history):
            if item["total"] >= goal:
                streak += 1
            else:
                break
        return streak

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
                f"目标已达成\n\n"
                f"继续保持!"
            )

        self.reminder.send_notification("喝水提醒", message)
        self.root.after(0, self.update_display)

    def on_sedentary_remind(self):
        self.reminder.send_sedentary_notification()
        self.root.after(0, self.update_sedentary_countdown)

    def schedule_update(self):
        """每分钟刷新一次进度显示"""
        if self.is_closing:
            return
        self.update_display()
        self.display_after_id = self.root.after(60000, self.schedule_update)

    def update_countdown(self):
        """每秒刷新喝水倒计时（单链路）"""
        if self.is_closing:
            return

        self._render_countdown_label()
        self.countdown_after_id = self.root.after(1000, self.update_countdown)

    def _render_countdown_label(self):
        remaining = self.reminder.get_remaining_time_str()
        if remaining == "--:--":
            self.countdown_label.config(text="提醒已关闭", foreground="gray")
        else:
            self.countdown_label.config(text=f"下次提醒: {remaining}", foreground="blue")

    def update_sedentary_countdown(self):
        """每秒刷新久坐倒计时（单链路）"""
        if self.is_closing:
            return

        remaining = self.reminder.get_sedentary_remaining_time_str()
        if remaining == "--:--":
            self.sedentary_countdown_label.config(text="久坐提醒已关闭", foreground="gray")
        else:
            self.sedentary_countdown_label.config(text=f"久坐提醒: {remaining}", foreground="orange")

        self.sedentary_after_id = self.root.after(1000, self.update_sedentary_countdown)

    def run(self, start_minimized=False):
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        if start_minimized:
            self.root.after(200, self.hide_window)
        self.root.mainloop()
