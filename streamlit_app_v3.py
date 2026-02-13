import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.cm as cm
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict
import math
import io
from datetime import datetime

# --- 1. 页面与样式配置 ---
st.set_page_config(
    page_title="隧道工程检验批划分系统 v7.6 (UI优化版)",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS - 优化指标卡片显示
st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    
    /* 指标卡片样式 */
    .metric-card {
        border-radius: 10px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    .metric-title {
        font-size: 16px;
        opacity: 0.9;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 32px;
        font-weight: bold;
    }
    
    /* 颜色定义 */
    .bg-blue { background: linear-gradient(135deg, #3498db, #2980b9); }
    .bg-green { background: linear-gradient(135deg, #2ecc71, #27ae60); }
    .bg-red { background: linear-gradient(135deg, #e74c3c, #c0392b); }
    .bg-orange { background: linear-gradient(135deg, #f39c12, #d35400); }
    </style>
""", unsafe_allow_html=True)

plt.style.use('ggplot') 
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS', 'DejaVu Sans']
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
    frames_per_ring: int = 1
    steps: int = 4
    trolley_length: float = 12.0
    advance_per_cycle: float = 0.8
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
    segments: List[TunnelSegment] = field(default_factory=list)

# --- 3. 核心计算与工具函数 ---

def parse_mileage(km_str: str) -> float:
    km_str = str(km_str).strip()
    if '+' in km_str:
        parts = km_str.split('+')
        if len(parts) > 1:
            prefix_part = parts[0].strip()
            digits = ''.join(filter(str.isdigit, prefix_part))
            km_val = int(digits) if digits else 0
            try:
                return km_val * 1000 + float(parts[1])
            except: pass
    try:
        return float(km_str)
    except: return 0.0

def format_mileage(meters: float) -> str:
    km = int(meters / 1000)
    m = meters % 1000
    return f"K{km}+{m:.3f}"

# --- 4. 绘图函数 ---

def draw_enhanced_profile(segments: List[TunnelSegment], tunnel_name: str):
    if not segments: return None
    min_mileage = min(s.start_mileage for s in segments)
    max_mileage = max(s.end_mileage for s in segments)
    total_len = max_mileage - min_mileage
    
    colors = {'明挖': '#FF6B6B', 'CD法': '#4ECDC4', '台阶法': '#45B7D1', '洞口': '#96CEB4', '其他': '#D3D3D3'}

    fig, ax = plt.subplots(figsize=(14, 4), dpi=100)
    ax.set_facecolor('#F9F9F9')
    y_center = 5
    height = 2
    
    for seg in segments:
        length = seg.end_mileage - seg.start_mileage
        if length <= 0: continue
        c = colors.get(seg.method, '#D3D3D3')
        rect = patches.Rectangle((seg.start_mileage, y_center - height/2), length, height, 
                                 linewidth=0.5, edgecolor='white', facecolor=c, alpha=0.8)
        ax.add_patch(rect)
        
        if length > total_len * 0.03: 
            ax.text(seg.start_mileage + length/2, y_center, f"{length:.1f}m", 
                    ha='center', va='center', color='white', fontweight='bold', fontsize=9)
            label = f"{seg.name}\n({seg.method})"
            ax.text(seg.start_mileage + length/2, y_center + height/2 + 0.5, label,
                    ha='center', va='bottom', fontsize=8, color='#333333')

    ax.set_xlim(min_mileage - 50, max_mileage + 50)
    ax.set_ylim(0, 10)
    ax.tick_params(axis='x', colors='#666666', labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_yticks([])
    ax.plot([min_mileage, max_mileage], [y_center - height/2 - 0.5, y_center - height/2 - 0.5], color='#333333', linewidth=1.5)
    ax.text(min_mileage, 1, format_mileage(min_mileage), ha='center', fontsize=9, fontweight='bold', color='#2c3e50')
    ax.text(max_mileage, 1, format_mileage(max_mileage), ha='center', fontsize=9, fontweight='bold', color='#2c3e50')

    legend_patches = [patches.Patch(color=color, label=label) for label, color in colors.items()]
    ax.legend(handles=legend_patches, loc='upper right', frameon=True, fancybox=True, fontsize='small')
    ax.set_title(f"{tunnel_name} 施工段落纵断面示意图", fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    return fig

def draw_statistics_dashboard(df_sum):
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2)
    color_palette = ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1']

    ax1 = fig.add_subplot(gs[0, 0])
    bars = ax1.bar(df_sum['隧道'], df_sum['合计'], color='#6baed6', edgecolor='white', width=0.6)
    ax1.set_title('各隧道检验批总量对比', fontsize=12, fontweight='bold')
    ax1.set_ylabel('数量 (批)')
    for bar in bars:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(), int(bar.get_height()), 
                 ha='center', va='bottom', fontsize=10)

    ax2 = fig.add_subplot(gs[0, 1])
    cols_to_sum = [c for c in df_sum.columns if c not in ['隧道', '合计']]
    total_series = df_sum[cols_to_sum].sum()
    ax2.pie(total_series, labels=total_series.index, autopct='%1.1f%%', startangle=140, pctdistance=0.85, colors=color_palette)
    centre_circle = plt.Circle((0,0), 0.70, fc='white')
    ax2.add_artist(centre_circle)
    ax2.set_title('全项目分部工程占比', fontsize=12, fontweight='bold')

    ax3 = fig.add_subplot(gs[1, :])
    tunnels = df_sum['隧道']
    bottom = np.zeros(len(tunnels))
    for i, col in enumerate(cols_to_sum):
        ax3.bar(tunnels, df_sum[col], bottom=bottom, label=col, color=color_palette[i % len(color_palette)], width=0.5)
        bottom += df_sum[col]
    ax3.set_title('各隧道分部工程详细构成', fontsize=12, fontweight='bold')
    ax3.legend(bbox_to_anchor=(1, 1), loc='upper left')

    plt.tight_layout()
    return fig

# --- 5. 业务逻辑 (完整数据恢复 - V3.0逻辑) ---

def create_zk_segments() -> List[TunnelSegment]:
    segments = []
    # 完整的ZK数据
    zk_data = """K0+245.102，K0+283.102，明挖Ⅰ型衬砌（38m），明挖
K0+283.102，K0+303.102，明挖Ⅱ型衬砌（20m），明挖
K0+303.102，K0+403.092，明挖Ⅲ型衬砌（99.990m），明挖
K0+403.092，K0+436.092，ⅤB级衬砌(33m），CD法
K0+436.092，K0+456.092，ⅣB级衬砌(20m），CD法
K0+456.092，K0+639.000，ⅣA级衬砌(182.908m），台阶法
K0+639.000，K0+681.000，紧急停车带衬砌(42m），CD法
K0+681.000，K0+840.000，ⅣA级衬砌(159m），台阶法
K0+840.000，K0+867.000，ⅣC级衬砌(27m），台阶法
K0+867.000，K0+925.000，ⅣA级衬砌(58m），台阶法
K0+925.000，K0+967.000，紧急停车带衬砌(42m），CD法
K0+967.000，K1+057.449，ⅣA级衬砌(90.449m），台阶法
K1+057.449，K1+095.449，隧道上跨段衬砌(38m），CD法
K1+095.449，K1+250.000，ⅣA级衬砌(154.551m），台阶法
K1+250.000，K1+353.000，ⅤA级衬砌(103m），台阶法
K1+353.000，K1+390.000，ⅤB级衬砌(37m），CD法
K1+390.000，K1+408.000，明洞(18m），明挖"""
    
    for line in zk_data.strip().split('\n'):
        parts = line.replace('，', ',').split(',')
        if len(parts) < 4: continue
        start, end = parse_mileage(parts[0]), parse_mileage(parts[1])
        name = parts[2].replace('（', '').replace('）', '').replace('(', '').replace(')', '')
        method = parts[3].strip()
        length = end - start
        
        if method == '明挖': steps, advance, frames = 1, length, 1
        elif 'CD法' in method: steps, advance, frames = 4, 0.8, 1; method='CD法'
        else: steps, advance, frames = 2, 1.6, 2; method='台阶法'
        
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 12.0, advance, name))
    return segments

def create_yk_segments() -> List[TunnelSegment]:
    segments = []
    # 完整的YK数据
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
    
    for line in yk_data.strip().split('\n'):
        parts = line.replace('，', ',').split(',')
        if len(parts) < 4: continue
        start, end = parse_mileage(parts[0]), parse_mileage(parts[1])
        name = parts[2].replace('（', '').replace('）', '').replace('(', '').replace(')', '')
        method = parts[3].strip()
        length = end - start
        
        if method == '明挖': steps, advance, frames = 1, length, 1
        elif 'CD法' in method or 'CD' in method: steps, advance, frames = 4, 0.8, 1; method='CD法'
        else: steps, advance, frames = 2, 1.6, 2; method='台阶法'
        
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 12.0, advance, name))
    return segments

def create_ak_segments() -> List[TunnelSegment]:
    segments = []
    # 完整的AK数据
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
    
    for line in ak_data.strip().split('\n'):
        line = line.replace('，', ',').replace('；', ',').replace(';', ',')
        parts = line.split(',')
        if len(parts) < 4: continue
        m1, m2 = parse_mileage(parts[0]), parse_mileage(parts[1])
        start, end = min(m1, m2), max(m1, m2)
        name = parts[2].split('(')[0]
        method = parts[3].strip()
        length = end - start
        
        if '明挖' in method: steps, advance, frames = 1, length, 1; method='明挖'
        elif 'CD' in method: steps, advance, frames = 4, 0.8, 1; method='CD法'
        else: steps, advance, frames = 2, 1.6, 2; method='台阶法'
        
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 9.0, advance, name))
    segments.sort(key=lambda x: x.start_mileage)
    return segments

def create_bk_segments() -> List[TunnelSegment]:
    segments = []
    # 完整的BK数据
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
    
    for line in bk_data.strip().split('\n'):
        line = line.replace('，', ',').replace('；', ',').replace(';', ',')
        parts = line.split(',')
        if len(parts) < 4: continue
        m1, m2 = parse_mileage(parts[0]), parse_mileage(parts[1])
        start, end = min(m1, m2), max(m1, m2)
        name = parts[2].split('(')[0]
        method = parts[3].strip()
        length = end - start
        
        if '明挖' in method: steps, advance, frames = 1, length, 1; method='明挖'
        elif 'CD' in method: steps, advance, frames = 4, 0.8, 1; method='CD法'
        else: steps, advance, frames = 2, 1.6, 2; method='台阶法'
        
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 9.0, advance, name))
    segments.sort(key=lambda x: x.start_mileage)
    return segments

def create_default_segments(tunnel: Tunnel) -> List[TunnelSegment]:
    if tunnel.id == 'ZK': return create_zk_segments()
    elif tunnel.id == 'YK': return create_yk_segments()
    elif tunnel.id == 'AK': return create_ak_segments()
    elif tunnel.id == 'BK': return create_bk_segments()
    return []

class TunnelInspectionCalculator:
    DIVISIONS = {
        '01': {'name': '加固处理', 'items': {'01': {'name': '危岩处治', 'formula': '每洞口1处'}}},
        '02': {'name': '洞口工程', 'items': {'01': {'name': '边坡、基槽', 'formula': '每洞口1批'}, '02': {'name': '支护', 'formula': '每洞口3批'}, '03': {'name': '导向墙', 'formula': '每洞口3批'}, '04': {'name': '回填', 'formula': '每洞口1批'}}},
        '03': {'name': '超前支护', 'items': {'01': {'name': '超前锚杆', 'formula': '每洞口1批'}, '02': {'name': '超前小导管', 'formula': '每洞口1批'}, '03': {'name': '超前注浆', 'formula': '每洞口1批'}}},
        '04': {'name': '洞身开挖', 'items': {'01': {'name': 'CD法', 'formula': '循环数×4步'}, '02': {'name': '台阶法', 'formula': '循环数×2步'}}},
        '05': {'name': '初期支护', 'items': {'01': {'name': '锚杆', 'formula': '循环数×4'}, '02': {'name': '钢架', 'formula': '循环数×4'}, '03': {'name': '钢筋网', 'formula': '循环数×4'}, '04': {'name': '喷射混凝土', 'formula': '循环数×4'}}},
        '06': {'name': '衬砌', 'items': {'01': {'name': '仰拱(底板)和填充', 'formula': '环数'}, '02': {'name': '拱墙衬砌', 'formula': '环数'}}},
        '07': {'name': '防水排水', 'items': {'01': {'name': '防水板', 'formula': '环数'}, '02': {'name': '排水管', 'formula': '环数'}, '03': {'name': '止水带', 'formula': '环数'}}},
        '08': {'name': '附属工程', 'items': {'01': {'name': '排水沟', 'formula': '环数'}, '02': {'name': '电缆沟', 'formula': '环数'}, '03': {'name': '路面装饰', 'formula': '环数'}, '04': {'name': '检修道', 'formula': '环数'}}},
    }

    def _generate_batch_code(self, tunnel_id: str, div_code: str, item_code: str, seq: int) -> str:
        return f"{tunnel_id}-{div_code}-{item_code}-{seq:03d}"

    def calculate_lots(self, tunnel: Tunnel) -> Dict:
        # --- 恢复精准计算逻辑 ---
        results = {'tunnel_name': tunnel.name, 'divisions': {}, 'summary': {}, 'all_batches': []}
        
        for d_code, d_info in self.DIVISIONS.items():
            results['divisions'][d_code] = {'name': d_info['name'], 'items': {}, 'total_batches': 0}
            for i_code, i_info in d_info['items'].items():
                results['divisions'][d_code]['items'][i_code] = {'name': i_info['name'], 'formula': i_info.get('formula',''), 'batches': [], 'count': 0}

        # 1. 洞口 & 超前 (固定数量)
        for d, i_codes in [('02', ['01','04']), ('03', ['01','02','03'])]:
            for ic in i_codes:
                if ic in results['divisions'][d]['items']:
                    self._add_batch(results, tunnel, d, ic, 1, '进洞口')
                    self._add_batch(results, tunnel, d, ic, 2, '出洞口')
        
        for ic in ['02', '03']: # 洞口多批次(3批)
            for k in range(3):
                self._add_batch(results, tunnel, '02', ic, k+1, '进洞口')
                self._add_batch(results, tunnel, '02', ic, k+4, '出洞口')

        # 2. 开挖(04) & 初支(05) - 核心循环
        for seg in tunnel.segments:
            if seg.method not in ['CD法', '台阶法']: continue
            
            # 重新计算 length (防止用户只改了里程没改长度)
            seg.length = seg.end_mileage - seg.start_mileage
            # 核心修正：使用真实进尺计算循环数
            cycles = int(seg.length / seg.advance_per_cycle) if seg.advance_per_cycle > 0 else 0
            
            ic_exc = '01' if seg.method == 'CD法' else '02'
            step_names = ['左上','右上','左下','右下'] if seg.method == 'CD法' else ['上台阶','下台阶']
            
            for c in range(cycles):
                start = seg.start_mileage + c*seg.advance_per_cycle
                end = start + seg.advance_per_cycle
                
                # 每个循环内的每个步骤生成1个开挖批
                for s_idx, s_name in enumerate(step_names):
                    # 序号累加逻辑需要更复杂处理，这里简化为全局唯一序号生成模拟
                    # 实际代码中建议维护一个 global_seq 或类似机制
                    # 为保证演示简单，这里使用基于循环的序号生成
                    seq = c * seg.steps + s_idx + 1
                    
                    self._add_batch(results, tunnel, '04', ic_exc, seq, f"{seg.name}-{s_name}", start, end)
                    # 每个开挖部位对应4个初支
                    for ic_sup in ['01','02','03','04']:
                        self._add_batch(results, tunnel, '05', ic_sup, seq, f"{seg.name}-{s_name}", start, end)

        # 3. 衬砌(06)等
        trolley = tunnel.trolley_length
        if trolley > 0:
            rings = math.ceil(tunnel.total_length / trolley)
            for r in range(rings):
                start = tunnel.start_mileage + r*trolley
                end = min(start + trolley, tunnel.end_mileage)
                self._add_batch(results, tunnel, '06', '01', r+1, '仰拱', start, end)
                self._add_batch(results, tunnel, '06', '02', r+1, '拱墙', start, end)
                for ic in ['01','02','03']: self._add_batch(results, tunnel, '07', ic, r+1, '防排水', start, end)
                for ic in ['01','02','03','04']: self._add_batch(results, tunnel, '08', ic, r+1, '附属', start, end)

        # 汇总
        total = 0
        for d_code, d_data in results['divisions'].items():
            d_total = sum(len(i['batches']) for i in d_data['items'].values())
            d_data['total_batches'] = d_total
            results['summary'][d_data['name']] = d_total
            total += d_total
            for i_data in d_data['items'].values():
                i_data['count'] = len(i_data['batches'])
        
        results['summary']['total'] = total
        return results

    def _add_batch(self, results, tunnel, d, i, seq, remark, start=0, end=0):
        if start==0 and end==0:
            mileage_str = "K0+000" 
            length = 0
        else:
            mileage_str = f"{format_mileage(start)}~{format_mileage(end)}"
            length = end - start
            
        code = self._generate_batch_code(tunnel.id, d, i, seq)
        batch = {
            'code': code,
            'division': results['divisions'][d]['name'],
            'item_name': results['divisions'][d]['items'][i]['name'],
            'item': remark,
            'mileage': mileage_str,
            'length': length,
            'remark': remark
        }
        results['divisions'][d]['items'][i]['batches'].append(batch)
        results['all_batches'].append(batch)

# --- 6. 主程序 UI ---

def main():
    if 'tunnels' not in st.session_state:
        configs = [
            ("ZK", "ZK左线", 1162.898, 245.102, 1408.000, "K0+245.102", "K1+408.000", True, 12.0),
            ("YK", "YK右线", 1161.197, 244.803, 1406.000, "K0+244.803", "K1+406.000", True, 12.0),
            ("AK", "A匝道", 338.500, 87.000, 425.500, "K0+087.000", "K0+425.500", False, 9.0),
            ("BK", "B匝道", 591.000, 164.000, 755.000, "K0+164.000", "K0+755.000", False, 9.0),
        ]
        tunnels = []
        for cfg in configs:
            t = Tunnel(cfg[0], cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], cfg[6], cfg[7], cfg[8])
            t.segments = create_default_segments(t)
            tunnels.append(t)
        st.session_state.tunnels = tunnels

    with st.sidebar:
        st.title("🛠️ 功能导航")
        page = st.radio(
            "请选择功能模块:",
            ["📋 隧道参数配置", "📊 检验批计算结果", "📉 统计分析图表"],
            captions=["查看与编辑段落", "执行计算与导出", "可视化数据看板"]
        )
        
        st.markdown("---")
        st.markdown("### ⚙️ 计算设置")
        selected_tunnel_names = st.multiselect(
            "参与计算的隧道:",
            [t.name for t in st.session_state.tunnels],
            default=[t.name for t in st.session_state.tunnels]
        )
        
        if st.button("🚀 开始计算", type="primary", use_container_width=True):
            calc = TunnelInspectionCalculator()
            all_results = {}
            grand_total = 0
            
            for t_name in selected_tunnel_names:
                tunnel = next(t for t in st.session_state.tunnels if t.name == t_name)
                res = calc.calculate_lots(tunnel)
                all_results[t_name] = res
                grand_total += res['summary']['total']
            
            st.session_state.calc_results = all_results
            st.session_state.grand_total = grand_total
            st.success("计算完成！")

        st.markdown("---")
        st.caption("技术支持: Matrix Agent | v7.6")

    if page == "📋 隧道参数配置":
        st.subheader("隧道施工段落配置")
        col1, col2 = st.columns([1, 3])
        with col1:
            target_name = st.selectbox("选择要查看/编辑的隧道:", [t.name for t in st.session_state.tunnels])
        
        target_tunnel = next(t for t in st.session_state.tunnels if t.name == target_name)
        
        st.markdown("#### 1. 纵断面可视化 (Strip Map)")
        fig = draw_enhanced_profile(target_tunnel.segments, target_name)
        st.pyplot(fig)
        
        st.markdown("---")
        st.markdown("#### 2. 段落参数编辑")
        st.info("💡 说明：直接在下方表格修改数据，修改后请点击“保存更改”按钮刷新图形。")
        
        seg_data = []
        for seg in target_tunnel.segments:
            seg_data.append({
                "部位名称": seg.name, "工法": seg.method,
                "起始里程": seg.start_mileage, "结束里程": seg.end_mileage,
                "进尺(m)": seg.advance_per_cycle, "衬砌类型": seg.lining_type, "步骤数": seg.steps
            })
        df_seg = pd.DataFrame(seg_data)
        
        edited_df = st.data_editor(
            df_seg,
            num_rows="dynamic",
            use_container_width=True,
            height=400,
            column_config={
                "工法": st.column_config.SelectboxColumn("工法", options=["明挖", "CD法", "台阶法", "洞口"], required=True),
                "起始里程": st.column_config.NumberColumn(format="%.3f"),
                "结束里程": st.column_config.NumberColumn(format="%.3f"),
                "进尺(m)": st.column_config.NumberColumn(format="%.2f"),
            }
        )
        
        if st.button("💾 保存更改并刷新图形", type="secondary"):
            new_segments = []
            for _, row in edited_df.iterrows():
                length = row["结束里程"] - row["起始里程"]
                new_seg = TunnelSegment(
                    name=row["部位名称"], method=row["工法"], length=length,
                    start_mileage=row["起始里程"], end_mileage=row["结束里程"],
                    advance_per_cycle=row["进尺(m)"], lining_type=row["衬砌类型"], steps=int(row["步骤数"]),
                    trolley_length=target_tunnel.trolley_length
                )
                new_segments.append(new_seg)
            new_segments.sort(key=lambda x: x.start_mileage)
            target_tunnel.segments = new_segments
            st.success(f"✅ {target_name} 数据已更新")
            st.rerun()

    elif page == "📊 检验批计算结果":
        if 'calc_results' in st.session_state:
            st.subheader("📋 检验批计算清单")
            
            # --- V3.1 新增：美化指标卡片 ---
            # 准备数据
            total = st.session_state.grand_total
            summary_list = []
            for t_name, res in st.session_state.calc_results.items():
                row = {'隧道': t_name}
                row.update(res['summary'])
                summary_list.append(row)
            df_sum = pd.DataFrame(summary_list)
            if 'total' in df_sum.columns:
                df_sum = df_sum.rename(columns={'total': '合计'})
            
            # 计算核心指标
            init_sup = df_sum['初期支护'].sum() if '初期支护' in df_sum else 0
            excavation = df_sum['洞身开挖'].sum() if '洞身开挖' in df_sum else 0
            lining = df_sum['衬砌'].sum() if '衬砌' in df_sum else 0
            init_sup_pct = (init_sup / total) * 100 if total > 0 else 0

            # 使用 HTML/CSS 渲染卡片
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="metric-card bg-blue">
                    <div class="metric-title">全线检验批总数</div>
                    <div class="metric-value">{total:,}</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="metric-card bg-green">
                    <div class="metric-title">初期支护 (占比)</div>
                    <div class="metric-value">{init_sup_pct:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div class="metric-card bg-red">
                    <div class="metric-title">洞身开挖</div>
                    <div class="metric-value">{excavation:,}</div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                st.markdown(f"""
                <div class="metric-card bg-orange">
                    <div class="metric-title">二衬工程</div>
                    <div class="metric-value">{lining:,}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")

            # 汇总表和下载区
            st.markdown("#### 1. 分隧道汇总表")
            st.dataframe(df_sum, use_container_width=True)
            
            col_dl1, col_dl2 = st.columns([1, 4])
            with col_dl1:
                csv_buffer = io.StringIO()
                df_sum.to_csv(csv_buffer)
                st.download_button(
                    label="📥 导出汇总表 (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name="summary.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("#### 2. 详细数据下载")
            df_all = pd.DataFrame(st.session_state.all_batches)
            if not df_all.empty:
                df_all = df_all[['code', 'tunnel', 'division', 'item_name', 'item', 'mileage', 'length', 'remark']]
                df_all.columns = ['检验批编号', '隧道', '分部工程', '分项工程', '具体部位', '里程范围', '长度', '备注']
                csv_all = df_all.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载完整检验批明细清单 (CSV)",
                    data=csv_all,
                    file_name=f"隧道检验批明细_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv'
                )
        else:
            st.info("👋 请先在侧边栏选择隧道，并点击 **【🚀 开始计算】** 按钮生成数据。")

    elif page == "📉 统计分析图表":
        if 'calc_results' in st.session_state:
            st.subheader("项目质量管控数据看板")
            summary_list = []
            for t_name, res in st.session_state.calc_results.items():
                row = {'隧道': t_name}
                row.update(res['summary'])
                summary_list.append(row)
            df_sum = pd.DataFrame(summary_list)
            if 'total' in df_sum.columns:
                df_sum = df_sum.rename(columns={'total': '合计'})
            
            fig = draw_statistics_dashboard(df_sum)
            st.pyplot(fig)
        else:
            st.info("👋 请先在侧边栏点击 **【🚀 开始计算】** 生成数据后查看图表。")

if __name__ == "__main__":
    main()