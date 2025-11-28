# Python标准库
import os
import logging
from typing import List, Dict, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pytz
from datetime import datetime, timezone, timedelta

# 第三方库
from docx.shared import Inches, Pt
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx import Document as DocxDocument
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 自定义库
from models import Meeting, Transcription
from db.minio_upload import MinioUploader

# 全局配置 & 初始化
logger = logging.getLogger(__name__)
TABLE_STYLE = 'Table Grid'
DATETIME_CHINESE_SIMPLE = "%Y年%m月%d日 %H:%M"
bucket_name = "meeting-minutes"
console_address = os.getenv('MINIO_CONSOLE_ADDRESS')


# MinIO 初始化
def _init_minio_uploader() -> Optional[MinioUploader]:
    """Safely initialize MinIO uploader. Returns None if config missing/invalid."""
    endpoint = os.getenv('MINIO_ENDPOINT')
    access_key = os.getenv('MINIO_ACCESS_KEY')
    secret_key = os.getenv('MINIO_SECRET_KEY')
    secure = str(os.getenv('MINIO_SECURE', 'False')).lower() == 'true'

    if not endpoint or not access_key or not secret_key:
        logger.warning("MinIO 未配置（缺少 MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY），将使用本地保存。")
        return None
    try:
        return MinioUploader(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
    except Exception as e:
        logger.error(f"MinIO 初始化失败，将使用本地保存。错误: {e}")
        return None


uploader: Optional[MinioUploader] = _init_minio_uploader()


class BaseDocumentService(object):
    """基础文档服务类 - 封装公共逻辑"""

    def __init__(self)->None:
        self.output_dir = "static/documents"
        self.east8_tz = timezone(timedelta(hours=8))
        os.makedirs(self.output_dir, exist_ok=True)

        # 公共配置
        self.table_config = {
            "align": WD_TABLE_ALIGNMENT.CENTER,
            "header_font_size": Pt(11),
            "content_font_size": Pt(10),
            "col_widths": [Inches(1.2), Inches(3.5)]
        }
        self.default_font = "微软雅黑"

    def _convert_to_east8_time(self, dt: datetime) -> datetime:
        """将时间转换为东八区时间"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        east8_tz = pytz.timezone('Asia/Shanghai')
        return dt.astimezone(east8_tz)

    def _translate_role(self, role: str) -> str:
        """翻译角色为中文"""
        role_map = {
            'organizer': '组织者',
            'participant': '参与者',
            'presenter': '主讲人',
            'guest': '嘉宾'
        }
        return role_map.get(role, role)

    def _save_and_upload_file(self, filename_prefix: str, meeting: Meeting, file_ext: str, save_func: str) -> str:
        """保存文件并上传到MinIO（公共逻辑）"""
        # 生成文件名和路径
        filename = f"{filename_prefix}_{meeting.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
        object_name = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
        filepath = os.path.join(self.output_dir, filename)

        # 执行保存逻辑
        save_func(filepath)
        result_path = filepath

        # MinIO 上传逻辑
        if uploader is None or not console_address:
            if uploader is None:
                logger.info("MinIO 未启用，返回本地文件路径。")
            else:
                logger.warning("MINIO_CONSOLE_ADDRESS 未设置，返回本地文件路径。")

        try:
            minio_path, presigned_url = uploader.upload_file(console_address, bucket_name, filepath, object_name)
            if minio_path and presigned_url:
                logger.info(f"文件已上传至MinIO: {minio_path}")
                result_path = presigned_url
            else:
                logger.warning("MinIO 上传失败，返回本地路径")
        except Exception as e:
            logger.error(f"MinIO 上传异常: {e}，返回本地路径")
        return result_path


class PDFDocumentService(BaseDocumentService):
    """PDF文档生成服务类"""

    def __init__(self)->None:
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=4)
        # 注册中文字体
        self.chinese_font_name = self._register_chinese_font()

    import os
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    import logging

    logger = logging.getLogger(__name__)

    def _register_chinese_font(self) -> str:
        """注册中文字体"""
        # 初始化默认返回字体（兜底）
        font_name = 'Helvetica'

        # 优先尝试TTF字体
        font_candidates = [
            ('SimHei', 'SimHei.ttf'),
            ('MicrosoftYaHei', 'msyh.ttf'),
            ('SimSun', 'simsun.ttc'),
            ('STSong', 'STSONG.TTF'),
        ]
        system_font_paths = [
            '/usr/share/fonts/truetype/',
            '/usr/share/fonts/truetype/msttcorefonts/',
            'C:/Windows/Fonts/',
            '/System/Library/Fonts/',
            '/Library/Fonts/'
        ]

        # 尝试注册TTF字体（遍历所有候选+路径，找到第一个可用的即终止）
        for font_candidate_name, font_file in font_candidates:
            # 直接注册（无路径）
            if self._register_ttf_font(font_candidate_name, font_file):
                font_name = font_candidate_name
                break  # 找到可用字体，终止遍历

            # 遍历系统路径注册
            for path in system_font_paths:
                full_path = os.path.join(path, font_file)
                if os.path.exists(full_path) and self._register_ttf_font(font_candidate_name, full_path):
                    font_name = font_candidate_name
                    break  # 找到可用字体，终止路径遍历
            else:
                continue  # 路径遍历完未找到，继续下一个字体候选
            break  # 找到字体后，终止字体候选遍历

        # 若TTF字体未注册成功，尝试CID字体
        if font_name == 'Helvetica':
            try:
                pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
                font_name = 'STSong-Light'
            except Exception:
                logger.warning("未找到中文字体，中文可能显示乱码")

        return font_name


    def _register_ttf_font(self, font_name: str, font_path: str) -> bool:
        """注册单个TTF字体"""
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return True
        except (IOError, pdfmetrics.FontError) as e:
            logger.debug(f"注册字体失败 {font_path}: {e}")
            return False

    def _create_pdf_styles(self) -> dict[str, ParagraphStyle]:
        """创建PDF样式"""
        styles = getSampleStyleSheet()
        return {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1,
                fontName=self.chinese_font_name
            ),
            'heading': ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                fontName=self.chinese_font_name
            ),
            'normal': ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                fontName=self.chinese_font_name
            )
        }

    def _build_notification_pdf(self, meeting: Meeting, filepath: str)->None:
        """构建会议通知PDF"""
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = self._create_pdf_styles()
        story = []

        # 标题
        story.append(Paragraph("会议通知", styles['title']))
        story.append(Spacer(1, 20))

        # 会议基本信息
        story.append(Paragraph("会议信息", styles['heading']))
        meeting_data = [
            ['会议主题', meeting.title],
            ['会议时间', meeting.date_time.strftime(DATETIME_CHINESE_SIMPLE)],
            ['会议地点', meeting.location or '待定'],
            ['预计时长', f'{meeting.duration_minutes}分钟'],
            ['会议描述', meeting.description or '无'],
            ['会议议程', '待补充']
        ]
        meeting_table = Table(meeting_data, colWidths=[2 * inch, 4 * inch])
        meeting_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.chinese_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(meeting_table)
        story.append(Spacer(1, 20))

        # 参会人员
        if meeting.participants:
            story.append(Paragraph("参会人员", styles['heading']))
            participant_data = [['姓名', '邮箱', '角色']]
            for p in meeting.participants:
                participant_data.append([p.name, p.email, self._translate_role(p.user_role)])
            part_table = Table(participant_data, colWidths=[2 * inch, 2.5 * inch, 1.5 * inch])
            part_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), self.chinese_font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(part_table)

        # 页脚
        story.append(Spacer(1, 30))
        story.append(Paragraph("请及时确认参会状态，如有冲突请提前告知。", styles['normal']))
        story.append(Paragraph(f"生成时间：{datetime.now().strftime(DATETIME_CHINESE_SIMPLE)}", styles['normal']))

        doc.build(story)

    def _build_minutes_pdf(self, meeting: Meeting, transcriptions: list[Transcription], filepath: str)->None:
        """构建会议纪要PDF"""
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = self._create_pdf_styles()
        story = []

        # 标题
        story.append(Paragraph("会议摘要", styles['title']))
        story.append(Spacer(1, 20))

        # 会议基本信息
        story.append(Paragraph("会议基本信息", styles['heading']))
        meeting_data = [
            ['会议主题', meeting.title],
            ['会议时间', meeting.date_time.strftime(DATETIME_CHINESE_SIMPLE)],
            ['会议地点', meeting.location or '线上会议'],
            ['参会人数', str(len(meeting.participants))]
        ]
        meeting_table = Table(meeting_data, colWidths=[2 * inch, 4 * inch])
        meeting_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.chinese_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(meeting_table)
        story.append(Spacer(1, 20))

        # 会议内容
        if transcriptions:
            story.append(Paragraph("会议内容", styles['heading']))
            for t in transcriptions:
                timestamp = self._convert_to_east8_time(t.created_time).strftime('%H:%M:%S')
                content = f"[{timestamp}] {t.speaker_id}: {t.text_message}"
                if t.is_action_item:
                    content += " [行动项]"
                if t.is_decision:
                    content += " [决议]"
                story.append(Paragraph(content, styles['normal']))
                story.append(Spacer(1, 6))

        # 行动项汇总
        action_items = [t for t in transcriptions if t.is_action_item]
        if action_items:
            story.append(Spacer(1, 20))
            story.append(Paragraph("行动项汇总", styles['heading']))
            for i, item in enumerate(action_items, 1):
                story.append(Paragraph(f"{i}. {item.text_message}", styles['normal']))
                story.append(Spacer(1, 6))

        # 决议汇总
        decisions = [t for t in transcriptions if t.is_decision]
        if decisions:
            story.append(Spacer(1, 20))
            story.append(Paragraph("重要决议", styles['heading']))
            for i, d in enumerate(decisions, 1):
                story.append(Paragraph(f"{i}. {d.text_message}", styles['normal']))
                story.append(Spacer(1, 6))

        # 页脚
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"生成时间：{datetime.now().strftime(DATETIME_CHINESE_SIMPLE)}", styles['normal']))

        doc.build(story)

    async def generate_notification(self, meeting: Meeting) -> str:
        """异步生成会议通知PDF"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self._save_and_upload_file(
                "会议通知",
                meeting,
                "pdf",
                lambda path: self._build_notification_pdf(meeting, path)
            )
        )

    async def generate_minutes(self, meeting: Meeting, transcriptions: list[Transcription]) -> str:
        """异步生成会议纪要PDF"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self._save_and_upload_file(
                "会议摘要",
                meeting,
                "pdf",
                lambda path: self._build_minutes_pdf(meeting, transcriptions, path)
            )
        )


class DocxDocumentService(BaseDocumentService):
    """Word（Docx）文档生成服务类"""

    def __init__(self)->None:
        super().__init__()

    def _build_notification_docx(self, meeting: Meeting, filepath: str)-> None:
        """构建会议通知Word文档"""
        doc = DocxDocument()

        # 标题
        title = doc.add_heading('会议通知', 0)
        title.alignment = 1

        # 会议信息表格
        doc.add_heading('会议信息', level=1)
        details_table = doc.add_table(rows=6, cols=2)
        details_table.style = TABLE_STYLE

        # 填充会议信息
        details_data = [
            ('会议主题', meeting.title),
            ('会议时间', meeting.date_time.strftime(DATETIME_CHINESE_SIMPLE)),
            ('会议地点', meeting.location or '待定'),
            ('预计时长', f'{meeting.duration_minutes}分钟'),
            ('会议描述', meeting.description or '无'),
            ('会议议程', '待补充')
        ]
        for i, (label, value) in enumerate(details_data):
            cells = details_table.rows[i].cells
            cells[0].text = label
            cells[1].text = value

        # 参会人员
        if meeting.participants:
            doc.add_heading('参会人员', level=1)
            part_table = doc.add_table(rows=1, cols=3)
            part_table.style = TABLE_STYLE
            # 表头
            header_cells = part_table.rows[0].cells
            header_cells[0].text = '姓名'
            header_cells[1].text = '邮箱'
            header_cells[2].text = '角色'
            # 填充参会人员
            for p in meeting.participants:
                row_cells = part_table.add_row().cells
                row_cells[0].text = p.name
                row_cells[1].text = p.email
                row_cells[2].text = self._translate_role(p.user_role)

        # 页脚
        doc.add_paragraph('')
        footer = doc.add_paragraph('请及时确认参会状态，如有冲突请提前告知。')
        footer.add_run(f'\n\n生成时间：{datetime.now().strftime(DATETIME_CHINESE_SIMPLE)}')

        doc.save(filepath)

    from typing import Optional
    from datetime import datetime

    # 假设已有相关导入：DocxDocument、TABLE_STYLE、DATETIME_CHINESE_SIMPLE、Meeting、Transcription

    def _build_minutes_docx(self, meeting: Meeting, transcriptions: Optional[Transcription], filepath: str) -> None:
        """构建会议纪要Word文档"""
        doc = DocxDocument()

        # 1. 生成标题
        self._add_minutes_title(doc)

        # 2. 生成会议基本信息表格
        self._add_minutes_basic_info(doc, meeting)

        # 3. 生成会议内容（转录文本）
        if transcriptions:
            self._add_minutes_content(doc, transcriptions)
            # 4. 生成行动项汇总
            self._add_minutes_action_items(doc, transcriptions)
            # 5. 生成重要决议
            self._add_minutes_decisions(doc, transcriptions)

        # 6. 生成页脚
        self._add_minutes_footer(doc)

        # 保存文档
        doc.save(filepath)

    # -------------------------- 拆分的子函数 --------------------------
    def _add_minutes_title(self, doc: DocxDocument) -> None:
        """添加会议纪要标题"""
        title = doc.add_heading('会议摘要', 0)
        title.alignment = 1

    def _add_minutes_basic_info(self, doc: DocxDocument, meeting: Meeting) -> None:
        """添加会议基本信息表格"""
        doc.add_heading('会议基本信息', level=1)
        details_table = doc.add_table(rows=4, cols=2)
        details_table.style = TABLE_STYLE

        # 整理会议基础数据（解耦数据准备与渲染）
        details_data = [
            ('会议主题', meeting.title),
            ('会议时间', meeting.date_time.strftime(DATETIME_CHINESE_SIMPLE)),
            ('会议地点', meeting.location or '线上会议'),
            ('参会人数', str(len(meeting.participants)))
        ]

        # 填充表格
        for i, (label, value) in enumerate(details_data):
            cells = details_table.rows[i].cells
            cells[0].text = label
            cells[1].text = value

    def _add_minutes_content(self, doc: DocxDocument, transcriptions: Transcription) -> None:
        """添加会议内容（处理转录文本）"""
        doc.add_heading('会议内容', level=1)
        current_speaker = None

        # 修复原逻辑：speaker_name 与 speaker_id 混淆问题
        if transcriptions.speaker_name and transcriptions.speaker_name != current_speaker:
            current_speaker = transcriptions.speaker_name
            doc.add_heading(f'{current_speaker}:', level=3)

        # 处理带👤标记的转录文本
        self._process_transcription_text(doc, transcriptions.text_message)

    def _process_transcription_text(self, doc: DocxDocument, text_message: str) -> None:
        """处理转录文本，解析时间戳和内容"""
        if '👤' in text_message:
            parts = [part.strip() for part in text_message.split('👤') if part.strip()]
            for part in parts:
                cleaned_text = part.replace('"', '')
                time_start = cleaned_text.find('[')
                time_end = cleaned_text.find(']')

                if time_start != -1 and time_end != -1:
                    # 提取时间戳和纯文本内容
                    timestamp = f"[{cleaned_text[time_start + 1:time_end].strip()}]"
                    text_content = f"{cleaned_text[:time_start].strip()} {cleaned_text[time_end + 1:].strip()}"
                    doc.add_paragraph(f'{timestamp}   {text_content}')
                else:
                    doc.add_paragraph(f' {cleaned_text}')
        else:
            doc.add_paragraph(text_message)

    def _add_minutes_action_items(self, doc: DocxDocument, transcriptions: Transcription) -> None:
        """添加行动项汇总"""
        if transcriptions.is_action_item:
            doc.add_heading('行动项汇总', level=1)
            doc.add_paragraph(f'1. {transcriptions.text_message}', style='List Number')

    def _add_minutes_decisions(self, doc: DocxDocument, transcriptions: Transcription) -> None:
        """添加重要决议"""
        if transcriptions.is_decision:
            doc.add_heading('重要决议', level=1)
            doc.add_paragraph(f'1. {transcriptions.text_message}', style='List Number')

    def _add_minutes_footer(self, doc: DocxDocument) -> None:
        """添加会议纪要页脚"""
        doc.add_paragraph('')
        doc.add_paragraph(f'会议摘要生成时间：{datetime.now().strftime(DATETIME_CHINESE_SIMPLE)}')

    async def generate_notification(self, meeting: Meeting) -> str:
        """生成会议通知Word文档"""
        return self._save_and_upload_file(
            "会议通知",
            meeting,
            "docx",
            lambda path: self._build_notification_docx(meeting, path)
        )

    async def generate_minutes(self, meeting: Meeting, transcriptions: Transcription) -> str:
        """生成会议纪要Word文档"""
        return self._save_and_upload_file(
            "会议摘要",
            meeting,
            "docx",
            lambda path: self._build_minutes_docx(meeting, transcriptions, path)
        )


# 对外提供统一入口（可选）
class DocumentService(object):
    """统一文档服务入口（兼容原有调用方式）"""

    def __init__(self)->None:
        self.pdf_service = PDFDocumentService()
        self.docx_service = DocxDocumentService()

    async def generate_notification(self, meeting: Meeting)-> dict[str, Optional[str]]:
        """生成会议通知（Word+PDF）"""
        word_path = await self.docx_service.generate_notification(meeting)
        # pdf_path = await self.pdf_service.generate_notification(meeting)
        return {"word": word_path}

    async def generate_minutes(self, meeting: Meeting, transcriptions: Transcription):
        """生成会议纪要（Word+PDF）"""
        word_path = await self.docx_service.generate_minutes(meeting, transcriptions)
        # pdf_path = await self.pdf_service.generate_minutes(meeting, transcriptions)
        return {"word": word_path}
