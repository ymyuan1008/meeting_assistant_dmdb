# 标准库
import os
import smtplib
import logging
import aiofiles
from typing import List, Optional

# 第三方库
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# 自定义库
from  models import Meeting

logger = logging.getLogger(__name__)

class NotificationService(object):
    def __init__(self)->None:
        # Email configuration (you would set these in environment variables)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_username = os.getenv("EMAIL_USERNAME", "")
        self.email_password = os.getenv("EMAIL_PASSWORD", "")
        self.sender_email = os.getenv("SENDER_EMAIL", self.email_username)

    async def send_meeting_invitation(self, meeting: Meeting, participants: list) -> bool:
        """Send meeting invitation emails to participants"""
        if not self.email_username or not self.email_password:
            logger.warning("Email credentials not configured, skipping email notification")
            return False
        try:
            # Create email content
            subject = f"会议邀请: {meeting.title}"
            # HTML email content
            html_content = self._create_invitation_html(meeting, participants)

            # Send to each participant
            for participant in participants:
                await self._send_email(
                    to_email=participant.email,
                    subject=subject,
                    html_content=html_content,
                    meeting=meeting
                )

            return True
        except Exception as e:
            logger.error(f"Failed to send meeting invitations: {str(e)}")
            return False

    async def send_meeting_reminder(self, meeting: Meeting, participants: List) -> bool:
        """Send meeting reminder emails"""
        if not self.email_username or not self.email_password:
            logger.warning("Email credentials not configured, skipping reminder")
            return False
        try:
            subject = f"会议提醒: {meeting.title}"
            html_content = self._create_reminder_html(meeting)
            for participant in participants:
                await self._send_email(
                    to_email=participant.email,
                    subject=subject,
                    html_content=html_content,
                    meeting=meeting
                )
            return True

        except Exception as e:
            logger.error(f"Failed to send meeting reminders: {str(e)}")
            return False

    async def send_meeting_summary(self, meeting: Meeting, participants: list, summary_content: str) -> bool:
        """Send meeting summary emails"""
        if not self.email_username or not self.email_password:
            logger.warning("Email credentials not configured, skipping summary")
            return False

        try:
            subject = f"会议纪要: {meeting.title}"
            html_content = self._create_summary_html(meeting, summary_content)
            for participant in participants:
                await self._send_email(
                    to_email=participant.email,
                    subject=subject,
                    html_content=html_content,
                    meeting=meeting
                )
            return True

        except Exception as e:
            logger.error(f"Failed to send meeting summary: {str(e)}")
            return False

    async def _send_email(self,
                          to_email: str,
                          subject: str,
                          html_content: str,
                          meeting: Meeting,
                          attachment_path: Optional[str] = None)->None:

        """Send individual email"""
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = to_email

            # Add HTML content
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            # Add attachment if provided
            if attachment_path and os.path.exists(attachment_path):
                async with aiofiles.open(attachment_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(attachment_path)}',
                )
                message.attach(part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_username, self.email_password)
                server.send_message(message)
            logger.info(f"Email sent successfully to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            raise e

    def _create_invitation_html(self, meeting: Meeting, participants: list) -> str:
        """Create HTML content for meeting invitation"""
        participants_list = "<br>".join([f"• {p.name} ({p.email})" for p in participants])
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                    会议邀请
                </h2>
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #2c3e50; margin-top: 0;">会议信息</h3>
                    <p><strong>会议标题：</strong>{meeting.title}</p>
                    <p><strong>会议时间：</strong>{meeting.start_time.strftime('%Y年%m月%d日 %H:%M')}</p>
                    <p><strong>会议地点：</strong>{meeting.location or '线上会议'}</p>
                    <p><strong>组织者：</strong>{meeting.organizer}</p>
                    {f'<p><strong>会议描述：</strong>{meeting.description}</p>' if meeting.description else ''}
                </div>
                {f'''<div style="background-color: #fff; padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #2c3e50; margin-top: 0;">参会人员</h3>
                    <p>{participants_list}</p>
                </div>
                ''' if participants else ''}
                <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; color: #2c3e50;">
                        <strong>请准时参加会议。如有问题，请联系会议组织者。</strong>
                    </p>
                </div>
                <p style="color: #7f8c8d; font-size: 12px; margin-top: 30px;">
                    此邮件由会议助手系统自动发送，请勿回复。
                </p>
            </div>
        </body>
        </html>
        """
        return html_content

    def _create_reminder_html(self, meeting: Meeting) -> str:
        """Create HTML content for meeting reminder"""
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 10px;">
                    会议提醒
                </h2>
                <div style="background-color: #fff3cd; padding: 20px; border: 1px solid #ffeaa7; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #856404; margin-top: 0;">即将开始的会议</h3>
                    <p><strong>会议标题：</strong>{meeting.title}</p>
                    <p><strong>会议时间：</strong>{meeting.start_time.strftime('%Y年%m月%d日 %H:%M')}</p>
                    <p><strong>会议地点：</strong>{meeting.location or '线上会议'}</p>
                    <p><strong>组织者：</strong>{meeting.organizer}</p>
                </div>
                <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; color: #155724;">
                        <strong>请确保您已做好会议准备，准时参加。</strong>
                    </p>
                </div>
                <p style="color: #7f8c8d; font-size: 12px; margin-top: 30px;">
                    此邮件由会议助手系统自动发送，请勿回复。
                </p>
            </div>
        </body>
        </html>
        """
        return html_content

    def _create_summary_html(self, meeting: Meeting, summary_content: str) -> str:
        """Create HTML content for meeting summary"""
        # Convert text summary to HTML
        summary_html = summary_content.replace('\\n', '<br>')

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #27ae60; border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                    会议纪要
                </h2>
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #2c3e50; margin-top: 0;">会议信息</h3>
                    <p><strong>会议标题：</strong>{meeting.title}</p>
                    <p><strong>会议时间：</strong>{meeting.start_time.strftime('%Y年%m月%d日 %H:%M')}</p>
                    <p><strong>会议地点：</strong>{meeting.location or '线上会议'}</p>
                    <p><strong>组织者：</strong>{meeting.organizer}</p>
                </div>
                <div style="background-color: #fff; padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #2c3e50; margin-top: 0;">会议纪要内容</h3>
                    <div style="white-space: pre-wrap;">
                        {summary_html}
                    </div>
                </div>

                <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; color: #2c3e50;">
                        <strong>感谢您参加本次会议。</strong>
                    </p>
                </div>
                <p style="color: #7f8c8d; font-size: 12px; margin-top: 30px;">
                    此邮件由会议助手系统自动发送，请勿回复。
                </p>
            </div>
        </body>
        </html>
        """
        return html_content
