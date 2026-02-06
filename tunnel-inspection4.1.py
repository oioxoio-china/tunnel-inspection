"""
泸州龙透关隧道工程检验批划分系统 V5.0
特性：
1. 项目数据更新：包含ZK, YK, AK, BK四条独立隧道
2. 默认分段结构：洞口(2m)+进洞(30m)+标准段+出洞(30m)+洞口(2m)
3. 支持循环进尺自由编辑
4. 修复Excel导出报错
"""

import streamlit as st
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import math
import io

# 设置页面配置
st.set_page_config(
    page_title="泸州龙透关隧道检验批系统 V5",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 1. 标准与配置定义 ====================

class InspectionStandard(Enum):
    TB10753_2018 = "TB10753-2018"  # 高铁隧道
    TB10417 = "TB10417"            # 普通铁路
    JTG_F80 = "JTG F80"            # 公路隧道
    CJJ_37 = "CJJ 37"              # 市政隧道
    GB50299 = "GB 50299"           # 地铁隧道

# 各标准的分部工程编码
SUBPROJECT_CODES_BY_STANDARD = {
    InspectionStandard.TB10753_2018: {"洞口工程": "01", "超前支护": "02", "洞身开挖": "03", "初期支护": "04", "防排水": "07", "二次衬砌": "06"},
    InspectionStandard.JTG_F80: {"洞口工程": "01", "洞身开挖": "02", "初期支护": "03", "防排水": "05", "二次衬砌": "04"},
    "DEFAULT": {"洞口工程": "01", "洞身开挖": "02", "初期支护": "03", "防排水": "04", "二次衬砌": "05"}
}

# 默认进尺参考 (仅作为新建段落的默认值)
DEFAULT_ADVANCE_REF = {
    "洞口": 0.0,
    "CD法": 0.6,
    "台阶法": 1.2,
    "全断面法": 1.2
}

# 工序拆解配置
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
        {"name": "下台阶喷射混凝土", "code": "09", "分部": "初期支护", "步骤": 2},
        {"name": "仰拱开挖", "code": "10", "分部": "洞身开挖", "步骤": 3},
        {"name": "仰拱初期支护", "code": "11", "分部": "初期支护", "步骤": 3},
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
    "全断面法": [
        {"name": "全断面开挖", "code": "01", "分部": "洞身开挖", "步骤": 1},
        {"name": "全断面钢架安装", "code": "02", "分部": "初期支护", "步骤": 1},
        {"name": "全断面钢筋网", "code": "03", "分部": "初期支护", "步骤": 1},
        {"name": "全断面锚杆", "code": "04", "分部": "初期支护", "步骤": 1},
        {"name": "全断面喷射混凝土", "code": "05", "分部": "初期支护", "步骤": 1},
    ],
    "洞口": [
        {"name": "洞口开挖", "code": "01", "分部": "洞口工程", "步骤": 1},
        {"name": "洞口防护", "code": "02", "分部": "洞口工程", "步骤": 2},
    ]
}

# 独立二衬工序
LINING_WORK_ITEMS = [
    {"name": "防水层铺设", "code": "01", "分部": "防排水"},
    {"name": "二衬钢筋安装", "code": "02", "分部": "二次衬砌"},
    {"name": "二衬模板安装", "code": "03", "分部": "二次衬砌"},
    {"name": "二衬混凝土浇筑", "code": "04", "分部": "二次衬砌"},
]

class ExcavationMethod(Enum):
    台阶法 = "台阶法"
    CD法 = "CD法"
    全断面法 = "全断面法"
    洞口 = "洞口"

class RockGrade(Enum):
    III级 = "III级"
    IV级 = "IV级"
    V级 = "V级"

# ==================== 2. 数据模型 ====================

@dataclass
class Section:
    section_id: str
    name: str
    length: float
    excavation_method: str
    rock_grade: str = "IV级"
    advance_per_cycle: float = 1.2
    is_portal: bool = False
    
    @property
    def is_simple_portal(self) -> bool:
        return self.excavation_method == "洞口"

@dataclass
class Tunnel:
    tunnel_id: str
    name: str
    start_mileage: float
    end_mileage: float
    excavation_direction: str = "正向"
    sections: List[Section] = field(default_factory=list)
    
    @property
    def total_length(self) -> float:
        return abs(self.end_mileage - self.start_mileage)
    
    @property
    def direction_sign(self) -> int:
        return 1 if self.excavation_direction == "正向" else -1
    
    def get_paragraphs_with_positions(self) -> List[dict]:
        """获取带绝对里程的段落列表"""
        direction = self.direction_sign
        result = []
        current = self.start_mileage
        
        for i, section in enumerate(self.sections):
            if direction == 1:
                start, end = current, current + section.length
                current = end
            else:
                start, end = current, current - section.length
                current = end
            
            # 直接使用对象中存储的进尺，不强制覆盖
            advance = section.advance_per_cycle
            
            result.append({
                "序号": i + 1,
                "ID": section.section_id,
                "名称": section.name,
                "起点桩号": format_mileage(start),
                "终点桩号": format_mileage(end),
                "长度(m)": section.length,
                "开挖方法": section.excavation_method,
                "循环进尺(m)": advance,
                "围岩等级": section.rock_grade,
                "检验批": "❌" if section.is_simple_portal else "✅"
            })
        return result
    
    def apply_changes(self, df: pd.DataFrame):
        """从Editor DataFrame更新对象状态"""
        new_sections = []
        
        for idx, row in df.iterrows():
            method = row["开挖方法"]
            length = row["长度(m)"]
            user_advance = row["循环进尺(m)"]
            
            # 优先使用用户输入的值
            if user_advance >= 0:
                advance = user_advance
            else:
                # 默认兜底
                if method == "洞口": advance = 0.0
                elif method == "CD法": advance = 0.6
                elif method == "台阶法": advance = 1.2
                else: advance = 1.2
            
            section = Section(
                section_id=row["ID"],
                name=row["名称"],
                length=length,
                excavation_method=method,
                rock_grade=row["围岩等级"],
                advance_per_cycle=advance,
                is_portal=(method == "洞口")
            )
            new_sections.append(section)
        
        self.sections = new_sections

    def validate(self) -> tuple[bool, List[str]]:
        issues = []
        if not self.sections: return True, issues
        
        calc_total = sum(s.length for s in self.sections)
        # 允许0.005的误差
        if abs(calc_total - self.total_length) > 0.005:
            issues.append(f"段落总长({calc_total:.3f}) ≠ 隧道设计长({self.total_length:.3f})")
        return len(issues) == 0, issues

@dataclass
class Project:
    project_id: str
    name: str
    tunnels: List[Tunnel] = field(default_factory=list)

# ==================== 3. 辅助函数 ====================

def get_current_standard() -> InspectionStandard:
    if 'current_standard' not in st.session_state:
        st.session_state.current_standard = InspectionStandard.TB10753_2018
    return st.session_state.current_standard

def get_subproject_codes(standard: InspectionStandard = None) -> Dict[str, str]:
    if standard is None: standard = get_current_standard()
    return SUBPROJECT_CODES_BY_STANDARD.get(standard, SUBPROJECT_CODES_BY_STANDARD["DEFAULT"])

def format_mileage(m_val: float) -> str:
    """格式化里程为 Kxxx+xxx.xxx"""
    km = int(m_val / 1000)
    m = abs(m_val) % 1000
    sign = "" if m_val >= 0 else "-"
    return f"{sign}K{km}+{m:07.3f}"

# ==================== 4. 核心逻辑：生成检验批 ====================

def generate_inspection_batches(tunnel: Tunnel, section: Section, section_start: float) -> List[dict]:
    """生成检验批：包含开挖初支（按循环）和 二衬（按台车）"""
    batches = []
    if section.is_simple_portal:
        return batches
    
    current_standard = get_current_standard()
    tunnel_code = {"ZK": "1", "YK": "2", "AK": "3", "BK": "4"}.get(tunnel.tunnel_id, "1")
    subproject_codes = get_subproject_codes(current_standard)
    
    # -------------------------------------------------
    # Part 1: 开挖与初期支护 (读取Section存储的进尺)
    # -------------------------------------------------
    advance = section.advance_per_cycle
    if advance <= 0.001: advance = 1.0 # 防止除零
    
    cycle_count = math.ceil(section.length / advance)
    work_items = WORK_ITEM_BY_METHOD.get(section.excavation_method, WORK_ITEM_BY_METHOD["台阶法"])
    
    direction = tunnel.direction_sign
    curr_m = section_start
    
    for cycle in range(1, cycle_count + 1):
        if direction == 1:
            next_m = min(curr_m + advance, section_start + section.length)
            start_str, end_str = format_mileage(curr_m), format_mileage(next_m)
        else:
            next_m = max(curr_m - advance, section_start - section.length)
            start_str, end_str = format_mileage(curr_m), format_mileage(next_m)
        
        mileage_range = f"{start_str}~{end_str}"
        step_len = abs(next_m - curr_m)
        
        for item in work_items:
            sp_code = subproject_codes.get(item["分部"], "01")
            batch_no = f"T{tunnel_code}-{sp_code}-{item['code']}-C{cycle:04d}"
            
            batches.append({
                "检验批编号": batch_no,
                "分部工程": item["分部"],
                "分项工程": item["name"],
                "开挖方法": section.excavation_method,
                "里程范围": mileage_range,
                "类别": "初期支护/开挖",
                "循环/板号": cycle,
                "进尺/长度": round(step_len, 3),
                "围岩等级": section.rock_grade,
                "验收标准": current_standard.value
            })
        curr_m = next_m

    # -------------------------------------------------
    # Part 2: 二次衬砌 (按台车长度)
    # -------------------------------------------------
    if "匝道" in tunnel.name or "AK" in tunnel.tunnel_id or "BK" in tunnel.tunnel_id:
        trolley_len = 9.0
        trolley_type = "9m台车"
    else:
        trolley_len = 12.0
        trolley_type = "12m台车"
        
    lining_cycles = math.ceil(section.length / trolley_len)
    l_curr_m = section_start
    
    for i in range(1, lining_cycles + 1):
        if direction == 1:
            l_next_m = min(l_curr_m + trolley_len, section_start + section.length)
            l_s_str, l_e_str = format_mileage(l_curr_m), format_mileage(l_next_m)
        else:
            l_next_m = max(l_curr_m - trolley_len, section_start - section.length)
            l_s_str, l_e_str = format_mileage(l_curr_m), format_mileage(l_next_m)
            
        l_range = f"{l_s_str}~{l_e_str}"
        l_step_len = abs(l_next_m - l_curr_m)
        
        for item in LINING_WORK_ITEMS:
            sp_code = subproject_codes.get(item["分部"], "04")
            batch_no = f"T{tunnel_code}-{sp_code}-{item['code']}-EC{i:03d}"
            
            batches.append({
                "检验批编号": batch_no,
                "分部工程": item["分部"],
                "分项工程": item["name"],
                "开挖方法": f"模筑({trolley_type})",
                "里程范围": l_range,
                "类别": "二次衬砌",
                "循环/板号": i,
                "进尺/长度": round(l_step_len, 3),
                "围岩等级": section.rock_grade,
                "验收标准": current_standard.value
            })
        l_curr_m = l_next_m

    return batches

# ==================== 5. 初始化与状态 ====================

def create_default_project() -> Project:
    project = Project(project_id="LZG", name="泸州龙透关隧道工程")
    
    # 按照用户提供的确切数据更新
    configs = [
        ("ZK", "主线左线隧道", 245.102, 1408.000), # 长度 1162.898
        ("YK", "主线右线隧道", 244.803, 1406.000), # 长度 1161.197
        ("AK", "A匝道隧道", 87.000, 425.500),      # 长度 338.500
        ("BK", "B匝道隧道", 164.000, 755.000)      # 长度 591.000
    ]
    
    for tid, name, start, end in configs:
        tunnel = Tunnel(tunnel_id=tid, name=name, start_mileage=start, end_mileage=end, excavation_direction="正向")
        
        total_len = abs(end - start)
        # 定义5段式结构: 进洞口2m + 进洞30m + 标准段 + 出洞30m + 出洞口2m
        # 剩余给标准段的长度
        std_len = total_len - 2.0 - 30.0 - 30.0 - 2.0
        
        tunnel.sections = [
            Section(f"{tid}-S01", "进口洞口", 2.0, "洞口", "V级", 0.0, is_portal=True),
            Section(f"{tid}-S02", "进洞段", 30.0, "CD法", "V级", 0.6, is_portal=False),
            Section(f"{tid}-S03", "标准段", std_len, "台阶法", "IV级", 1.2, is_portal=False),
            Section(f"{tid}-S04", "出洞段", 30.0, "CD法", "V级", 0.6, is_portal=False),
            Section(f"{tid}-S05", "出口洞口", 2.0, "洞口", "V级", 0.0, is_portal=True),
        ]
        project.tunnels.append(tunnel)
    return project

def init_state():
    if 'project' not in st.session_state:
        st.session_state.project = create_default_project()
    if 'selected_tunnel' not in st.session_state:
        st.session_state.selected_tunnel = "ZK"
    if 'edited_df' not in st.session_state:
        update_edited_df(get_tunnel())

def get_tunnel() -> Optional[Tunnel]:
    return next((t for t in st.session_state.project.tunnels if t.tunnel_id == st.session_state.selected_tunnel), None)

def update_edited_df(tunnel: Tunnel):
    if tunnel:
        st.session_state.edited_df = pd.DataFrame(tunnel.get_paragraphs_with_positions())
    else:
        st.session_state.edited_df = pd.DataFrame()

# ==================== 6. SVG 绘图 ====================

def generate_svg(tunnel: Tunnel, width: int = 900, height: int = 200) -> str:
    if not tunnel.sections:
        return f'<svg width="100%" height="{height}"><text x="50%" y="50%">暂无数据</text></svg>'
    
    total = tunnel.total_length or 100
    colors = {"CD法": "#FF6B6B", "台阶法": "#4ECDC4", "全断面法": "#9B59B6", "洞口": "#95A5A6"}
    
    padding = 50
    chart_w = width - 2 * padding
    scale = chart_w / total if total > 0 else 1
    
    svg = [f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}">']
    svg.append('<rect width="100%" height="100%" fill="#fafbfc"/>')
    svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-weight="bold">{tunnel.name} ({format_mileage(tunnel.start_mileage)} ~ {format_mileage(tunnel.end_mileage)})</text>')
    
    y = height - 60
    bar_h = 40
    
    curr_x = padding
    for s in tunnel.sections:
        w = s.length * scale
        c = colors.get(s.excavation_method, "#BDC3C7")
        svg.append(f'<rect x="{curr_x}" y="{y}" width="{w}" height="{bar_h}" fill="{c}" stroke="white"/>')
        if w > 30:
            svg.append(f'<text x="{curr_x+w/2}" y="{y+25}" text-anchor="middle" font-size="10" fill="white">{s.name}</text>')
        curr_x += w
    
    svg.append(f'<line x1="{padding}" y1="{y+bar_h+10}" x2="{width-padding}" y2="{y+bar_h+10}" stroke="#333"/>')
    svg.append(f'<text x="{padding}" y="{y+bar_h+25}" text-anchor="middle" font-size="10">{format_mileage(tunnel.start_mileage)}</text>')
    svg.append(f'<text x="{width-padding}" y="{y+bar_h+25}" text-anchor="middle" font-size="10">{format_mileage(tunnel.end_mileage)}</text>')
    svg.append('</svg>')
    return "".join(svg)

# ==================== 7. 主界面逻辑 ====================

def main():
    init_state()
    tunnel = get_tunnel()
    
    with st.sidebar:
        st.title("🚇 工程配置")
        st.info("泸州龙透关隧道工程 V5.0")
        
        std_names = [s.value for s in InspectionStandard]
        sel_std = st.selectbox("验收标准", std_names, index=0)
        st.session_state.current_standard = InspectionStandard(sel_std)
        
        st.markdown("---")
        t_ids = [t.tunnel_id for t in st.session_state.project.tunnels]
        t_names = [t.name for t in st.session_state.project.tunnels]
        sel_t_idx = t_ids.index(st.session_state.selected_tunnel) if st.session_state.selected_tunnel in t_ids else 0
        sel_name = st.selectbox("选择隧道", t_names, index=sel_t_idx)
        new_id = t_ids[t_names.index(sel_name)]
        
        if new_id != st.session_state.selected_tunnel:
            st.session_state.selected_tunnel = new_id
            update_edited_df(get_tunnel())
            st.rerun()
            
        if st.button("🔄 重置所有配置"):
            st.session_state.project = create_default_project()
            update_edited_df(get_tunnel())
            st.rerun()
            
        if tunnel:
            st.markdown("### 隧道参数")
            st.caption(f"全长: {tunnel.total_length:.3f}m")
            ns = st.number_input("起点", value=float(tunnel.start_mileage), format="%.3f")
            ne = st.number_input("终点", value=float(tunnel.end_mileage), format="%.3f")
            
            if ns != tunnel.start_mileage or ne != tunnel.end_mileage:
                tunnel.start_mileage = ns
                tunnel.end_mileage = ne
                update_edited_df(tunnel)
                st.rerun()

    if not tunnel: return
    
    st.subheader(f"📐 {tunnel.name} 配置")
    st.markdown(generate_svg(tunnel), unsafe_allow_html=True)
    
    st.markdown("### 📝 施工段落 (支持编辑)")
    
    # 编辑器配置
    col_cfg = {
        "序号": st.column_config.NumberColumn(disabled=True, width="small"),
        "ID": st.column_config.TextColumn(disabled=True, width="small"),
        "名称": st.column_config.TextColumn(width="medium"),
        "起点桩号": st.column_config.TextColumn(disabled=True, width="small"),
        "终点桩号": st.column_config.TextColumn(disabled=True, width="small"),
        "长度(m)": st.column_config.NumberColumn(min_value=0.1, step=1.0, format="%.3f"),
        "开挖方法": st.column_config.SelectboxColumn(options=[e.value for e in ExcavationMethod], required=True),
        "循环进尺(m)": st.column_config.NumberColumn(
            disabled=False, 
            min_value=0.1, 
            step=0.1, 
            format="%.1f",
            help="可自由修改，生成检验批时将严格使用此值"
        ),
        "围岩等级": st.column_config.SelectboxColumn(options=[r.value for r in RockGrade]),
        "检验批": st.column_config.TextColumn(disabled=True, width="small"),
    }
    
    edited_df = st.data_editor(
        st.session_state.edited_df,
        column_config=col_cfg,
        use_container_width=True,
        num_rows="dynamic",
        key="editor"
    )
    
    if not edited_df.equals(st.session_state.edited_df):
        tunnel.apply_changes(edited_df)
        update_edited_df(tunnel)
        st.rerun()
        
    ok, issues = tunnel.validate()
    if not ok:
        for iss in issues: st.error(iss)
    else:
        st.caption("✅ 长度校验通过")
        
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("#### 检验批生成")
        st.write("包含：开挖/初期支护(按循环) + 二衬(按台车)")
        gen_btn = st.button("🚀 生成检验批台账", type="primary")
        
    if gen_btn:
        all_batches = []
        curr_abs = tunnel.start_mileage
        direction = tunnel.direction_sign
        
        for i, s in enumerate(tunnel.sections):
            if not s.is_simple_portal:
                all_batches.extend(generate_inspection_batches(tunnel, s, curr_abs))
            
            if direction == 1:
                curr_abs += s.length
            else:
                curr_abs -= s.length
                
        if all_batches:
            df_res = pd.DataFrame(all_batches)
            st.success(f"生成成功！共 {len(df_res)} 条记录")
            st.dataframe(df_res.head(50), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_res.to_excel(writer, index=False, sheet_name='检验批台账')
                workbook = writer.book
                worksheet = writer.sheets['检验批台账']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
                for col_num, value in enumerate(df_res.columns.values):
                    worksheet.write(0, col_num, value, header_fmt)
                    worksheet.set_column(col_num, col_num, 18)
                
            st.download_button(
                label="📥 下载 Excel 台账",
                data=output.getvalue(),
                file_name=f"{tunnel.name}_检验批.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("没有生成有效数据")

if __name__ == "__main__":
    main()
