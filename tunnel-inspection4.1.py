"""
泸州龙透关隧道工程检验批划分系统 V4
基于TB10753-2018铁路隧道工程施工质量验收标准
支持多标准切换：高铁隧道、普通铁路、公路隧道、市政隧道、地铁隧道

Author: Matrix Agent
"""

import streamlit as st
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json
import math

st.set_page_config(
    page_title="泸州龙透关隧道检验批系统",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 多标准切换系统 ====================
class InspectionStandard(Enum):
    """验收标准枚举"""
    TB10753_2018 = "TB10753-2018"  # 高铁隧道
    TB10417 = "TB10417"            # 普通铁路
    JTG_F80 = "JTG F80"            # 公路隧道
    CJJ_37 = "CJJ 37"              # 市政隧道
    GB50299 = "GB 50299"           # 地铁隧道

# 标准基本信息
STANDARD_INFO = {
    InspectionStandard.TB10753_2018: {
        "name": "TB10753-2018",
        "full_name": "铁路隧道工程施工质量验收标准",
        "industry": "铁路工程-高铁隧道",
        "description": "适用于高速铁路隧道工程施工质量验收"
    },
    InspectionStandard.TB10417: {
        "name": "TB10417",
        "full_name": "铁路隧道工程施工质量验收标准",
        "industry": "铁路工程-普通铁路",
        "description": "适用于普通铁路隧道工程施工质量验收"
    },
    InspectionStandard.JTG_F80: {
        "name": "JTG F80",
        "full_name": "公路工程质量检验评定标准",
        "industry": "公路工程",
        "description": "适用于公路隧道工程质量检验评定"
    },
    InspectionStandard.CJJ_37: {
        "name": "CJJ 37",
        "full_name": "城市道路工程施工质量验收规范",
        "industry": "市政工程",
        "description": "适用于市政隧道工程质量验收"
    },
    InspectionStandard.GB50299: {
        "name": "GB 50299",
        "full_name": "地下铁道工程施工质量验收标准",
        "industry": "地铁工程",
        "description": "适用于地铁隧道工程质量验收"
    }
}

# 各标准的分部工程编码
SUBPROJECT_CODES_BY_STANDARD = {
    InspectionStandard.TB10753_2018: {
        "洞口工程": "01",
        "洞身开挖": "02", 
        "初期支护": "03",
        "二次衬砌": "04",
        "防排水": "05",
        "附属工程": "06"
    },
    InspectionStandard.TB10417: {
        "洞口工程": "01",
        "洞身开挖": "02",
        "初期支护": "03", 
        "二次衬砌": "04",
        "防排水": "05",
        "附属工程": "06"
    },
    InspectionStandard.JTG_F80: {
        "洞口工程": "01",
        "洞身开挖": "02",
        "初期支护": "03",
        "二次衬砌": "04",
        "防排水": "05",
        "附属工程": "06"
    },
    InspectionStandard.CJJ_37: {
        "土石方工程": "01",
        "结构工程": "02",
        "防排水工程": "03",
        "附属工程": "04"
    },
    InspectionStandard.GB50299: {
        "洞口工程": "01",
        "土方工程": "02",
        "初期支护": "03",
        "二次衬砌": "04",
        "防排水工程": "05",
        "附属工程": "06"
    }
}

# 各标准的开挖方法每循环进尺(m)
ADVANCE_PER_CYCLE_BY_STANDARD = {
    InspectionStandard.TB10753_2018: {
        "洞口": 0.0,
        "CD法": 0.8,
        "CRD法": 0.8,
        "双隔壁法": 0.8,
        "双隔壁法(8步)": 0.8,
        "全断面法": 1.6,
        "台阶法": 1.6,
        "环形开挖法": 1.2
    },
    InspectionStandard.TB10417: {
        "洞口": 0.0,
        "CD法": 0.8,
        "CRD法": 0.8,
        "双隔壁法": 0.8,
        "双隔壁法(8步)": 0.8,
        "全断面法": 1.6,
        "台阶法": 1.6,
        "环形开挖法": 1.2
    },
    InspectionStandard.JTG_F80: {
        "洞口": 0.0,
        "CD法": 0.8,
        "CRD法": 0.8,
        "双隔壁法": 0.8,
        "双隔壁法(8步)": 0.8,
        "全断面法": 1.8,
        "台阶法": 1.8,
        "环形开挖法": 1.5
    },
    InspectionStandard.CJJ_37: {
        "洞口": 0.0,
        "CD法": 0.8,
        "CRD法": 0.8,
        "双隔壁法": 0.8,
        "双隔壁法(8步)": 0.8,
        "全断面法": 2.0,
        "台阶法": 2.0,
        "环形开挖法": 1.5
    },
    InspectionStandard.GB50299: {
        "洞口": 0.0,
        "CD法": 0.6,
        "CRD法": 0.6,
        "双隔壁法": 0.6,
        "双隔壁法(8步)": 0.6,
        "全断面法": 1.2,
        "台阶法": 1.2,
        "环形开挖法": 1.0
    }
}

# 各标准的检验批最大长度限制(m)
BATCH_MAX_LENGTH_BY_STANDARD = {
    InspectionStandard.TB10753_2018: {
        "洞身开挖": 60,
        "初期支护": 60,
        "二次衬砌": 5,  # 浇筑段数
        "防排水": 100,
        "附属工程": 200
    },
    InspectionStandard.TB10417: {
        "洞身开挖": 80,
        "初期支护": 80,
        "二次衬砌": 6,
        "防排水": 100,
        "附属工程": 200
    },
    InspectionStandard.JTG_F80: {
        "洞身开挖": 50,
        "初期支护": 50,
        "二次衬砌": 4,
        "防排水": 100,
        "附属工程": 200
    },
    InspectionStandard.CJJ_37: {
        "土石方工程": 100,
        "结构工程": 6,
        "防排水工程": 100,
        "附属工程": 200
    },
    InspectionStandard.GB50299: {
        "土方工程": 40,
        "初期支护": 40,
        "二次衬砌": 5,
        "防排水工程": 80,
        "附属工程": 150
    }
}

# 获取当前选中的标准配置
def get_current_standard() -> InspectionStandard:
    """获取当前选中的验收标准"""
    if 'current_standard' not in st.session_state:
        st.session_state.current_standard = InspectionStandard.TB10753_2018
    return st.session_state.current_standard

def get_subproject_codes(standard: InspectionStandard = None) -> Dict[str, str]:
    """获取指定标准的分部工程编码"""
    if standard is None:
        standard = get_current_standard()
    return SUBPROJECT_CODES_BY_STANDARD.get(standard, SUBPROJECT_CODES_BY_STANDARD[InspectionStandard.TB10753_2018])

def get_advance_per_cycle(standard: InspectionStandard = None) -> Dict[str, float]:
    """获取指定标准的循环进尺"""
    if standard is None:
        standard = get_current_standard()
    return ADVANCE_PER_CYCLE_BY_STANDARD.get(standard, ADVANCE_PER_CYCLE_BY_STANDARD[InspectionStandard.TB10753_2018])

def get_batch_max_length(standard: InspectionStandard = None) -> Dict[str, float]:
    """获取指定标准的检验批最大长度"""
    if standard is None:
        standard = get_current_standard()
    return BATCH_MAX_LENGTH_BY_STANDARD.get(standard, BATCH_MAX_LENGTH_BY_STANDARD[InspectionStandard.TB10753_2018])

# ==================== TB10753-2018 标准完整分部分项定义 ====================
# 分部工程编码（TB10753-2018附录B完整版本 - 10个分部）
SUBPROJECT_CODES = {
    "洞口工程": "01",
    "超前支护": "02",
    "洞身开挖": "03",
    "初期支护": "04",
    "监控量测": "05",
    "二次衬砌": "06",
    "防排水": "07",
    "附属工程": "08",
    "盾构掘进": "09",
    "明洞工程": "10"
}

# 开挖方法对应的分项工程
# 每个循环的步骤数：
# - 台阶法: 2步骤（上台阶、下台阶）
# - CD法: 4步骤（左上、左下、右上、右下）
# - 全断面法: 1步骤
# - 双隔壁法: 6步骤（左上、左下、右上、右下、中上、中下）
# - 双隔壁法(8步): 8步骤（左上左中左下、右上右中右下、中上正中中下）
WORK_ITEM_BY_METHOD = {
    "台阶法": [
        {"name": "上台阶开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "上台阶支护", "code": "01", "分部": "初期支护", "步骤": 1},
        {"name": "下台阶开挖", "code": "02", "分部": "洞身开挖", "步骤": 2},
        {"name": "下台阶支护", "code": "02", "分部": "初期支护", "步骤": 2},
        {"name": "仰拱开挖", "code": "03", "分部": "洞身开挖", "步骤": 3},
        {"name": "仰拱支护", "code": "03", "分部": "初期支护", "步骤": 3},
        {"name": "仰拱衬砌", "code": "01", "分部": "二次衬砌", "步骤": 4},
        {"name": "二次衬砌", "code": "02", "分部": "二次衬砌", "步骤": 5},
    ],
    "CD法": [
        {"name": "左上导坑开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "左上导坑支护", "code": "01", "分部": "初期支护", "步骤": 1},
        {"name": "左下导坑开挖", "code": "02", "分部": "洞身开挖", "步骤": 2},
        {"name": "左下导坑支护", "code": "02", "分部": "初期支护", "步骤": 2},
        {"name": "右上导坑开挖", "code": "03", "分部": "洞身开挖", "步骤": 3},
        {"name": "右上导坑支护", "code": "03", "分部": "初期支护", "步骤": 3},
        {"name": "右下导坑开挖", "code": "04", "分部": "洞身开挖", "步骤": 4},
        {"name": "右下导坑支护", "code": "04", "分部": "初期支护", "步骤": 4},
        {"name": "仰拱开挖", "code": "05", "分部": "洞身开挖", "步骤": 5},
        {"name": "仰拱支护", "code": "05", "分部": "初期支护", "步骤": 5},
        {"name": "仰拱衬砌", "code": "01", "分部": "二次衬砌", "步骤": 6},
        {"name": "二次衬砌", "code": "02", "分部": "二次衬砌", "步骤": 7},
    ],
    "双隔壁法": [
        {"name": "左上导坑开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "左上导坑支护", "code": "01", "分部": "初期支护", "步骤": 1},
        {"name": "左下导坑开挖", "code": "02", "分部": "洞身开挖", "步骤": 2},
        {"name": "左下导坑支护", "code": "02", "分部": "初期支护", "步骤": 2},
        {"name": "右上导坑开挖", "code": "03", "分部": "洞身开挖", "步骤": 3},
        {"name": "右上导坑支护", "code": "03", "分部": "初期支护", "步骤": 3},
        {"name": "右下导坑开挖", "code": "04", "分部": "洞身开挖", "步骤": 4},
        {"name": "右下导坑支护", "code": "04", "分部": "初期支护", "步骤": 4},
        {"name": "中上导坑开挖", "code": "05", "分部": "洞身开挖", "步骤": 5},
        {"name": "中上导坑支护", "code": "05", "分部": "初期支护", "步骤": 5},
        {"name": "中下导坑开挖", "code": "06", "分部": "洞身开挖", "步骤": 6},
        {"name": "中下导坑支护", "code": "06", "分部": "初期支护", "步骤": 6},
        {"name": "仰拱开挖", "code": "07", "分部": "洞身开挖", "步骤": 7},
        {"name": "仰拱支护", "code": "07", "分部": "初期支护", "步骤": 7},
        {"name": "仰拱衬砌", "code": "01", "分部": "二次衬砌", "步骤": 8},
        {"name": "二次衬砌", "code": "02", "分部": "二次衬砌", "步骤": 9},
    ],
    "双隔壁法(8步)": [
        {"name": "左上导坑开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "左中导坑开挖", "code": "02", "分部": "洞身开挖", "步骤": 2},
        {"name": "左下导坑开挖", "code": "03", "分部": "洞身开挖", "步骤": 3},
        {"name": "左上导坑支护", "code": "01", "分部": "初期支护", "步骤": 1},
        {"name": "左中导坑支护", "code": "02", "分部": "初期支护", "步骤": 2},
        {"name": "左下导坑支护", "code": "03", "分部": "初期支护", "步骤": 3},
        {"name": "右上导坑开挖", "code": "04", "分部": "洞身开挖", "步骤": 4},
        {"name": "右中导坑开挖", "code": "05", "分部": "洞身开挖", "步骤": 5},
        {"name": "右下导坑开挖", "code": "06", "分部": "洞身开挖", "步骤": 6},
        {"name": "右上导坑支护", "code": "04", "分部": "初期支护", "步骤": 4},
        {"name": "右中导坑支护", "code": "05", "分部": "初期支护", "步骤": 5},
        {"name": "右下导坑支护", "code": "06", "分部": "初期支护", "步骤": 6},
        {"name": "中上导坑开挖", "code": "07", "分部": "洞身开挖", "步骤": 7},
        {"name": "正中导坑开挖", "code": "08", "分部": "洞身开挖", "步骤": 8},
        {"name": "中下导坑开挖", "code": "09", "分部": "洞身开挖", "步骤": 9},
        {"name": "中上导坑支护", "code": "07", "分部": "初期支护", "步骤": 7},
        {"name": "正中导坑支护", "code": "08", "分部": "初期支护", "步骤": 8},
        {"name": "中下导坑支护", "code": "09", "分部": "初期支护", "步骤": 9},
        {"name": "仰拱开挖", "code": "10", "分部": "洞身开挖", "步骤": 10},
        {"name": "仰拱支护", "code": "10", "分部": "初期支护", "步骤": 10},
        {"name": "仰拱衬砌", "code": "01", "分部": "二次衬砌", "步骤": 11},
        {"name": "二次衬砌", "code": "02", "分部": "二次衬砌", "步骤": 12},
    ],
    "全断面法": [
        {"name": "全断面开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "全断面支护", "code": "01", "分部": "初期支护", "步骤": 1},
        {"name": "仰拱开挖", "code": "02", "分部": "洞身开挖", "步骤": 2},
        {"name": "仰拱支护", "code": "02", "分部": "初期支护", "步骤": 2},
        {"name": "仰拱衬砌", "code": "01", "分部": "二次衬砌", "步骤": 3},
        {"name": "二次衬砌", "code": "02", "分部": "二次衬砌", "步骤": 4},
    ],
    "CRD法": [
        {"name": "左上导坑开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "左上导坑支护", "code": "01", "分部": "初期支护", "步骤": 1},
        {"name": "左下导坑开挖", "code": "02", "分部": "洞身开挖", "步骤": 2},
        {"name": "左下导坑支护", "code": "02", "分部": "初期支护", "步骤": 2},
        {"name": "右上导坑开挖", "code": "03", "分部": "洞身开挖", "步骤": 3},
        {"name": "右上导坑支护", "code": "03", "分部": "初期支护", "步骤": 3},
        {"name": "右下导坑开挖", "code": "04", "分部": "洞身开挖", "步骤": 4},
        {"name": "右下导坑支护", "code": "04", "分部": "初期支护", "步骤": 4},
        {"name": "仰拱开挖", "code": "05", "分部": "洞身开挖", "步骤": 5},
        {"name": "仰拱支护", "code": "05", "分部": "初期支护", "步骤": 5},
        {"name": "仰拱衬砌", "code": "01", "分部": "二次衬砌", "步骤": 6},
        {"name": "二次衬砌", "code": "02", "分部": "二次衬砌", "步骤": 7},
    ],
    "环形开挖法": [
        {"name": "环形开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "环形初期支护", "code": "01", "分部": "初期支护", "步骤": 1},
        {"name": "核心土开挖", "code": "02", "分部": "洞身开挖", "步骤": 2},
        {"name": "下台阶开挖", "code": "03", "分部": "洞身开挖", "步骤": 3},
        {"name": "下台阶支护", "code": "02", "分部": "初期支护", "步骤": 3},
        {"name": "仰拱开挖", "code": "04", "分部": "洞身开挖", "步骤": 4},
        {"name": "仰拱支护", "code": "03", "分部": "初期支护", "步骤": 4},
        {"name": "仰拱衬砌", "code": "01", "分部": "二次衬砌", "步骤": 5},
        {"name": "二次衬砌", "code": "02", "分部": "二次衬砌", "步骤": 6},
    ],
    "洞口": [
        {"name": "洞口开挖", "code": "01", "分部": "洞口工程", "步骤": 1},
        {"name": "洞口支护", "code": "02", "分部": "洞口工程", "步骤": 2},
        {"name": "洞口衬砌", "code": "03", "分部": "洞口工程", "步骤": 3},
    ]
}

class ExcavationMethod(Enum):
    台阶法 = "台阶法"
    CD法 = "CD法"
    双隔壁法 = "双隔壁法"
    双隔壁法8步 = "双隔壁法(8步)"
    全断面法 = "全断面法"
    CRD法 = "CRD法"
    环形开挖法 = "环形开挖法"
    洞口 = "洞口"

# 每个开挖方法每循环的步骤数
STEPS_PER_CYCLE = {
    "台阶法": 2,        # 上台阶、下台阶
    "CD法": 4,          # 左上、左下、右上、右下
    "双隔壁法": 6,      # 左上、左下、右上、右下、中上、中下
    "双隔壁法(8步)": 8, # 左上左中左下、右上右中右下、中上正中中下
    "全断面法": 1,      # 全断面
    "CRD法": 4,         # 左上、左下、右上、右下
    "环形开挖法": 4,    # 环形、核心土、下台阶、仰拱
    "洞口": 3           # 开挖、支护、衬砌
}

class RockGrade(Enum):
    III级 = "III级"
    IV级 = "IV级"
    V级 = "V级"
    VI级 = "VI级"

@dataclass
class Section:
    section_id: str
    name: str
    length: float
    excavation_method: str
    rock_grade: str = "IV级"
    advance_per_cycle: float = 1.6
    cycle_count: int = 2
    is_portal: bool = False
    portal_type: str = ""
    
    @property
    def is_simple_portal(self) -> bool:
        return self.excavation_method == "洞口"

@dataclass
class Tunnel:
    tunnel_id: str
    name: str
    start_mileage: float
    end_mileage: float
    excavation_direction: str = "正向"  # 正向=递增，反向=递减
    sections: List[Section] = field(default_factory=list)
    
    @property
    def total_length(self) -> float:
        return self.end_mileage - self.start_mileage
    
    @property
    def direction_sign(self) -> int:
        """返回方向符号：正向=+1，反向=-1"""
        return 1 if self.excavation_direction == "正向" else -1
    
    def recalculate_positions(self):
        """根据开挖方向重新计算各段落的起止里程"""
        direction = self.direction_sign
        
        if direction == 1:  # 正向：从起点向终点递增
            current = self.start_mileage
            for section in self.sections:
                section.start_mileage = current
                section.end_mileage = current + section.length
                current = section.end_mileage
        else:  # 反向：从起点向终点递减
            current = self.start_mileage
            for section in self.sections:
                section.start_mileage = current
                section.end_mileage = current - section.length
                current = section.end_mileage
    
    def get_paragraphs_with_positions(self) -> List[dict]:
        """获取段落列表，包含里程桩号信息"""
        direction = self.direction_sign
        result = []
        
        # 获取当前标准的循环进尺配置
        current_standard = get_current_standard()
        advance_table = get_advance_per_cycle(current_standard)
        
        if direction == 1:  # 正向：从起点向终点递增
            current = self.start_mileage
            for i, section in enumerate(self.sections):
                start = current
                end = current + section.length
                
                # 计算循环进尺和步骤数（使用当前标准）
                advance = advance_table.get(section.excavation_method, 1.6)
                steps = STEPS_PER_CYCLE.get(section.excavation_method, 2)
                
                # 格式化里程桩号
                start_km = int(start / 1000)
                start_m = start % 1000
                end_km = int(end / 1000)
                end_m = end % 1000
                
                result.append({
                    "序号": i + 1,
                    "ID": section.section_id,
                    "名称": section.name,
                    "起点桩号": f"K{start_km}+{start_m:03.0f}",
                    "终点桩号": f"K{end_km}+{end_m:03.0f}",
                    "长度(m)": section.length,
                    "开挖方法": section.excavation_method,
                    "循环进尺(m)": advance,
                    "步骤数": steps,
                    "围岩等级": section.rock_grade,
                    "检验批": "❌" if section.is_simple_portal else "✅"
                })
                current = end
        else:  # 反向：从起点向终点递减
            current = self.start_mileage
            for i, section in enumerate(self.sections):
                start = current
                end = current - section.length
                
                # 计算循环进尺和步骤数（使用当前标准）
                advance = advance_table.get(section.excavation_method, 1.6)
                steps = STEPS_PER_CYCLE.get(section.excavation_method, 2)
                
                # 格式化里程桩号（反向用K后缀）
                start_km = int(start / 1000)
                start_m = start % 1000
                end_km = int(end / 1000)
                end_m = end % 1000
                
                result.append({
                    "序号": i + 1,
                    "ID": section.section_id,
                    "名称": section.name,
                    "起点桩号": f"K{start_km}+{start_m:03.0f}",
                    "终点桩号": f"K{end_km}+{end_m:03.0f}",
                    "长度(m)": section.length,
                    "开挖方法": section.excavation_method,
                    "循环进尺(m)": advance,
                    "步骤数": steps,
                    "围岩等级": section.rock_grade,
                    "检验批": "❌" if section.is_simple_portal else "✅"
                })
                current = end
        
        return result
    
    def apply_changes(self, df: pd.DataFrame):
        new_sections = []
        
        # 获取当前标准的循环进尺配置
        current_standard = get_current_standard()
        advance_table = get_advance_per_cycle(current_standard)
        
        for idx, row in df.iterrows():
            method = row["开挖方法"]
            length = row["长度(m)"]
            
            # 根据开挖方法确定循环进尺（使用当前标准）
            advance = advance_table.get(method, 1.6)
            
            # 根据开挖方法和段落长度自动计算循环数
            if method == "洞口":
                cycle_count = 0
            elif method in ["CD法", "CRD法"]:
                # CD法/CRD法: 使用当前标准的循环进尺
                advance_val = advance_table.get("CD法", 0.8)
                cycle_count = max(1, int(length / advance_val)) if advance_val > 0 else 1
            elif method in ["双隔壁法", "双隔壁法(8步)"]:
                # 双隔壁法: 使用当前标准的循环进尺
                advance_val = advance_table.get("双隔壁法", 0.8)
                cycle_count = max(1, int(length / advance_val)) if advance_val > 0 else 1
            elif method == "全断面法":
                # 全断面法: 使用当前标准的循环进尺
                advance_val = advance_table.get("全断面法", 1.6)
                cycle_count = max(1, int(length / advance_val)) if advance_val > 0 else 1
            else:  # 台阶法、环形开挖法等
                # 台阶法等: 使用当前标准的循环进尺
                advance_val = advance_table.get("台阶法", 1.6)
                cycle_count = max(1, int(length / advance_val)) if advance_val > 0 else 1
            
            section = Section(
                section_id=row["ID"],
                name=row["名称"],
                length=length,
                excavation_method=method,
                rock_grade=row["围岩等级"],
                advance_per_cycle=advance,
                cycle_count=cycle_count,
                is_portal=(method == "洞口")
            )
            
            new_sections.append(section)
        
        self.sections = new_sections
        self.recalculate_positions()
    
    def validate(self) -> tuple[bool, List[str]]:
        issues = []
        
        if not self.sections:
            return True, issues
        
        if abs(self.sections[0].start_mileage - self.start_mileage) > 0.1:
            issues.append("首段起点≠隧道起点")
        
        total = sum(s.length for s in self.sections)
        if abs(total - self.total_length) > 0.1:
            issues.append("段落总长≠隧道长")
        
        current = self.start_mileage
        for i, section in enumerate(self.sections):
            if abs(section.start_mileage - current) > 0.1:
                issues.append(f"第{i+1}段断链")
            current = section.end_mileage
        
        return len(issues) == 0, issues

@dataclass
class Project:
    project_id: str
    name: str
    tunnels: List[Tunnel] = field(default_factory=list)

# ==================== 检验批生成（基于TB10753-2018） ====================
def generate_inspection_batches(tunnel: Tunnel, section: Section, section_start: float) -> List[dict]:
    """
    根据当前选定标准生成检验批
    编码规则: [隧道]-[分部]-[分项]-[里程段]-[循环号]
    支持多标准切换：TB10753-2018, TB10417, JTG F80, CJJ 37, GB50299
    """
    batches = []
    
    if section.is_simple_portal:
        return batches
    
    # 获取当前标准配置
    current_standard = get_current_standard()
    
    # 隧道编码
    tunnel_code = {"ZK": "1", "YK": "2", "AK": "3", "BK": "4"}.get(tunnel.tunnel_id, "1")
    
    # 获取该开挖方法的分项工程列表
    work_items = WORK_ITEM_BY_METHOD.get(section.excavation_method, [])
    
    # 循环进尺（使用当前标准的配置）
    advance_table = get_advance_per_cycle(current_standard)
    advance = advance_table.get(section.excavation_method, 1.6)
    
    if advance <= 0:
        advance = 1.6
    
    # 根据段落长度和开挖方法自动计算循环数（使用当前标准的配置）
    if section.excavation_method == "洞口":
        cycle_count = 0
    elif section.excavation_method in ["CD法", "CRD法"]:
        # CD法/CRD法: 使用当前标准的循环进尺
        advance_val = advance_table.get("CD法", 0.8)
        cycle_count = max(1, int(section.length / advance_val)) if advance_val > 0 else 1
    elif section.excavation_method in ["双隔壁法", "双隔壁法(8步)"]:
        # 双隔壁法: 使用当前标准的循环进尺
        advance_val = advance_table.get("双隔壁法", 0.8)
        cycle_count = max(1, int(section.length / advance_val)) if advance_val > 0 else 1
    elif section.excavation_method == "全断面法":
        # 全断面法: 使用当前标准的循环进尺
        advance_val = advance_table.get("全断面法", 1.6)
        cycle_count = max(1, int(section.length / advance_val)) if advance_val > 0 else 1
    else:  # 台阶法、环形开挖法等
        # 台阶法等: 使用当前标准的循环进尺
        advance_val = advance_table.get("台阶法", 1.6)
        cycle_count = max(1, int(section.length / advance_val)) if advance_val > 0 else 1
    
    mileage_start = section_start
    mileage_end = section_start + section.length
    
    # 获取当前标准的分部工程编码
    subproject_codes = get_subproject_codes(current_standard)
    
    for cycle in range(1, cycle_count + 1):
        # 当前循环的里程范围
        cycle_start = mileage_start + (cycle - 1) * advance
        cycle_end = min(cycle_start + advance, mileage_end)
        
        if cycle_end <= cycle_start:
            cycle_end = cycle_start + 0.1
        
        mileage_range = f"K{cycle_start/1000:.3f}~K{cycle_end/1000:.3f}"
        
        # 生成各分项工程的检验批
        for item in work_items:
            # 编码（使用当前标准的分部工程编码）
            subproject_code = subproject_codes.get(item["分部"], "01")
            work_code = item["code"]
            
            batch_no = f"{tunnel_code}-{subproject_code}-{work_code}-{mileage_range}-C{cycle:02d}"
            
            batches.append({
                "检验批编号": batch_no,
                "分部工程": item["分部"],
                "分项工程": item["name"],
                "开挖方法": section.excavation_method,
                "里程范围": mileage_range,
                "循环号": cycle,
                "围岩等级": section.rock_grade,
                "长度(m)": round(cycle_end - cycle_start, 2),
                "验收标准": current_standard.value
            })
    
    return batches

# ==================== 默认项目 ====================
def create_default_project() -> Project:
    project = Project(project_id="LZG", name="泸州龙透关隧道工程")
    
    configs = [
        ("ZK", "左线", 0.0, 1615.0),
        ("YK", "右线", 0.0, 1628.0),
        ("AK", "A匝道", 0.0, 556.0),
        ("BK", "B匝道", 0.0, 591.0)
    ]
    
    for tid, name, start, end in configs:
        tunnel = Tunnel(tunnel_id=tid, name=name, start_mileage=start, end_mileage=end, excavation_direction="正向")
        
        tunnel.sections = [
            Section(f"{tid}-S01", "进口洞口", 2, "洞口", "V级", 0.0, is_portal=True, portal_type="进口"),
            Section(f"{tid}-S02", "进洞段(CD法)", 30, "CD法", "V级", 0.8, is_portal=True, portal_type="进口"),
            Section(f"{tid}-S03", "主洞段(台阶法)", end - 4 - 30 - 30, "台阶法", "IV级", 1.6, is_portal=False, portal_type=""),
            Section(f"{tid}-S04", "出洞段(CD法)", 30, "CD法", "V级", 0.8, is_portal=True, portal_type="出口"),
            Section(f"{tid}-S05", "出口洞口", 2, "洞口", "V级", 0.0, is_portal=True, portal_type="出口")
        ]
        
        tunnel.recalculate_positions()
        project.tunnels.append(tunnel)
    
    return project

# ==================== SVG图形 ====================
def generate_svg(tunnel: Tunnel, width: int = 900, height: int = 200) -> str:
    if not tunnel.sections:
        return f'<svg width="100%" height="{height}"><rect fill="#f8f9fa"/><text x="50%" y="50%">暂无数据</text></svg>'
    
    total = tunnel.total_length or 100
    colors = {
        "CD法": "#FF6B6B", "台阶法": "#4ECDC4", "双隔壁法": "#9B59B6",
        "CRD法": "#E74C3C", "环形开挖法": "#F39C12", "洞口": "#95A5A6"
    }
    
    padding = max(50, width * 0.06)
    chart_w = width - 2 * padding
    min_bar = 25
    scale = chart_w / total if total > 0 else 1
    
    svg = [f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}">']
    svg.append('<defs><style>.title{font-size:14px;font-weight:bold;fill:#2c3e50}.txt{font-size:10px;fill:#666}.lbl{font-size:10px;fill:#fff;font-weight:500}.len{font-size:9px;fill:#333}</style></defs>')
    svg.append('<rect width="100%" height="100%" fill="#fafbfc"/>')
    svg.append(f'<text x="{width/2}" y="20" text-anchor="middle" class="title">{tunnel.name} ({tunnel.start_mileage:.0f}~{tunnel.end_mileage:.0f}m)</text>')
    
    y = height - 50
    bar_h = 32
    current = tunnel.start_mileage
    
    for idx, s in enumerate(tunnel.sections):
        c = colors.get(s.excavation_method, "#BDC3C7")
        x1 = padding + (current - tunnel.start_mileage) * scale
        x2 = padding + (current + s.length - tunnel.start_mileage) * scale
        bar_w = max(x2 - x1, min_bar)
        
        dash = 'stroke-dasharray="3,2"' if s.is_simple_portal else ""
        stroke = "#7f8c8d" if s.is_simple_portal else "#fff"
        
        svg.append(f'<g><rect x="{x1}" y="{y-bar_h/2}" width="{bar_w}" height="{bar_h}" fill="{c}" rx="3" stroke="{stroke}" stroke-width="1.5" {dash}/>')
        svg.append(f'<text x="{x1+bar_w/2}" y="{y}" text-anchor="middle" class="lbl">{s.name}</text>')
        
        if bar_w >= 60:
            svg.append(f'<text x="{x1+bar_w/2}" y="{y+12}" text-anchor="middle" class="len">{s.length:.0f}m</text>')
        
        if idx == 0:
            svg.append(f'<text x="{x1}" y="{y+bar_h/2+14}" text-anchor="middle" class="txt">{current:.0f}m</text>')
        if idx == len(tunnel.sections) - 1:
            svg.append(f'<text x="{x2}" y="{y+bar_h/2+14}" text-anchor="middle" class="txt">{current+s.length:.0f}m</text>')
        
        svg.append('</g>')
        current += s.length
    
    svg.append(f'<line x1="{padding}" y1="{height-8}" x2="{width-padding}" y2="{height-8}" stroke="#bdc3c7" stroke-width="1"/>')
    svg.append(f'<text x="{padding}" y="{height-12}" text-anchor="middle" class="txt" font-weight="500">{tunnel.start_mileage:.0f}m</text>')
    svg.append(f'<text x="{width-padding}" y="{height-12}" text-anchor="middle" class="txt" font-weight="500">{tunnel.end_mileage:.0f}m</text>')
    
    legend = [("洞口", "#95A5A6"), ("CD法", "#FF6B6B"), ("台阶法", "#4ECDC4")]
    lx = width - 180
    for i, (name, color) in enumerate(legend):
        svg.append(f'<g><rect x="{lx+i*60}" y="35" width="10" height="10" fill="{color}" rx="2"/><text x="{lx+i*60+14}" y="44" font-size="9" fill="#666">{name}</text></g>')
    
    svg.append('</svg>')
    return '\n'.join(svg)

# ==================== 会话状态 ====================
def init_state():
    if 'project' not in st.session_state:
        st.session_state.project = create_default_project()
    if 'selected_tunnel' not in st.session_state:
        st.session_state.selected_tunnel = "ZK"
    if 'edited_df' not in st.session_state:
        project = st.session_state.project
        tunnel = next((t for t in project.tunnels if t.tunnel_id == st.session_state.selected_tunnel), None)
        if tunnel:
            st.session_state.edited_df = pd.DataFrame(tunnel.get_paragraphs_with_positions())
        else:
            st.session_state.edited_df = pd.DataFrame()

def get_tunnel() -> Optional[Tunnel]:
    return next((t for t in st.session_state.project.tunnels if t.tunnel_id == st.session_state.selected_tunnel), None)

def update_edited_df(tunnel: Tunnel):
    if tunnel:
        st.session_state.edited_df = pd.DataFrame(tunnel.get_paragraphs_with_positions())

# ==================== 主界面 ====================
def main():
    init_state()
    tunnel = get_tunnel()
    
    with st.sidebar:
        st.title("🚇 隧道工程")
        st.markdown("---")
        st.info("**泸州龙透关隧道工程**")
        
        # 标准选择器
        st.markdown("### 📋 验收标准")
        
        # 标准选项
        standard_options = {
            "TB10753-2018": ("TB10753-2018", "铁路隧道-高铁"),
            "TB10417": ("TB10417", "铁路隧道-普通"),
            "JTG F80": ("JTG F80", "公路隧道"),
            "CJJ 37": ("CJJ 37", "市政隧道"),
            "GB 50299": ("GB 50299", "地铁隧道")
        }
        
        # 当前选中
        current_std_name = get_current_standard().value
        options_list = list(standard_options.keys())
        current_idx = options_list.index(current_std_name) if current_std_name in options_list else 0
        
        selected_std_name = st.selectbox(
            "选择验收标准",
            options=options_list,
            index=current_idx,
            help="切换不同的验收标准会影响检验批划分规则"
        )
        
        # 更新标准
        new_standard = None
        for std in InspectionStandard:
            if std.value == selected_std_name:
                new_standard = std
                break
        
        if new_standard and new_standard != get_current_standard():
            st.session_state.current_standard = new_standard
            st.success(f"已切换至: {STANDARD_INFO[new_standard]['full_name']}")
            st.rerun()
        
        # 显示当前标准信息
        current_std = get_current_standard()
        std_info = STANDARD_INFO[current_std]
        st.caption(f"📌 {std_info['industry']}")
        
        st.markdown("---")
        
        st.markdown("### 🛤 隧道")
        names = ["左线", "右线", "A匝道", "B匝道"]
        ids = ["ZK", "YK", "AK", "BK"]
        
        idx = ids.index(st.session_state.selected_tunnel) if st.session_state.selected_tunnel in ids else 0
        name = st.selectbox("选择", names, index=idx)
        new_id = ids[names.index(name)]
        
        if new_id != st.session_state.selected_tunnel:
            st.session_state.selected_tunnel = new_id
            update_edited_df(get_tunnel())
            st.rerun()
        
        if st.button("🔄 重置配置", type="secondary"):
            st.session_state.project = create_default_project()
            update_edited_df(get_tunnel())
            st.rerun()
        
        if tunnel:
            st.markdown("---")
            st.markdown("### 📐 隧道参数")
            
            c1, c2 =st.columns(2)
            with c1:
                new_start = st.number_input("起点(m)", value=float(tunnel.start_mileage), step=1.0)
            with c2:
                min_end = new_start + 10
                new_end = st.number_input("终点(m)", value=float(tunnel.end_mileage), min_value=min_end, step=1.0)
            
            if new_start != tunnel.start_mileage or new_end != tunnel.end_mileage:
                tunnel.start_mileage = new_start
                tunnel.end_mileage = new_end
                tunnel.recalculate_positions()
                update_edited_df(tunnel)
                st.rerun()
            
            # 开挖方向选择
            c_dir, c_len = st.columns(2)
            with c_dir:
                direction = st.selectbox(
                    "开挖方向", 
                    ["正向", "反向"],
                    index=0 if tunnel.excavation_direction == "正向" else 1,
                    help="正向=里程递增，反向=里程递减"
                )
                if direction != tunnel.excavation_direction:
                    tunnel.excavation_direction = direction
                    tunnel.recalculate_positions()
                    update_edited_df(tunnel)
                    st.rerun()
            
            with c_len:
                st.write(f"**总长: {tunnel.total_length:.1f}m**")
            
            stats = {
                "段落数": len(tunnel.sections),
                "检验批": sum(len(generate_inspection_batches(tunnel, s, tunnel.start_mileage + sum(x.length for x in tunnel.sections[:i]))) 
                            for i, s in enumerate(tunnel.sections) if not s.is_simple_portal)
            }
            
            st.markdown("---")
            st.markdown("### 📊 统计")
            st.write(f"- 段落: {stats['段落数']}")
            st.write(f"- 检验批: {stats['检验批']}")
        
        # 当前标准信息
        current_std = get_current_standard()
        std_info = STANDARD_INFO[current_std]
        
        with st.expander(f"📖 {std_info['name']} 分部分项"):
            st.markdown(f"**{std_info['full_name']}**")
            st.markdown(f"*{std_info['description']}*")
            st.markdown("---")
            
            # 显示当前标准的分部工程
            st.markdown("**分部工程：**")
            subproject_codes = get_subproject_codes()
            for name, code in subproject_codes.items():
                st.markdown(f"- {code} {name}")
            
            # 显示当前标准的循环进尺
            st.markdown("---")
            st.markdown("**循环进尺(m/循环)：**")
            advance_table = get_advance_per_cycle()
            for method, advance in advance_table.items():
                st.markdown(f"- {method}: {advance}m")
    
    st.title("🚇 泸州龙透关隧道检验批划分系统")
    
    # 动态显示当前标准
    current_std = get_current_standard()
    std_info = STANDARD_INFO[current_std]
    st.markdown(f"**{std_info['name']} 标准 · {std_info['industry']} · 检验批自动生成**")
    
    if not tunnel:
        st.error("未找到隧道")
        return
    
    # 纵断面图
    st.subheader(f"📐 {tunnel.name} 纵断面图")
    
    with st.container():
        st.markdown(f'<div style="border:1px solid #e9ecef;border-radius:5px;padding:10px 0;overflow-x:auto">{generate_svg(tunnel)}</div>', unsafe_allow_html=True)
    
    # 段落列表
    st.markdown("---")
    st.subheader("📝 段落列表 (点击直接编辑)")
    
    if tunnel.sections:
        # 段落列表
        config = {
            "序号": st.column_config.NumberColumn("№", width="small", disabled=True),
            "ID": st.column_config.TextColumn("ID", width="small", disabled=True),
            "名称": st.column_config.TextColumn("名称", width="medium"),
            "起点桩号": st.column_config.TextColumn("起点里程*", width="small", disabled=False, help="Kxxx+xxx格式，修改后自动更新所有里程"),
            "终点桩号": st.column_config.TextColumn("终点桩号", width="small", disabled=True),
            "长度(m)": st.column_config.NumberColumn("长度(m)", width="small", min_value=2.0),
            "开挖方法": st.column_config.SelectboxColumn("开挖方法*", width="small", 
                options=[m.value for m in ExcavationMethod], required=True),
            "循环进尺(m)": st.column_config.NumberColumn("循环进尺*", width="small", disabled=True),
            "步骤数": st.column_config.TextColumn("步骤数", width="small", disabled=True),
            "围岩等级": st.column_config.SelectboxColumn("围岩", width="small", 
                options=[g.value for g in RockGrade]),
            "检验批": st.column_config.TextColumn("检验批", width="small", disabled=True)
        }
        
        edited_df = st.data_editor(
            st.session_state.edited_df,
            column_config=config,
            width='stretch',
            num_rows="dynamic",
            key="editor"
        )
        
        # 检测起点里程是否被修改
        if not edited_df.empty and len(st.session_state.edited_df) > 0:
            old_start = st.session_state.edited_df.iloc[0]["起点桩号"]
            new_start = edited_df.iloc[0]["起点桩号"]
            
            # 如果起点里程被修改
            if new_start != old_start and new_start.startswith("K"):
                try:
                    # 解析新起点里程（格式 Kxxx+xxx）
                    parts = new_start.replace("K", "").split("+")
                    new_start_m = float(parts[0]) * 1000 + float(parts[1])
                    
                    # 计算差值
                    diff = new_start_m - tunnel.start_mileage
                    
                    # 更新隧道起点
                    tunnel.start_mileage = new_start_m
                    
                    # 重新计算所有段落里程
                    tunnel.recalculate_positions()
                    
                    # 重新生成表格
                    update_edited_df(tunnel)
                    edited_df = st.session_state.edited_df.copy()
                    
                    st.success(f"✅ 起点里程已更新: {new_start}，所有段落里程自动同步")
                except Exception as e:
                    st.error(f"❌ 里程格式错误，请使用 Kxxx+xxx 格式")
        
        # 继续处理其他字段变更
        if not edited_df.equals(st.session_state.edited_df):
            for i in edited_df.index:
                edited_df.at[i, "ID"] = f"{tunnel.tunnel_id}-S{i+1:02d}"
                
                method = edited_df.at[i, "开挖方法"]
                if method in ["CD法", "CRD法"]:
                    edited_df.at[i, "循环进尺(m)"] = 0.8
                    edited_df.at[i, "步骤数"] = "4步(左上下/右上下)"
                elif method == "双隔壁法":
                    edited_df.at[i, "循环进尺(m)"] = 0.8
                    edited_df.at[i, "步骤数"] = "6步(左上下/右上下/中上下)"
                elif method == "双隔壁法(8步)":
                    edited_df.at[i, "循环进尺(m)"] = 0.8
                    edited_df.at[i, "步骤数"] = "8步(左中下/右中下/正中下)"
                elif method == "洞口":
                    edited_df.at[i, "循环进尺(m)"] = 0.0
                    edited_df.at[i, "步骤数"] = "3步(开挖/支护/衬砌)"
                elif method == "全断面法":
                    edited_df.at[i, "循环进尺(m)"] = 1.6
                    edited_df.at[i, "步骤数"] = "1步(全断面)"
                else:  # 台阶法、环形开挖法等
                    edited_df.at[i, "循环进尺(m)"] = 1.6
                    if method == "台阶法":
                        edited_df.at[i, "步骤数"] = "2步(上台阶/下台阶)"
                    else:
                        edited_df.at[i, "步骤数"] = "4步"
                
                edited_df.at[i, "检验批"] = "❌" if method == "洞口" else "✅"
            
            tunnel.apply_changes(edited_df)
            st.session_state.edited_df = edited_df.copy()
            st.rerun()
        
        ok, issues = tunnel.validate()
        if ok:
            st.success("✅ 段落连续")
        else:
            st.warning("⚠️ " + " | ".join(issues))
        
        c_auto, c_reset = st.columns(2)
        
        with c_auto:
            if st.button("🔧 自动排版", help="整理所有段落位置"):
                tunnel.recalculate_positions()
                update_edited_df(tunnel)
                st.rerun()
        
        with c_reset:
            if st.button("🔄 取消"):
                update_edited_df(tunnel)
                st.rerun()
    
    # 检验批生成
    st.markdown("---")
    st.subheader("📋 检验批清单 (TB10753-2018)")
    
    c1, c2, c3 = st.columns([1, 1, 1])
    
    with c1:
        opts = ["全部(不含洞口)"]
        for s in tunnel.sections:
            if not s.is_simple_portal:
                opts.append(f"{s.section_id}: {s.name}")
        sel = st.selectbox("选择段落", opts)
    
    with c2:
        gen_btn = st.button("📄 生成检验批", type="primary")
    
    with c3:
        fmt = st.selectbox("导出格式", ["CSV", "Excel", "JSON"])
    
    if gen_btn:
        with st.spinner("生成中..."):
            all_batches = []
            paragraphs = tunnel.get_paragraphs_with_positions()
            
            if "全部" in sel:
                for i, s in enumerate(tunnel.sections):
                    if not s.is_simple_portal:
                        # 解析起点桩号获取数值
                        start_str = paragraphs[i]["起点桩号"]
                        parts = start_str.replace("K", "").split("+")
                        start_m = float(parts[0]) * 1000 + float(parts[1])
                        all_batches.extend(generate_inspection_batches(tunnel, s, start_m))
            else:
                for i, s in enumerate(tunnel.sections):
                    if not s.is_simple_portal and f"{s.section_id}:" in sel:
                        # 解析起点桩号获取数值
                        start_str = paragraphs[i]["起点桩号"]
                        parts = start_str.replace("K", "").split("+")
                        start_m = float(parts[0]) * 1000 + float(parts[1])
                        all_batches.extend(generate_inspection_batches(tunnel, s, start_m))
                        break
            
            if all_batches:
                df = pd.DataFrame(all_batches)
                st.success(f"✅ 成功生成 **{len(df)}** 条检验批")
                
                # 统计
                c = st.columns(4)
                c[0].metric("分部数", df["分部工程"].nunique())
                c[1].metric("分项数", df["分项工程"].nunique())
                c[2].metric("里程段", df["里程范围"].nunique())
                c[3].metric("循环", df["循环号"].max())
                
                # 分部工程统计
                st.markdown("#### 分部工程统计")
                subproject_stats = df.groupby("分部工程").size()
                st.dataframe(subproject_stats.to_frame("检验批数"), width=300)
                
                # 数据预览
                st.dataframe(df, width='stretch', height=250)
                
                # 导出
                if fmt == "CSV":
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button("下载CSV", csv, f"{tunnel.tunnel_id}_检验批.csv", "text/csv")
                elif fmt == "Excel":
                    from io import BytesIO
                    b = BytesIO()
                    with pd.ExcelWriter(b, engine='openpyxl') as w:
                        df.to_excel(w, index=False)
                    st.download_button("下载Excel", b.getvalue(), f"{tunnel.tunnel_id}_检验批.xlsx", "application/vnd.openxmlformats")
                else:
                    st.download_button("下载JSON", json.dumps(all_batches, ensure_ascii=False, indent=2), f"{tunnel.tunnel_id}_检验批.json", "application/json")
            else:
                st.warning("无有效段落")
    
    with st.expander("ℹ️ 操作说明"):
        st.markdown("""
        **操作说明：**
        
        ✅ 点击单元格直接编辑段落参数
        
        ✅ 循环进尺自动设置：
        - 洞口: 0.0
        - CD法/CRD法/双隔壁法: 0.8m
        - 台阶法/环形开挖法: 1.6m
        
        ✅ 检验批生成基于TB10753-2018标准
        """)

if __name__ == "__main__":
    main()
