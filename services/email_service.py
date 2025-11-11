# 标准库
import os
import smtplib
from typing import List

# 第三方库
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from jinja2 import Template

#自定义库
from  models import Meeting


class EmailService(object):
    def __init__(self) -> None:
        # Email configuration - these should be set as environment variables
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.163.com')  # 163邮箱服务器
        self.smtp_port = int(os.getenv('SMTP_PORT', '465'))  # 163邮箱SSL端口
        self.email_user = os.getenv('EMAIL_USER', '')  # 完整的163邮箱地址
        self.email_password = os.getenv('EMAIL_PASSWORD', '')  # 163邮箱授权码
        self.from_email = os.getenv('FROM_EMAIL', self.email_user)

    async def send_meeting_notification(self, meeting: Meeting) -> bool:
        """Send meeting notification emails to participants"""
        if not self.email_user or not self.email_password:
            print("Email configuration not set. Skipping email sending.")
            return False
        try:
            # Create SMTP connection
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            # Send email to each participant
            for participant in meeting.participants:
                msg = self._create_notification_email(meeting, participant)
                if msg:
                    text = msg.as_string()
                    server.sendmail(self.from_email, participant.email, text)
                    print(f"Notification sent to {participant.email}")
            server.quit()
            return True

        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def _create_notification_email(self, meeting: Meeting, participant) -> MIMEMultipart:
        """Create email message for meeting notification"""
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = participant.email
        msg['Subject'] = f"会议通知: {meeting.title}"
        # Email template
        email_template = Template("""
        <html>
        <body>
            <h2>会议通知</h2>
            <p>亲爱的 {{ participant_name }}，</p>
            <p>您被邀请参加以下会议：</p>
            <table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse;">
                <tr>
                    <td><strong>会议主题</strong></td>
                    <td>{{ meeting_title }}</td>
                </tr>
                <tr>
                    <td><strong>会议时间</strong></td>
                    <td>{{ meeting_datetime }}</td>
                </tr>
                <tr>
                    <td><strong>会议地点</strong></td>
                    <td>{{ meeting_location }}</td>
                </tr>
                <tr>
                    <td><strong>预计时长</strong></td>
                    <td>{{ meeting_duration }}分钟</td>
                </tr>
                {% if meeting_description %}
                <tr>
                    <td><strong>会议描述</strong></td>
                    <td>{{ meeting_description }}</td>
                </tr>
                {% endif %}
                {% if meeting_agenda %}
                <tr>
                    <td><strong>会议议程</strong></td>
                    <td>{{ meeting_agenda }}</td>
                </tr>
                {% endif %}
            </table>
            {% if participants_list %}
            <h3>参会人员</h3>
            <ul>
            {% for p in participants_list %}
                <li>{{ p.name }} ({{ p.role }}) - {{ p.email }}</li>
            {% endfor %}
            </ul>
            {% endif %}
            <p><strong>请及时确认参会状态。如有冲突，请提前告知组织者。</strong></p>
            <p>此邮件由会议助手系统自动发送。</p>
            <br>
            <p>会议助手系统<br>
            {{ send_time }}</p>
        </body>
        </html>
        """)

        # Render template
        html_content = email_template.render(
            participant_name=participant.name,
            meeting_title=meeting.title,
            meeting_datetime=meeting.date_time.strftime('%Y年%m月%d日 %H:%M'),
            meeting_location=meeting.location or '待定',
            meeting_duration=meeting.duration_minutes,
            meeting_description=meeting.description,
            meeting_agenda=meeting.agenda,
            participants_list=meeting.participants,
            send_time=meeting.created_at.strftime('%Y年%m月%d日 %H:%M')
        )
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        return msg

    async def send_meeting_reminder(self, meeting: Meeting, hours_before: int = 24) -> bool:
        """Send meeting reminder emails"""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            for participant in meeting.participants:
                msg = self._create_reminder_email(meeting, participant, hours_before)
                if msg:
                    text = msg.as_string()
                    server.sendmail(self.from_email, participant.email, text)
                    print(f"Reminder sent to {participant.email}")
            server.quit()
            return True
        except Exception as e:
            print(f"Error sending reminder: {e}")
            return False

    def _create_reminder_email(self, meeting: Meeting, participant, hours_before: int) -> MIMEMultipart:
        """Create reminder email message"""
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = participant.email
        msg['Subject'] = f"会议提醒: {meeting.title} ({hours_before}小时后开始)"

        reminder_template = Template("""
        <html>
        <body>
            <h2>会议提醒</h2>
            <p>亲爱的 {{ participant_name }}，</p>
            <p>提醒您，以下会议将在 {{ hours_before }} 小时后开始：</p>
            <div style="background-color: #f0f8ff; padding: 15px; border-left: 5px solid #007acc;">
                <h3>{{ meeting_title }}</h3>
                <p><strong>时间：</strong>{{ meeting_datetime }}</p>
                <p><strong>地点：</strong>{{ meeting_location }}</p>
            </div>
            <p>请准时参加。如有任何问题，请及时联系组织者。</p>
            <p>此邮件由会议助手系统自动发送。</p>
        </body>
        </html>
        """)
        html_content = reminder_template.render(
            participant_name=participant.name,
            meeting_title=meeting.title,
            meeting_datetime=meeting.date_time.strftime('%Y年%m月%d日 %H:%M'),
            meeting_location=meeting.location or '待定',
            hours_before=hours_before
        )
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        return msg

    async def send_meeting_minutes(self, meeting: Meeting, minutes_file_path: str) -> bool:
        """Send meeting minutes as email attachment"""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            for participant in meeting.participants:
                msg = self._create_minutes_email(meeting, participant, minutes_file_path)
                if msg:
                    text = msg.as_string()
                    server.sendmail(self.from_email, participant.email, text)
                    print(f"Meeting minutes sent to {participant.email}")
            server.quit()
            return True
        except Exception as e:
            print(f"Error sending meeting minutes: {e}")
            return False

    def _create_minutes_email(self, meeting: Meeting, participant, minutes_file_path: str) -> MIMEMultipart:
        """Create email with meeting minutes attachment"""
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = participant.email
        msg['Subject'] = f"会议纪要: {meeting.title}"
        # Email body
        body = f"""
        亲爱的 {participant.name}，
        附件为会议纪要文档。
        会议：{meeting.title}
        时间：{meeting.date_time.strftime('%Y年%m月%d日 %H:%M')}
        如有任何问题，请及时联系。
        会议助手系统
        """

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Add attachment if file exists
        if os.path.exists(minutes_file_path):
            with open(minutes_file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)

            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(minutes_file_path)}'
            )

            msg.attach(part)
        return msg
