import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from dataclasses import dataclass, field
from typing import List, Dict
import math
import io
import json
from datetime import datetime

# 设置页面配置
st.set_page_config(
    page_title="隧道工程检验批划分系统 v7.1 (Web版)",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 核心数据结构 (保持与原版一致) ---

@dataclass
class TunnelSegment:
    """施工段落配置"""
    name: str
    method: str
    length: float
    frame_spacing: float = 0.8
    frames_per_ring: int = 1
    steps: int = 4
    trolley_length: float = 12.0
    advance_per_cycle: float = 0.8
    start_mileage: float = 0.0
    end_mileage: float = 0.0
    lining_type: str = ""

@dataclass
class Tunnel:
    """隧道参数"""
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

# --- 工具函数 ---

def parse_mileage(km_str: str) -> float:
    """解析里程字符串"""
    km_str = str(km_str).strip()
    if '+' in km_str:
        parts = km_str.split('+')
        if len(parts) > 1:
            prefix_part = parts[0].strip()
            km_val = 0
            digits = ''.join(filter(str.isdigit, prefix_part))
            if digits:
                km_val = int(digits)
            try:
                meter_val = float(parts[1])
                return km_val * 1000 + meter_val
            except:
                pass
    try:
        return float(km_str)
    except:
        return 0.0

def format_mileage(meters: float) -> str:
    """格式化里程"""
    km = int(meters / 1000)
    m = meters % 1000
    return f"K{km}+{m:.3f}"

# --- 绘图函数 ---

def draw_tunnel_profile(segments: List[TunnelSegment], tunnel_name: str):
    """绘制隧道纵断面图"""
    # 设置字体以支持中文
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
    matplotlib.rcParams['axes.unicode_minus'] = False
    
    if not segments:
        st.warning("暂无段落数据")
        return None

    fig, ax = plt.subplots(figsize=(12, 3))
    
    method_colors = {
        '明挖': '#FF6B6B',    # 红色
        'CD法': '#4ECDC4',    # 青色
        '台阶法': '#45B7D1',  # 蓝色
        '洞口': '#96CEB4',    # 绿色
    }
    
    start_mileage = min(seg.start_mileage for seg in segments)
    end_mileage = max(seg.end_mileage for seg in segments)
    total_length = end_mileage - start_mileage
    
    y_base = 0.5
    height = 0.4
    
    for seg in segments:
        x_start = seg.start_mileage
        x_width = seg.end_mileage - seg.start_mileage
        color = method_colors.get(seg.method, '#CCCCCC')
        
        rect = plt.Rectangle((x_start, y_base - height/2), x_width, height, 
                             facecolor=color, edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)
        
        if x_width > 20: # 仅在足够宽时显示标签
            label_text = f"{seg.name}\n{seg.method}"
            ax.text(x_start + x_width/2, y_base, label_text, 
                   ha='center', va='center', fontsize=8, color='black')

    ax.set_xlim(start_mileage - 10, end_mileage + 10)
    ax.set_ylim(0, 1)
    ax.set_xlabel('里程 (m)')
    ax.set_title(f'{tunnel_name} - 纵断面示意图 (全长: {total_length:.1f}m)')
    ax.set_yticks([])
    
    # 图例
    legend_elements = [plt.Rectangle((0,0),1,1, color=color, label=method) 
                      for method, color in method_colors.items() 
                      if method in [s.method for s in segments]]
    ax.legend(handles=legend_elements, loc='upper right', fontsize='small')
    
    plt.tight_layout()
    return fig

# --- 核心逻辑 (段落生成) ---
# (为了节省篇幅，这里复用了你原代码中的逻辑，稍作适配)

def create_zk_segments() -> List[TunnelSegment]:
    # ... (保持原代码 create_zk_segments 的内容不变，直接复制过来) ...
    # 为方便演示，这里简化一点，请把原函数完整粘贴回来
    segments = []
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
        elif 'CD' in method: steps, advance, frames = 4, 0.8, 1
        else: steps, advance, frames = 2, 1.6, 2
        
        segments.append(TunnelSegment(name, method, length, advance/frames, frames, steps, 12.0, advance, start, end, name))
    return segments

def create_yk_segments() -> List[TunnelSegment]:
    # ... (简化的 YK 逻辑，实际使用时请完整复制原函数) ...
    segments = []
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
        parts = line.split(',')
        if len(parts) < 4: continue
        start, end = parse_mileage(parts[0]), parse_mileage(parts[1])
        name = parts[2].replace('（', '').replace('）', '').replace('(', '').replace(')', '')
        method = parts[3].strip()
        length = end - start
        if method == '明挖': steps, advance, frames = 1, length, 1
        elif 'CD' in method: steps, advance, frames = 4, 0.8, 1
        else: steps, advance, frames = 2, 1.6, 2
        segments.append(TunnelSegment(name, method, length, advance/frames, frames, steps, 12.0, advance, start, end, name))
    return segments

def create_ak_segments() -> List[TunnelSegment]:
    # ... (简化的 AK 逻辑) ...
    segments = []
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
        segments.append(TunnelSegment(name, method, length, advance/frames if frames>0 else 0, frames, steps, 9.0, advance, start, end, name))
    segments.sort(key=lambda x: x.start_mileage)
    return segments

def create_bk_segments() -> List[TunnelSegment]:
    # ... (简化的 BK 逻辑) ...
    segments = []
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
        segments.append(TunnelSegment(name, method, length, advance/frames if frames>0 else 0, frames, steps, 9.0, advance, start, end, name))
    segments.sort(key=lambda x: x.start_mileage)
    return segments

def create_default_segments(tunnel: Tunnel) -> List[TunnelSegment]:
    if tunnel.id == 'ZK': return create_zk_segments()
    elif tunnel.id == 'YK': return create_yk_segments()
    elif tunnel.id == 'AK': return create_ak_segments()
    elif tunnel.id == 'BK': return create_bk_segments()
    return []

# --- 检验批计算器类 (重构为函数式或保持类结构) ---

class TunnelInspectionCalculator:
    # ... (保持原类的 DIVISIONS 定义和逻辑，此处省略部分代码以聚焦核心) ...
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
        results = {'tunnel_name': tunnel.name, 'divisions': {}, 'summary': {}, 'all_batches': []}
        
        # 初始化结构
        for d_code, d_info in self.DIVISIONS.items():
            results['divisions'][d_code] = {'name': d_info['name'], 'items': {}, 'total_batches': 0}
            for i_code, i_info in d_info['items'].items():
                results['divisions'][d_code]['items'][i_code] = {'name': i_info['name'], 'formula': i_info.get('formula',''), 'batches': [], 'count': 0}

        # 1. 洞口 & 超前 (简化逻辑：进出洞各1套)
        for d, i_codes in [('02', ['01','04']), ('03', ['01','02','03'])]: # 1批的项目
            for ic in i_codes:
                if ic in results['divisions'][d]['items']:
                    self._add_batch(results, tunnel, d, ic, 1, '进洞口')
                    self._add_batch(results, tunnel, d, ic, 2, '出洞口')
        
        # 洞口多批次项目 (02-02支护, 02-03导向墙)
        for ic in ['02', '03']:
            for k in range(3):
                self._add_batch(results, tunnel, '02', ic, k+1, '进洞口')
                self._add_batch(results, tunnel, '02', ic, k+4, '出洞口')

        # 2. 开挖(04) & 初支(05)
        for seg in tunnel.segments:
            if seg.method not in ['CD法', '台阶法']: continue
            cycles = int(seg.length / seg.advance_per_cycle)
            
            # 开挖
            ic_exc = '01' if seg.method == 'CD法' else '02'
            step_names = ['左上','右上','左下','右下'] if seg.method == 'CD法' else ['上台阶','下台阶']
            
            for c in range(cycles):
                start = seg.start_mileage + c*seg.advance_per_cycle
                end = start + seg.advance_per_cycle
                
                # 添加开挖批
                for s_idx, s_name in enumerate(step_names):
                    seq = c * seg.steps + s_idx + 1
                    self._add_batch(results, tunnel, '04', ic_exc, seq, f"{seg.name}-{s_name}", start, end)
                    
                    # 添加初支批 (每个开挖部位对应4个初支：锚/钢/网/喷)
                    for ic_sup in ['01','02','03','04']:
                        self._add_batch(results, tunnel, '05', ic_sup, seq, f"{seg.name}-{s_name}", start, end)

        # 3. 衬砌(06), 防排水(07), 附属(08)
        trolley = tunnel.trolley_length
        rings = math.ceil(tunnel.total_length / trolley)
        
        for r in range(rings):
            start = tunnel.start_mileage + r*trolley
            end = min(start + trolley, tunnel.end_mileage)
            # 衬砌
            self._add_batch(results, tunnel, '06', '01', r+1, '仰拱', start, end)
            self._add_batch(results, tunnel, '06', '02', r+1, '拱墙', start, end)
            # 防排水
            for ic in ['01','02','03']: self._add_batch(results, tunnel, '07', ic, r+1, '防排水', start, end)
            # 附属
            for ic in ['01','02','03','04']: self._add_batch(results, tunnel, '08', ic, r+1, '附属', start, end)

        # 汇总统计
        total = 0
        for d_code, d_data in results['divisions'].items():
            d_total = sum(len(i['batches']) for i in d_data['items'].values())
            d_data['total_batches'] = d_total
            results['summary'][d_data['name']] = d_total
            total += d_total
            # 更新item count
            for i_data in d_data['items'].values():
                i_data['count'] = len(i_data['batches'])
        
        results['summary']['total'] = total
        return results

    def _add_batch(self, results, tunnel, d, i, seq, remark, start=0, end=0):
        if start==0 and end==0: # 洞口工程等
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

# --- 主程序逻辑 ---

def main():
    # 初始化数据
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

    # --- 侧边栏 ---
    st.sidebar.title("🛠️ 工程配置")
    
    selected_tunnel_names = st.sidebar.multiselect(
        "选择参与计算的隧道",
        [t.name for t in st.session_state.tunnels],
        default=[t.name for t in st.session_state.tunnels]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.info("点击下方按钮开始计算")
    run_calc = st.sidebar.button("🚀 开始计算检验批", type="primary")

    # --- 主界面 ---
    st.title("🚇 隧道工程检验批划分系统 (Web版)")
    st.markdown("基于 **TB 10417-2018** 标准 | 支持 **ZK/YK/A/B** 全线数据")

    # Tab页切换
    tab1, tab2, tab3 = st.tabs(["📋 隧道参数概览", "📊 检验批计算结果", "📉 统计图表"])

    with tab1:
        st.subheader("隧道基础数据")
        tunnel_df = []
        for t in st.session_state.tunnels:
            tunnel_df.append({
                "ID": t.id, "名称": t.name, "全长(m)": t.total_length,
                "起讫里程": f"{t.start_label} ~ {t.end_label}",
                "台车长度": t.trolley_length, "段落数": len(t.segments)
            })
        st.dataframe(pd.DataFrame(tunnel_df), hide_index=True)
        
        st.subheader("纵断面示意图")
        # 展示选中隧道的第一条（示例）
        if selected_tunnel_names:
            preview_tunnel = next(t for t in st.session_state.tunnels if t.name == selected_tunnel_names[0])
            fig = draw_tunnel_profile(preview_tunnel.segments, preview_tunnel.name)
            st.pyplot(fig)

    if run_calc:
        calc = TunnelInspectionCalculator()
        all_results = {}
        grand_total = 0
        all_batches_flat = []

        for t_name in selected_tunnel_names:
            tunnel = next(t for t in st.session_state.tunnels if t.name == t_name)
            res = calc.calculate_lots(tunnel)
            all_results[t_name] = res
            grand_total += res['summary']['total']
            
            for b in res['all_batches']:
                b['tunnel'] = t_name # 添加隧道名以便汇总
                all_batches_flat.append(b)

        st.session_state.calc_results = all_results
        st.session_state.grand_total = grand_total
        st.session_state.all_batches = all_batches_flat
        st.toast(f"计算完成！共生成 {grand_total} 个检验批")

    # 展示计算结果
    if 'calc_results' in st.session_state:
        with tab2:
            st.success(f"✅ 计算完成！全线共计 **{st.session_state.grand_total}** 个检验批")
            
            # 汇总表
            st.subheader("分部工程汇总表")
            summary_data = []
            for t_name, res in st.session_state.calc_results.items():
                row = {"隧道": t_name}
                row.update(res['summary'])
                summary_data.append(row)
            
            df_sum = pd.DataFrame(summary_data)
            # 调整列顺序
            cols = ['隧道', '洞口工程', '超前支护', '洞身开挖', '初期支护', '衬砌', '防水排水', '附属工程', 'total']
            df_sum = df_sum[cols].rename(columns={'total': '合计'})
            st.dataframe(df_sum, hide_index=True)

            # 详细数据下载
            st.subheader("数据导出")
            df_all = pd.DataFrame(st.session_state.all_batches)
            
            # 重命名列以符合阅读习惯
            df_all = df_all[['code', 'tunnel', 'division', 'item_name', 'item', 'mileage', 'length', 'remark']]
            df_all.columns = ['检验批编号', '隧道', '分部工程', '分项工程', '具体部位', '里程范围', '长度', '备注']
            
            csv = df_all.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载完整检验批明细 (CSV)",
                data=csv,
                file_name=f"隧道检验批明细_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
            )

        with tab3:
            st.subheader("可视化统计")
            if not df_sum.empty:
                # 绘制堆叠柱状图
                fig, ax = plt.subplots(figsize=(10, 6))
                
                tunnels = df_sum['隧道']
                divisions = ['洞口工程', '超前支护', '洞身开挖', '初期支护', '衬砌', '防水排水', '附属工程']
                colors = ['#95a5a6', '#34495e', '#e74c3c', '#2ecc71', '#3498db', '#9b59b6', '#f1c40f']
                
                bottom = [0] * len(tunnels)
                for idx, div in enumerate(divisions):
                    values = df_sum[div].values
                    ax.bar(tunnels, values, bottom=bottom, label=div, color=colors[idx], width=0.5)
                    bottom += values
                
                ax.set_ylabel("检验批数量")
                ax.set_title("各隧道分部工程检验批分布")
                ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                st.pyplot(fig)

                # 关键指标卡片
                c1, c2, c3 = st.columns(3)
                c1.metric("初期支护占比", f"{df_sum['初期支护'].sum() / df_sum['合计'].sum():.1%}")
                c2.metric("开挖检验批", f"{df_sum['洞身开挖'].sum()}")
                c3.metric("总检验批", f"{st.session_state.grand_total}")

if __name__ == "__main__":
    main()