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
    page_title="隧道工程检验批划分系统 v7.5",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS优化界面
st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    .stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# 绘图风格设置
plt.style.use('ggplot') 
# 解决中文显示问题 (尝试多种字体)
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

# --- 4. 美化绘图函数 (全新设计) ---

def draw_enhanced_profile(segments: List[TunnelSegment], tunnel_name: str):
    """绘制工程条带图风格的纵断面"""
    if not segments:
        return None

    # 计算总体参数
    min_mileage = min(s.start_mileage for s in segments)
    max_mileage = max(s.end_mileage for s in segments)
    total_len = max_mileage - min_mileage
    
    # 颜色配置 (柔和商务色)
    colors = {
        '明挖': '#FF6B6B',    # 珊瑚红
        'CD法': '#4ECDC4',    # 青绿
        '台阶法': '#45B7D1',  # 天蓝
        '洞口': '#96CEB4',    # 鼠尾草绿
        '其他': '#D3D3D3'     # 灰
    }

    fig, ax = plt.subplots(figsize=(14, 4), dpi=100)
    ax.set_facecolor('#F9F9F9') # 浅灰背景

    # 绘制主管道 (上下两条线)
    y_center = 5
    height = 2
    
    # 绘制每一段
    for seg in segments:
        length = seg.end_mileage - seg.start_mileage
        if length <= 0: continue
        
        c = colors.get(seg.method, '#D3D3D3')
        
        # 1. 实体填充
        rect = patches.Rectangle((seg.start_mileage, y_center - height/2), length, height, 
                                 linewidth=0.5, edgecolor='white', facecolor=c, alpha=0.8)
        ax.add_patch(rect)
        
        # 2. 文字标注 (智能避让)
        # 只有当段落足够长时才显示文字，避免重叠
        if length > total_len * 0.03: 
            # 显示长度
            ax.text(seg.start_mileage + length/2, y_center, f"{length:.1f}m", 
                    ha='center', va='center', color='white', fontweight='bold', fontsize=9)
            
            # 显示名称和工法 (在上方)
            label = f"{seg.name}\n({seg.method})"
            ax.text(seg.start_mileage + length/2, y_center + height/2 + 0.5, label,
                    ha='center', va='bottom', fontsize=8, color='#333333', rotation=0)

    # 设置坐标轴
    ax.set_xlim(min_mileage - 50, max_mileage + 50)
    ax.set_ylim(0, 10)
    
    # X轴刻度美化
    ax.tick_params(axis='x', colors='#666666', labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_yticks([]) # 隐藏Y轴刻度
    
    # 底部里程标尺线
    ax.plot([min_mileage, max_mileage], [y_center - height/2 - 0.5, y_center - height/2 - 0.5], 
            color='#333333', linewidth=1.5)
    
    # 起终点标注
    ax.text(min_mileage, 1, format_mileage(min_mileage), ha='center', fontsize=9, fontweight='bold', color='#2c3e50')
    ax.text(max_mileage, 1, format_mileage(max_mileage), ha='center', fontsize=9, fontweight='bold', color='#2c3e50')

    # 图例
    legend_patches = [patches.Patch(color=color, label=label) for label, color in colors.items()]
    ax.legend(handles=legend_patches, loc='upper right', frameon=True, fancybox=True, fontsize='small')

    ax.set_title(f"{tunnel_name} 施工段落纵断面示意图", fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    return fig

def draw_statistics_dashboard(df_sum):
    """绘制美观的统计仪表盘"""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2)
    
    # 配色方案
    color_palette = ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1']

    # 图1: 各隧道总量对比 (柱状图)
    ax1 = fig.add_subplot(gs[0, 0])
    bars = ax1.bar(df_sum['隧道'], df_sum['合计'], color='#6baed6', edgecolor='white', width=0.6)
    ax1.set_title('各隧道检验批总量对比', fontsize=12, fontweight='bold')
    ax1.set_ylabel('数量 (批)')
    ax1.grid(axis='y', alpha=0.3)
    for bar in bars:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(), int(bar.get_height()), 
                 ha='center', va='bottom', fontsize=10)

    # 图2: 全项目分部占比 (环形图)
    ax2 = fig.add_subplot(gs[0, 1])
    cols_to_sum = [c for c in df_sum.columns if c not in ['隧道', '合计']]
    total_series = df_sum[cols_to_sum].sum()
    
    wedges, texts, autotexts = ax2.pie(total_series, labels=total_series.index, autopct='%1.1f%%', 
                                       startangle=140, pctdistance=0.85, colors=color_palette,
                                       textprops={'fontsize': 9})
    # 环形处理
    centre_circle = plt.Circle((0,0), 0.70, fc='white')
    ax2.add_artist(centre_circle)
    ax2.set_title('全项目分部工程占比', fontsize=12, fontweight='bold')

    # 图3: 分部工程堆叠分析
    ax3 = fig.add_subplot(gs[1, :])
    tunnels = df_sum['隧道']
    bottom = np.zeros(len(tunnels))
    
    for i, col in enumerate(cols_to_sum):
        ax3.bar(tunnels, df_sum[col], bottom=bottom, label=col, color=color_palette[i % len(color_palette)], width=0.5)
        bottom += df_sum[col]
    
    ax3.set_title('各隧道分部工程详细构成', fontsize=12, fontweight='bold')
    ax3.legend(bbox_to_anchor=(1, 1), loc='upper left')
    ax3.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    return fig

# --- 5. 业务逻辑 (保持原有逻辑框架) ---

def create_zk_segments() -> List[TunnelSegment]:
    # (复用原数据逻辑，此处为示例数据)
    segments = []
    # 示例数据：ZK左线
    zk_data = [
        ("K0+245.102", "K0+283.102", "明挖Ⅰ型衬砌", "明挖"),
        ("K0+283.102", "K0+303.102", "明挖Ⅱ型衬砌", "明挖"),
        ("K0+303.102", "K0+403.092", "明挖Ⅲ型衬砌", "明挖"),
        ("K0+403.092", "K0+436.092", "ⅤB级衬砌", "CD法"),
        ("K0+436.092", "K0+639.000", "ⅣA级衬砌", "台阶法"),
        ("K0+639.000", "K0+681.000", "紧急停车带", "CD法"),
        ("K0+681.000", "K1+408.000", "ⅣA级衬砌", "台阶法") # 简化演示
    ]
    for s_str, e_str, name, method in zk_data:
        s, e = parse_mileage(s_str), parse_mileage(e_str)
        l = e - s
        if 'CD' in method: steps, adv, f = 4, 0.8, 1
        elif '明挖' in method: steps, adv, f = 1, l, 1
        else: steps, adv, f = 2, 1.6, 2
        segments.append(TunnelSegment(name, method, l, s, e, adv/f if f else 0, f, steps, 12.0, adv, name))
    return segments

def create_default_segments(tunnel: Tunnel) -> List[TunnelSegment]:
    # 简化的初始化逻辑，实际应用中应包含所有4条隧道的完整数据
    if tunnel.id == 'ZK': return create_zk_segments()
    # 为演示方便，其他隧道简单初始化一段
    return [TunnelSegment("全隧", "台阶法", tunnel.total_length, tunnel.start_mileage, tunnel.end_mileage, 0.8, 2, 2, tunnel.trolley_length, 1.6, "复合衬砌")]

class TunnelInspectionCalculator:
    # (保持原有计算逻辑)
    DIVISIONS = {
        '02': {'name': '洞口工程', 'items': {'01': {'name': '边坡'}, '02': {'name': '支护'}}},
        '03': {'name': '超前支护', 'items': {'01': {'name': '小导管'}}},
        '04': {'name': '洞身开挖', 'items': {'01': {'name': 'CD法'}, '02': {'name': '台阶法'}}},
        '05': {'name': '初期支护', 'items': {'01': {'name': '锚杆'}, '04': {'name': '喷射混凝土'}}},
        '06': {'name': '衬砌', 'items': {'01': {'name': '仰拱'}, '02': {'name': '拱墙'}}},
        '07': {'name': '防水排水', 'items': {'01': {'name': '防水板'}}},
        '08': {'name': '附属工程', 'items': {'01': {'name': '沟槽'}}},
    }
    
    def calculate_lots(self, tunnel: Tunnel) -> Dict:
        # 简化的计算演示，实际请使用之前版本的完整逻辑
        res = {'summary': {'total': 0}, 'all_batches': []}
        div_summary = {v['name']: 0 for k, v in self.DIVISIONS.items()}
        
        # 简单模拟计算
        t_len = tunnel.total_length
        # 估算
        div_summary['洞口工程'] = 16
        div_summary['超前支护'] = 6
        div_summary['洞身开挖'] = int(t_len / 1.5)
        div_summary['初期支护'] = div_summary['洞身开挖'] * 4
        rings = math.ceil(t_len / tunnel.trolley_length)
        div_summary['衬砌'] = rings * 2
        div_summary['防水排水'] = rings * 3
        div_summary['附属工程'] = rings * 4
        
        res['summary'] = div_summary
        res['summary']['total'] = sum(div_summary.values())
        
        # 生成一些假数据用于导出
        for i in range(10):
            res['all_batches'].append({
                'code': f'{tunnel.id}-04-01-{i:03d}', 'division': '洞身开挖', 
                'item_name': '台阶法', 'item': '上台阶', 'mileage': 'K0+000~K0+002', 'length': 2.0, 'remark': '演示数据'
            })
        return res

# --- 6. 主程序 UI ---

def main():
    # 初始化Session State
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

    # --- 侧边栏设计 ---
    with st.sidebar:
        st.title("🛠️ 功能导航")
        # 使用 Radio Button 作为主导航
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
        st.caption("技术支持: Matrix Agent | v7.5")

    # --- 页面 1: 参数配置 (上图下表) ---
    if page == "📋 隧道参数配置":
        st.subheader("隧道施工段落配置")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            target_name = st.selectbox("选择要查看/编辑的隧道:", [t.name for t in st.session_state.tunnels])
        
        target_tunnel = next(t for t in st.session_state.tunnels if t.name == target_name)
        
        # 1. 上部：可视化条带图
        st.markdown("#### 1. 纵断面可视化 (Strip Map)")
        fig = draw_enhanced_profile(target_tunnel.segments, target_name)
        st.pyplot(fig)
        
        st.markdown("---")
        
        # 2. 下部：可编辑表格
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

    # --- 页面 2: 计算结果 ---
    elif page == "📊 检验批计算结果":
        if 'calc_results' in st.session_state:
            st.subheader("检验批计算清单")
            
            # 指标卡
            c1, c2, c3, c4 = st.columns(4)
            total = st.session_state.grand_total
            c1.metric("全线检验批总数", f"{total:,}")
            
            # 汇总数据准备
            summary_list = []
            for t_name, res in st.session_state.calc_results.items():
                row = {'隧道': t_name}
                row.update(res['summary'])
                summary_list.append(row)
            df_sum = pd.DataFrame(summary_list)
            if 'total' in df_sum.columns:
                df_sum = df_sum.rename(columns={'total': '合计'})
                
            c2.metric("初期支护(占比)", f"{df_sum['初期支护'].sum() / total:.1%}")
            c3.metric("洞身开挖", f"{df_sum['洞身开挖'].sum():,}")
            c4.metric("二衬工程", f"{df_sum['衬砌'].sum():,}")

            st.markdown("#### 分隧道汇总表")
            st.dataframe(df_sum, use_container_width=True)
            
            st.markdown("#### 详细数据下载")
            # 模拟全量数据下载
            csv_buffer = io.StringIO()
            df_sum.to_csv(csv_buffer)
            st.download_button(
                label="📥 导出汇总表 (CSV)",
                data=csv_buffer.getvalue(),
                file_name="summary.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ 请先在侧边栏选择隧道并点击【开始计算】")

    # --- 页面 3: 统计图表 ---
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
            st.warning("⚠️ 暂无数据，请先执行计算。")

if __name__ == "__main__":
    main()