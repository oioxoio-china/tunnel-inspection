"""
泸州龙透关隧道工程检验批划分系统 V5
基于TB10753-2018铁路隧道工程施工质量验收标准
支持多标准切换、多工程管理、汇总统计、方案编制V2

Author: Matrix Agent
"""

import streamlit as st
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import json
import math
from datetime import datetime
import io

# 导入方案编制V2模块
try:
    from page_scheme_generator_v2_fixed import get_page_content_v2
    SCHEME_GENERATOR_V2_AVAILABLE = True
    SCHEME_GENERATOR_V2_TYPE = "fixed"
except ImportError:
    try:
        from page_scheme_generator_v2 import page_scheme_generator_v2
        SCHEME_GENERATOR_V2_AVAILABLE = True
        SCHEME_GENERATOR_V2_TYPE = "original"
    except ImportError:
        SCHEME_GENERATOR_V2_AVAILABLE = False
        SCHEME_GENERATOR_V2_TYPE = None

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="泸州龙透关隧道检验批系统 V5",
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

# ==================== V4标准配置：循环进尺 ====================
# 恢复V4版本设置
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

# 优化二：细化工序定义（一序一验：开挖、钢架、网片、锚杆、喷射混凝土）
WORK_ITEM_BY_METHOD = {
    "台阶法": [
        {"name": "上台阶开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "上台阶钢架安装", "code": "02", "分部": "初期支护", "步骤": 1},
        {"name": "上台阶钢筋网", "code": "03", "分部": "初期支护", "步骤": 1},
        {"name": "上台阶锚杆", "code": "04", "分部": "初期支护", "步骤": 1},
        {"name": "上台阶喷射混凝土", "code": "05", "分部": "初期支护", "步骤": 1},
        {"name": "下台阶开挖", "code": "06", "分部": "洞身开挖", "步骤": 2},
        {"name": "下台阶钢架安装", "code": "07", "分部": "初期支护", "步骤": 2},
        {"name": "下台阶钢筋网", "code": "08", "分部": "初期支护", "步骤": 2},
        {"name": "下台阶锚杆", "code": "09", "分部": "初期支护", "步骤": 2},
        {"name": "下台阶喷射混凝土", "code": "10", "分部": "初期支护", "步骤": 2},
        {"name": "仰拱开挖", "code": "11", "分部": "洞身开挖", "步骤": 3},
        {"name": "仰拱初期支护", "code": "12", "分部": "初期支护", "步骤": 3},
    ],
    "CD法": [
        {"name": "①部(左上)开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "①部(左上)钢架", "code": "02", "分部": "初期支护", "步骤": 1},
        {"name": "①部(左上)网/锚/喷", "code": "03", "分部": "初期支护", "步骤": 1},
        {"name": "②部(左下)开挖", "code": "04", "分部": "洞身开挖", "步骤": 2},
        {"name": "②部(左下)钢架", "code": "05", "分部": "初期支护", "步骤": 2},
        {"name": "③部(右上)开挖", "code": "06", "分部": "洞身开挖", "步骤": 3},
        {"name": "③部(右上)钢架", "code": "07", "分部": "初期支护", "步骤": 3},
        {"name": "④部(右下)开挖", "code": "08", "分部": "洞身开挖", "步骤": 4},
        {"name": "④部(右下)钢架", "code": "09", "分部": "初期支护", "步骤": 4},
    ],
    "双隔壁法": [
        {"name": "①部(左上)开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "①部(左上)钢架", "code": "02", "分部": "初期支护", "步骤": 1},
        {"name": "①部(左上)网/锚/喷", "code": "03", "分部": "初期支护", "步骤": 1},
        {"name": "②部(左下)开挖", "code": "04", "分部": "洞身开挖", "步骤": 2},
        {"name": "②部(左下)钢架", "code": "05", "分部": "初期支护", "步骤": 2},
        {"name": "③部(右上)开挖", "code": "06", "分部": "洞身开挖", "步骤": 3},
        {"name": "③部(右上)钢架", "code": "07", "分部": "初期支护", "步骤": 3},
        {"name": "④部(右下)开挖", "code": "08", "分部": "洞身开挖", "步骤": 4},
        {"name": "④部(右下)钢架", "code": "09", "分部": "初期支护", "步骤": 4},
        {"name": "⑤部(中上)开挖", "code": "10", "分部": "洞身开挖", "步骤": 5},
        {"name": "⑤部(中上)钢架", "code": "11", "分部": "初期支护", "步骤": 5},
        {"name": "⑥部(中下)开挖", "code": "12", "分部": "洞身开挖", "步骤": 6},
        {"name": "⑥部(中下)钢架", "code": "13", "分部": "初期支护", "步骤": 6},
    ],
    "全断面法": [
        {"name": "全断面开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "全断面钢架", "code": "02", "分部": "初期支护", "步骤": 1},
        {"name": "全断面网/锚/喷", "code": "03", "分部": "初期支护", "步骤": 1},
    ],
    "环形开挖法": [
        {"name": "环形开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "环形支护", "code": "02", "分部": "初期支护", "步骤": 1},
    ],
    "洞口": [
        {"name": "洞口开挖", "code": "01", "分部": "洞口工程", "步骤": 1},
        {"name": "洞口支护", "code": "02", "分部": "洞口工程", "步骤": 2},
        {"name": "洞口排水", "code": "03", "分部": "洞口工程", "步骤": 3},
    ]
}

# 优化三：定义二衬独立工序 (按台车长度生成，与开挖循环解耦)
LINING_WORK_ITEMS = [
    {"name": "防水层铺设", "code": "01", "分部": "防排水"},
    {"name": "二衬钢筋安装", "code": "02", "分部": "二次衬砌"},
    {"name": "二衬模板安装", "code": "03", "分部": "二次衬砌"},
    {"name": "二衬混凝土浇筑", "code": "04", "分部": "二次衬砌"},
]

# 台车长度配置
TROLLEY_LENGTHS = {
    "主线": 12.0,
    "ZK": 12.0,
    "YK": 12.0,
    "匝道": 9.0,
    "AK": 9.0,
    "BK": 9.0,
    "DK": 9.0,
    "EK": 9.0,
    "default": 12.0
}

# 分部工程编码
SUBPROJECT_CODES = {
    "洞口工程": "01",
    "洞身开挖": "02",
    "初期支护": "03",
    "防排水": "04",
    "二次衬砌": "05",
    "附属工程": "06",
    "明洞工程": "07",
}

# ==================== 获取当前标准配置 ====================
def get_current_standard() -> InspectionStandard:
    """获取当前选中的验收标准"""
    if 'current_standard' not in st.session_state:
        st.session_state.current_standard = InspectionStandard.TB10753_2018
    return st.session_state.current_standard

def get_advance_per_cycle(standard: InspectionStandard = None) -> Dict[str, float]:
    """获取指定标准的循环进尺"""
    if standard is None:
        standard = get_current_standard()
    return ADVANCE_PER_CYCLE_BY_STANDARD.get(standard, ADVANCE_PER_CYCLE_BY_STANDARD[InspectionStandard.TB10753_2018])

# ==================== 数据模型 ====================
@dataclass
class Section:
    """隧道段落"""
    section_id: str
    name: str
    length: float
    excavation_method: str
    rock_grade: str = "IV级"
    advance_per_cycle: float = 1.2
    cycle_count: int = 2
    start_mileage: float = 0.0
    end_mileage: float = 0.0
    is_portal: bool = False
    portal_type: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Section':
        return cls(**data)

@dataclass
class Tunnel:
    """隧道"""
    tunnel_id: str
    name: str
    start_mileage: float
    end_mileage: float
    excavation_direction: str = "正向"
    sections: List[Section] = field(default_factory=list)
    
    @property
    def total_length(self) -> float:
        return self.end_mileage - self.start_mileage
    
    @property
    def direction_sign(self) -> int:
        return 1 if self.excavation_direction == "正向" else -1
    
    def recalculate_positions(self):
        """根据开挖方向重新计算各段落的起止里程"""
        direction = self.direction_sign
        advance_table = get_advance_per_cycle()
        
        if direction == 1:
            current = self.start_mileage
            for section in self.sections:
                section.start_mileage = current
                section.end_mileage = current + section.length
                current = section.end_mileage
        else:
            current = self.start_mileage
            for section in self.sections:
                section.start_mileage = current
                section.end_mileage = current - section.length
                current = section.end_mileage
    
    def get_paragraphs_with_positions(self) -> List[dict]:
        """获取段落列表，包含里程桩号信息"""
        direction = self.direction_sign
        advance_table = get_advance_per_cycle()
        result = []
        
        if direction == 1:
            current = self.start_mileage
            for i, section in enumerate(self.sections):
                start = current
                end = current + section.length
                advance = advance_table.get(section.excavation_method, 1.2)
                
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
                    "围岩等级": section.rock_grade,
                    "检验批": "❌" if section.is_portal else "✅"
                })
                current = end
        else:
            current = self.start_mileage
            for i, section in enumerate(self.sections):
                start = current
                end = current - section.length
                advance = advance_table.get(section.excavation_method, 1.2)
                
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
                    "围岩等级": section.rock_grade,
                    "检验批": "❌" if section.is_portal else "✅"
                })
                current = end
        
        return result
    
    def apply_changes(self, df: pd.DataFrame):
        """应用段落变更"""
        new_sections = []
        advance_table = get_advance_per_cycle()
        
        for idx, row in df.iterrows():
            method = row["开挖方法"]
            length = row["长度(m)"]
            advance = advance_table.get(method, 1.2)
            
            if method == "洞口":
                cycle_count = 0
            elif method in ["CD法", "CRD法"]:
                advance_val = advance_table.get("CD法", 0.6)
                cycle_count = max(1, int(length / advance_val)) if advance_val > 0 else 1
            elif method in ["双隔壁法", "双隔壁法(8步)"]:
                advance_val = advance_table.get("双隔壁法", 0.6)
                cycle_count = max(1, int(length / advance_val)) if advance_val > 0 else 1
            elif method == "全断面法":
                advance_val = advance_table.get("全断面法", 1.2)
                cycle_count = max(1, int(length / advance_val)) if advance_val > 0 else 1
            else:
                advance_val = advance_table.get("台阶法", 1.2)
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
    
    def validate(self) -> Tuple[bool, List[str]]:
        """验证隧道数据"""
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
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "tunnel_id": self.tunnel_id,
            "name": self.name,
            "start_mileage": self.start_mileage,
            "end_mileage": self.end_mileage,
            "excavation_direction": self.excavation_direction,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Tunnel':
        """从字典创建"""
        tunnel = cls(
            tunnel_id=data["tunnel_id"],
            name=data["name"],
            start_mileage=data["start_mileage"],
            end_mileage=data["end_mileage"],
            excavation_direction=data.get("excavation_direction", "正向")
        )
        tunnel.sections = [Section.from_dict(s) for s in data.get("sections", [])]
        return tunnel
    
    def copy_with_new_id(self, new_id: str, new_name: str) -> 'Tunnel':
        """复制隧道并生成新ID"""
        new_tunnel = Tunnel(
            tunnel_id=new_id,
            name=new_name,
            start_mileage=self.start_mileage,
            end_mileage=self.end_mileage,
            excavation_direction=self.excavation_direction
        )
        new_tunnel.sections = []
        for s in self.sections:
            new_section = Section(
                section_id=f"{new_id}-S{len(new_tunnel.sections)+1:02d}",
                name=s.name,
                length=s.length,
                excavation_method=s.excavation_method,
                rock_grade=s.rock_grade,
                advance_per_cycle=s.advance_per_cycle,
                cycle_count=s.cycle_count,
                is_portal=s.is_portal,
                portal_type=s.portal_type
            )
            new_tunnel.sections.append(new_section)
        new_tunnel.recalculate_positions()
        return new_tunnel

@dataclass
class Project:
    """工程项目"""
    project_id: str
    name: str
    description: str = ""
    created_date: str = ""
    tunnels: List[Tunnel] = field(default_factory=list)
    
    @property
    def tunnel_count(self) -> int:
        return len(self.tunnels)
    
    @property
    def total_length(self) -> float:
        return sum(t.total_length for t in self.tunnels)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "created_date": self.created_date,
            "tunnels": [t.to_dict() for t in self.tunnels]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Project':
        """从字典创建"""
        project = cls(
            project_id=data["project_id"],
            name=data["name"],
            description=data.get("description", ""),
            created_date=data.get("created_date", "")
        )
        project.tunnels = [Tunnel.from_dict(t) for t in data.get("tunnels", [])]
        return project
    
    def copy_with_new_id(self, new_id: str, new_name: str) -> 'Project':
        """复制项目并生成新ID"""
        new_project = Project(
            project_id=new_id,
            name=new_name,
            description=self.description,
            created_date=datetime.now().strftime("%Y-%m-%d")
        )
        for t in self.tunnels:
            new_tunnel = t.copy_with_new_id(
                f"T{len(new_project.tunnels)+1:02d}",
                f"{t.name}-副本"
            )
            new_project.tunnels.append(new_tunnel)
        return new_project

# ==================== 检验批生成 ====================
def generate_inspection_batches(tunnel, section, section_start):
    """
    Generate inspection batches: excavation/support (by cycle) and lining (by trolley)
    Part 1: Excavation and initial support (by design advance cycle)
    Part 2: Secondary lining (independent, by trolley length)
    """
    batches = []
    
    if section.is_portal:
        return batches
    
    current_standard = get_current_standard()
    tunnel_code = {"ZK": "1", "YK": "2", "AK": "3", "BK": "4"}.get(tunnel.tunnel_id, "1")
    advance_table = get_advance_per_cycle()
    
    # Part 1: Excavation and initial support
    advance = advance_table.get(section.excavation_method, 1.2)
    
    if advance <= 0:
        advance = 1.0
    
    work_items = WORK_ITEM_BY_METHOD.get(section.excavation_method, WORK_ITEM_BY_METHOD["台阶法"])
    cycle_count = max(1, int(section.length / advance)) if advance > 0 else 1
    
    curr_m = section_start
    
    for cycle in range(1, cycle_count + 1):
        next_m = min(curr_m + advance, section_start + section.length)
        mileage_range = "K{:.3f}~K{:.3f}".format(curr_m/1000, next_m/1000)
        
        for item in work_items:
            if item["分部"] in ["二次衬砌", "防排水"]:
                continue
            
            sp_code = SUBPROJECT_CODES.get(item["分部"], "02")
            batch_no = "T{}-{}-{}-{}-C{:04d}".format(tunnel_code, sp_code, item['code'], mileage_range.replace("K", "").replace("+", ""), cycle)
            
            batches.append({
                "检验批编号": batch_no,
                "隧道名称": tunnel.name,
                "隧道ID": tunnel.tunnel_id,
                "分部工程": item["分部"],
                "分项工程": item["name"],
                "类别": "开挖/支护",
                "开挖方法": section.excavation_method,
                "里程范围": mileage_range,
                "循环/板号": cycle,
                "进尺/长度": round(next_m - curr_m, 3),
                "围岩等级": section.rock_grade,
                "验收标准": current_standard.value
            })
        
        curr_m = next_m
    
    # Part 2: Secondary lining (independent by trolley)
    if any(x in tunnel.name for x in ["A匝道", "B匝道", "AK", "BK", "DK", "EK"]):
        trolley_len = 9.0
    else:
        trolley_len = 12.0
    
    lining_cycles = math.ceil(section.length / trolley_len)
    l_curr_m = section_start
    
    for i in range(1, lining_cycles + 1):
        l_next_m = min(l_curr_m + trolley_len, section_start + section.length)
        l_range = "K{:.3f}~K{:.3f}".format(l_curr_m/1000, l_next_m/1000)
        
        for item in LINING_WORK_ITEMS:
            sp_code = SUBPROJECT_CODES.get(item["分部"], "05")
            batch_no = "T{}-{}-{}-{}-EC{:03d}".format(tunnel_code, sp_code, item['code'], l_range.replace("K", "").replace("+", ""), i)
            
            batches.append({
                "检验批编号": batch_no,
                "隧道名称": tunnel.name,
                "隧道ID": tunnel.tunnel_id,
                "分部工程": item["分部"],
                "分项工程": item["name"],
                "类别": "二次衬砌",
                "开挖方法": "台车模筑",
                "里程范围": l_range,
                "循环/板号": i,
                "进尺/长度": round(l_next_m - l_curr_m, 3),
                "围岩等级": section.rock_grade,
                "验收标准": current_standard.value
            })
        
        l_curr_m = l_next_m
    
    return batches


def generate_all_batches_for_project(project: Project) -> pd.DataFrame:
    """为整个项目生成所有检验批"""
    all_batches = []
    
    for tunnel in project.tunnels:
        tunnel_start = tunnel.start_mileage
        
        for section in tunnel.sections:
            section_start = tunnel_start + sum(
                s.length for s in tunnel.sections[:tunnel.sections.index(section)]
            )
            
            batches = generate_inspection_batches(tunnel, section, section_start)
            all_batches.extend(batches)
    
    return pd.DataFrame(all_batches)


# ==================== 泸州龙透关隧道工程配置 ====================
def create_lztg_project(standard_key: str = "TB10753-2018") -> Project:
    """
    创建泸州龙透关隧道工程项目
    
    隧道配置：
    - ZK: 主线左线隧道，起点K245+102，终点K1408+000，长度1162.898m
    - YK: 主线右线隧道，起点K244+803，终点K1406+000，长度1161.197m
    - AK: A匝道隧道，起点K87+000，终点K425+500，长度338.500m
    - BK: B匝道隧道，起点K164+000，终点K755+000，长度591.000m
    """
    # 隧道定义：(ID, 名称, 起点里程km, 终点里程km)
    tunnel_configs = [
        ("ZK", "主线左线隧道", 245.102, 1408.000),   # 长度 1162.898m
        ("YK", "主线右线隧道", 244.803, 1406.000),  # 长度 1161.197m
        ("AK", "A匝道隧道", 87.000, 425.500),       # 长度 338.500m
        ("BK", "B匝道隧道", 164.000, 755.000),      # 长度 591.000m
    ]
    
    project = Project(
        project_id="LZTG-2024",
        name="泸州龙透关隧道工程",
        description=f"基于{standard_key}标准，包含主线左右线及A、B匝道共4条隧道",
        created_date=datetime.now().strftime("%Y-%m-%d")
    )
    
    for tunnel_id, tunnel_name, start_km, end_km in tunnel_configs:
        tunnel = Tunnel(
            tunnel_id=tunnel_id,
            name=tunnel_name,
            start_mileage=start_km * 1000,
            end_mileage=end_km * 1000,
            excavation_direction="正向"
        )
        
        # 根据隧道类型设置段落
        total_length = tunnel.total_length
        
        if tunnel_id in ["ZK", "YK"]:
            # 主线隧道：洞口段30m + 洞身段
            sections = [
                Section(
                    section_id=f"{tunnel_id}-S01",
                    name="洞口段",
                    length=30.0,
                    excavation_method="洞口",
                    rock_grade="V级",
                    is_portal=True
                ),
                Section(
                    section_id=f"{tunnel_id}-S02",
                    name="洞身段",
                    length=total_length - 30.0,
                    excavation_method="台阶法",
                    rock_grade="IV级",
                    is_portal=False
                ),
            ]
        else:
            # 匝道隧道：洞口段20m + 洞身段
            sections = [
                Section(
                    section_id=f"{tunnel_id}-S01",
                    name="洞口段",
                    length=20.0,
                    excavation_method="洞口",
                    rock_grade="V级",
                    is_portal=True
                ),
                Section(
                    section_id=f"{tunnel_id}-S02",
                    name="洞身段",
                    length=total_length - 20.0,
                    excavation_method="台阶法",
                    rock_grade="IV级",
                    is_portal=False
                ),
            ]
        
        tunnel.sections = sections
        tunnel.recalculate_positions()
        project.tunnels.append(tunnel)
    
    return project


# ==================== 页面函数 ====================
def page_project_manager():
    """项目管理页面"""
    st.header("🏗️ 工程管理")
    
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
    if 'current_project_id' not in st.session_state:
        st.session_state.current_project_id = None
    
    with st.expander("📝 创建新项目", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_project_id = st.text_input("项目ID", value=f"PJ{len(st.session_state.projects)+1:03d}")
            new_project_name = st.text_input("项目名称")
        with col2:
            new_project_desc = st.text_area("项目描述")
            if st.button("创建项目"):
                if new_project_id and new_project_name:
                    project = Project(
                        project_id=new_project_id,
                        name=new_project_name,
                        description=new_project_desc,
                        created_date=datetime.now().strftime("%Y-%m-%d")
                    )
                    st.session_state.projects[new_project_id] = project
                    st.success(f"项目 {new_project_name} 创建成功！")
                    st.rerun()
    
    # 快速创建泸州龙透关项目
    st.subheader("🚇 快速创建示例项目")
    st.info("泸州龙透关隧道工程 - 包含4条隧道")
    
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        if st.button("创建泸州龙透关项目 (TB10753-2018)", use_container_width=True):
            project = create_lztg_project("TB10753-2018")
            st.session_state.projects[project.project_id] = project
            st.session_state.current_project_id = project.project_id
            st.success(f"项目 {project.name} 创建成功！")
            st.rerun()
    
    with col_ex2:
        if st.button("创建泸州龙透关项目 (GB50299地铁)", use_container_width=True):
            project = create_lztg_project("GB50299")
            st.session_state.projects[project.project_id] = project
            st.session_state.current_project_id = project.project_id
            st.success(f"项目 {project.name} 创建成功！")
            st.rerun()
    
    st.markdown("---")
    
    if st.session_state.projects:
        st.subheader("📂 现有项目")
        
        for pid, proj in st.session_state.projects.items():
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.info(f"**{proj.name}**")
                with col2:
                    st.write(f"隧道: {proj.tunnel_count}座")
                with col3:
                    st.write(f"总长: {proj.total_length:.0f}m")
                with col4:
                    if st.button("选择", key=f"select_{pid}"):
                        st.session_state.current_project_id = pid
                        st.rerun()
                
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    if st.button("复制项目", key=f"copy_{pid}"):
                        copy_id = f"{pid}_copy"
                        new_proj = proj.copy_with_new_id(copy_id, f"{proj.name}-副本")
                        st.session_state.projects[copy_id] = new_proj
                        st.success("项目复制成功！")
                        st.rerun()
                with col_b:
                    if st.button("删除项目", key=f"delete_{pid}"):
                        del st.session_state.projects[pid]
                        if st.session_state.current_project_id == pid:
                            st.session_state.current_project_id = None
                        st.success("项目已删除！")
                        st.rerun()
                
                st.divider()
    else:
        st.info("暂无项目，请创建新项目")


def page_tunnel_editor():
    """隧道编辑页面"""
    st.header("🚇 隧道编辑")
    
    if not st.session_state.projects:
        st.warning("请先创建项目！")
        return
    
    if not st.session_state.current_project_id:
        st.warning("请先选择一个项目！")
        return
    
    project = st.session_state.projects[st.session_state.current_project_id]
    st.subheader(f"当前项目: {project.name}")
    
    with st.expander("➕ 添加/编辑隧道", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            tunnel_id = st.text_input("隧道ID", value=f"T{len(project.tunnels)+1:02d}")
        with col2:
            tunnel_name = st.text_input("隧道名称", placeholder="如：龙透关隧道左线(ZK)")
        with col3:
            direction = st.selectbox("开挖方向", ["正向", "反向"])
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            start_km = st.number_input("起点里程(km)", value=0.0, step=0.001)
        with col_b:
            length = st.number_input("隧道长度(m)", value=100.0, step=10.0)
        with col_c:
            direction_sign = 1 if direction == "正向" else -1
            end_km = start_km + (length / 1000 * direction_sign)
            st.number_input("终点里程(km)", value=end_km, disabled=True)
        
        if st.button("添加隧道"):
            tunnel = Tunnel(
                tunnel_id=tunnel_id,
                name=tunnel_name,
                start_mileage=start_km * 1000,
                end_mileage=end_km * 1000,
                excavation_direction=direction
            )
            project.tunnels.append(tunnel)
            st.success(f"隧道 {tunnel_name} 添加成功！")
            st.rerun()
    
    if project.tunnels:
        st.subheader("📋 隧道列表")
        
        for idx, tunnel in enumerate(project.tunnels):
            with st.expander(f"🚇 {tunnel.name} (ID: {tunnel.tunnel_id})", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"长度: {tunnel.total_length:.0f}m")
                with col2:
                    st.write(f"方向: {tunnel.excavation_direction}")
                with col3:
                    if st.button("复制隧道", key=f"copy_t_{idx}"):
                        new_id = f"{tunnel.tunnel_id}_copy"
                        new_tunnel = tunnel.copy_with_new_id(new_id, f"{tunnel.name}-副本")
                        project.tunnels.append(new_tunnel)
                        st.success("隧道复制成功！")
                        st.rerun()
                with col4:
                    if st.button("删除隧道", key=f"del_t_{idx}"):
                        project.tunnels.pop(idx)
                        st.success("隧道已删除！")
                        st.rerun()
                
                st.write("---")
                st.write("**段落划分**")
                
                default_df = pd.DataFrame([
                    {"ID": f"{tunnel.tunnel_id}-S01", "名称": "洞口段", "长度(m)": 30.0, "开挖方法": "洞口", "围岩等级": "V级"},
                    {"ID": f"{tunnel.tunnel_id}-S02", "名称": "洞身段", "长度(m)": tunnel.total_length - 30.0, "开挖方法": "台阶法", "围岩等级": "IV级"},
                ])
                
                edited_df = st.data_editor(default_df, num_rows="dynamic", key=f"edit_{tunnel.tunnel_id}")
                
                if st.button("保存段落", key=f"save_{tunnel.tunnel_id}"):
                    tunnel.apply_changes(edited_df)
                    st.success("段落保存成功！")
    else:
        st.info("暂无隧道，请添加！")


def page_batch_generator():
    """检验批生成页面"""
    st.header("📦 检验批生成")
    
    if not st.session_state.projects or not st.session_state.current_project_id:
        st.warning("请先选择项目！")
        return
    
    project = st.session_state.projects[st.session_state.current_project_id]
    st.subheader(f"当前项目: {project.name}")
    
    selected_tunnels = st.multiselect(
        "选择要生成的隧道",
        options=[t.name for t in project.tunnels],
        default=[t.name for t in project.tunnels]
    )
    
    col1, col2 = st.columns(2)
    with col1:
        selected_standard = st.selectbox(
            "选择验收标准",
            options=[e for e in InspectionStandard],
            format_func=lambda e: f"{e.value} - {STANDARD_INFO[e]['industry']}"
        )
    
    if st.button("生成检验批"):
        if not selected_tunnels:
            st.warning("请选择至少一条隧道！")
        else:
            st.session_state.current_standard = selected_standard
            
            all_batches = []
            for tunnel in project.tunnels:
                if tunnel.name in selected_tunnels:
                    tunnel_start = tunnel.start_mileage
                    for section in tunnel.sections:
                        section_start = tunnel_start + sum(
                            s.length for s in tunnel.sections[:tunnel.sections.index(section)]
                        )
                        batches = generate_inspection_batches(tunnel, section, section_start)
                        all_batches.extend(batches)
            
            if all_batches:
                df = pd.DataFrame(all_batches)
                st.session_state.batch_df = df
                st.success(f"成功生成 {len(df)} 条检验批记录！")
                
                st.write("### 📊 生成统计")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("总记录数", len(df))
                with col_b:
                    st.metric("分部工程数", df["分部工程"].nunique())
                with col_c:
                    st.metric("隧道数", df["隧道名称"].nunique())
                
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 下载CSV",
                    csv,
                    f"检验批数据_{project.name}.csv",
                    "text/csv"
                )
            else:
                st.warning("未生成任何检验批记录！")


def page_summary():
    """汇总统计页面"""
    st.header("📈 汇总统计")
    
    if not st.session_state.projects:
        st.warning("暂无项目数据！")
        return
    
    summary_scope = st.radio("汇总范围", ["按工程汇总", "按选择隧道汇总"], horizontal=True)
    
    if summary_scope == "按工程汇总":
        all_batches_list = []
        for pid, proj in st.session_state.projects.items():
            df = generate_all_batches_for_project(proj)
            if not df.empty:
                df['项目名称'] = proj.name
                all_batches_list.append(df)
        
        if not all_batches_list:
            st.warning("暂无检验批数据！")
            return
        
        combined_df = pd.concat(all_batches_list, ignore_index=True)
        st.subheader("📊 全工程汇总统计")
    else:
        all_tunnel_options = []
        for pid, proj in st.session_state.projects.items():
            for t in proj.tunnels:
                all_tunnel_options.append(f"{proj.name} - {t.name}")
        
        selected_for_summary = st.multiselect("选择要汇总的隧道", all_tunnel_options)
        
        if not selected_for_summary:
            st.warning("请选择要汇总的隧道！")
            return
        
        all_batches_list = []
        for pid, proj in st.session_state.projects.items():
            for t in proj.tunnels:
                if f"{proj.name} - {t.name}" in selected_for_summary:
                    df = generate_all_batches_for_project(proj)
                    if not df.empty:
                        all_batches_list.append(df)
        
        if not all_batches_list:
            st.warning("未找到选中隧道的检验批数据！")
            return
        
        combined_df = pd.concat(all_batches_list, ignore_index=True)
        st.subheader(f"📊 选定隧道汇总统计 ({len(selected_for_summary)}条)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总检验批数", len(combined_df))
    with col2:
        st.metric("分部工程类型", combined_df["分部工程"].nunique())
    with col3:
        st.metric("涉及隧道", combined_df["隧道名称"].nunique())
    
    st.write("### 📋 按分部工程统计")
    by_subproject = combined_df.groupby("分部工程").agg({
        "检验批编号": "count",
        "进尺/长度": "sum"
    }).rename(columns={"检验批编号": "检验批数量", "进尺/长度": "总长度(m)"})
    st.dataframe(by_subproject)
    
    st.write("### 🚇 按隧道统计")
    by_tunnel = combined_df.groupby("隧道名称").agg({
        "检验批编号": "count",
        "进尺/长度": "sum"
    }).rename(columns={"检验批编号": "检验批数量", "进尺/长度": "总长度(m)"})
    st.dataframe(by_tunnel)


# ==================== 主程序 ====================
def main():
    """主函数"""
    st.title("🚇 泸州龙透关隧道检验批划分系统 V5")
    st.markdown("---")
    
    st.sidebar.title("导航菜单")
    
    st.sidebar.subheader("📐 验收标准")
    current_std = st.sidebar.selectbox(
        "当前标准",
        options=[e for e in InspectionStandard],
        index=0,
        format_func=lambda e: f"{e.value}",
        key="sidebar_standard"
    )
    if current_std != st.session_state.get('current_standard'):
        st.session_state.current_standard = current_std
    
    st.sidebar.info(f"当前: {STANDARD_INFO[current_std]['industry']}")
    
    page = st.sidebar.radio("功能模块", [
        "项目管理",
        "隧道编辑", 
        "检验批生成",
        "汇总统计",
        "方案编制V2"
    ])
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**快捷操作**")
    if st.sidebar.button("🔄 刷新数据"):
        st.rerun()
    
    if page == "项目管理":
        page_project_manager()
    elif page == "隧道编辑":
        page_tunnel_editor()
    elif page == "检验批生成":
        page_batch_generator()
    elif page == "汇总统计":
        page_summary()
    elif page == "方案编制V2":
        if SCHEME_GENERATOR_V2_AVAILABLE:
            if SCHEME_GENERATOR_V2_TYPE == "fixed":
                get_page_content_v2()
            else:
                page_scheme_generator_v2()
        else:
            st.error("方案编制V2模块不可用！")


if __name__ == "__main__":
    main()
