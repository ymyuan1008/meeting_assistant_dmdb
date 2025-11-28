import openpyxl
from openpyxl.styles import Alignment, Font
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Generator, Optional, Tuple, Union
import logging
from contextlib import contextmanager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import re

def extract_row_number(cell_ref: str) ->int:
    """从单元格引用中提取行号，如 'A1' -> 1, 'Y2' -> 2"""
    # 使用正则表达式提取数字部分
    match = re.search(r'\d+', cell_ref)
    if match:
        return int(match.group())
    return 1  # 默认值


class ExcelService(object):
    """通用Excel生成工具，支持自定义表头、标题、合并单元格及数据格式"""

    def __init__(self, output_dir: str = "./uploads")->None:
        self.output_dir = Path(output_dir)
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _excel_worker(self, filepath: Path) -> Generator[openpyxl.Workbook, None, None]:
        """上下文管理器：安全处理Excel工作簿的创建、保存和关闭"""
        wb = openpyxl.Workbook()
        try:
            yield wb
            wb.save(filepath)
            logger.info(f"Excel文件已保存至: {filepath}")
        except Exception as e:
            logger.error(f"Excel处理失败: {str(e)}")
            if filepath.exists():
                filepath.unlink()  # 删除不完整文件
            raise
        finally:
            wb.close()

    def _auto_adjust_column_width(self, worksheet: openpyxl.worksheet.worksheet,
                                  min_width: int = 8, max_width: int = 50) -> None:
        """
        自动调整列宽（兼容合并单元格，基于单元格内容长度）
        :param worksheet: 工作表对象
        :param min_width: 最小列宽
        :param max_width: 最大列宽
        """
        try:
            # 获取最大列索引（避免遍历空列）
            max_col = worksheet.max_column
            if max_col == 0:
                return

            # 按列索引遍历（1-based）
            for col_idx in range(1, max_col + 1):
                max_length = 0
                column_letter = openpyxl.utils.get_column_letter(col_idx)  # 通过索引获取列字母

                # 遍历当前列的所有行
                for row_idx in range(1, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)

                    # 跳过合并单元格（MergedCell没有value属性）
                    if isinstance(cell, openpyxl.cell.cell.MergedCell):
                        continue

                    if cell.value is not None:
                        # 计算内容长度（中文按2个字符，英文/数字按1个字符）
                        value_str = str(cell.value)
                        length = sum(2 if '\u4e00' <= c <= '\u9fff' else 1 for c in value_str)
                        max_length = max(max_length, length)

                # 调整列宽（预留2个字符的余量）
                adjusted_width = min(max_length + 2, max_width)
                worksheet.column_dimensions[column_letter].width = max(adjusted_width, min_width)

        except Exception as e:
            logger.warning(f"自动调整列宽失败: {str(e)}")

    def _generate_filename(self, prefix: str = "data") -> str:
        """
        生成带时间戳的唯一文件名
        :param prefix: 文件名前缀
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.xlsx"


    def create_excel(
            self,
            data: list[Union[List, Dict]],  # 数据列表（支持列表或字典格式）
            # 表头列表（如["姓名", "年龄"]）
            headers: list[str],
            sheet_name: str = "Sheet1",  # 工作表名称
            title: Optional[str] = None,  # 表格标题（None则不设置）
            title_merge_range: str = "A1:G1",  # 标题合并范围（如"A1:C1"）
            # 额外合并单元格（如[("A2:B2", "姓名："), ...]）
            merge_cells: Optional[list[Tuple[str, str]]] = None,
            wrap_text_columns: Optional[list[int]] = None,  # 需要自动换行的列索引（从1开始）
            filename_prefix: str = "data",  # 文件名前缀
            date_format_columns: Optional[list[int]] = None  # 需要日期格式化的列索引（从1开始）
    ) -> Path:
        """
        创建通用Excel文件
        :param data: 数据列表，支持两种格式：
                     - 列表格式：[[值1, 值2, ...], [值1, 值2, ...]]（与表头顺序对应）
                     - 字典格式：[{"表头1": 值1, "表头2": 值2, ...}, ...]
        :param headers: 表头列表（决定列顺序和数量）
        :param sheet_name: 工作表名称
        :param title: 表格标题（位于最上方）
        :param title_merge_range: 标题合并的单元格范围（如"A1:G1"）
        :param merge_cells: 额外合并单元格配置，格式为[(合并范围, 单元格值), ...]
        :param wrap_text_columns: 需要自动换行的列索引（从1开始，如[4,5]表示第4、5列）
        :param filename_prefix: 生成文件名的前缀
        :param date_format_columns: 需要日期格式化的列索引（自动转换为"%Y-%m-%d"格式）
        :return: 生成的Excel文件路径
        """
        try:
            # 生成文件路径
            filename = self._generate_filename(prefix=filename_prefix)
            filepath = self.output_dir / filename

            with self._excel_worker(filepath) as wb:
                ws = wb.active
                ws.title = sheet_name

                # 跟踪当前数据起始行（根据标题和合并单元格动态调整）
                current_row = 1

                # 1. 设置标题（如果需要）
                if title:
                    ws.merge_cells(title_merge_range)
                    title_cell = ws[title_merge_range.split(':')[0]]  # 合并范围的左上角单元格
                    title_cell.value = title
                    title_cell.font = Font(bold=True, size=14, name="微软雅黑")
                    title_cell.alignment = Alignment(horizontal="center", vertical="center")
                    current_row += 1  # 标题占1行

                # 2. 设置额外合并单元格（如姓名、职务行）
                if merge_cells:
                    for merge_range, value in merge_cells:
                        ws.merge_cells(merge_range)
                        merge_cell = ws[merge_range.split(':')[0]]
                        merge_cell.value = value
                        merge_cell.alignment = Alignment(horizontal="center", vertical="center")
                    # 计算合并单元格占用的行数（取合并范围中的最大行号）
                    #max_merge_row = max(int(range_str.split(':')[-1][1:]) for range_str, _ in merge_cells)
                    max_merge_row = max(extract_row_number(range_str.split(':')[-1]) for range_str, _ in merge_cells)
                    current_row = max_merge_row + 1

                # 3. 设置表头
                for col_idx, header in enumerate(headers, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=header)
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                current_row += 1  # 表头占1行

                # 4. 填充数据
                for row_data in data:
                    # 处理字典格式数据（转换为与表头顺序一致的列表）
                    if isinstance(row_data, dict):
                        row_values = [row_data.get(header, "") for header in headers]
                    else:
                        row_values = row_data  # 列表格式直接使用

                    # 填充一行数据
                    for col_idx, value in enumerate(row_values, 1):
                        # 日期格式化处理
                        if date_format_columns and col_idx in date_format_columns:
                            if value is not None:
                                try:
                                    # 转换为日期字符串
                                    if isinstance(value, datetime):
                                        value = value.strftime("%Y-%m-%d")
                                    else:
                                        value = str(value)  # 非日期类型直接转字符串
                                except Exception as e:
                                    logger.warning(f"列{col_idx}日期格式化失败: {str(e)}")

                        cell = ws.cell(row=current_row, column=col_idx, value=value)
                        # 设置自动换行
                        if wrap_text_columns and col_idx in wrap_text_columns:
                            cell.alignment = Alignment(wrap_text=True)

                    current_row += 1

                # 5. 自动调整列宽
                self._auto_adjust_column_width(ws)

            logger.info(f"Excel文件创建成功: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"创建Excel文件失败: {str(e)}")
            raise


# ------------------------------
# 使用示例
# ------------------------------
def create_work_log(sample_data: list[Dict]):
    # 1. 初始化生成器
    excel_gen = ExcelService(output_dir="./uploads")

    # 2. 准备数据（支持列表或字典格式）
    sample_data = [
        {"日期": datetime(2023, 10, 1), "工作单位": "技术部", "工作内容": "开发Excel工具类\n处理各种边缘情况",
         "工作成效":"未知说话人:然后我这个服务器再发到那个第三方，啊没有我通过那代理去转，转就转个意思 👤 说话人A: ",
         "工时": 8,"备注":"林新"},
        {"日期": datetime(2023, 10, 2), "工作单位": "产品部", "工作内容": "需求评审会议",
         "工作成效":"未知说话人:然后我这个服务器再发到那个第三方，啊没有我通过那代理去转，转就转个意思 👤 说话人A: ",
         "工时": 4,"备注":"林新"},
    ]

    # 3. 定义表头（决定列顺序）
    headers = ["日期", "工作单位", "工作内容", "工时","工作成效","工时","备注"]

    # 4. 定义合并单元格（可选）
    merge_cells = [
        ("A2:B2", "姓名：张三"),
        ("C2:G2", "所任职企业及职务：技术部"),
    ]

    # 5. 生成Excel
    excel_gen.create_excel(
        data=sample_data,
        headers=headers,
        sheet_name="工作记录",
        title="员工工作台账",
        title_merge_range="A1:G1",  # 标题合并A1到D1
        merge_cells=merge_cells,
        wrap_text_columns=[3],  # 第3列（工作内容）自动换行
        date_format_columns=[1],  # 第1列（日期）自动格式化
        filename_prefix="工作记录"
    )

def create_ledger_info(sample_data: list[Dict]):
    # 1. 初始化生成器
    excel_gen = ExcelService(output_dir="./uploads")

    # 2. 准备数据（支持列表或字典格式）
    sample_data = sample_data

    # 3. 定义表头（决定列顺序）
    headers = ["议题编号（内部使用）", "议题名称","议题提出部门","适用治理主体权责清单文件名及文号","适用治理主体权责清单事项编号（含三重一大编号）及具体事项",
               "议题决策程序(根据权责清单确定)","三重一大分类(根据权责清单中的三重一大编号判断)",
               "三重一大系统事项编码*（按三重一大系统《企业'三重一大'事项清单采集指标》事项清单填写）","议题类型1（按权责清单中的'业务领域'填写）",
               "议题类型2","议题类型3","投资类议题金额（万元）","投资类议题是否开展专项调研","投资类议题是否开展重大投资项目评价及反馈","是否董事会授权","议题类型（原一览表要求）",
               "是否涉及合规审核","是否涉及职工权益","是否属于依托治理型行权管控事项","是否党委前置研究讨论","是否召开专门委员会",
               "是否报国资委*","会议时间*","会议名称*","会议形式*","主持人*","参会人*","领导参会详情",
               "领导请假情况","应到人数","实到人数","投票同意","投票反对","投票弃权","投票结果",
               "是否涉及回避原则","是否满足出席人数要求（原一览表要求）","纪委书记是否列席","总法律顾问/合规官是否列席","是否召开沟通会","列席部门/单位、具体人员"]



    # 4. 定义合并单元格（可选）
    merge_cells = [
        ("A2:AY2", "统计时间：2025年11月6日 "),
        ("A3:D3", "基本信息 "),
        ("E3:W3", "行权信息 "),
        ("X3:AY3", "会议信息 ")
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
        title_merge_range="A1:AY1",  # 标题合并A1到H1
        merge_cells=merge_cells,
        wrap_text_columns=[4],  # 第4列（工作内容）自动换行
        filename_prefix="台账登记"
    )


if __name__ == "__main__":
    create_work_log("hello world")
