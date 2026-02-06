"""
泸州龙透关隧道工程检验批划分系统 V6.0
基于TB10753-2018铁路隧道工程施工质量验收标准
参照泸州龙透关隧道工程检验批划分方案（V2.0）

重大更新：
1. 按照泸州方案标准，四条隧道完整参数配置
2. 初支检验批细分为4个：喷射混凝土、锚杆、钢架、钢筋网
3. CD法：每循环8个检验批（4开挖+4初支）
4. 台阶法：每循环4个检验批（2开挖+2初支）
5. 实时联动更新表格和图形
6. 防水和二衬剥离开来，单独从洞口重新按照台车长度划分
   - 主线隧道：12m/段
   - 匝道隧道：9m/段

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
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="泸州龙透关隧道检验批系统 V6.0",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 泸州龙透关四条隧道完整配置 ====================
# 按照泸州龙透关隧道工程检验批划分方案（V2.0）提取

LZTG_TUNNELS = {
    "ZK": {
        "name": "主线左线隧道",
        "start_km": 245.102,
        "end_km": 1408.000,
        "total_length": 1162.898,
        "excavation_direction": "正向",
        "rock_grades": [
            {"grade": "V级", "start_km": 245.102, "end_km": 725.000, "length": 479.898, "method": "CD法"},
            {"grade": "IV级", "start_km": 725.000, "end_km": 1408.000, "length": 683.000, "method": "台阶法"}
        ],
        "portal_length": 30.0  # 洞口段长度
    },
    "YK": {
        "name": "主线右线隧道",
        "start_km": 244.803,
        "end_km": 1406.000,
        "total_length": 1161.197,
        "excavation_direction": "正向",
        "rock_grades": [
            {"grade": "V级", "start_km": 244.803, "end_km": 516.000, "length": 271.197, "method": "CD法"},
            {"grade": "IV级", "start_km": 516.000, "end_km": 1406.000, "length": 890.000, "method": "台阶法"}
        ],
        "portal_length": 30.0
    },
    "AK": {
        "name": "A匝道隧道",
        "start_km": 87.000,
        "end_km": 425.500,
        "total_length": 338.500,
        "excavation_direction": "正向",
        "rock_grades": [
            {"grade": "V级", "start_km": 87.000, "end_km": 287.000, "length": 200.000, "method": "CD法"},
            {"grade": "IV级", "start_km": 287.000, "end_km": 425.500, "length": 138.500, "method": "台阶法"}
        ],
        "portal_length": 20.0
    },
    "BK": {
        "name": "B匝道隧道",
        "start_km": 164.000,
        "end_km": 755.000,
        "total_length": 591.000,
        "excavation_direction": "正向",
        "rock_grades": [
            {"grade": "V级", "start_km": 164.000, "end_km": 510.000, "length": 346.000, "method": "CD法"},
            {"grade": "IV级", "start_km": 510.000, "end_km": 755.000, "length": 245.000, "method": "台阶法"}
        ],
        "portal_length": 20.0
    }
}

# ==================== 泸州方案标准配置 ====================
# 循环进尺（按照泸州方案V2.0）
ADVANCE_PER_CYCLE = {
    "CD法": 0.8,      # V级围岩
    "台阶法": 1.6,     # IV级围岩
    "洞口": 0.4,       # 洞口段按0.4m一段
    "全断面法": 1.6,
    "环形开挖法": 1.2
}

# 二衬台车长度（泸州方案：主线12m，匝道9m）
TROLLEY_LENGTHS = {
    "ZK": 12.0,  # 主线左线
    "YK": 12.0,  # 主线右线
    "AK": 9.0,   # A匝道
    "BK": 9.0,   # B匝道
    "default": 12.0
}

def is_ramp_tunnel(tunnel_id: str) -> bool:
    """判断是否为匝道隧道"""
    return tunnel_id in ["AK", "BK"]

def get_trolley_length(tunnel_id: str) -> float:
    """获取台车长度（主线12m，匝道9m）"""
    return TROLLEY_LENGTHS.get(tunnel_id, TROLLEY_LENGTHS["default"])

# 里程段长度（泸州方案：200m一段）
MILEAGE_SEGMENT_LENGTH = 200.0

# ==================== 泸州方案检验批工序映射 ====================
# 关键修正：初支包含4个检验批（喷射混凝土、锚杆、钢架、钢筋网）

# CD法工序（每循环20个检验批：4开挖+4×4初支）
CD_METHOD_WORK_ITEMS = [
    # 开挖检验批（4个）
    {"name": "左上导洞开挖", "code": "01", "分部": "02", "分项": "01", "工序": "开挖", "序号": "001"},
    {"name": "右上导洞开挖", "code": "01", "分部": "02", "分项": "01", "工序": "开挖", "序号": "002"},
    {"name": "左下导洞开挖", "code": "01", "分部": "02", "分项": "01", "工序": "开挖", "序号": "003"},
    {"name": "右下导洞开挖", "code": "01", "分部": "02", "分项": "01", "工序": "开挖", "序号": "004"},
    # 初支检验批（4×4=16个）- 修正：分开为4个检验批
    {"name": "左上导洞喷射混凝土", "code": "01", "分部": "03", "分项": "01", "工序": "初支", "序号": "001"},
    {"name": "左上导洞锚杆", "code": "02", "分部": "03", "分项": "02", "工序": "初支", "序号": "001"},
    {"name": "左上导洞钢架", "code": "03", "分部": "03", "分项": "03", "工序": "初支", "序号": "001"},
    {"name": "左上导洞钢筋网", "code": "04", "分部": "03", "分项": "04", "工序": "初支", "序号": "001"},
    {"name": "右上导洞喷射混凝土", "code": "01", "分部": "03", "分项": "01", "工序": "初支", "序号": "002"},
    {"name": "右上导洞锚杆", "code": "02", "分部": "03", "分项": "02", "工序": "初支", "序号": "002"},
    {"name": "右上导洞钢架", "code": "03", "分部": "03", "分项": "03", "工序": "初支", "序号": "002"},
    {"name": "右上导洞钢筋网", "code": "04", "分部": "03", "分项": "04", "工序": "初支", "序号": "002"},
    {"name": "左下导洞喷射混凝土", "code": "01", "分部": "03", "分项": "01", "工序": "初支", "序号": "003"},
    {"name": "左下导洞锚杆", "code": "02", "分部": "03", "分项": "02", "工序": "初支", "序号": "003"},
    {"name": "左下导洞钢架", "code": "03", "分部": "03", "分项": "03", "工序": "初支", "序号": "003"},
    {"name": "左下导洞钢筋网", "code": "04", "分部": "03", "分项": "04", "工序": "初支", "序号": "003"},
    {"name": "右下导洞喷射混凝土", "code": "01", "分部": "03", "分项": "01", "工序": "初支", "序号": "004"},
    {"name": "右下导洞锚杆", "code": "02", "分部": "03", "分项": "02", "工序": "初支", "序号": "004"},
    {"name": "右下导洞钢架", "code": "03", "分部": "03", "分项": "03", "工序": "初支", "序号": "004"},
    {"name": "右下导洞钢筋网", "code": "04", "分部": "03", "分项": "04", "工序": "初支", "序号": "004"},
]

# 台阶法工序（每循环10个检验批：2开挖+4×2初支）
BENCH_METHOD_WORK_ITEMS = [
    # 开挖检验批（2个）
    {"name": "上台阶开挖", "code": "01", "分部": "02", "分项": "01", "工序": "开挖", "序号": "001"},
    {"name": "下台阶开挖", "code": "01", "分部": "02", "分项": "01", "工序": "开挖", "序号": "002"},
    # 初支检验批（4×2=8个）- 修正：分开为4个检验批
    {"name": "上台阶喷射混凝土", "code": "01", "分部": "03", "分项": "01", "工序": "初支", "序号": "001"},
    {"name": "上台阶锚杆", "code": "02", "分部": "03", "分项": "02", "工序": "初支", "序号": "001"},
    {"name": "上台阶钢架", "code": "03", "分部": "03", "分项": "03", "工序": "初支", "序号": "001"},
    {"name": "上台阶钢筋网", "code": "04", "分部": "03", "分项": "04", "工序": "初支", "序号": "001"},
    {"name": "下台阶喷射混凝土", "code": "01", "分部": "03", "分项": "01", "工序": "初支", "序号": "002"},
    {"name": "下台阶锚杆", "code": "02", "分部": "03", "分项": "02", "工序": "初支", "序号": "002"},
    {"name": "下台阶钢架", "code": "03", "分部": "03", "分项": "03", "工序": "初支", "序号": "002"},
    {"name": "下台阶钢筋网", "code": "04", "分部": "03", "分项": "04", "工序": "初支", "序号": "002"},
]

# 洞口工序
PORTAL_WORK_ITEMS = [
    {"name": "洞口开挖", "code": "01", "分部": "01", "分项": "01", "工序": "洞口"},
    {"name": "洞口喷射混凝土", "code": "01", "分部": "01", "分项": "02", "工序": "洞口"},
    {"name": "洞口锚杆", "code": "02", "分部": "01", "分项": "02", "工序": "洞口"},
    {"name": "洞口钢架", "code": "03", "分部": "01", "分项": "02", "工序": "洞口"},
    {"name": "洞口钢筋网", "code": "04", "分部": "01", "分项": "02", "工序": "洞口"},
    {"name": "洞口排水", "code": "01", "分部": "01", "分项": "03", "工序": "洞口"},
]

# 二衬工序
LINING_WORK_ITEMS = [
    {"name": "二衬模板台车", "code": "01", "分部": "04", "分项": "01", "工序": "二衬"},
    {"name": "二衬混凝土浇筑", "code": "02", "分部": "04", "分项": "02", "工序": "二衬"},
]

# 防水工序
WATERPROOF_WORK_ITEMS = [
    {"name": "防水板铺设", "code": "01", "分部": "05", "分项": "01", "工序": "防水"},
    {"name": "止水带安装", "code": "02", "分部": "05", "分项": "02", "工序": "防水"},
    {"name": "排水管安装", "code": "03", "分部": "05", "分项": "03", "工序": "防水"},
]

# ==================== 数据模型 ====================
@dataclass
class TunnelSection:
    """隧道段落"""
    section_id: str
    name: str
    start_km: float
    end_km: float
    length: float
    excavation_method: str
    rock_grade: str
    cycle_count: int = 0
    
    @property
    def mileage_range(self) -> str:
        prefix = "ZK" if self.section_id.startswith("ZK") else \
                 "YK" if self.section_id.startswith("YK") else \
                 "AK" if self.section_id.startswith("AK") else \
                 "BK" if self.section_id.startswith("BK") else ""
        return f"{prefix}{self.start_km:.3f}~{prefix}{self.end_km:.3f}"
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass  
class Tunnel:
    """完整隧道定义"""
    tunnel_id: str
    name: str
    start_km: float
    end_km: float
    total_length: float
    excavation_direction: str = "正向"
    sections: List[TunnelSection] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.sections:
            self.auto_generate_sections()
    
    def auto_generate_sections(self):
        """自动生成段落（按照泸州方案）"""
        config = LZTG_TUNNELS.get(self.tunnel_id, {})
        rock_grades = config.get("rock_grades", [])
        portal_length = config.get("portal_length", 20.0)
        
        self.sections = []
        
        # 添加洞口段
        portal_end_km = self.start_km + portal_length / 1000
        portal_section = TunnelSection(
            section_id=f"{self.tunnel_id}-S01",
            name="洞口段",
            start_km=self.start_km,
            end_km=portal_end_km,
            length=portal_length,
            excavation_method="洞口",
            rock_grade="V级",
            cycle_count=0
        )
        self.sections.append(portal_section)
        
        # 添加洞身段
        for i, rg in enumerate(rock_grades):
            section = TunnelSection(
                section_id=f"{self.tunnel_id}-S{i+2:02d}",
                name=f"洞身段{rg['grade']}",
                start_km=rg["start_km"],
                end_km=rg["end_km"],
                length=rg["length"],
                excavation_method=rg["method"],
                rock_grade=rg["grade"],
                cycle_count=0
            )
            section.cycle_count = self.calculate_cycle_count(section)
            self.sections.append(section)
    
    def calculate_cycle_count(self, section: TunnelSection) -> int:
        """计算循环数"""
        if section.excavation_method == "洞口":
            return int(section.length / 0.4)
        elif section.excavation_method == "CD法":
            return int(section.length / 0.8)
        elif section.excavation_method == "台阶法":
            return int(section.length / 1.6)
        else:
            return int(section.length / 1.6)
    
    def recalculate_all_cycles(self):
        """重新计算所有循环数"""
        for section in self.sections:
            section.cycle_count = self.calculate_cycle_count(section)
    
    def to_dict(self) -> dict:
        return {
            "tunnel_id": self.tunnel_id,
            "name": self.name,
            "start_km": self.start_km,
            "end_km": self.end_km,
            "total_length": self.total_length,
            "excavation_direction": self.excavation_direction,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Tunnel':
        tunnel = cls(
            tunnel_id=data["tunnel_id"],
            name=data["name"],
            start_km=data["start_km"],
            end_km=data["end_km"],
            total_length=data["total_length"],
            excavation_direction=data.get("excavation_direction", "正向")
        )
        tunnel.sections = []
        for s_data in data.get("sections", []):
            section = TunnelSection(
                section_id=s_data["section_id"],
                name=s_data["name"],
                start_km=s_data["start_km"],
                end_km=s_data["end_km"],
                length=s_data["length"],
                excavation_method=s_data["excavation_method"],
                rock_grade=s_data["rock_grade"],
                cycle_count=s_data.get("cycle_count", 0)
            )
            tunnel.sections.append(section)
        return tunnel

# ==================== 检验批生成核心函数 ====================
def generate_inspection_batch_code(
    tunnel_id: str, 
    section_code: str, 
    method_code: str,
    mileage_segment: str,
    cycle_num: int,
    item_seq: str
) -> str:
    """
    生成泸州方案标准检验批编号
    格式: [单位工程]-[分部]-[分项]-[施工方法]-[里程段]-[循环号]-[序号]
    示例: ZK-02-01-C-0001-0001-001
    """
    return f"{tunnel_id}-{section_code}-{method_code}-{mileage_segment}-{cycle_num:04d}-{item_seq}"

def get_mileage_segment(km: float) -> str:
    """计算里程段编号（每200m一段）"""
    segment = int(km / 200)
    return f"{segment:04d}"

def calculate_lining_segments(tunnel: Tunnel) -> List[dict]:
    """
    计算二衬分段（从洞口开始，按台车长度独立划分）
    - 主线隧道：12m/段
    - 匝道隧道：9m/段
    防水和二衬剥离开来，单独从洞口重新划分
    """
    segments = []
    current_km = tunnel.start_km  # 从洞口起点开始
    segment_num = 1
    trolley_len = get_trolley_length(tunnel.tunnel_id)
    
    while current_km < tunnel.end_km:
        next_km = min(current_km + trolley_len / 1000, tunnel.end_km)
        length = (next_km - current_km) * 1000
        
        prefix = tunnel.tunnel_id
        mileage_range = f"{prefix}{current_km:.3f}~{prefix}{next_km:.3f}"
        
        segments.append({
            "段号": segment_num,
            "里程范围": mileage_range,
            "长度(m)": round(length, 1),
            "起点里程": current_km,
            "终点里程": next_km
        })
        
        current_km = next_km
        segment_num += 1
    
    return segments

def calculate_waterproof_segments(tunnel: Tunnel) -> List[dict]:
    """
    计算防水分段（与二衬同步，从洞口开始按台车长度划分）
    """
    return calculate_lining_segments(tunnel)

def calculate_total_batches(tunnel: Tunnel) -> dict:
    """
    计算隧道检验批总数
    - 开挖+初支：按段落循环计算
    - 二衬+防水：从洞口开始按台车长度独立划分（主线12m，匝道9m）
    """
    total = 0
    by_section = {}
    by_phase = {"开挖初支": 0, "二衬": 0, "防水": 0, "洞口": 0}
    
    for section in tunnel.sections:
        if section.excavation_method == "洞口":
            batches = 6  # 洞口：开挖1 + 喷射1 + 锚杆1 + 钢架1 + 钢筋网1 + 排水1
            by_section[section.name] = batches
            by_phase["洞口"] += batches
            total += batches
        elif section.excavation_method == "CD法":
            # CD法：4开挖 + 4×4初支 = 20个/循环
            batches = section.cycle_count * 20
            by_section[section.name] = batches
            by_phase["开挖初支"] += batches
            total += batches
        elif section.excavation_method == "台阶法":
            # 台阶法：2开挖 + 4×2初支 = 10个/循环
            batches = section.cycle_count * 10
            by_section[section.name] = batches
            by_phase["开挖初支"] += batches
            total += batches
    
    # 二衬：按台车长度划分，从洞口开始
    trolley_len = get_trolley_length(tunnel.tunnel_id)
    lining_segments = calculate_lining_segments(tunnel)
    
    # 二衬：每个分段2个检验批（模板台车+混凝土浇筑）
    lining_batches = len(lining_segments) * 2
    by_phase["二衬"] = lining_batches
    total += lining_batches
    
    # 防水：每个分段2个检验批（防水板+止水带）
    # 排水管按每2段设置1个
    waterproof_batches = len(lining_segments) * 2  # 防水板+止水带
    if len(lining_segments) > 1:
        waterproof_batches += (len(lining_segments) + 1) // 2  # 排水管
    by_phase["防水"] = waterproof_batches
    total += waterproof_batches
    
    return {
        "total": total,
        "by_section": by_section,
        "by_phase": by_phase,
        "lining_segments": len(lining_segments),
        "trolley_length": trolley_len
    }

# ==================== 实时联动更新函数 ====================
def update_tunnel_from_sections(tunnel_id: str, sections_df: pd.DataFrame) -> Tunnel:
    """从编辑后的表格更新隧道段落"""
    config = LZTG_TUNNELS.get(tunnel_id, {})
    tunnel = Tunnel(
        tunnel_id=tunnel_id,
        name=config.get("name", tunnel_id),
        start_km=config.get("start_km", 0),
        end_km=config.get("end_km", 0),
        total_length=config.get("total_length", 0)
    )
    
    # 清空自动生成的段落
    tunnel.sections = []
    
    # 从表格读取段落
    for idx, row in sections_df.iterrows():
        section = TunnelSection(
            section_id=row["ID"],
            name=row["名称"],
            start_km=row["起点里程"],
            end_km=row["终点里程"],
            length=row["长度(m)"],
            excavation_method=row["开挖方法"],
            rock_grade=row["围岩等级"],
            cycle_count=row.get("循环数", 0)
        )
        tunnel.sections.append(section)
    
    # 重新计算总长度
    tunnel.total_length = sum(s.length for s in tunnel.sections)
    
    return tunnel

def generate_linked_visualization(tunnels: Dict[str, Tunnel]) -> go.Figure:
    """生成四条隧道的可视化对比图"""
    fig = go.Figure()
    
    colors = {"ZK": "#1f77b4", "YK": "#ff7f0e", "AK": "#2ca02c", "BK": "#d62728"}
    
    for tunnel_id, tunnel in tunnels.items():
        color = colors.get(tunnel_id, "#333333")
        
        # 绘制各段落
        for section in tunnel.sections:
            # 洞口段
            if section.excavation_method == "洞口":
                fig.add_trace(go.Scatter(
                    x=[section.start_km, section.end_km],
                    y=[tunnel_id, tunnel_id],
                    mode='lines+markers',
                    line=dict(color=color, width=20),
                    marker=dict(size=8),
                    name=f"{tunnel_id}-{section.name}",
                    hovertemplate=f"{tunnel.name}<br>{section.name}<br>"
                                 f"里程: {section.mileage_range}<br>"
                                 f"长度: {section.length}m<br>"
                                 f"方法: {section.excavation_method}<br>"
                                 f"<extra></extra>"
                ))
            else:
                # 洞身段
                fig.add_trace(go.Scatter(
                    x=[section.start_km, section.end_km],
                    y=[tunnel_id, tunnel_id],
                    mode='lines',
                    line=dict(color=color, width=30),
                    name=f"{tunnel_id}-{section.rock_grade}",
                    hovertemplate=f"{tunnel.name}<br>{section.name}<br>"
                                 f"里程: {section.mileage_range}<br>"
                                 f"长度: {section.length}m<br>"
                                 f"方法: {section.excavation_method}<br>"
                                 f"循环: {section.cycle_count}<br>"
                                 f"<extra></extra>"
                ))
    
    fig.update_layout(
        title="泸州龙透关四条隧道段落划分对比图",
        xaxis_title="里程 (km)",
        yaxis_title="隧道",
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig

def generate_batch_statistics_chart(tunnel: Tunnel) -> go.Figure:
    """生成检验批统计图表"""
    stats = calculate_total_batches(tunnel)
    
    # 按施工阶段分类
    phases = list(stats["by_phase"].keys())
    counts = list(stats["by_phase"].values())
    
    fig = px.bar(
        x=phases,
        y=counts,
        labels={"x": "施工阶段", "y": "检验批数量"},
        title=f"{tunnel.name} - 检验批统计",
        color=counts,
        color_continuous_scale="Blues"
    )
    
    fig.update_layout(height=300)
    
    return fig

# ==================== Streamlit页面函数 ====================
def page_tunnel_editor():
    """隧道编辑页面"""
    st.header("🚇 四条隧道段落编辑")
    st.markdown("""
    **泸州龙透关隧道工程** - 四条隧道完整参数配置
    
    按里程段自动划分，实时联动更新表格和图形。
    """)
    
    # 初始化session state
    if 'tunnels' not in st.session_state:
        st.session_state.tunnels = {}
        for tunnel_id, config in LZTG_TUNNELS.items():
            tunnel = Tunnel(
                tunnel_id=tunnel_id,
                name=config["name"],
                start_km=config["start_km"],
                end_km=config["end_km"],
                total_length=config["total_length"]
            )
            st.session_state.tunnels[tunnel_id] = tunnel
    
    # 标签页显示四条隧道
    tabs = st.tabs([f"{tid}: {tun['name']}" for tid, tun in LZTG_TUNNELS.items()])
    
    for tab, (tunnel_id, config) in zip(tabs, LZTG_TUNNELS.items()):
        with tab:
            tunnel = st.session_state.tunnels[tunnel_id]
            
            st.subheader(f"{tunnel.name} - {tunnel.total_length:.3f}m")
            
            # 显示总统计
            stats = calculate_total_batches(tunnel)
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("检验批总数", stats["total"])
            with col2:
                cd_cycles = stats["by_phase"]["开挖初支"] // 20 if tunnel.sections[1].excavation_method == "CD法" else 0
                st.metric("CD法循环", cd_cycles)
            with col3:
                bench_cycles = stats["by_phase"]["开挖初支"] // 10 if tunnel.sections[1].excavation_method == "台阶法" else 0
                st.metric("台阶法循环", bench_cycles)
            with col4:
                st.metric("二衬分段", stats["lining_segments"])
            with col5:
                st.metric("段落数", len(tunnel.sections))
            
            # 显示台车长度
            trolley_len = get_trolley_length(tunnel_id)
            st.info(f"📏 二衬台车长度: {trolley_len:.0f}m ({'主线' if not is_ramp_tunnel(tunnel_id) else '匝道'})")
            
            # 编辑段落表格
            st.write("### 段落划分（实时编辑）")
            
            # 创建可编辑表格
            sections_data = []
            for section in tunnel.sections:
                sections_data.append({
                    "ID": section.section_id,
                    "名称": section.name,
                    "起点里程": section.start_km,
                    "终点里程": section.end_km,
                    "长度(m)": section.length,
                    "开挖方法": section.excavation_method,
                    "围岩等级": section.rock_grade,
                    "循环数": section.cycle_count
                })
            
            edited_df = st.data_editor(
                pd.DataFrame(sections_data),
                num_rows="dynamic",
                key=f"edit_{tunnel_id}",
                column_config={
                    "开挖方法": st.column_config.SelectboxColumn(
                        "开挖方法",
                        options=["洞口", "CD法", "台阶法", "全断面法"],
                        required=True
                    ),
                    "围岩等级": st.column_config.SelectboxColumn(
                        "围岩等级",
                        options=["III级", "IV级", "V级", "VI级"],
                        required=True
                    ),
                    "长度(m)": st.column_config.NumberColumn(
                        "长度(m)",
                        min_value=0.1,
                        format="%.1f"
                    ),
                    "起点里程": st.column_config.NumberColumn(
                        "起点里程",
                        format="%.3f"
                    ),
                    "终点里程": st.column_config.NumberColumn(
                        "终点里程",
                        format="%.3f"
                    ),
                }
            )
            
            # 检测变化并更新
            if not edited_df.equals(pd.DataFrame(sections_data)):
                # 用户修改了表格，更新隧道
                new_tunnel = update_tunnel_from_sections(tunnel_id, edited_df)
                st.session_state.tunnels[tunnel_id] = new_tunnel
                
                # 重新计算循环数
                new_tunnel.recalculate_all_cycles()
                
                st.success("✅ 段落已更新，循环数已重新计算！")
                st.rerun()
            
            # 显示检验批预览
            with st.expander("检验批数量预览", expanded=True):
                st.write("#### 按段落统计")
                for section in tunnel.sections:
                    if section.excavation_method == "洞口":
                        batch_count = 6
                    elif section.excavation_method == "CD法":
                        batch_count = section.cycle_count * 20
                    else:
                        batch_count = section.cycle_count * 10
                    
                    st.write(f"- **{section.name}** ({section.length:.1f}m): {batch_count} 个检验批")
                
                st.write("#### 二衬分段预览")
                lining_segments = calculate_lining_segments(tunnel)
                for seg in lining_segments[:5]:  # 只显示前5段
                    st.write(f"- 第{seg['段号']:02d}段: {seg['里程范围']} ({seg['长度(m)']:.1f}m)")
                if len(lining_segments) > 5:
                    st.write(f"... 共{len(lining_segments)}段")


def page_batch_generator():
    """检验批生成页面"""
    st.header("📦 检验批生成")
    st.markdown("根据泸州方案V2.0标准生成检验批")
    
    if not st.session_state.get('tunnels'):
        st.warning("请先在【隧道编辑】页面生成隧道配置！")
        return
    
    # 选择隧道
    tunnel_ids = list(st.session_state.tunnels.keys())
    selected_tunnels = st.multiselect(
        "选择要生成的隧道",
        options=tunnel_ids,
        default=tunnel_ids
    )
    
    if st.button("生成检验批"):
        all_batches = []
        
        for tunnel_id in selected_tunnels:
            tunnel = st.session_state.tunnels[tunnel_id]
            
            for section in tunnel.sections:
                mileage_seg = get_mileage_segment(section.start_km)
                
                if section.excavation_method == "CD法":
                    work_items = CD_METHOD_WORK_ITEMS
                elif section.excavation_method == "台阶法":
                    work_items = BENCH_METHOD_WORK_ITEMS
                else:  # 洞口
                    work_items = PORTAL_WORK_ITEMS
                
                for cycle in range(1, section.cycle_count + 1):
                    curr_m = section.start_km * 1000 + (cycle - 1) * (
                        800 if section.excavation_method == "CD法" else 1600
                    )
                    next_m = curr_m + (
                        800 if section.excavation_method == "CD法" else 1600
                    )
                    
                    prefix = tunnel_id
                    mileage_range = f"{prefix}{curr_m/1000:.3f}~{prefix}{next_m/1000:.3f}"
                    
                    for item in work_items:
                        if section.excavation_method == "洞口":
                            # 洞口不区分循环
                            batch_code = f"{tunnel_id}-{item['分部']}-{item['code']}-{mileage_seg}-0001-{item['序号']}"
                        else:
                            batch_code = generate_inspection_batch_code(
                                tunnel_id,
                                item['分部'],
                                "C" if section.excavation_method == "CD法" else "B",
                                mileage_seg,
                                cycle,
                                item['序号']
                            )
                        
                        all_batches.append({
                            "检验批编号": batch_code,
                            "隧道名称": tunnel.name,
                            "分部工程": {
                                "02": "洞身开挖", "03": "支护", "01": "洞口工程",
                                "04": "衬砌", "05": "防水与排水"
                            }.get(item['分部'], "未知"),
                            "分项工程": item['name'],
                            "施工方法": section.excavation_method,
                            "里程范围": mileage_range if section.excavation_method != "洞口" else 
                                       f"{prefix}{section.start_km:.3f}~{prefix}{section.end_km:.3f}",
                            "循环号": cycle if section.excavation_method != "洞口" else "-",
                            "围岩等级": section.rock_grade,
                            "验收标准": "TB10753-2018"
                        })
                    
                    # 仰拱（每10个循环一个）
                    if cycle % 10 == 0:
                        all_batches.append({
                            "检验批编号": f"{tunnel_id}-02-02-{mileage_seg}-{cycle:04d}-001",
                            "隧道名称": tunnel.name,
                            "分部工程": "洞身开挖",
                            "分项工程": "仰拱开挖",
                            "施工方法": section.excavation_method,
                            "里程范围": mileage_range,
                            "循环号": cycle,
                            "围岩等级": section.rock_grade,
                            "验收标准": "TB10753-2018"
                        })
            
            # 二衬检验批（从洞口开始，按台车长度划分）
            lining_segments = calculate_lining_segments(tunnel)
            for seg in lining_segments:
                # 里程段编号
                mileage_seg = get_mileage_segment(seg["起点里程"])
                
                for item in LINING_WORK_ITEMS:
                    batch_code = f"{tunnel_id}-{item['分部']}-{item['code']}-{mileage_seg}-{seg['段号']:04d}-001"
                    all_batches.append({
                        "检验批编号": batch_code,
                        "隧道名称": tunnel.name,
                        "分部工程": {"04": "衬砌"}.get(item['分部'], "未知"),
                        "分项工程": item['name'],
                        "施工方法": "台车模筑",
                        "里程范围": seg["里程范围"],
                        "循环号": seg['段号'],
                        "围岩等级": "-",
                        "验收标准": "TB10753-2018"
                    })
                
                # 防水检验批
                for w_item in WATERPROOF_WORK_ITEMS[:2]:  # 防水板和止水带
                    batch_code = f"{tunnel_id}-{w_item['分部']}-{w_item['code']}-{mileage_seg}-{seg['段号']:04d}-001"
                    all_batches.append({
                        "检验批编号": batch_code,
                        "隧道名称": tunnel.name,
                        "分部工程": {"05": "防水与排水"}.get(w_item['分部'], "未知"),
                        "分项工程": w_item['name'],
                        "施工方法": "台车模筑",
                        "里程范围": seg["里程范围"],
                        "循环号": seg['段号'],
                        "围岩等级": "-",
                        "验收标准": "TB10753-2018"
                    })
                
                # 排水管：每隔1段设置1个检验批
                if seg['段号'] % 2 == 1:
                    drainage_item = WATERPROOF_WORK_ITEMS[2]  # 排水管安装
                    batch_code = f"{tunnel_id}-{drainage_item['分部']}-{drainage_item['code']}-{mileage_seg}-{seg['段号']:04d}-001"
                    all_batches.append({
                        "检验批编号": batch_code,
                        "隧道名称": tunnel.name,
                        "分部工程": "防水与排水",
                        "分项工程": drainage_item['name'],
                        "施工方法": "台车模筑",
                        "里程范围": seg["里程范围"],
                        "循环号": seg['段号'],
                        "围岩等级": "-",
                        "验收标准": "TB10753-2018"
                    })
        
        if all_batches:
            df = pd.DataFrame(all_batches)
            st.session_state.batch_df = df
            st.success(f"✅ 成功生成 {len(df)} 条检验批记录！")
            
            # 显示统计
            st.write("### 📊 生成统计")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总记录数", len(df))
            with col2:
                st.metric("分部类型数", df["分部工程"].nunique())
            with col3:
                st.metric("隧道数", df["隧道名称"].nunique())
            with col4:
                st.metric("循环数", df[df["循环号"] != "-"]["循环号"].max())
            
            # 按分部统计
            st.write("#### 按分部工程统计")
            by_subproject = df.groupby("分部工程").size().reset_index(name="检验批数量")
            st.dataframe(by_subproject)
            
            # 显示数据
            st.dataframe(df, use_container_width=True)
            
            # 导出
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 下载CSV",
                csv,
                f"检验批数据_V6.0.csv",
                "text/csv"
            )
        else:
            st.warning("未生成任何检验批记录！")


def page_visualization():
    """可视化页面"""
    st.header("📊 可视化分析")
    
    if not st.session_state.get('tunnels'):
        st.warning("请先在【隧道编辑】页面生成隧道配置！")
        return
    
    tunnels = st.session_state.tunnels
    
    # 四条隧道对比图
    st.write("### 四条隧道段落对比")
    fig = generate_linked_visualization(tunnels)
    st.plotly_chart(fig, use_container_width=True)
    
    # 各隧道统计图
    st.write("### 各隧道检验批统计")
    cols = st.columns(4)
    
    for idx, (tunnel_id, tunnel) in enumerate(tunnels.items()):
        with cols[idx]:
            fig = generate_batch_statistics_chart(tunnel)
            st.plotly_chart(fig, use_container_width=True)


def page_summary():
    """汇总统计页面"""
    st.header("📈 汇总统计")
    
    if not st.session_state.get('tunnels'):
        st.warning("暂无隧道数据！")
        return
    
    tunnels = st.session_state.tunnels
    
    # 项目总体统计
    st.write("### 泸州龙透关项目总体统计")
    
    total_batches = 0
    total_length = 0
    total_cycles = 0
    
    stats_data = []
    
    for tunnel_id, tunnel in tunnels.items():
        stats = calculate_total_batches(tunnel)
        total_batches += stats["total"]
        total_length += tunnel.total_length
        total_cycles += sum(s.cycle_count for s in tunnel.sections)
        
        # 计算CD法和台阶法循环数
        cd_cycles = 0
        bench_cycles = 0
        for section in tunnel.sections:
            if section.excavation_method == "CD法":
                cd_cycles += section.cycle_count
            elif section.excavation_method == "台阶法":
                bench_cycles += section.cycle_count
        
        stats_data.append({
            "隧道": tunnel.name,
            "长度(m)": round(tunnel.total_length, 3),
            "段落数": len(tunnel.sections),
            "检验批总数": stats["total"],
            "CD法循环": cd_cycles,
            "台阶法循环": bench_cycles,
            "二衬分段": stats["lining_segments"],
            "台车长度(m)": stats["trolley_length"]
        })
    
    # 总计行
    stats_data.append({
        "隧道": "**合计**",
        "长度(m)": round(total_length, 3),
        "段落数": sum(len(t.sections) for t in tunnels.values()),
        "检验批总数": total_batches,
        "CD法循环": sum(s["CD法循环"] for s in stats_data[:-1]),
        "台阶法循环": sum(s["台阶法循环"] for s in stats_data[:-1]),
        "二衬分段": sum(s["二衬分段"] for s in stats_data[:-1]),
        "台车长度(m)": "-"
    })
    
    st.dataframe(pd.DataFrame(stats_data), use_container_width=True)
    
    # 对比图表
    st.write("### 隧道对比分析")
    
    df_stats = pd.DataFrame(stats_data[:-1])  # 排除合计行
    
    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.bar(
            df_stats,
            x="隧道",
            y="检验批总数",
            title="各隧道检验批数量对比",
            color="检验批总数",
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        fig2 = px.bar(
            df_stats,
            x="隧道",
            y="长度(m)",
            title="各隧道长度对比",
            color="长度(m)",
            color_continuous_scale="Greens"
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # 检验批构成饼图
    st.write("### 检验批构成分析")
    
    phase_stats = {"开挖初支": 0, "二衬": 0, "防水": 0, "洞口": 0}
    for tunnel in tunnels.values():
        stats = calculate_total_batches(tunnel)
        for phase, count in stats["by_phase"].items():
            phase_stats[phase] = phase_stats.get(phase, 0) + count
    
    fig3 = px.pie(
        values=list(phase_stats.values()),
        names=list(phase_stats.keys()),
        title="检验批构成（按施工阶段）",
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    st.plotly_chart(fig3, use_container_width=True)


# ==================== 主程序 ====================
def main():
    """主函数"""
    st.title("🚇 泸州龙透关隧道检验批划分系统 V6.0")
    st.markdown("""
    **基于泸州龙透关隧道工程检验批划分方案（V2.0）**
    
    重大更新：
    - ✅ 四条隧道完整参数配置
    - ✅ 初支细分为4个检验批（喷射混凝土、锚杆、钢架、钢筋网）
    - ✅ CD法：每循环20个检验批（4开挖+4初支×4）
    - ✅ 台阶法：每循环10个检验批（2开挖+2初支×4）
    - ✅ 防水和二衬剥离开来，单独从洞口重新划分
    - ✅ 实时联动更新表格和图形
    - ✅ 台车长度：主线12m，匝道9m
    """)
    
    st.sidebar.title("导航菜单")
    
    page = st.sidebar.radio("功能模块", [
        "隧道编辑",
        "检验批生成",
        "可视化分析",
        "汇总统计"
    ])
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**当前配置**")
    st.sidebar.info("标准: TB10753-2018")
    st.sidebar.info("CD法进尺: 0.8m/循环")
    st.sidebar.info("台阶法进尺: 1.6m/循环")
    st.sidebar.info("主线台车: 12m")
    st.sidebar.info("匝道台车: 9m")
    
    if page == "隧道编辑":
        page_tunnel_editor()
    elif page == "检验批生成":
        page_batch_generator()
    elif page == "可视化分析":
        page_visualization()
    elif page == "汇总统计":
        page_summary()


if __name__ == "__main__":
    main()
