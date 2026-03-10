"""
提醒模块 - 负责发送Windows通知提醒
"""
import threading
import time
import subprocess
import os
from datetime import datetime

class ReminderManager:
    def __init__(self, config_manager, on_remind_callback=None, on_notification_click=None,
                 on_sedentary_callback=None):
        self.config = config_manager
        self.on_remind_callback = on_remind_callback
        self.on_notification_click = on_notification_click
        self.on_sedentary_callback = on_sedentary_callback
        self.timer_thread = None
        self.sedentary_thread = None
        self.running = False
        self.last_remind_time = time.time()
        self.last_sedentary_time = time.time()

    def start(self):
        """启动提醒服务"""
        if self.running:
            return

        self.running = True
        self.timer_thread = threading.Thread(target=self._remind_loop, daemon=True)
        self.timer_thread.start()

        # 启动久坐提醒线程
        self.sedentary_thread = threading.Thread(target=self._sedentary_loop, daemon=True)
        self.sedentary_thread.start()

    def stop(self):
        """停止提醒服务"""
        self.running = False
        if self.timer_thread:
            self.timer_thread.join(timeout=1)
        if self.sedentary_thread:
            self.sedentary_thread.join(timeout=1)

    def _remind_loop(self):
        """提醒循环"""
        while self.running:
            try:
                interval = self.config.get_remind_interval() * 60

                if self.config.is_remind_enabled() and interval > 0:
                    current_time = time.time()

                    if self.last_remind_time is None or \
                       (current_time - self.last_remind_time) >= interval:
                        self._send_reminder()
                        self.last_remind_time = current_time

                time.sleep(1)

            except Exception as e:
                print(f"Reminder loop error: {e}")
                time.sleep(1)

    def _send_reminder(self):
        """发送喝水提醒"""
        if self.on_remind_callback:
            try:
                self.on_remind_callback()
            except Exception as e:
                print(f"Callback error: {e}")

    def send_notification(self, title, message):
        """发送Windows系统通知"""
        success = False

        # 方式1: 使用 winotify (支持点击回调)
        try:
            from winotify import Notification, audio

            toast = Notification(
                app_id="Microsoft.Windows.Shell.RunDialog",
                title=title,
                msg=message,
                duration="long"
            )

            # 添加点击回调
            toast.add_actions(label="Open", link="")
            toast.on_click = lambda: self._on_notification_clicked()

            if self.config.is_sound_enabled():
                toast.set_audio(audio.Default, loop=False)
            else:
                toast.set_audio(audio.Silent, loop=False)

            toast.show()
            success = True
            print("winotify notification sent")
        except Exception as e:
            print(f"winotify failed: {e}")

        # 方式2: 使用 PowerShell Toast 通知
        if not success:
            try:
                self._send_powershell_notification(title, message)
                success = True
                print("PowerShell notification sent")
            except Exception as e:
                print(f"PowerShell failed: {e}")

        # 方式3: 使用 win10toast
        if not success:
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()

                # win10toast 的点击回调需要特殊处理
                def on_clicked():
                    self._on_notification_clicked()

                toaster.show_toast(
                    title,
                    message,
                    icon_path=None,
                    duration=10,
                    threaded=True,
                    callback_on_click=on_clicked
                )
                success = True
                print("win10toast notification sent")
            except Exception as e:
                print(f"win10toast failed: {e}")

        # 方式4: 独立弹窗（总是可用）
        if not success:
            self._show_popup_notification(title, message)

    def _on_notification_clicked(self):
        """通知被点击时的回调"""
        print("Notification clicked!")
        if self.on_notification_click:
            try:
                self.on_notification_click()
            except Exception as e:
                print(f"Click callback error: {e}")

    def _send_powershell_notification(self, title, message):
        """使用 PowerShell 发送 Windows Toast 通知"""
        title = title.replace("'", "''").replace('"', '""')
        message = message.replace("'", "''").replace('"', '""').replace('\n', '`n')

        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $template = @"
        <toast duration="long">
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("DailyHydrate").Show($toast)
        '''

        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            timeout=10
        )

    def _show_popup_notification(self, title, message):
        """显示独立的弹窗通知"""
        def show_popup():
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            try:
                root.iconbitmap("icon.ico")
            except:
                pass

            result = messagebox.showinfo(title, message)

            # 点击OK后唤醒主窗口
            self._on_notification_clicked()

            root.destroy()

        popup_thread = threading.Thread(target=show_popup, daemon=False)
        popup_thread.start()

    def reset_timer(self):
        """重置提醒计时器"""
        self.last_remind_time = time.time()

    def get_remaining_seconds(self):
        """获取距离下次提醒的剩余秒数"""
        if not self.config.is_remind_enabled():
            return None

        interval = self.config.get_remind_interval() * 60
        if interval <= 0:
            return None

        elapsed = time.time() - self.last_remind_time
        remaining = interval - elapsed

        return max(0, int(remaining))

    def get_remaining_time_str(self):
        """获取距离下次提醒的剩余时间字符串"""
        seconds = self.get_remaining_seconds()
        if seconds is None:
            return "--:--"

        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    # 久坐提醒相关方法
    def _sedentary_loop(self):
        """久坐提醒循环"""
        while self.running:
            try:
                interval = self.config.get_sedentary_interval() * 60

                if self.config.is_sedentary_enabled() and interval > 0:
                    current_time = time.time()

                    if self.last_sedentary_time is None or \
                       (current_time - self.last_sedentary_time) >= interval:
                        self._send_sedentary_reminder()
                        self.last_sedentary_time = current_time

                time.sleep(1)

            except Exception as e:
                print(f"Sedentary reminder loop error: {e}")
                time.sleep(1)

    def _send_sedentary_reminder(self):
        """发送久坐提醒"""
        if self.on_sedentary_callback:
            try:
                self.on_sedentary_callback()
            except Exception as e:
                print(f"Sedentary callback error: {e}")

    def send_sedentary_notification(self):
        """发送久坐提醒通知"""
        message = (
            "您已经坐了很长时间了！\n\n"
            "起来活动一下吧~\n"
            "伸伸懒腰，走动走动\n\n"
            "健康小贴士：每小时起身活动5分钟"
        )
        self.send_notification("久坐提醒", message)

    def reset_sedentary_timer(self):
        """重置久坐提醒计时器"""
        self.last_sedentary_time = time.time()

    def get_sedentary_remaining_seconds(self):
        """获取距离下次久坐提醒的剩余秒数"""
        if not self.config.is_sedentary_enabled():
            return None

        interval = self.config.get_sedentary_interval() * 60
        if interval <= 0:
            return None

        elapsed = time.time() - self.last_sedentary_time
        remaining = interval - elapsed

        return max(0, int(remaining))

    def get_sedentary_remaining_time_str(self):
        """获取距离下次久坐提醒的剩余时间字符串"""
        seconds = self.get_sedentary_remaining_seconds()
        if seconds is None:
            return "--:--"

        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
