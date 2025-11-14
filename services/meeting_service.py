# 标准库
import uuid
import os

from datetime import datetime, timezone
from typing import List, Optional, Dict
from loguru import logger
import pytz
from pathlib import Path


# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import func, select, case , distinct, literal,cast,String
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from fastapi import UploadFile


# 自定义类
from  models import Meeting, Participant, Agendas, Attachment
from  models import Transcription,PersonSign, User, TranscriptionText
from services.excel_service import ExcelService

from schema import MeetingCreate, TranscriptionCreate,MeetingUpdate, AttachmentCreate, AttachmentUpdate
from schema import  DailyWorkResponse, MeetingAgendaResponse, MeetingResponse,MeetingLedgerResponse


shanghai_tz = pytz.timezone('Asia/Shanghai')

# 配置
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf','.doc', '.docx', '.txt'}

# 创建上传目录
Path(UPLOAD_DIR).mkdir(exist_ok=True)

def validate_file_extension(filename: str):
    """验证文件扩展名"""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}。允许的类型: {', '.join(ALLOWED_EXTENSIONS)}"
        )

def generate_safe_filename(original_filename: str) -> str:
    """生成安全的文件名"""
    ext = Path(original_filename).suffix
    unique_id = uuid.uuid4().hex
    return f"{unique_id}{ext}"

def create_work_log(sample_data: List[Dict]):
    # 1. 初始化生成器
    excel_gen = ExcelService(output_dir="./uploads")

    # 2. 准备数据（支持列表或字典格式）
    sample_data = sample_data

    # 3. 定义表头（决定列顺序）
    headers = ["会议编号", "日期", "工作单位","工作事项",  "工作内容",  "工作成效", "工时", "备注"]

    # 4. 定义合并单元格（可选）
    merge_cells = [
        ("A2:C2", "姓名： "),
        ("D2:H2", "所任职企业及职务： "),
    ]

    title_style = {
        "font": {"bold": True},  # 核心：字体加粗
        # 可选：补充其他样式（如字体大小、颜色等）
        # "font_size": 14,
        # "font_color": "000000"
    }

    # 5. 生成Excel
    excel_gen.create_excel(
        data=sample_data,
        headers=headers,
        sheet_name="履职工作日志",
        title="履职工作日志（管理员的权限）",
        title_merge_range="A1:H1",  # 标题合并A1到H1
        merge_cells=merge_cells,
        wrap_text_columns=[3],  # 第3列（工作内容）自动换行
        date_format_columns=[2],  # 第1列（日期）自动格式化
        filename_prefix="履职工作日志"
    )

def create_ledger_info(sample_data: List[Dict]):
    # 1. 初始化生成器
    excel_gen = ExcelService(output_dir="./uploads")

    # 2. 准备数据（支持列表或字典格式）
    sample_data = sample_data

    # 3. 定义表头（决定列顺序）
    headers = ["议题编号（内部使用）", "议题名称","议题提出部门","适用治理主体权责清单文件名及文号","适用治理主体权责清单事项编号（含三重一大编号）及具体事项",
               "议题决策程序(根据权责清单确定)","三重一大分类(根据权责清单中的三重一大编号判断)","三重一大系统事项编码*（按三重一大系统《企业'三重一大'事项清单采集指标》事项清单填写）","议题类型1（按权责清单中的'业务领域'填写）",
               "议题类型2","议题类型3","投资类议题金额（万元）","投资类议题是否开展专项调研","投资类议题是否开展重大投资项目评价及反馈","是否董事会授权","议题类型（原一览表要求）",
               "是否涉及合规审核","是否涉及职工权益","是否属于依托治理型行权管控事项","是否党委前置研究讨论","是否召开专门委员会","是否报国资委*","会议时间*","会议名称*","会议形式*","主持人*","参会人*","领导参会详情",
               "领导请假情况","应到人数","实到人数","投票同意","投票反对","投票弃权","投票结果","是否涉及回避原则","是否满足出席人数要求（原一览表要求）","纪委书记是否列席","总法律顾问/合规官是否列席","是否召开沟通会","列席部门/单位、具体人员"]


    #"议题名称", "议题提出部门", "三重一大分类", "议题类型1", "议题类型2", "议题类型3", "是否董事会授权", "是否上报国资委", "会议时间", "会议名称", "会议形式", "主持人", "参会人", "应到人数", "实到人数"
    # 4. 定义合并单元格（可选）
    merge_cells = [
        ("A2:AP2", "统计时间：2025年11月6日 "),
        ("A3:D3", "基本信息 "),
        ("E3:W3", "行权信息 "),
        ("X3:AP3", "会议信息 ")
    ]

    title_style = {
        "font": {"bold": True},  # 核心：字体加粗
        # 可选：补充其他样式（如字体大小、颜色等）
        "font_size": 20,
        # "font_color": "000000"
    }


    excel_gen.create_excel(
        data=sample_data,
        headers=headers,
        sheet_name="子表3-董事会会议",
        title="南网数研院2025年董事会会议议题清单",
        title_merge_range="A1:AP1",  # 标题合并A1到H1
        merge_cells=merge_cells,
        wrap_text_columns=[4],  # 第4列（工作内容）自动换行
        filename_prefix="台账登记管理"
    )


class MeetingService(object):
    async def create_meeting(self, db: Session, meeting_data: MeetingCreate, user_id: str) -> MeetingAgendaResponse:
        """Create a new meeting with participants and attachments"""
        try:
            # Create meeting
            meeting = Meeting(
                id=str(uuid.uuid4()),
                title=meeting_data.title,
                description=meeting_data.description,
                date_time=meeting_data.date_time,
                location=meeting_data.location,
                duration_minutes=meeting_data.duration_minutes,
                status="scheduled",
                created_by=user_id,
                created_at=datetime.now(shanghai_tz)
            )
            db.add(meeting)
            db.flush()  # 获取meeting.id

            # 创建议程
            for agenda_data in meeting_data.agendas:
                db_agenda = Agendas(
                    agenda_name=agenda_data.agenda_name,
                    meeting_form=agenda_data.meeting_form,
                    meeting_id=meeting.id,
                    is_board_meeting=agenda_data.is_board_meeting,
                    three_important=agenda_data.three_important,
                    topic_type1=agenda_data.topic_type1,
                    topic_type2=agenda_data.topic_type2,
                    topic_type3=agenda_data.topic_type3,
                    is_escalation=agenda_data.is_escalation,
                    created_by = agenda_data.created_by  # 添加创建人字段
                )
                db.add(db_agenda)

            # Create participants
            for participant_data in meeting_data.participants:
                user = db.query(User).filter(User.name == participant_data.name).first()
                if not user:
                    raise ValueError(f"用户 '{participant_data.name}' 不存在，请检查姓名是否正确")
                participant = Participant(
                    id=str(uuid.uuid4()),
                    meeting_id=meeting.id,
                    user_code=str(user.id),
                    name=participant_data.name,
                    email=participant_data.email,
                    user_role=participant_data.user_role,
                    is_required=participant_data.is_required,
                    created_at=datetime.now(shanghai_tz)
                )
                db.add(participant)

            # 处理附件（从上传的文件创建）
            for attachment_data in meeting_data.attachments:
                attachment = Attachment(
                    id=str(uuid.uuid4()),
                    meeting_id=meeting.id,
                    file_name=attachment_data['file_name'],  # 改为字典访问方式
                    file_path=attachment_data['file_path'],
                    file_size=attachment_data['file_size'],
                    download_url=attachment_data['download_url'],
                    content_type=attachment_data['content_type'],
                    uploaded_by=attachment_data['uploaded_by'],
                    uploaded_at=datetime.now(shanghai_tz)
                )
                db.add(attachment)

            db.commit()
            db.refresh(meeting)
            return meeting

        except Exception as e:
            db.rollback()
            logger.error(f"创建会议服务层错误: {str(e)}")
            raise

    async def get_daily_work(
            self,
            db: Session,
            current_user_id: str,
            participants_list: List[str] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[DailyWorkResponse]:
        """获取用户会议信息 - 适配达梦数据库"""
        try:
            # 获取用户角色
            user_role = db.query(User.user_role).filter(
                User.id == current_user_id).scalar() if current_user_id else None
            logger.info(f"查询用户 {current_user_id} 的会议信息，角色: {user_role}")

            # 权限控制
            if user_role != "admin":
                logger.info(f"用户 {current_user_id} 非admin角色，无权限查询数据")
                return []

            # 处理参与者列表为空的情况
            if not participants_list:
                # 为空时不过滤参与者，查询所有会议
                query = db.query(
                    Meeting.id,
                    Meeting.date_time,
                    Meeting.title,
                    # 达梦使用listagg进行分组拼接，distinct去重，分隔符为逗号
                    func.listagg(func.distinct(Agendas.agenda_name), ',').within_group(Agendas.agenda_name).label(
                        'agenda'),
                    func.listagg(func.distinct(Transcription.text_message), ',').within_group(
                        Transcription.text_message).label('text_message'),
                    # 达梦需显式转换为浮点型避免整数除法取整
                    (Meeting.duration_minutes / 60).label('duration_minutes'),
                    func.listagg(func.distinct(User.name), ',').within_group(User.name).label('participant_names'),
                    func.listagg(func.distinct(User.company), ',').within_group(User.company).label('company_names')
                ).join(Participant, Meeting.id == Participant.meeting_id) \
                    .join(User, Participant.user_code == User.id) \
                    .join(Agendas, Agendas.meeting_id == Meeting.id) \
                    .join(Transcription, Meeting.id == Transcription.meeting_id)
            else:
                # 不为空时过滤参与者
                query = db.query(
                    Meeting.id,
                    Meeting.date_time,
                    Meeting.title,
                    func.listagg(func.distinct(Agendas.agenda_name), ',').within_group(Agendas.agenda_name).label(
                        'agenda'),
                    func.listagg(func.distinct(Transcription.text_message), ',').within_group(
                        Transcription.text_message).label('text_message'),
                    (Meeting.duration_minutes/ 60).label('duration_minutes'),
                    func.listagg(func.distinct(User.name), ',').within_group(User.name).label('participant_names'),
                    func.listagg(func.distinct(User.company), ',').within_group(User.company).label('company_names')
                ).join(Participant, Meeting.id == Participant.meeting_id) \
                    .join(User, Participant.user_code == User.id) \
                    .join(Agendas, Agendas.meeting_id == Meeting.id) \
                    .join(Transcription, Meeting.id == Transcription.meeting_id) \
                    .filter(Participant.user_code.in_(participants_list))  # 过滤参与者

            # 统一添加 GROUP BY、排序和分页
            query = query.group_by(
                Meeting.id,
                Meeting.date_time,
                Meeting.title,
                Meeting.duration_minutes  # 达梦要求GROUP BY包含所有非聚合列
            )

            # 执行查询并处理结果
            results = query.all()

            meetings = []
            for row in results:
                meetings.append({
                    'meeting_id': row.id,
                    'date_time': row.date_time,
                    'title': row.title,
                    'agenda': row.agenda,
                    'text_message': row.text_message,
                    'duration_minutes': row.duration_minutes,
                    # 处理空值（达梦拼接空值可能返回空字符串而非None）
                    'participant_names': row.participant_names.split(
                        ',') if row.participant_names and row.participant_names != '' else [],
                    'company_names': row.company_names.split(
                        ',') if row.company_names and row.company_names != '' else []
                })

            logger.info(f"成功查询到 {len(meetings)} 个会议")
            return meetings

        except Exception as e:
            logger.error(f"查询会议失败（用户: {current_user_id}），错误: {str(e)}")
            raise

    async def get_ledger_info(
            self,
            db: Session,
            current_user_id: str
    ) -> list[MeetingLedgerResponse]:
        """获取用户会议信息 - 适配达梦数据库"""
        try:
            # 获取用户角色
            user_role = db.query(User.user_role).filter(
                User.id == current_user_id).scalar() if current_user_id else None
            logger.info(f"查询用户 {current_user_id} 的会议信息，角色: {user_role}")

            # 权限控制
            if user_role != "admin":
                logger.info(f"用户 {current_user_id} 非admin角色，无权限查询数据")
                return []

            query = db.query(
                # 非聚合列（与 GROUP BY 严格对应）
                Agendas.agenda_id,
                Agendas.agenda_name,
                User.company,
                Agendas.three_important,
                Agendas.topic_type1,
                Agendas.topic_type2,
                Agendas.topic_type3,
                Agendas.is_board_meeting,
                Agendas.is_escalation,
                Meeting.date_time,
                Meeting.title,
                literal("线上会议").label("meeting_type"),  # 常量：线上会议
                literal("未知").label("host_user"),  # 常量：未知
                # 聚合函数列（达梦用listagg替换group_concat）
                func.listagg(func.distinct(PersonSign.name), ',').label('participant_names'),  # 拼接参会人姓名，去重
                func.count(func.distinct(PersonSign.user_code)).label('planned_attendance'),  # 达梦支持count(distinct)
                func.sum(PersonSign.is_signed).label('actual_attendance')  # 求和逻辑不变
            ).select_from(Meeting) \
                .outerjoin(User, Meeting.created_by == User.id) \
                .outerjoin(PersonSign, Meeting.id == PersonSign.meeting_id) \
                .join(Agendas, Meeting.id == Agendas.meeting_id) \
                .group_by(
                Agendas.agenda_id,
                Agendas.agenda_name,
                User.company,
                Agendas.three_important,
                Agendas.topic_type1,
                Agendas.topic_type2,
                Agendas.topic_type3,
                Agendas.is_board_meeting,
                Agendas.is_escalation,
                Meeting.date_time,
                Meeting.title
            ) \
                .filter(Agendas.agenda_id.isnot(None))

            # 执行查询
            ledger_results = query.all()

            ledger_info = []
            for row in ledger_results:
                # 处理participant_names空值（达梦可能返回空字符串而非None）
                participant_names = row.participant_names.split(
                    ',') if row.participant_names and row.participant_names != '' else []
                ledger_info.append({
                    "agenda_id": row.agenda_id,
                    "agenda_name": row.agenda_name,
                    "company": row.company,
                    "three_important": row.three_important,
                    "topic_type1": row.topic_type1,
                    "topic_type2": row.topic_type2,
                    "topic_type3": row.topic_type3,
                    "is_board_meeting": row.is_board_meeting,
                    "is_escalation": row.is_escalation,
                    "meeting_time": row.date_time,
                    "meeting_type": row.meeting_type,
                    "meeting_title": row.title,
                    "host_user": row.host_user,
                    "participant_user": participant_names,  # 转换为列表
                    "planned_attendance": row.planned_attendance,
                    "actual_attendance": row.actual_attendance
                })

            logger.info(f"会议台账查询成功，返回 {len(ledger_info)} 条记录")
            return ledger_info

        except Exception as e:
            logger.error(f"会议台账查询失败：{str(e)}", exc_info=True)
            raise


    async def export_daily_work(
            self,
            db: Session,
            current_user_id: str,
            participants_list: List[str] = None,
            meeting_ids: List[str] = None
    ) -> dict[str, str]:
        """获取用户会议信息 - 修复GROUP BY问题"""
        try:
            # 获取用户角色
            user_role = db.query(User.user_role).filter(
                User.id == current_user_id).scalar() if current_user_id else None

            logger.info(f"查询用户 {current_user_id} 的会议信息，角色: {user_role}")

            # 权限控制
            if user_role != "admin":
                logger.info(f"用户 {current_user_id} 非admin角色，无权限查询数据")
                return []
            participants_list = participants_list

            if current_user_id not in participants_list:
                participants_list.append(current_user_id)

            # 构建查询 - 确保包含所有SELECT的列在GROUP BY中
            query = db.query(
                Meeting.id,
                Meeting.date_time,
                func.group_concat(func.distinct(User.company)).label('company_names'),
                Meeting.title,
                func.group_concat(func.distinct(Agendas.agenda_name)).label('agenda'),
                func.group_concat(func.distinct(Transcription.text_message)).label('text_message'),
                (Meeting.duration_minutes/60).label('duration_minutes'),
                func.group_concat(func.distinct(User.name)).label('participant_names')
            ).select_from(Meeting).join(Participant, Meeting.id == Participant.meeting_id) \
                .join(User, Participant.user_code == User.id) \
                .join(Agendas, Agendas.meeting_id == Meeting.id) \
                .join(Transcription, Meeting.id == Transcription.meeting_id).filter(
                Participant.user_code.in_(participants_list))

            # 关键：添加完整的 GROUP BY 子句
            query = query.group_by(
                Meeting.id,
                Meeting.date_time,  # SELECT 中的列
                Meeting.title,  # SELECT 中的列
                Meeting.duration_minutes  # SELECT 中的列
            ).order_by(Meeting.date_time.desc())

            # 执行查询
            if meeting_ids:
                results = query.filter(Meeting.id.in_(meeting_ids)).all()
            else:
                results = query.all()


            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"履职工作日志_{timestamp}.xlsx"
            file_path = './uploads/'+filename
            create_work_log(results)
            output_text = {}
            output_text["file_name"] = filename
            output_text["file_path"] = file_path
            return output_text

        except Exception as e:
            logger.error(f"Failed to retrieve meetings for user: {current_user_id}, error: {str(e)}")
            raise

    async def export_ledger_info(
            self,
            db: Session,
            current_user_id: str,
            agenda_ids: list[int]=None
    ) -> dict[str, str]:
        """获取用户会议信息 - 修复GROUP BY问题"""
        try:
            # 获取用户角色
            user_role = db.query(User.user_role).filter(
                User.id == current_user_id).scalar() if current_user_id else None

            logger.info(f"查询用户 {current_user_id} 的会议信息，角色: {user_role}")

            # 权限控制
            if user_role != "admin":
                logger.info(f"用户 {current_user_id} 非admin角色，无权限查询数据")
                return []

            agenda_ids = agenda_ids

            # 构建基础查询（公共部分）
            query = db.query(
                cast(Agendas.agenda_id, String).label("agenda_id"),
                Agendas.agenda_name,
                User.company,
                literal("").label("适用治理主体权责清单文件名及文号"),
                literal("").label("适用治理主体权责清单事项编号（含三重一大编号）及具体事项"),
                literal("").label("议题决策程序(根据权责清单确定)"),
                Agendas.three_important,
                literal("").label("三重一大系统事项编码*（按三重一大系统《企业'三重一大'事项清单采集指标》事项清单填写）"),
                Agendas.topic_type1,
                Agendas.topic_type2,
                Agendas.topic_type3,
                literal(0).label("投资类议题金额（万元）"),
                literal("").label("投资类议题是否开展专项调研"),
                literal("").label("投资类议题是否开展重大投资项目评价及反馈"),
                case(
                    (Agendas.is_board_meeting == 1, "是"),  # 去掉外层的[]
                    else_="否"
                ).label("is_board_meeting"),
                literal("").label("议题类型（原一览表要求）"),
                literal("").label("是否涉及合规审核"),
                literal("").label("是否涉及职工权益"),
                literal("").label("是否属于依托治理型行权管控事项"),
                literal("").label("是否党委前置研究讨论"),
                literal("").label("是否召开专门委员会"),
                case(
                    (Agendas.is_escalation == 1, "是"),
                    else_="否"
                ).label("is_escalation"),
                Meeting.date_time,
                Meeting.title,
                literal("线上会议").label("meeting_type"),
                literal("未知").label("host_user"),
                func.group_concat(PersonSign.name).label('participant_names'),
                literal("").label("领导参会详情"),
                literal("").label("领导请假情况"),
                func.count(distinct(PersonSign.user_code)).label('planned_attendance'),
                func.sum(PersonSign.is_signed).label('actual_attendance'),
                literal("").label("投票同意"),
                literal("").label("投票反对"),
                literal("").label("投票弃权"),
                literal("").label("投票结果"),
                literal("").label("是否涉及回避原则"),
                literal("").label("是否满足出席人数要求（原一览表要求）"),
                literal("").label("纪委书记是否列席"),
                literal("").label("总法律顾问/合规官是否列席"),
                literal("").label("是否召开沟通会"),
                literal("").label("列席部门/单位、具体人员")
            ).select_from(Meeting) \
                .join(Agendas, Meeting.id == Agendas.meeting_id) \
                .join(User, Meeting.created_by == User.id) \
                .outerjoin(PersonSign, Meeting.id == PersonSign.meeting_id) \
                .group_by(
                Agendas.agenda_id,
                Agendas.agenda_name,
                Agendas.three_important,
                Agendas.topic_type1,
                Agendas.topic_type2,
                Agendas.topic_type3,
                Agendas.is_board_meeting,
                Agendas.is_escalation,
                Meeting.date_time,
                Meeting.title,
                User.company
            )

            # 根据 agenda_ids 是否为空，动态添加过滤条件
            if agenda_ids:  # 非空列表时，添加 in 条件
                query = query.filter(Agendas.agenda_id.in_(agenda_ids))

            # 执行查询
            results = query.all()
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"台账登记管理_{timestamp}.xlsx"
            file_path = Path("./uploads") / filename


            create_ledger_info(results)
            output_text = {}
            output_text["file_name"] = filename
            output_text["file_path"] = file_path
            return output_text

        except Exception as e:
            logger.error(f"Failed to retrieve meetings for user: {current_user_id}, error: {str(e)}")
            raise

    async def get_meetings(self, db: Session, current_user_id: str) -> list[Meeting]:
        """Get all meetings - admin users see all, regular users see only their meetings"""
        # 查询用户角色
        try:
            current_user_id_str = str(current_user_id)
        except (TypeError, ValueError):
            current_user_id_str = None
        user_role = db.query(User.user_role).filter(User.id == current_user_id_str).scalar() if current_user_id_str is not None else None

        query = db.query(Meeting)

        # 如果不是管理员，添加参与者过滤条件
        if user_role != "admin":
            # 第一个查询：用户参与的会议
            query1 = (db.query(Meeting)
                      .join(Participant, Meeting.id == Participant.meeting_id)
                      .filter(Participant.user_code == current_user_id_str)
                      .distinct())

            # 第二个查询：用户创建的会议
            query2 = (db.query(Meeting)
                      .filter(Meeting.created_by == current_user_id_str))

            # 使用 UNION 合并两个查询
            query = query1.union(query2)

        # 统一按时间排序
        query = query.order_by(Meeting.date_time.desc())

        logger.info(f"User {current_user_id} (role: {user_role}) retrieved meetings")
        return query.all()

    async def get_meeting(self, db: Session, meeting_id: str, current_user_id: str) -> Optional[Meeting]:
        """Get a specific meeting by ID and validate user access using JOIN"""
        # 查询用户角色
        try:
            current_user_id_str = str(current_user_id)
        except (TypeError, ValueError):
            current_user_id_str = None
        user_role = db.query(User.user_role).filter(User.id == current_user_id_str).scalar() if current_user_id_str is not None else None
        query = db.query(Meeting)
        # 如果不是管理员，添加参与者验证条件
        if user_role != "admin":
            query = query.join(Participant, Meeting.id == Participant.meeting_id).filter(
                Participant.user_code == current_user_id_str)

        # 添加会议ID过滤条件
        meeting = query.filter(Meeting.id == meeting_id).first()
        return meeting

    async def get_meetings(self, db: Session, current_user_id: str) -> List[Meeting]:
        """获取当前用户可访问的会议列表
        - 管理员返回全部会议
        - 普通用户返回自己参与的会议
        """
        try:
            try:
                current_user_id_str = str(current_user_id)
            except (TypeError, ValueError):
                current_user_id_str = None

            user_role = (
                db.query(User.user_role)
                .filter(User.id == current_user_id_str)
                .scalar()
                if current_user_id_str is not None
                else None
            )

            query = db.query(Meeting)
            if user_role != "admin":
                query = (
                    query
                    .join(Participant, Meeting.id == Participant.meeting_id)
                    .filter(Participant.user_code == current_user_id_str)
                )

            # 简单排序，最近的会议在前
            query = query.order_by(Meeting.date_time.desc())
            return query.all()
        except Exception as e:
            # 保持最小实现，直接抛出以便上层捕获并记录
            raise e

    async def update_meeting(self,
                             meeting_id: str,
                             meeting_data: MeetingUpdate,
                             db: Session,
                             current_user_id: str) -> MeetingResponse:
        """Update a meeting with participants and attachments"""
        try:
            # 查询用户角色
            try:
                current_user_id_str = str(current_user_id)
            except (TypeError, ValueError):
                current_user_id_str = None
            user_role = (
                db.query(User.user_role)
                .filter(User.id == current_user_id_str)
                .scalar()
                if current_user_id_str is not None
                else None
            )

            query = db.query(Meeting)
            if user_role != "admin":
                query = query.join(Participant, Meeting.id == Participant.meeting_id).filter(
                    Participant.user_code == current_user_id_str)
            meeting = query.filter(Meeting.id == meeting_id).first()
            if not meeting:
                return None

            # Update meeting fields
            meeting.title = meeting_data.title
            meeting.description = meeting_data.description
            meeting.date_time = meeting_data.date_time
            meeting.location = meeting_data.location
            meeting.duration_minutes = meeting_data.duration_minutes
            meeting.updated_at = datetime.now(shanghai_tz)

            # 删除原有的参与者
            db.query(Participant).filter(Participant.meeting_id == meeting_id).delete()
            # 创建新的参与者
            for participant_data in meeting_data.participants:
                user = db.query(User).filter(User.name == participant_data.name).first()
                if not user:
                    raise ValueError(f"用户 '{participant_data.name}' 不存在，请检查姓名是否正确")
                participant = Participant(
                    id=str(uuid.uuid4()),
                    meeting_id=meeting_id,
                    user_code=str(user.id),
                    name=participant_data.name,
                    email=participant_data.email,
                    user_role=participant_data.user_role,
                    is_required=participant_data.is_required,
                    created_at=datetime.now(shanghai_tz)
                )
                db.add(participant)

            db.query(Agendas).filter(Agendas.meeting_id == meeting_id).delete()
            # 创建议程
            for agenda_data in meeting_data.agendas:
                db_agenda = Agendas(
                    agenda_name=agenda_data.agenda_name,
                    meeting_form=agenda_data.meeting_form,
                    meeting_id=meeting_id,
                    is_board_meeting=agenda_data.is_board_meeting,
                    three_important=agenda_data.three_important,
                    topic_type1=agenda_data.topic_type1,
                    topic_type2=agenda_data.topic_type2,
                    topic_type3=agenda_data.topic_type3,
                    is_escalation=agenda_data.is_escalation,
                    created_by=agenda_data.created_by  # 添加创建人字段
                )
                db.add(db_agenda)

            db.commit()
            db.refresh(meeting)
            return meeting

        except Exception as e:
            db.rollback()
            logger.error(f"更新会议服务层错误: {str(e)}")
            raise


    async def delete_meeting(self, db: Session, meeting_id: str, current_user_id: str) -> bool:
        """Delete a meeting"""
        # 查询用户角色
        try:
            current_user_id_str = str(current_user_id)
        except (TypeError, ValueError):
            current_user_id_str = None
            # 首先删除所有关联的附件记录
        db.query(Attachment).filter(Attachment.meeting_id == meeting_id).delete()
        # 删除所有关联的议程记录
        db.query(Agendas).filter(Agendas.meeting_id == meeting_id).delete()
        # 删除所有关联的参会人员记录
        db.query(PersonSign).filter(PersonSign.meeting_id == meeting_id).delete()
        user_role = db.query(User.user_role).filter(User.id == current_user_id_str).scalar() if current_user_id_str is not None else None
        query = db.query(Meeting)
        if user_role != "admin":
            query = (
                query
                .join(Participant, Meeting.id == Participant.meeting_id)
                .filter(Participant.user_code == current_user_id_str)
            )
        meeting = query.filter(Meeting.id == meeting_id).first()
        if not meeting:
            return False
        db.delete(meeting)
        db.commit()
        return True


    async def save_transcription(self, db: AsyncSession, transcription_data: TranscriptionCreate) -> Transcription:
        # 新增：查询会议是否存在（异步操作，必须加 await）
        # 关键：await 不可少
        from time import timezone
        meeting_result = await db.execute(
            select(Meeting).filter(Meeting.id == transcription_data.meeting_id)
        )
        meeting = meeting_result.scalars().first()
        if not meeting:
            raise ValueError(f"会议 {transcription_data.meeting_id} 不存在")
        # 验证必填字段（不变）
        if not all([transcription_data.meeting_id, transcription_data.speaker_id, transcription_data.text]):
            raise ValueError("meeting_id, speaker_id和text是必填字段")

        try:
            # 关键修复：用 async with 开启异步事务，自动管理提交/回滚
            transcription = Transcription(
                id=str(uuid.uuid4()),
                meeting_id=transcription_data.meeting_id,
                speaker_id=transcription_data.speaker_id,
                speaker_name=transcription_data.speaker_name,
                text=transcription_data.text,
                timestamp=transcription_data.timestamp or datetime.now(pytz.timezone('Asia/Shanghai')),
                confidence_score=transcription_data.confidence_score
            )
            # add 是同步方法，无需 await
            db.add(transcription)
            await db.commit()
            # 事务提交后，异步刷新对象（已加 await，正确）
            await db.refresh(transcription)
            return transcription

        except Exception as e:
            # 记录错误日志（建议用 logging 模块，而非 print）
            import logging
            logging.error(f"保存转录记录失败: {str(e)}")
            # 注：若用了 async with db.begin()，异常会自动回滚，无需手动 await db.rollback()
            # 重新抛出异常，让接口层捕获并返回 500 错误
            raise e

    async def get_meeting_transcriptions(self, db: Session, meeting_id: str) -> list[Transcription]:
        """Get all transcriptions for a meeting"""
        return db.query(TranscriptionText).filter(TranscriptionText.meeting_id == meeting_id).order_by(
            TranscriptionText.created_time.asc()).all()

    async def get_transcription_message(self, db: Session, meeting_id: str) -> Transcription:
        """Get all transcriptions for a meeting"""
        return db.query(Transcription).filter(Transcription.meeting_id == meeting_id).order_by(
            Transcription.created_time.desc()).first()

    async def update_meeting_status(self, db: Session, meeting_id: str, status: str) -> bool:
        """Update meeting status"""
        from time import timezone
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            return False

        meeting.status = status
        meeting.updated_at = datetime.now(pytz.timezone('Asia/Shanghai')) # Compliant

        db.commit()
        return True

    async def mark_action_items(self, db: Session, transcription_ids: list[str]) -> bool:
        """Mark transcriptions as action items"""
        transcriptions = db.query(Transcription).filter(
            Transcription.id.in_(transcription_ids)
        ).all()

        for transcription in transcriptions:
            transcription.is_action_item = True

        db.commit()
        return True

    async def mark_decisions(self, db: Session, transcription_ids: list[str]) -> bool:
        """Mark transcriptions as decisions"""
        transcriptions = db.query(Transcription).filter(
            Transcription.id.in_(transcription_ids)
        ).all()
        for transcription in transcriptions:
            transcription.is_decision = True
        db.commit()
        return True
