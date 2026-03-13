"""
提醒模块 - 负责发送 Windows 通知提醒
"""
import threading
import time
import subprocess
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


class ReminderManager:
    def __init__(
        self,
        config_manager,
        on_remind_callback=None,
        on_notification_click=None,
        on_sedentary_callback=None,
        ui_dispatch=None,
    ):
        self.config = config_manager
        self.on_remind_callback = on_remind_callback
        self.on_notification_click = on_notification_click
        self.on_sedentary_callback = on_sedentary_callback
        self.ui_dispatch = ui_dispatch

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
        """喝水提醒循环"""
        while self.running:
            try:
                interval = self.config.get_remind_interval() * 60
                if self.config.is_remind_enabled() and interval > 0:
                    current_time = time.time()
                    snooze_until = self.config.get_snooze_until()
                    if snooze_until and current_time < snooze_until:
                        time.sleep(1)
                        continue
                    if self._is_quiet_time():
                        time.sleep(1)
                        continue
                    if self.last_remind_time is None or (current_time - self.last_remind_time) >= interval:
                        self._send_reminder()
                        self.last_remind_time = current_time
                time.sleep(1)
            except Exception as e:
                logger.exception("Reminder loop error: %s", e)
                time.sleep(1)

    def _send_reminder(self):
        """发送喝水提醒"""
        if self.on_remind_callback:
            try:
                self.on_remind_callback()
            except Exception as e:
                logger.exception("Reminder callback error: %s", e)

    def send_notification(self, title, message):
        """发送 Windows 系统通知"""
        success = False

        # 方式1: winotify（支持点击回调）
        try:
            from winotify import Notification, audio

            toast = Notification(
                app_id="Microsoft.Windows.Shell.RunDialog",
                title=title,
                msg=message,
                duration="long",
            )
            toast.add_actions(label="Open", link="")
            toast.add_actions(label="喝250ml", link="dailyhydrate://drink/250")
            toast.add_actions(label="稍后10分钟", link="dailyhydrate://snooze/10")
            toast.on_click = lambda: self._on_notification_clicked()

            if self.config.is_sound_enabled():
                toast.set_audio(audio.Default, loop=False)
            else:
                toast.set_audio(audio.Silent, loop=False)

            toast.show()
            success = True
            logger.info("winotify notification sent")
        except Exception as e:
            logger.warning("winotify failed: %s", e)

        # 方式2: PowerShell Toast
        if not success:
            try:
                self._send_powershell_notification(title, message)
                success = True
                logger.info("PowerShell notification sent")
            except Exception as e:
                logger.warning("PowerShell notification failed: %s", e)

        # 方式3: win10toast
        if not success:
            try:
                from win10toast import ToastNotifier

                toaster = ToastNotifier()

                def on_clicked():
                    self._on_notification_clicked()

                toaster.show_toast(
                    title,
                    message,
                    icon_path=None,
                    duration=10,
                    threaded=True,
                    callback_on_click=on_clicked,
                )
                success = True
                logger.info("win10toast notification sent")
            except Exception as e:
                logger.warning("win10toast failed: %s", e)

        # 方式4: popup 保底
        if not success:
            self._show_popup_notification(title, message)

    def _on_notification_clicked(self):
        """通知被点击时触发"""
        logger.info("Notification clicked")
        if self.on_notification_click:
            try:
                self.on_notification_click()
            except Exception as e:
                logger.exception("Notification click callback error: %s", e)

    def _send_powershell_notification(self, title, message):
        """使用 PowerShell 发送 Windows Toast"""
        title = title.replace("'", "''").replace('"', '""')
        message = message.replace("'", "''").replace('"', '""').replace("\n", "`n")

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

        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"PowerShell toast failed with exit code {result.returncode}: {stderr}")

    def _show_popup_notification(self, title, message):
        """显示保底弹窗，优先调度到主线程执行"""

        def show_popup():
            try:
                from tkinter import messagebox

                messagebox.showinfo(title, message)
            except Exception:
                import ctypes

                ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 | 0x1000)

            self._on_notification_clicked()

        if self.ui_dispatch:
            try:
                self.ui_dispatch(show_popup)
                return
            except Exception as e:
                logger.warning("ui_dispatch failed: %s", e)

        show_popup()

    def reset_timer(self):
        """重置喝水提醒计时器"""
        self.last_remind_time = time.time()
        self.config.set_snooze_until(None)

    def snooze_reminder(self, minutes):
        """稍后提醒，单位分钟。"""
        if minutes <= 0:
            return
        self.config.set_snooze_until(time.time() + minutes * 60)

    def _parse_hhmm(self, value):
        try:
            hour, minute = value.split(":", 1)
            hour = int(hour)
            minute = int(minute)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
            return None
        except Exception:
            return None

    def _is_quiet_time(self):
        if not self.config.is_quiet_hours_enabled():
            return False

        start = self._parse_hhmm(self.config.get_quiet_start())
        end = self._parse_hhmm(self.config.get_quiet_end())
        if not start or not end:
            return False

        now = datetime.now().time()
        start_t = now.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
        end_t = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)

        if start_t <= end_t:
            return start_t <= now <= end_t
        return now >= start_t or now <= end_t

    def get_remaining_seconds(self):
        """获取下次喝水提醒剩余秒数"""
        if not self.config.is_remind_enabled():
            return None

        snooze_until = self.config.get_snooze_until()
        if snooze_until and snooze_until > time.time():
            return int(snooze_until - time.time())

        interval = self.config.get_remind_interval() * 60
        if interval <= 0:
            return None

        elapsed = time.time() - self.last_remind_time
        remaining = interval - elapsed
        return max(0, int(remaining))

    def get_remaining_time_str(self):
        """获取下次喝水提醒剩余时间字符串"""
        seconds = self.get_remaining_seconds()
        if seconds is None:
            return "--:--"

        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    def _sedentary_loop(self):
        """久坐提醒循环"""
        while self.running:
            try:
                interval = self.config.get_sedentary_interval() * 60
                if self.config.is_sedentary_enabled() and interval > 0:
                    current_time = time.time()
                    if self._is_quiet_time():
                        time.sleep(1)
                        continue
                    if self.last_sedentary_time is None or (current_time - self.last_sedentary_time) >= interval:
                        self._send_sedentary_reminder()
                        self.last_sedentary_time = current_time
                time.sleep(1)
            except Exception as e:
                logger.exception("Sedentary reminder loop error: %s", e)
                time.sleep(1)

    def _send_sedentary_reminder(self):
        """发送久坐提醒"""
        if self.on_sedentary_callback:
            try:
                self.on_sedentary_callback()
            except Exception as e:
                logger.exception("Sedentary callback error: %s", e)

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
        """获取下次久坐提醒剩余秒数"""
        if not self.config.is_sedentary_enabled():
            return None

        interval = self.config.get_sedentary_interval() * 60
        if interval <= 0:
            return None

        elapsed = time.time() - self.last_sedentary_time
        remaining = interval - elapsed
        return max(0, int(remaining))

    def get_sedentary_remaining_time_str(self):
        """获取下次久坐提醒剩余时间字符串"""
        seconds = self.get_sedentary_remaining_seconds()
        if seconds is None:
            return "--:--"

        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
