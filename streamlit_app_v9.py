import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import math
import json
from datetime import datetime

# --- 1. 页面与样式配置 ---
st.set_page_config(
    page_title="隧道工程检验批划分系统 Pro v9.1",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .metric-card {
        border-radius: 8px; padding: 15px; color: white; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 10px;
    }
    .metric-value { font-size: 28px; font-weight: bold; }
    .metric-label { font-size: 14px; opacity: 0.9; }
    .bg-blue { background: linear-gradient(135deg, #3498db, #2980b9); }
    .bg-green { background: linear-gradient(135deg, #2ecc71, #27ae60); }
    .bg-purple { background: linear-gradient(135deg, #9b59b6, #8e44ad); }
    .bg-orange { background: linear-gradient(135deg, #f39c12, #d35400); }
    </style>
""", unsafe_allow_html=True)

plt.style.use('ggplot') 
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# --- 2. 数据结构定义 ---

@dataclass
class TunnelSegment:
    name: str
    method: str
    length: float
    start_mileage: float
    end_mileage: float
    frame_spacing: float = 0.8
    frames_per_ring: int = 2
    steps: int = 2
    trolley_length: float = 12.0
    advance_per_cycle: float = 1.6
    lining_type: str = ""

@dataclass
class Tunnel:
    id: str
    name: str
    total_length: float
    start_mileage: float
    end_mileage: float
    start_label: str
    end_label: str
    is_main_line: bool
    trolley_length: float = 12.0
    direction: str = "正向"
    segments: List[TunnelSegment] = field(default_factory=list)

@dataclass
class Project:
    name: str
    created_at: str
    tunnels: List[Tunnel] = field(default_factory=list)

# --- 3. 辅助函数 ---

def parse_mileage(km_str: str) -> float:
    try:
        km_str = str(km_str).strip().upper().replace('K', '')
        if '+' in km_str:
            parts = km_str.split('+')
            p1 = ''.join(filter(lambda x: x.isdigit() or x == '-', parts[0]))
            return int(p1) * 1000 + float(parts[1])
        return float(km_str)
    except: return 0.0

def format_mileage(meters: float) -> str:
    if pd.isna(meters): return "K0+000.000"
    sign = "-" if meters < 0 else ""
    meters = abs(meters)
    km = int(meters / 1000)
    m = meters % 1000
    return f"{sign}K{km}+{m:.3f}"

def export_project_to_json(project: Project) -> str:
    return json.dumps(asdict(project), ensure_ascii=False, indent=2)

def import_project_from_json(json_str: str) -> Optional[Project]:
    try:
        data = json.loads(json_str)
        tunnels = []
        for t_data in data.get('tunnels', []):
            segments = [TunnelSegment(**s) for s in t_data.get('segments', [])]
            t_data_clean = {k:v for k,v in t_data.items() if k != 'segments'}
            tunnels.append(Tunnel(segments=segments, **t_data_clean))
        return Project(name=data['name'], created_at=data.get('created_at', datetime.now().strftime("%Y-%m-%d")), tunnels=tunnels)
    except Exception as e:
        st.error(f"文件解析失败: {e}")
        return None

# --- 4. 完整的全线 53 段数据生成器 ---

def _create_segments_from_raw(raw_data: str, trolley: float) -> List[TunnelSegment]:
    """通用解析器，将原始文本转化为完整的 TunnelSegment 列表"""
    segments = []
    for line in raw_data.strip().split('\n'):
        # 兼容中文逗号和分号
        line = line.replace('，', ',').replace('；', ',').replace(';', ',')
        parts = line.split(',')
        if len(parts) < 4: continue
        
        m1, m2 = parse_mileage(parts[0]), parse_mileage(parts[1])
        start, end = min(m1, m2), max(m1, m2)
        
        name_raw = parts[2].strip()
        # 提取括号前的名称作为衬砌类型
        clean_name = name_raw.split('(')[0].split('（')[0]
        
        method_raw = parts[3].strip()
        length = end - start
        
        # 智能匹配参数
        if '明挖' in method_raw:
            method = '明挖'
            steps, frames, spacing, adv = 1, 1, length, length
        elif 'CD法' in method_raw or 'CD' in method_raw:
            method = 'CD法'
            steps, frames, spacing, adv = 4, 1, 0.8, 0.8
        else: # 默认台阶法
            method = '台阶法'
            steps, frames, spacing, adv = 2, 2, 0.8, 1.6
            
        segments.append(TunnelSegment(
            name=clean_name, method=method, length=length,
            start_mileage=start, end_mileage=end,
            frame_spacing=spacing, frames_per_ring=frames,
            steps=steps, trolley_length=trolley, advance_per_cycle=adv,
            lining_type=clean_name
        ))
    segments.sort(key=lambda x: x.start_mileage)
    return segments

def create_demo_project() -> Project:
    # 1. ZK左线
    zk_data = """K0+245.102,K0+283.102,明挖Ⅰ型衬砌（38m）,明挖
K0+283.102,K0+303.102,明挖Ⅱ型衬砌（20m）,明挖
K0+303.102,K0+403.092,明挖Ⅲ型衬砌（99.990m）,明挖
K0+403.092,K0+436.092,ⅤB级衬砌(33m）,CD法
K0+436.092,K0+456.092,ⅣB级衬砌(20m）,CD法
K0+456.092,K0+639.000,ⅣA级衬砌(182.908m）,台阶法
K0+639.000,K0+681.000,紧急停车带衬砌(42m）,CD法
K0+681.000,K0+840.000,ⅣA级衬砌(159m）,台阶法
K0+840.000,K0+867.000,ⅣC级衬砌(27m）,台阶法
K0+867.000,K0+925.000,ⅣA级衬砌(58m）,台阶法
K0+925.000,K0+967.000,紧急停车带衬砌(42m）,CD法
K0+967.000,K1+057.449,ⅣA级衬砌(90.449m）,台阶法
K1+057.449,K1+095.449,隧道上跨段衬砌(38m）,CD法
K1+095.449,K1+250.000,ⅣA级衬砌(154.551m）,台阶法
K1+250.000,K1+353.000,ⅤA级衬砌(103m）,台阶法
K1+353.000,K1+390.000,ⅤB级衬砌(37m）,CD法
K1+390.000,K1+408.000,明洞(18m）,明挖"""
    t_zk = Tunnel("ZK", "ZK左线", 1162.898, 245.102, 1408.000, "K0+245.102", "K1+408.000", True, 12.0, "正向", _create_segments_from_raw(zk_data, 12.0))

    # 2. YK右线
    yk_data = """K0+244.803,K0+282.803,明挖Ⅰ型衬砌（38m）,明挖
K0+282.803,K0+302.803,明挖Ⅱ型衬砌（20m）,明挖
K0+302.803,K0+403.400,明挖Ⅲ型衬砌(100.597m）,CD法
K0+403.400,K0+518.000,ⅤC级衬砌(114.6m）,台阶法
K0+518.000,K0+545.000,ⅤD级衬砌(27m）,台阶法
K0+545.000,K0+603.400,ⅤC级衬砌(58.4m）,台阶法
K0+603.400,K0+639.000,ⅣA级衬砌(35.6m）,台阶法
K0+639.000,K0+681.000,紧急停车带衬砌(42m）,CD法
K0+681.000,K0+929.000,ⅣA级衬砌(248m）,台阶法
K0+929.000,K0+971.000,紧急停车带衬砌(42m）,CD法
K0+971.000,K1+069.714,ⅣA级衬砌(98.714m）,台阶法
K1+069.714,K1+107.714,隧道上跨段衬砌(38m）,台阶法
K1+107.714,K1+323.000,ⅣA级衬砌(215.286m）,台阶法
K1+323.000,K1+352.000,ⅤA级衬砌(29m）,台阶法
K1+352.000,K1+394,ⅤB级衬砌(42m）,台阶法
K1+394,K1+406.000,明洞(12m）,明挖"""
    t_yk = Tunnel("YK", "YK右线", 1161.197, 244.803, 1406.000, "K0+244.803", "K1+406.000", True, 12.0, "正向", _create_segments_from_raw(yk_data, 12.0))

    # 3. A匝道
    ak_data = """AK0+425.5, AK0+410.5, 明洞(15m), 明挖
AK0+410.5, AK0+400.5, Vc衬砌(10m), CD法
AK0+400.5, AK0+370, Vb衬砌(30.5m), CD法
AK0+370, AK0+335, IVa衬砌(35m), 台阶法
AK0+335, AK0+265, IVb衬砌(70m), 台阶法
AK0+265, AK0+195, IVa衬砌(70m), 台阶法
AK0+195, AK0+158, IVb衬砌(37m), 台阶法
AK0+158, AK0+134, Vb衬砌(24m), 台阶法
AK0+134, AK0+104, Vc衬砌(30m), CD法
AK0+104, AK0+87, 明洞(17m), 明挖"""
    t_ak = Tunnel("AK", "A匝道", 338.5, 87.0, 425.5, "AK0+087", "AK0+425.5", False, 9.0, "正向", _create_segments_from_raw(ak_data, 9.0))

    # 4. B匝道
    bk_data = """BK0+164, BK0+178, 明洞(14m), 明挖
BK0+178, BK0+194, Vc衬砌(16m), CD法
BK0+194, BK0+214, Vb衬砌(20m), CD法
BK0+214, BK0+244, IVb衬砌(30m), 台阶法
BK0+244, BK0+340, IVc衬砌(96m), 台阶法
BK0+340, BK0+540, IVa衬砌(200m), 台阶法
BK0+540, BK0+570, IVb衬砌(30m), 台阶法
BK0+570, BK0+630, IVd衬砌(60m), 台阶法
BK0+630, BK0+690, IVa衬砌(60m), 台阶法
BK0+690, BK0+715, Va衬砌(25m), 台阶法
BK0+715, BK0+740, Vb衬砌(25m), CD法
BK0+740, BK0+755, 明洞(15m), 明挖"""
    t_bk = Tunnel("BK", "B匝道", 591.0, 164.0, 755.0, "BK0+164", "BK0+755.0", False, 9.0, "正向", _create_segments_from_raw(bk_data, 9.0))

    return Project(name="泸州老旧改造配套项目(全线)", created_at=datetime.now().strftime("%Y-%m-%d"), tunnels=[t_zk, t_yk, t_ak, t_bk])

# --- 5. 可视化绘图 ---

def draw_enhanced_profile(segments: List[TunnelSegment], tunnel_name: str, direction: str):
    if not segments: return None
    min_m = min(min(s.start_mileage, s.end_mileage) for s in segments)
    max_m = max(max(s.start_mileage, s.end_mileage) for s in segments)
    total_len = max_m - min_m
    if total_len <= 0: return None
    
    colors = {'明挖': '#FF6B6B', 'CD法': '#4ECDC4', '台阶法': '#45B7D1', '洞口': '#96CEB4'}
    fig, ax = plt.subplots(figsize=(12, 3.5), dpi=100)
    ax.set_facecolor('#F9F9F9')
    
    for seg in segments:
        l = abs(seg.end_mileage - seg.start_mileage)
        if l <= 0: continue
        start_x = min(seg.start_mileage, seg.end_mileage)
        c = colors.get(seg.method, '#D3D3D3')
        rect = patches.Rectangle((start_x, 4), l, 2, linewidth=0.5, edgecolor='white', facecolor=c)
        ax.add_patch(rect)
        if l > total_len * 0.05:
            ax.text(start_x + l/2, 5, f"{l:.1f}m", ha='center', va='center', color='white', fontweight='bold', fontsize=9)
            ax.text(start_x + l/2, 6.2, f"{seg.name}\n({seg.method})", ha='center', va='bottom', fontsize=8, color='#333')

    ax.set_xlim(min_m - 50, max_m + 50)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    arrow_x, arrow_dx = (min_m, max_m - min_m) if direction == "正向" else (max_m, -(max_m - min_m))
    ax.arrow(arrow_x, 3.5, arrow_dx, 0, head_width=0.3, head_length=20, fc='#333', ec='#333', length_includes_head=True)
    
    ax.text(min_m, 2.5, format_mileage(min_m), ha='center', fontsize=9, fontweight='bold')
    ax.text(max_m, 2.5, format_mileage(max_m), ha='center', fontsize=9, fontweight='bold')
    ax.text((min_m+max_m)/2, 2.5, f"掘进方向: {direction}", ha='center', fontsize=10, color='red', fontweight='bold')
    
    legs = [patches.Patch(color=c, label=l) for l,c in colors.items()]
    ax.legend(handles=legs, loc='upper right', fontsize='small', frameon=False, ncol=4)
    ax.set_title(f"{tunnel_name} 施工条带图", fontsize=12, fontweight='bold', pad=10)
    plt.tight_layout()
    return fig

# --- 6. 终极精准计算器 ---

class InspectionCalculator:
    DIVISIONS = {
        '01': {'name': '加固处理', 'items': {'01': {'name': '危岩处治', 'formula': '每洞口1处'}}},
        '02': {'name': '洞口工程', 'items': {'01': {'name': '边坡、基槽', 'formula': '每洞口1批'}, 
                                             '02': {'name': '支护', 'formula': '每洞口3批(锚/网/喷)'}, 
                                             '03': {'name': '导向墙', 'formula': '每洞口3批(模/筋/砼)'}, 
                                             '04': {'name': '回填', 'formula': '每洞口1批'}}},
        '03': {'name': '超前支护', 'items': {'01': {'name': '超前锚杆', 'formula': '每洞口1批'}, '02': {'name': '超前小导管', 'formula': '每洞口1批'}, '03': {'name': '超前注浆', 'formula': '每洞口1批'}}},
        '04': {'name': '洞身开挖', 'items': {'01': {'name': 'CD法', 'formula': '循环数×4步'}, '02': {'name': '台阶法', 'formula': '循环数×2步'}}},
        '05': {'name': '初期支护', 'items': {'01': {'name': '锚杆', 'formula': '循环数×4'}, '02': {'name': '钢架', 'formula': '循环数×4'}, '03': {'name': '钢筋网', 'formula': '循环数×4'}, '04': {'name': '喷射混凝土', 'formula': '循环数×4'}}},
        '06': {'name': '衬砌', 'items': {'01': {'name': '仰拱(底板)和填充', 'formula': '环数×3(模/筋/砼)'}, '02': {'name': '拱墙衬砌', 'formula': '环数×3(模/筋/砼)'}}},
        '07': {'name': '防水排水', 'items': {'01': {'name': '防水板', 'formula': '环数'}, '02': {'name': '排水管', 'formula': '环数'}, '03': {'name': '止水带', 'formula': '环数'}}},
        '08': {'name': '附属工程', 'items': {'01': {'name': '排水沟', 'formula': '环数'}, '02': {'name': '电缆沟', 'formula': '环数'}, '03': {'name': '路面装饰', 'formula': '环数'}, '04': {'name': '检修道', 'formula': '环数'}}},
    }

    def _generate_batch_code(self, tunnel_id: str, div_code: str, item_code: str, seq: int) -> str:
        return f"{tunnel_id}-{div_code}-{item_code}-{seq:03d}"

    def _add_batch(self, results, tunnel_name, tunnel_id, d, i, seq, remark, start=0, end=0):
        mileage_str = "K0+000" if start==0 and end==0 else f"{format_mileage(start)}~{format_mileage(end)}"
        length = 0.0 if start==0 and end==0 else abs(end - start)
        
        code = self._generate_batch_code(tunnel_id, d, i, seq)
        batch = {
            '检验批编号': code, '隧道': tunnel_name,
            '分部工程': self.DIVISIONS[d]['name'],
            '分项工程': self.DIVISIONS[d]['items'][i]['name'],
            '具体部位': remark, '里程范围': mileage_str,
            '长度': round(length, 3), '备注': remark
        }
        results['divisions'][d]['items'][i]['batches'].append(batch)
        results['all_batches'].append(batch)

    def calculate_single_tunnel(self, tunnel: Tunnel) -> Dict:
        results = {'tunnel_name': tunnel.name, 'divisions': {}, 'summary': {}, 'all_batches': []}
        for d_code, d_info in self.DIVISIONS.items():
            results['divisions'][d_code] = {'name': d_info['name'], 'items': {}, 'total_batches': 0}
            for i_code, i_info in d_info['items'].items():
                results['divisions'][d_code]['items'][i_code] = {'name': i_info['name'], 'batches': [], 'count': 0}

        dir_sign = 1 if tunnel.direction == "正向" else -1

        # 1. 洞口 & 超前
        for d, i_codes in [('02', ['01','04']), ('03', ['01','02','03'])]:
            for ic in i_codes:
                self._add_batch(results, tunnel.name, tunnel.id, d, ic, 1, '进洞口')
                self._add_batch(results, tunnel.name, tunnel.id, d, ic, 2, '出洞口')
                
        for idx, sub_item in enumerate(['锚杆', '钢筋网', '喷射混凝土']):
            self._add_batch(results, tunnel.name, tunnel.id, '02', '02', idx+1, f'进洞口-{sub_item}')
            self._add_batch(results, tunnel.name, tunnel.id, '02', '02', idx+4, f'出洞口-{sub_item}')

        for idx, sub_item in enumerate(['模板', '钢筋', '混凝土']):
            self._add_batch(results, tunnel.name, tunnel.id, '02', '03', idx+1, f'进洞口-{sub_item}')
            self._add_batch(results, tunnel.name, tunnel.id, '02', '03', idx+4, f'出洞口-{sub_item}')

        # 2. 开挖 & 初支
        for seg in tunnel.segments:
            if seg.method not in ['CD法', '台阶法']: continue
            cycles = int(seg.length / seg.advance_per_cycle) if seg.advance_per_cycle > 0 else 0
            
            ic_exc = '01' if seg.method == 'CD法' else '02'
            step_names = ['左上','右上','左下','右下'] if seg.method == 'CD法' else ['上台阶','下台阶']
            
            # 使用正确的起始点（无论是正向还是反向，都从 start_mileage 算起）
            base_start = min(seg.start_mileage, seg.end_mileage) if dir_sign == 1 else max(seg.start_mileage, seg.end_mileage)
            
            for c in range(cycles):
                start = base_start + c * seg.advance_per_cycle * dir_sign
                end = start + seg.advance_per_cycle * dir_sign
                
                for s_idx, s_name in enumerate(step_names):
                    seq = c * seg.steps + s_idx + 1
                    self._add_batch(results, tunnel.name, tunnel.id, '04', ic_exc, seq, f"{seg.name}-{s_name}", start, end)
                    for ic_sup in ['01','02','03','04']:
                        self._add_batch(results, tunnel.name, tunnel.id, '05', ic_sup, seq, f"{seg.name}-{s_name}", start, end)

        # 3. 衬砌/防排水/附属
        trolley = tunnel.trolley_length
        if trolley > 0:
            rings = math.ceil(tunnel.total_length / trolley)
            # 同样从隧道的起始点开始按方向推
            base_t_start = min(tunnel.start_mileage, tunnel.end_mileage) if dir_sign == 1 else max(tunnel.start_mileage, tunnel.end_mileage)
            base_t_end = max(tunnel.start_mileage, tunnel.end_mileage) if dir_sign == 1 else min(tunnel.start_mileage, tunnel.end_mileage)
            
            for r in range(rings):
                start = base_t_start + r * trolley * dir_sign
                if dir_sign == 1: end = min(start + trolley, base_t_end)
                else: end = max(start - trolley, base_t_end)
                
                for idx, sub_item in enumerate(['模板', '钢筋', '混凝土']):
                    seq = r * 3 + idx + 1
                    self._add_batch(results, tunnel.name, tunnel.id, '06', '01', seq, f'仰拱-{sub_item}', start, end)
                    self._add_batch(results, tunnel.name, tunnel.id, '06', '02', seq, f'拱墙-{sub_item}', start, end)
                
                for ic in ['01','02','03']: self._add_batch(results, tunnel.name, tunnel.id, '07', ic, r+1, '防排水', start, end)
                for ic in ['01','02','03','04']: self._add_batch(results, tunnel.name, tunnel.id, '08', ic, r+1, '附属', start, end)

        # 汇总隧道单体
        total = 0
        for d_code, d_data in results['divisions'].items():
            d_total = sum(len(i['batches']) for i in d_data['items'].values())
            results['summary'][d_data['name']] = d_total
            total += d_total
        results['summary']['合计'] = total
        return results

    def calculate(self, project: Project):
        grand_total = 0
        summary_list = []
        all_batches_flat = []
        for tunnel in project.tunnels:
            tunnel_res = self.calculate_single_tunnel(tunnel)
            sum_dict = {'隧道': tunnel.name}
            sum_dict.update(tunnel_res['summary'])
            summary_list.append(sum_dict)
            grand_total += tunnel_res['summary']['合计']
            all_batches_flat.extend(tunnel_res['all_batches'])

        df_sum = pd.DataFrame(summary_list)
        df_detail = pd.DataFrame(all_batches_flat)
        return grand_total, df_sum, df_detail

# --- 7. 主程序 GUI ---

def main():
    if 'projects' not in st.session_state:
        st.session_state.projects = [create_demo_project()]
    if 'current_project_index' not in st.session_state:
        st.session_state.current_project_index = 0

    try:
        current_project = st.session_state.projects[st.session_state.current_project_index]
    except IndexError:
        st.session_state.current_project_index = 0
        current_project = st.session_state.projects[0]

    with st.sidebar:
        st.title("🏗️ 工程管理")
        project_names = [p.name for p in st.session_state.projects]
        selected_idx = st.selectbox("当前工作工程:", range(len(project_names)), format_func=lambda x: project_names[x], index=st.session_state.current_project_index)
        st.session_state.current_project_index = selected_idx
        
        new_proj_name = st.text_input("📝 重命名工程:", current_project.name)
        if new_proj_name and new_proj_name != current_project.name:
            current_project.name = new_proj_name
            st.rerun()

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("➕ 新建工程"):
                default_seg = TunnelSegment("首段施工", "台阶法", 100, 0, 100, 0.8, 2, 2, 12.0, 1.6, "复合衬砌")
                default_tunnel = Tunnel("T1", "一号隧道", 100, 0, 100, "K0+000", "K0+100", True, 12.0, "正向", [default_seg])
                st.session_state.projects.append(Project(name=f"新建工程_{len(project_names)+1}", created_at=datetime.now().strftime("%Y-%m-%d"), tunnels=[default_tunnel]))
                st.session_state.current_project_index = len(st.session_state.projects) - 1
                st.rerun()
        with col_p2:
            if st.button("🗑️ 删除工程") and len(st.session_state.projects) > 1:
                st.session_state.projects.pop(selected_idx)
                st.session_state.current_project_index = 0
                st.rerun()

        with st.expander("📂 数据导入/导出", expanded=False):
            st.download_button("📤 导出当前工程 (.json)", export_project_to_json(current_project), f"{current_project.name}_配置.json", "application/json")
            uploaded_file = st.file_uploader("📥 导入工程配置", type=['json'])
            if uploaded_file is not None:
                if st.button("✅ 确认导入"):
                    imported_proj = import_project_from_json(uploaded_file.getvalue().decode("utf-8"))
                    if imported_proj:
                        st.session_state.projects.append(imported_proj)
                        st.session_state.current_project_index = len(st.session_state.projects) - 1
                        st.success(f"成功导入: {imported_proj.name}")
                        st.rerun()

        st.markdown("---")
        st.title("🛠️ 功能模块")
        page = st.radio("前往:", ["📋 参数配置", "📊 检验批计算"])

    # ===== 页面：参数配置 =====
    if page == "📋 参数配置":
        st.subheader(f"📋 参数配置 - {current_project.name}")
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            tunnel_names = [t.name for t in current_project.tunnels]
            if not tunnel_names:
                st.warning("当前工程暂无隧道，请添加。")
                if st.button("➕ 添加首条隧道"):
                    default_seg = TunnelSegment("首段施工", "台阶法", 100, 0, 100, 0.8, 2, 2, 12.0, 1.6, "复合衬砌")
                    current_project.tunnels.append(Tunnel("NEW", "新建隧道", 100, 0, 100, "K0", "K1", True, 12.0, "正向", [default_seg]))
                    st.rerun()
                return
            selected_tunnel_name = st.selectbox("选择要编辑的隧道:", tunnel_names)
            target_tunnel = next(t for t in current_project.tunnels if t.name == selected_tunnel_name)
        with c2:
            st.write(""); st.write("")
            if st.button("➕ 新增隧道"):
                default_seg = TunnelSegment("新建段落", "台阶法", 100, 0, 100, 0.8, 2, 2, 12.0, 1.6, "复合衬砌")
                current_project.tunnels.append(Tunnel(f"T{len(current_project.tunnels)+1}", "新建隧道", 100, 0, 100, "K0", "K1", True, 12.0, "正向", [default_seg]))
                st.rerun()
        with c3:
            st.write(""); st.write("")
            if st.button("🗑️ 删除当前隧道") and len(current_project.tunnels) > 1:
                current_project.tunnels.remove(target_tunnel)
                st.rerun()

        st.markdown("##### 1. 纵断面可视化")
        fig = draw_enhanced_profile(target_tunnel.segments, target_tunnel.name, target_tunnel.direction)
        if fig: st.pyplot(fig)
        else: st.info("暂无段落数据")

        st.markdown("---")
        col_basic, col_seg = st.columns([1, 4])
        with col_basic:
            st.markdown("##### 2. 基础信息")
            with st.form("basic_info"):
                new_id = st.text_input("隧道ID", target_tunnel.id)
                new_name = st.text_input("名称", target_tunnel.name)
                new_dir = st.radio("掘进方向", ["正向 (里程递增)", "反向 (里程递减)"], index=0 if target_tunnel.direction=="正向" else 1)
                new_start = st.text_input("起点桩号 (如 K1+000)", target_tunnel.start_label)
                new_end = st.text_input("终点桩号 (如 K1+500)", target_tunnel.end_label)
                new_trolley = st.number_input("台车长度(m)", value=float(target_tunnel.trolley_length))
                
                if st.form_submit_button("保存基础信息"):
                    target_tunnel.id = new_id
                    target_tunnel.name = new_name
                    target_tunnel.start_label = new_start
                    target_tunnel.end_label = new_end
                    target_tunnel.start_mileage = parse_mileage(new_start)
                    target_tunnel.end_mileage = parse_mileage(new_end)
                    target_tunnel.total_length = abs(target_tunnel.end_mileage - target_tunnel.start_mileage)
                    target_tunnel.direction = "正向" if "正向" in new_dir else "反向"
                    target_tunnel.trolley_length = new_trolley
                    st.success("已更新"); st.rerun()

        with col_seg:
            st.markdown("##### 3. 施工段落表")
            st.info("💡 **智能计算开启**：填写【起始桩号】和【长度】后保存，自动计算终止桩号。进尺和步骤数也会根据工法和榀距自动推导。")
            
            expected_columns = ["部位名称", "工法", "起始桩号", "长度(m)", "终止桩号", "衬砌类型", "榀数/环", "榀距(m)", "进尺(m)", "步骤数"]
            
            if not target_tunnel.segments:
                df_seg = pd.DataFrame(columns=expected_columns)
            else:
                seg_data = [{
                    "部位名称": s.name, 
                    "工法": s.method, 
                    "起始桩号": format_mileage(min(s.start_mileage, s.end_mileage)), 
                    "长度(m)": float(s.length),
                    "终止桩号": format_mileage(max(s.start_mileage, s.end_mileage)), 
                    "衬砌类型": s.lining_type, 
                    "榀数/环": int(s.frames_per_ring), 
                    "榀距(m)": float(s.frame_spacing),
                    "进尺(m)": float(s.advance_per_cycle), 
                    "步骤数": int(s.steps)
                } for s in target_tunnel.segments]
                df_seg = pd.DataFrame(seg_data)[expected_columns]

            edited_df = st.data_editor(
                df_seg, 
                num_rows="dynamic", 
                use_container_width=True,
                height=400,
                column_config={
                    "工法": st.column_config.SelectboxColumn(options=["明挖", "CD法", "台阶法", "洞口", "其他"]),
                    "起始桩号": st.column_config.TextColumn(help="支持 K1+234 格式"),
                    "终止桩号": st.column_config.TextColumn(disabled=True, help="点击保存后自动计算"),
                    "长度(m)": st.column_config.NumberColumn(format="%.3f"),
                    "进尺(m)": st.column_config.NumberColumn(format="%.2f", help="若不填将根据榀数x榀距自动计算"),
                    "步骤数": st.column_config.NumberColumn(disabled=True, help="随工法自动锁定 (CD=4, 台阶=2)"),
                }
            )
            
            if st.button("💾 保存段落 & 触发智能计算", type="primary"):
                new_segs = []
                dir_sign = 1 if target_tunnel.direction == "正向" else -1
                
                for _, row in edited_df.iterrows():
                    try:
                        def get_val(val, default): return default if pd.isna(val) else val
                        
                        start_m = parse_mileage(str(get_val(row.get('起始桩号'), "K0+000")))
                        length = float(get_val(row.get('长度(m)'), 0.0))
                        
                        # 不管正反向，表格输入统一认为是正数值，由程序控制内部渲染逻辑
                        end_m = start_m + length
                        
                        method = str(get_val(row.get('工法'), "台阶法"))
                        frames = int(get_val(row.get('榀数/环'), 2))
                        spacing = float(get_val(row.get('榀距(m)'), 0.8))
                        
                        if frames > 0 and spacing > 0: advance = frames * spacing
                        else: advance = float(get_val(row.get('进尺(m)'), 1.6))
                        
                        if 'CD' in method: steps = 4
                        elif '台阶' in method: steps = 2
                        elif '明挖' in method: steps = 1
                        else: steps = int(get_val(row.get('步骤数'), 2))
                        
                        name = str(get_val(row.get('部位名称'), "新建段落"))
                        if not name or name == 'nan': name = "新建段落"
                        
                        new_segs.append(TunnelSegment(
                            name=name, method=method, length=length, 
                            start_mileage=start_m, end_mileage=end_m,
                            advance_per_cycle=advance, lining_type=str(get_val(row.get('衬砌类型'), "")), 
                            steps=steps, frames_per_ring=frames, frame_spacing=spacing,
                            trolley_length=target_tunnel.trolley_length
                        ))
                    except Exception as e:
                        st.error(f"行数据存在错误被跳过: {e}")

                new_segs.sort(key=lambda x: min(x.start_mileage, x.end_mileage))
                target_tunnel.segments = new_segs
                st.success("智能计算已完成！终止桩号、进尺已补全，图形已刷新。")
                st.rerun()

    # ===== 页面：检验批计算 =====
    elif page == "📊 检验批计算":
        st.subheader(f"📊 检验批计算 - {current_project.name}")
        st.info("📌 **精度及标准说明**：根据TB 10417-2018，导向墙及衬砌均已按【模板】、【钢筋】、【混凝土】拆分；导出的数据长度保留 3 位小数。起止桩号自动随【正反向】调整。")
        
        if st.button("🚀 开始精准计算 (执行全线扫描)", type="primary", use_container_width=True):
            calc = InspectionCalculator()
            total, df_sum, df_detail = calc.calculate(current_project)
            st.session_state.last_result = (total, df_sum, df_detail)
            
        if 'last_result' in st.session_state:
            total, df_sum, df_detail = st.session_state.last_result
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f'<div class="metric-card bg-blue"><div class="metric-label">全线总数</div><div class="metric-value">{total:,}</div></div>', unsafe_allow_html=True)
            with c2: 
                ratio = df_sum['初期支护'].sum()/total if total>0 else 0
                st.markdown(f'<div class="metric-card bg-green"><div class="metric-label">初支占比</div><div class="metric-value">{ratio:.1%}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card bg-purple"><div class="metric-label">开挖批数</div><div class="metric-value">{df_sum["洞身开挖"].sum():,}</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card bg-orange"><div class="metric-label">衬砌批数 (模/筋/砼)</div><div class="metric-value">{df_sum["衬砌"].sum():,}</div></div>', unsafe_allow_html=True)

            st.markdown("#### 1. 分部工程汇总表")
            st.dataframe(df_sum, use_container_width=True)
            
            st.markdown("#### 2. 数据导出区")
            c_d1, c_d2 = st.columns(2)
            with c_d1: st.download_button("📥 导出【汇总表】 (CSV)", df_sum.to_csv(index=False, float_format='%.3f').encode('utf-8-sig'), f"{current_project.name}_汇总.csv", "text/csv", use_container_width=True)
            with c_d2: st.download_button("📥 导出【详细明细】 (CSV)", df_detail.to_csv(index=False, float_format='%.3f').encode('utf-8-sig'), f"{current_project.name}_明细.csv", "text/csv", use_container_width=True)

if __name__ == "__main__":
    main()