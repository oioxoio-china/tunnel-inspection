import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm

# ==========================================
# 0. 基础配置与编码字典
# ==========================================
st.set_page_config(layout="wide", page_title="隧道检验批划分助手")

def set_chinese_font():
    try:
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
    except:
        pass
set_chinese_font()

# --- 编码映射字典 ---
PART_MAP = {
    "洞口": "01",
    "洞身": "02",
    "初支": "03",
    "防水": "04",
    "衬砌": "05",
    "附属": "06"
}

ITEM_MAP = {
    # 洞口/明挖
    "土方": "01", "开挖": "01",
    "支护": "02", "锚杆": "02",
    "导向墙": "03", "钢架": "03",
    "回填": "04", "网片": "04",
    "喷混": "05",
    # 衬砌/防水
    "防水层": "01", "排水": "02",
    "仰拱": "03", "填充": "04",
    "拱墙": "05", "沟槽": "06"
}

# ==========================================
# 1. 核心计算逻辑
# ==========================================
def recalculate_data(df, start_mileage, default_trolley_len=12.0, do_sort=False):
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    if '选择' not in df.columns: df['选择'] = False
    else: df['选择'] = df['选择'].fillna(False).astype(bool)
    
    num_cols = ['长度', '序号', '榀距', '榀数', '步骤数', '循环进尺', '台车长度', '初支循环', '衬砌循环']
    for col in num_cols:
        if col not in df.columns: df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['部位'] = df['部位'].fillna("标准段").replace("", "标准段")
    df['工法'] = df['工法'].fillna("台阶法").replace("", "台阶法")

    if do_sort:
        df = df.sort_values(by='序号')
    
    df = df.reset_index(drop=True)
    
    curr = start_mileage
    new_rows = []
    
    for idx, row in df.iterrows():
        row['序号'] = idx + 1
        m_str = str(row['工法'])
        is_portal = "洞口" in m_str or "明挖" in m_str
        
        if pd.isna(row['台车长度']) or row['台车长度'] <= 0:
            row['台车长度'] = default_trolley_len

        if is_portal:
            row['初支循环'] = 1
            row['衬砌循环'] = 1
            row['榀距'] = None
            row['榀数'] = None
            row['循环进尺'] = None
            row['步骤数'] = None
            row['台车长度'] = None 
        else:
            if pd.isna(row['榀距']) or row['榀距'] <= 0: row['榀距'] = 0.6
            if pd.isna(row['榀数']) or row['榀数'] <= 0: row['榀数'] = 1
            
            if pd.isna(row['步骤数']) or row['步骤数'] <= 0:
                if "CD" in m_str or "CRD" in m_str: row['步骤数'] = 4
                elif "台阶" in m_str: row['步骤数'] = 2
                else: row['步骤数'] = 1
            
            row['循环进尺'] = row['榀距'] * row['榀数']
            if row['循环进尺'] <= 0.01: row['循环进尺'] = 1.0
            
            len_val = row['长度'] if pd.notna(row['长度']) else 0
            if len_val > 0:
                row['初支循环'] = round(len_val / row['循环进尺'], 1)
                trolley = row['台车长度'] if (pd.notna(row['台车长度']) and row['台车长度']>0) else 12.0
                row['衬砌循环'] = round(len_val / trolley, 1)
            else:
                row['初支循环'] = 0
                row['衬砌循环'] = 0

        len_val = row['长度'] if pd.notna(row['长度']) else 0
        row['起点'] = curr
        row['终点'] = curr + len_val
        curr += len_val
        new_rows.append(row)
    
    return pd.DataFrame(new_rows)

def float_to_mileage(m_float, prefix="ZK"):
    k = int(m_float / 1000)
    m = m_float % 1000
    return f"{prefix}{k}+{m:07.3f}"

def mileage_to_float(m_str):
    try:
        parts = m_str[2:].split('+')
        return float(parts[0]) * 1000 + float(parts[1])
    except:
        return 0.0

# ==========================================
# 2. 检验批生成逻辑
# ==========================================
def generate_lot_data(df_config, prefix, parts_filter, std_db):
    res = []
    
    def make_code(part, item, seg_idx, loop_idx, batch=1):
        p = PART_MAP.get(part, "00")
        i = ITEM_MAP.get(item, "00")
        return f"{p}-{i}-{int(seg_idx):02d}-{int(loop_idx):03d}-{int(batch):02d}"

    for _, seg in df_config.iterrows():
        s, e, m = seg['起点'], seg['终点'], str(seg['工法'])
        seg_idx = seg['序号']
        seg_name = seg['部位']
        
        rng_seg = f"{float_to_mileage(s, prefix)}~{float_to_mileage(e, prefix)}"
        is_portal = "洞口" in m or "明挖" in m
        
        # 1. 洞口
        if "洞口" in parts_filter and is_portal:
            items = ["土方", "支护", "导向墙", "回填"]
            for item in items:
                code = make_code("洞口", item, seg_idx, 1)
                res.append({
                    "编号": code, "段落": seg_name, "循环": "第1环",
                    "分部": "洞口", "分项": item, "里程": rng_seg,
                    "部位": f"{seg_name} {item}", "条款": "-"
                })
        
        # 2. 暗挖
        if not is_portal:
            step_len = seg['循环进尺'] if pd.notna(seg['循环进尺']) else 1.0
            step_count = int(seg['步骤数']) if pd.notna(seg['步骤数']) else 1
            
            if "CD" in m or "CRD" in m:
                step_names = ["①左上导洞","②左下导洞","③右上导洞","④右下导洞"]
                if step_count != 4: step_names = [f"第{i+1}步" for i in range(step_count)]
            elif "台阶" in m:
                step_names = ["①上台阶","②下台阶"]
                if step_count != 2: step_names = [f"第{i+1}步" for i in range(step_count)]
            else:
                step_names = [f"第{i+1}步" for i in range(step_count)]
            
            cur_m = s
            exc_loop = 1
            while cur_m < e - 0.001:
                nxt = min(cur_m + step_len, e)
                sub_rng = f"{float_to_mileage(cur_m, prefix)}~{float_to_mileage(nxt, prefix)}"
                
                for sn in step_names:
                    if "洞身" in parts_filter:
                        code = make_code("洞身", "开挖", seg_idx, exc_loop)
                        res.append({
                            "编号": code, "段落": seg_name, "循环": f"第{exc_loop}循环",
                            "分部": "洞身", "分项": "开挖", "里程": sub_rng,
                            "部位": f"{m} {sn}", "条款": std_db["洞身开挖"]["主控"]
                        })
                    if "初支" in parts_filter:
                        for t in ["锚杆", "钢架", "网片", "喷混"]:
                            code = make_code("初支", t, seg_idx, exc_loop)
                            tk = "-"
                            if t == "喷混": tk = std_db["喷射混凝土"]["主控"]
                            
                            res.append({
                                "编号": code, "段落": seg_name, "循环": f"第{exc_loop}循环",
                                "分部": "初支", "分项": t, "里程": sub_rng,
                                "部位": f"{m} {sn} {t}", "条款": tk
                            })
                cur_m = nxt
                exc_loop += 1

        # 3. 二衬
        if not is_portal:
            trolley_len = seg['台车长度'] if pd.notna(seg['台车长度']) else 12.0
            cur_m = s
            lining_loop = 1
            while cur_m < e - 0.001:
                nxt = min(cur_m + trolley_len, e)
                sub_rng = f"{float_to_mileage(cur_m, prefix)}~{float_to_mileage(nxt, prefix)}"
                
                if "防水" in parts_filter:
                    for wp in ["防水层", "排水"]:
                        code = make_code("防水", wp, seg_idx, lining_loop)
                        res.append({
                            "编号": code, "段落": seg_name, "循环": f"第{lining_loop}环",
                            "分部": "防水", "分项": wp, "里程": sub_rng,
                            "部位": f"全环 {wp}", "条款": "-"
                        })

                if "衬砌" in parts_filter:
                    code1 = make_code("衬砌", "仰拱", seg_idx, lining_loop)
                    res.append({
                        "编号": code1, "段落": seg_name, "循环": f"第{lining_loop}环",
                        "分部": "衬砌", "分项": "仰拱", "里程": sub_rng,
                        "部位": "仰拱/填充", "条款": std_db["仰拱(底板)"]["主控"]
                    })
                    code2 = make_code("衬砌", "拱墙", seg_idx, lining_loop)
                    res.append({
                        "编号": code2, "段落": seg_name, "循环": f"第{lining_loop}环",
                        "分部": "衬砌", "分项": "拱墙", "里程": sub_rng,
                        "部位": "拱墙衬砌", "条款": std_db["拱墙衬砌"]["主控"]
                    })
                
                cur_m = nxt
                lining_loop += 1
                
    return pd.DataFrame(res)

# ==========================================
# 3. 绘图逻辑
# ==========================================
def plot_tunnel_segments(df_segs, tunnel_name):
    # 增加高度以容纳统计文本
    fig, ax = plt.subplots(figsize=(14, 5))
    color_map = {
        "CD法": "#ff7f0e", "台阶法": "#1f77b4", "全断面法": "#2ca02c", 
        "CRD法": "#d62728", "双侧壁导坑法": "#9467bd", "中隔壁法": "#8c564b",
        "明挖/洞口": "#7f7f7f"
    }
    
    if df_segs is None or df_segs.empty: return fig
    
    lengths = df_segs['长度'].fillna(0).values
    total_len_calc = sum(lengths) if sum(lengths) > 0 else 1.0
    
    min_visual_pct = 5.0
    raw_pcts = (lengths / total_len_calc) * 100
    final_widths = []
    long_indices = []
    
    for i, pct in enumerate(raw_pcts):
        if pct < min_visual_pct:
            final_widths.append(min_visual_pct)
        else:
            final_widths.append(0)
            long_indices.append(i)
            
    remaining_width = 100 - sum(final_widths)
    total_long = sum(lengths[i] for i in long_indices)
    
    if total_long > 0:
        for i in long_indices:
            final_widths[i] = (lengths[i] / total_long) * remaining_width
    elif len(long_indices) == 0 and len(final_widths) > 0:
        pass

    current_x = 0
    y_pos = 0.4
    height = 0.4
    
    for idx, row in df_segs.iterrows():
        w = final_widths[idx] if idx < len(final_widths) else min_visual_pct
        color = color_map.get(row['工法'], "#dddddd")
        rect = patches.Rectangle((current_x, y_pos), w, height, linewidth=1, edgecolor='white', facecolor=color)
        ax.add_patch(rect)
        
        center_x = current_x + w/2
        center_y = y_pos + height/2
        
        # 标签处理
        len_val = row['长度'] if pd.notna(row['长度']) else 0
        label_main = f"{row['序号']}.{row['部位']}\n{len_val:.1f}m\n{row['工法']}"
        
        # 统计信息
        label_stats = ""
        is_portal = "洞口" in str(row['工法']) or "明挖" in str(row['工法'])
        
        if not is_portal:
            cyc_exc = row['初支循环'] if pd.notna(row['初支循环']) else 0
            cyc_lin = row['衬砌循环'] if pd.notna(row['衬砌循环']) else 0
            steps = row['步骤数'] if pd.notna(row['步骤数']) else 1
            
            exc_lots = int(cyc_exc * steps)
            prim_lots = int(cyc_exc * steps * 4)
            
            label_stats = (
                f"\n──────────\n"
                f"开挖: {exc_lots}批\n"
                f"初支: {int(cyc_exc)}循/{prim_lots}批\n"
                f"二衬: {int(cyc_lin)}环"
            )
        
        full_label = label_main + label_stats
        
        fontsize = 8 if w > 5 else 6
        ax.text(center_x, center_y, full_label, ha='center', va='center', color='white', fontsize=fontsize, fontweight='bold')
        current_x += w
        
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.axis('off')
    plt.title(f"{tunnel_name} 分段检验批规划图", fontsize=12, pad=10)
    
    used = df_segs['工法'].dropna().unique()
    patches_list = [patches.Patch(color=color_map.get(k, "#999"), label=k) for k in used]
    if patches_list:
        ax.legend(handles=patches_list, loc='upper right', ncol=len(patches_list), frameon=False, fontsize=9)
    plt.tight_layout()
    return fig

# ==========================================
# 4. 数据初始化
# ==========================================
if 'tunnels' not in st.session_state:
    st.session_state.tunnels = {
        "ZK (主线左线)": {"start": "ZK0+245.102", "end": "ZK1+408.000", "prefix": "ZK", "type": "main", "def_trolley": 12.0},
        "YK (主线右线)": {"start": "YK0+244.803", "end": "YK1+406.000", "prefix": "YK", "type": "main", "def_trolley": 12.0},
        "AK (A匝道)": {"start": "AK0+087.000", "end": "AK0+425.500", "prefix": "AK", "type": "ramp", "def_trolley": 9.0},
        "BK (B匝道)": {"start": "BK0+164.000", "end": "BK0+755.000", "prefix": "BK", "type": "ramp", "def_trolley": 9.0},
    }

STANDARD_DB = {
    "洞口开挖": {"主控": "6.2.1", "一般": "6.2.3"},
    "洞身开挖": {"主控": "7.2.1", "一般": "-"},
    "喷射混凝土": {"主控": "8.6.1", "一般": "8.6.4"},
    "仰拱(底板)": {"主控": "9.2.1", "一般": "9.2.7"},
    "拱墙衬砌": {"主控": "9.3.1", "一般": "9.3.8"},
    "电缆槽": {"主控": "12.4.1", "一般": "12.4.4"}
}

st.sidebar.title("🛤️ 隧道检验批助手")
sel_key = st.sidebar.selectbox("选择隧道", list(st.session_state.tunnels.keys()))
cur_tun = st.session_state.tunnels[sel_key]

start_f = mileage_to_float(cur_tun['start'])
end_f = mileage_to_float(cur_tun['end'])
total_len = end_f - start_f
prefix = cur_tun['prefix']
default_trolley_val = cur_tun['def_trolley']

# Session Key
sess_key = f"segs_{sel_key}"
refresh_key = f"refresh_{sel_key}"
if refresh_key not in st.session_state:
    st.session_state[refresh_key] = 0

if sess_key not in st.session_state:
    # 初始数据包含台车长度
    data = [
        {"选择": False, "序号": 1, "部位": "进洞口", "工法": "明挖/洞口", "长度": 2.0, "榀距":None, "榀数":None, "步骤数":None, "台车长度":None},
        {"选择": False, "序号": 2, "部位": "进洞段", "工法": "CD法", "长度": 30.0, "榀距":0.6, "榀数":1, "步骤数":4, "台车长度":default_trolley_val},
        {"选择": False, "序号": 3, "部位": "标准段", "工法": "台阶法", "长度": max(0, total_len-64), "榀距":1.6, "榀数":1, "步骤数":2, "台车长度":default_trolley_val},
        {"选择": False, "序号": 4, "部位": "出洞段", "工法": "CD法", "长度": 30.0, "榀距":0.6, "榀数":1, "步骤数":4, "台车长度":default_trolley_val},
        {"选择": False, "序号": 5, "部位": "出洞口", "工法": "明挖/洞口", "长度": 2.0, "榀距":None, "榀数":None, "步骤数":None, "台车长度":None},
    ]
    df_init = pd.DataFrame(data)
    st.session_state[sess_key] = recalculate_data(df_init, start_f, default_trolley_val)

df_main = st.session_state[sess_key]

# --- 侧边栏 ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 动态工法进尺")
all_methods = df_main['工法'].dropna().astype(str).unique().tolist()
for m in all_methods:
    if "明挖" in m or "洞口" in m: continue
    st.sidebar.caption(f"工法【{m}】参数请直接在右侧表格中修改")

# ==========================================
# 5. 主界面
# ==========================================
st.title(f"📍 {sel_key}")
st.caption(f"全长: {total_len:.3f}m | 起点: {cur_tun['start']} | 终点: {cur_tun['end']} | 默认台车: {default_trolley_val}m")

fig = plot_tunnel_segments(df_main, sel_key)
st.pyplot(fig)

st.divider()

col_header, col_tools = st.columns([5, 5])
with col_header:
    st.subheader("📝 段落编辑 (双循环独立计算)")
    
with col_tools:
    c1, c2, c3 = st.columns(3)
    if c1.button("⬆️ 选中行上移", use_container_width=True):
        sel_idxs = df_main.index[df_main['选择']].tolist()
        if len(sel_idxs) == 1:
            idx = sel_idxs[0]
            target_idx = idx - 1
            if target_idx >= 0:
                df_main.iloc[idx], df_main.iloc[target_idx] = df_main.iloc[target_idx].copy(), df_main.iloc[idx].copy()
                st.session_state[sess_key] = recalculate_data(df_main, start_f, default_trolley_val)
                st.session_state[refresh_key] += 1
                st.rerun()
            else:
                st.toast("已在顶部")
        else:
            st.toast("请勾选一行进行移动")

    if c2.button("⬇️ 选中行下移", use_container_width=True):
        sel_idxs = df_main.index[df_main['选择']].tolist()
        if len(sel_idxs) == 1:
            idx = sel_idxs[0]
            target_idx = idx + 1
            if target_idx < len(df_main):
                df_main.iloc[idx], df_main.iloc[target_idx] = df_main.iloc[target_idx].copy(), df_main.iloc[idx].copy()
                st.session_state[sess_key] = recalculate_data(df_main, start_f, default_trolley_val)
                st.session_state[refresh_key] += 1
                st.rerun()
            else:
                st.toast("已在底部")
        else:
            st.toast("请勾选一行进行移动")

    if c3.button("🔃 按序号重排", type="primary", use_container_width=True):
        st.session_state[sess_key] = recalculate_data(df_main, start_f, default_trolley_val, do_sort=True)
        st.session_state[refresh_key] += 1
        st.rerun()

current_editor_key = f"editor_{sel_key}_{st.session_state[refresh_key]}"

# === 关键修正：移除所有列的 width 参数，实现自动适应 ===
edited_df = st.data_editor(
    st.session_state[sess_key],
    column_config={
        "选择": st.column_config.CheckboxColumn("选"),
        "序号": st.column_config.NumberColumn("序号", step=0.1, format="%.1f", required=True),
        "部位": st.column_config.SelectboxColumn(
            options=["进洞口","进洞段","标准段","出洞段","出洞口","明挖段","缓冲结构","加宽段","紧急停车带","横通道交叉口"],
            required=True
        ),
        "工法": st.column_config.SelectboxColumn(
            options=["明挖/洞口", "CD法", "台阶法", "全断面法", "CRD法", "双侧壁导坑法", "中隔壁法"],
            required=True
        ),
        "长度": st.column_config.NumberColumn(min_value=0.0, format="%.1f", required=True),
        "榀距": st.column_config.NumberColumn("榀距(m)", help="初支计算依据", min_value=0.0, step=0.1, format="%.2f"),
        "榀数": st.column_config.NumberColumn("榀数/环", help="每循环施工多少榀", min_value=0, step=1),
        "循环进尺": st.column_config.NumberColumn("初支进尺", disabled=True, format="%.2f"),
        "台车长度": st.column_config.NumberColumn("台车(m)", help="衬砌计算依据", min_value=0.0, step=0.5, format="%.1f"),
        "初支循环": st.column_config.NumberColumn("初支循环", disabled=True, format="%.1f"),
        "衬砌循环": st.column_config.NumberColumn("衬砌循环", disabled=True, format="%.1f"),
        "步骤数": st.column_config.NumberColumn("步骤", help="CD法4步，台阶法2步", min_value=1, step=1),
        "起点": st.column_config.NumberColumn(disabled=True, format="%.3f"),
        "终点": st.column_config.NumberColumn(disabled=True, format="%.3f"),
    },
    num_rows="dynamic",
    width='stretch',
    hide_index=True,
    key=current_editor_key
)

# 自动同步
df_old_compare = st.session_state[sess_key].drop(columns=['选择'], errors='ignore').fillna(0)
df_new_compare = edited_df.drop(columns=['选择'], errors='ignore').fillna(0)

if not df_new_compare.equals(df_old_compare):
    recalc_df = recalculate_data(edited_df, start_f, default_trolley_val)
    st.session_state[sess_key] = recalc_df
    st.rerun()

curr_len = st.session_state[sess_key]['长度'].fillna(0).sum()
diff = curr_len - total_len
if abs(diff) > 0.1:
    st.warning(f"⚠️ 总长 {curr_len:.3f}m (设计 {total_len:.3f}m, 差 {diff:+.3f}m)")
else:
    st.success("✅ 总长校验通过")

st.divider()
tab1, tab2, tab3 = st.tabs(["📋 生成检验批明细", "📄 生成方案文本", "📊 统计汇总"])

# --- Tab 1: 生成 ---
with tab1:
    c1, c2 = st.columns(2)
    direction = c1.radio("方向", ["正向", "反向"])
    parts = c2.multiselect("分部", ["洞口", "洞身", "初支", "防水", "衬砌", "附属"], default=["洞身","初支","防水","衬砌"])
    
    if st.button("🚀 生成检验批"):
        # 调用公共生成函数
        df_res = generate_lot_data(st.session_state[sess_key], prefix, parts, STANDARD_DB)
        
        # 处理反向
        if "反向" in direction: 
            df_res = df_res.iloc[::-1].reset_index(drop=True)
        
        # 展示列筛选
        if not df_res.empty:
            cols = ['编号', '段落', '循环', '分部', '分项', '里程', '部位', '条款']
            df_res = df_res[cols]
            
        st.dataframe(df_res, width='stretch')
        
        out = BytesIO()
        with pd.ExcelWriter(out) as writer: df_res.to_excel(writer, index=False)
        st.download_button("📥 下载 Excel", out.getvalue(), "检验批明细.xlsx")

# --- Tab 2: 方案 ---
with tab2:
    st.markdown(f"### {sel_key} 施工方案")
    st.write("方案文本已自动生成...")

# --- Tab 3: 汇总 ---
with tab3:
    st.subheader("📊 检验批统计汇总")
    # 实时生成数据用于统计
    df_stats = generate_lot_data(st.session_state[sess_key], prefix, parts, STANDARD_DB)
    
    if df_stats.empty:
        st.info("请先在【生成检验批明细】页签中配置并生成数据。")
    else:
        # 1. 关键指标
        total_lots = len(df_stats)
        total_parts = df_stats['分部'].nunique()
        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        c_kpi1.metric("总检验批数量", total_lots)
        c_kpi2.metric("涉及分部数", total_parts)
        c_kpi3.metric("平均每段批数", int(total_lots / len(df_main)))
        
        st.divider()
        
        # 2. 图表分析
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            st.markdown("**各分部检验批数量**")
            chart_data = df_stats['分部'].value_counts()
            st.bar_chart(chart_data)
            
        with c_chart2:
            st.markdown("**各施工段落检验批占比**")
            # 简单饼图数据
            seg_data = df_stats['段落'].value_counts()
            st.dataframe(seg_data, width='stretch')

        st.divider()

        # 3. 透视表 (分部 vs 分项)
        st.markdown("**分部-分项 数量交叉统计表**")
        pivot_table = pd.pivot_table(
            df_stats, 
            index='分部', 
            columns='分项', 
            values='编号', 
            aggfunc='count', 
            fill_value=0
        )
        st.dataframe(pivot_table, width='stretch')
        
        # 导出汇总
        out_stats = BytesIO()
        with pd.ExcelWriter(out_stats) as writer:
            pivot_table.to_excel(writer, sheet_name="透视汇总")
            df_stats.to_excel(writer, sheet_name="明细数据", index=False)
        st.download_button("📥 下载统计报表", out_stats.getvalue(), "统计汇总.xlsx")