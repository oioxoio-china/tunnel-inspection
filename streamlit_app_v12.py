import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import math
import json
import base64
import os
from datetime import datetime

# --- 1. 页面与样式配置 ---
st.set_page_config(
    page_title="隧道工程检验批划分系统 Pro v12.1",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    .metric-card {
        border-radius: 12px; padding: 24px 16px; color: white; text-align: center;
        box-shadow: 0 8px 16px rgba(0,0,0,0.1); margin-top: 10px; margin-bottom: 20px;
        min-height: 130px; display: flex; flex-direction: column; justify-content: center;
        transition: transform 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.15); }
    .metric-title { font-size: 1.1rem; opacity: 0.95; margin-bottom: 8px; font-weight: 500;}
    .metric-value { font-size: 2.2rem; font-weight: 800; line-height: 1.2; letter-spacing: 1px;}
    .bg-blue { background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); }
    .bg-green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .bg-purple { background: linear-gradient(135deg, #654ea3 0%, #eaafc8 100%); }
    .bg-orange { background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%); }
    h3 { margin-top: 1.5rem !important; margin-bottom: 1rem !important; color: #2c3e50;}
    .standard-text { font-size: 1.05rem; line-height: 1.8; color: #333; background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); white-space: pre-wrap; font-family: 'Microsoft YaHei', sans-serif;}
    .highlight { background-color: #ffeaa7; padding: 2px 4px; border-radius: 3px; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# 防乱码字体设置
plt.style.use('ggplot') 
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
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

# --- 3. 辅助函数与 IO ---

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

# --- 标准电子书文本库 ---
def get_tb10417_full_text():
    return {
        "1 总则": """1.0.1 为加强铁路隧道工程施工质量管理,统一验收要求,制定本标准。
1.0.2 本标准适用于新建和改建设计速度为200km/h 及以下铁路隧道工程施工质量验收。
1.0.3 铁路隧道工程建设各方应执行国家法律法规及相关技术标准,按设计文件进行施工,满足工程结构安全、耐久性能及使用功能要求。
1.0.4 铁路隧道工程建设各方应建立健全质量保证体系,对工程施工质量进行全过程控制,加强对进场检验及隐蔽工程、关键工序的质量验收。
1.0.7 铁路隧道工程涉及的环境保护、水土保持等工程应与主体工程同时设计、同时施工和同时验收。""",
        
        "2 术语": """2.0.1 工程施工质量：反映工程施工过程或实体满足相关标准规定或合同约定的要求。
2.0.2 检验：对检验项目的特征、性能进行量测、检查、试验等，并将结果与标准规定要求进行比较。
2.0.13 检验批：按同一生产条件或按规定的方式汇总起来供抽样检验用的，由一定数量样本组成的检验体。
2.0.17 超挖：隧道实际开挖断面大于设计开挖断面的部分。
2.0.18 欠挖：隧道实际开挖断面小于设计开挖断面的部分。
2.0.20 回填注浆：在衬砌完成后,为了填充衬砌与围岩之间的空隙面进行的注浆。""",
        
        "3 基本规定": """3.1.3 铁路隧道工程施工质量控制应符合下列规定: 隐蔽工程覆盖前应按国家法律法规和本标准要求全数检查并形成记录,经监理工程师检查认可后才能进行下道工序施工。
3.2.1 铁路隧道工程施工质量验收应按单位工程、分部工程、分项工程和检验批划分。
3.2.5 检验批可根据施工、质量控制和验收的需要,按施工段、工程量等进行划分。
3.3.2 检验批质量验收合格应符合下列规定：主控项目的质量经抽样检验全部合格；一般项目的质量经抽样检验应合格，其合格点率应达到80%及以上。""",

        "4 原材料、构配件和半成品": """4.1.1 隧道模筑混凝土、喷射混凝土及结构钢筋等原材料的技术指标和进场检验应符合《铁路混凝土工程施工质量验收标准》TB 10424的相关规定。
4.1.3 钢架、钢筋网片、小导管、沟槽盖板等半成品、构配件应实现工厂化生产,检验合格方能出厂,可采用出厂检验合格证作为质量证明文件。
4.2.1 锚杆的规格和性能应符合设计要求和有关标准的规定。
4.3.1 防水板原材料物理、力学性能指标应符合设计及《铁路隧道防水材料 第1部分:防水板》TB/T 3360.1相关规定。
4.4.1 钢架的型钢(钢筋)规格和材质、节段几何尺寸、焊接质量等应符合设计要求。试拼成型后,钢架的高度、宽度允许偏差应符合要求。""",

        "5 加固处理": """5.1.1 地表注浆、隧底加固桩施工前,应进行工艺性试验,确定施工工艺参数。
5.2.1 浆液类型应符合设计要求。检验数量:施工单位、监理单位全数检查。
5.2.3 注浆加固效果应符合设计要求。检验方法:钻孔取芯检查固结或充填情况。
5.3.1 隧底加固桩的类型、加固范围和数量应符合设计要求。
5.3.3 隧底加固桩混凝土强度应符合设计要求,检验应符合TB10424的规定。""",
        
        "6 洞口及明洞工程": """6.1.1 隧道洞口及边、仰坡开挖过程中应及时核查地形、地质情况。
6.2.1 洞口边、仰坡的范围及形式应符合设计要求。(主控项目)
6.2.2 洞口边、仰坡的坡度不应大于设计坡度。(主控项目)
6.3.1 明洞(棚洞)结构基础的地质情况和基底承载力应符合设计要求。
6.4.1 隧道洞门端翼墙、挡土墙基础的地质情况和基底承载力应符合设计要求。(主控项目)
6.5.1 回填材料、粒径应符合设计要求。回填压实质量应符合设计要求。""",
        
        "7 洞身开挖": """7.1.3 隧道钻爆开挖应遵循减少围岩扰动、严格控制超欠挖的原则进行爆破设计。
7.2.1 隧道开挖断面的中线和高程应符合设计要求。检验数量:每一开挖循环检查一次。(主控项目)
7.2.2 隧道开挖轮廓尺寸应符合设计要求,并应严格控制欠挖,围岩完整、石质坚硬时个别突出部位最大欠挖值不大于5cm,且每平方米不大于0.1m²。(主控项目)
7.2.3 隧道开挖后应对地质情况进行确认；隧底设计有地基承载力要求的地段，应进行承载力试验检测。""",
        
        "8 支护": """8.1.1 隧道初期支护应紧跟开挖及时施作,并应及早封闭成环。
8.2.1 管棚钢管的种类、规格和长度应符合设计要求。
8.3.1 超前小导管的种类、规格和长度应符合设计要求。
8.6.1 喷射混凝土的24h强度不应小于10MPa。
8.6.3 喷射混凝土平均厚度应满足设计要求，且90%以上的检测点应不小于设计厚度值。(主控项目)
8.6.4 喷射混凝土表面应平顺，两突出物之间的深长比(D/L)不应大于1/20。(一般项目)
8.7.2 钢筋网搭接长度应不少于1个网格。(主控项目)
8.8.1 锚杆类型、规格、长度应符合设计要求。(主控项目)
8.9.1 钢架及其连接螺栓的种类和材料规格应符合设计要求。""",
        
        "9 衬砌": """9.1.5 拱墙混凝土在初期支护变形稳定后施工的,拆模时的混凝土强度不应小于10 MPa。
9.1.6 仰拱(底板)和填充、拱墙二次衬砌完成后,应采用地质雷达对其实体质量进行检查。
9.2.1 仰拱(底板)和填充的基底清理及断面尺寸应符合设计要求。(主控项目)
9.3.1 隧道拱墙衬砌施工前,应对初期支护净空断面进行检查,断面尺寸应符合设计要求。
9.3.3 拱墙衬砌混凝土强度应符合设计要求。
9.3.7 实体混凝土的厚度、密实度、钢筋间距、保护层厚度应符合设计要求。(主控项目)
9.4.2 回填注浆后,拱墙衬砌与初期支护之间应密实、无空洞。""",
        
        "10 防水和排水": """10.1.3 防(排)水板铺设宜采用专用作业台架或自动铺设台车,铺设前应对基面进行清理和处置。
10.3.3 防(排)水板铺设范围应符合设计要求,搭接宽度不应小于15 cm,与衬砌端头的搭接预留长度不应小于100cm。(主控项目)
10.3.4 防水板焊缝应符合设计要求，无漏焊、假焊、焊焦、焊穿等。
10.5.2 止水带的连接方式和搭接长度应符合设计要求。
10.5.3 遇水膨胀止水条接头搭接长度不应小于50 mm。
10.7.2 排水盲管铺设位置和范围应符合设计要求，固定应牢固、平顺。
10.12.3 注浆防水效果主要通过每昼夜出水量来检验，看是否符合设计要求。""",

        "11 辅助坑道": """11.1.2 辅助坑道口截水、排水系统和防冲刷设施应在进洞前按设计要求完成。
11.1.3 辅助坑道与正洞的结合部应加强支护设计,结合部的二次衬砌及时施作。
11.2.1 辅助坑道开挖断面的中线、高程应符合设计要求。
11.3.1 辅助坑道口边、仰坡形式,坡度及防护工程应符合设计要求。
11.3.2 横洞、斜井和平行导坑的洞门,竖井的锁口圈,井口段衬砌等断面应符合设计要求。""",

        "12 附属设施": """12.1.1 铁路隧道通风、防灾救援、洞内附属构筑物等与土建相关的运营设施安装不应侵入隧道建筑限界。
12.2.1 通风机房、风道结构位置、结构尺寸应符合设计要求。
12.3.1 救援站位置、长度,站台宽度、高度及其站内横通道尺寸应符合设计要求。
12.3.6 疏散救援设施的各类防护门的技术标准、尺寸及开启方向应符合设计要求。
12.4.1 电缆槽结构断面尺寸应符合设计要求。
12.5.1 隧道各类附属洞室设置位置、支护结构、断面尺寸应符合设计要求。
12.6.1 接地体的位置、埋设深度、外露长度应符合设计要求。
12.7.1 弃渣场的位置、弃渣高度、各级平台宽度应符合设计要求。""",

        "13 明挖隧道": """13.1.6 基坑开挖应根据地质、环境条件自上而下、分段分层进行,并应及时完成支撑和支护。
13.2.1 地下连续墙位置、宽度、深度应符合设计要求。
13.2.5 地下连续墙接头处理对于基坑开挖安全非常重要，应不渗不漏。
13.3.1 钢筋混凝土支撑结构的平面位置、断面尺寸应符合设计要求。
13.4.1 基底承载力及基底处理应符合设计要求。
13.5.1 混凝土垫层厚度应符合设计要求。""",

        "14 盾构(TBM)隧道": """14.1.2 盾构(TBM) 法施工应做好设备选型,合理确定技术参数。
14.2.1 管片拼装应符合设计要求,管片无内外贯穿裂缝。
14.2.4 螺栓规格及拧紧度必须符合设计要求。
14.3.2 同步注浆压力和注浆量应符合设计要求。
14.4.2 二次注浆压力应符合设计要求。注浆量应根据管片外间隙检测结果合理确定。
14.5.2 TBM隧道管片与围岩之间的空隙应及时充填豆砾石并注浆。
14.6.3 防水密封条应干净整洁,安装位置正确,粘贴牢固。""",

        "15 隧道单位工程质量综合验收": """15.0.2 单位工程衬砌混凝土厚度、密实度应符合设计要求。
15.0.3 单位工程衬砌混凝土强度应符合设计要求。
15.0.5 隧道衬砌内轮廓不得侵入建筑限界。
15.0.6 衬砌混凝土无纵向贯通裂缝,裂缝宽度不应大于0.2mm。
15.0.9 隧道及其设备洞室不渗水,道床无积水,泄水孔排水畅通。""",

        "附录A 隐蔽工程影像资料留存": """A.0.1 隧道工程中隧底开挖、初期支护、防水和排水、二次衬砌等隐蔽工程和重要工序验收时,应留存相关影像资料。
A.0.2 影像资料应包括标识牌、隐蔽工程实体、检验人员影像和验收结论等内容。
A.0.3 标识牌应包括检验参与单位名称、单位工程、分部工程、验收部位、检验人员姓名、检验日期等。
A.0.4 影像资料采集应主题突出,图像清晰。视频分辨率应不小于1080×720像素。
A.0.5 影像资料采集频率应与有关检验批验收频率一致。""",

        "附录B 分部分项及检验批划分": """【矿山法隧道分部分项划分要求】
1. 加固处理：地表注浆加固、隧底加固桩（检验批：同一连续加固段且不大于100m）。
2. 洞口工程：洞门及端翼墙、回填、边仰坡防护、洞门检查设施（检验批：每个洞口）。
3. 洞身开挖：开挖（检验批：同一围岩不大于60隧道延米）。
4. 初期支护：管棚、小导管、喷射混凝土、钢筋网、系统锚杆、钢架等。
5. 衬砌工程：仰拱和填充、拱墙衬砌（检验批：同一围岩不大于5个浇筑段）。
6. 防水和排水：防排水板、施工缝、变形缝、盲管、检查井等。
7. 辅助坑道：开挖、支护、衬砌、坑道口封闭。
8. 附属设施：通风土建、疏散救援、电缆槽、附属洞室、综合接地、弃渣场。
【明挖隧道划分】增加围护结构（连续墙等）、基坑开挖、基坑回填等。
【盾构TBM划分】增加始发接收洞、管片拼装、同步注浆、豆砾石充填等分项。""",

        "附录C~F 验收记录表格": """附录C 检验批质量验收记录：包含主控项目、一般项目的检查评定及监理验收结论。
附录D 分项工程质量验收记录：汇总各检验批评定结果及实体检测结果。
附录E 分部工程质量验收记录：汇总分项工程结果、质量控制资料及主要功能检验报告。
附录F 单位工程质量验收记录：包含实体质量核查、观感质量验收、综合质量评定等，需施工、勘察设计、监理、建设单位四方签字盖章。""",

        "《条文说明》重点解读": """1.0.7 隧道工程涉及的环境保护、水土保持等工程应与主体工程“三同时”。
3.1.4 强调隐蔽工程覆盖前全数检查并留存影像资料，落实工程终身责任制。
6.1.7 洞门和明洞结构回填应在混凝土达到设计强度后对称分层回填，避免破坏结构。
7.1.4 岩溶隧道开挖后，应采用物探、钻探对洞身周边及底板进行探明，防止突水。
8.1.2 隧道开挖后及时进行支护，利用围岩成拱效应，及早封闭成环。
8.6.4 提高喷射混凝土平整度要求(D/L不大于1/20)，防止刺破防水板导致背后空洞。
9.1.5 软岩大变形隧道，混凝土达到设计强度70%以上（通常7天）即可拆模。
9.4 拱墙背后回填注浆需确保二次衬砌背后无空洞，且控制好注浆压力防止破坏衬砌。
10.3.3 防水板挂点间距拱部0.5~0.8m，边墙0.8~1.0m，需具备合适松弛度防止浇筑时绷紧扯裂。
12.7.1 严禁随意弃渣，弃渣场必须按设计位置堆放并做好挡护、复垦、绿化，避免安全及环境隐患。"""
    }

def get_tb10417_db():
    data = [
        {"分部工程": "06 洞口工程", "分项工程": "洞口开挖", "条款号": "6.2.1~6.2.2", "性质": "主控项目", "核心内容": "边、仰坡的范围、形式及坡度应符合设计要求。"},
        {"分部工程": "06 洞口工程", "分项工程": "洞口开挖", "条款号": "6.2.3~6.2.4", "性质": "一般项目", "核心内容": "洞口开挖允许偏差；边、仰坡应稳定，无危石。"},
        {"分部工程": "06 洞口工程", "分项工程": "导向墙(洞门)", "条款号": "6.4.1~6.4.4", "性质": "主控项目", "核心内容": "基底承载力、断面尺寸、混凝土强度及变形缝处理应符合设计。"},
        {"分部工程": "06 洞口工程", "分项工程": "导向墙(洞门)", "条款号": "6.4.5~6.4.6", "性质": "一般项目", "核心内容": "泄水孔位置、间距通畅；预埋件及预留孔洞偏差符合表6.4.6规定。"},
        {"分部工程": "06 洞口工程", "分项工程": "回填", "条款号": "6.5.1~6.5.2", "性质": "主控项目", "核心内容": "回填材料、粒径应符合设计要求；回填压实质量应符合设计要求。"},
        {"分部工程": "07 洞身开挖", "分项工程": "洞身开挖", "条款号": "7.2.1~7.2.3", "性质": "主控项目", "核心内容": "开挖断面的中线和高程符合设计；严格控制欠挖；地质情况及地基承载力检验。"},
        {"分部工程": "08 支护", "分项工程": "喷射混凝土", "条款号": "8.6.1~8.6.3", "性质": "主控项目", "核心内容": "24h强度不小于10MPa；实体强度符合设计；平均厚度满足要求。"},
        {"分部工程": "08 支护", "分项工程": "喷射混凝土", "条款号": "8.6.4", "性质": "一般项目", "核心内容": "表面平顺，两突出物之间的深长比(D/L)不应大于1/20。"},
        {"分部工程": "08 支护", "分项工程": "钢筋网", "条款号": "8.7.1~8.7.2", "性质": "主控项目", "核心内容": "网格尺寸符合设计；搭接长度不少于1个网格。"},
        {"分部工程": "08 支护", "分项工程": "系统锚杆", "条款号": "8.8.1~8.8.3", "性质": "主控项目", "核心内容": "类型、规格、数量符合设计；胶结及锚固长度符合要求。"},
        {"分部工程": "08 支护", "分项工程": "钢架", "条款号": "8.9.1~8.9.3", "性质": "主控项目", "核心内容": "规格、材质、数量符合设计；基础牢固、连接符合设计。"},
        {"分部工程": "09 衬砌", "分项工程": "仰拱(底板)和填充", "条款号": "9.2.1~9.2.6", "性质": "主控项目", "核心内容": "基底清理、尺寸、钢筋、预埋件、强度、抗渗、密实度符合设计。"},
        {"分部工程": "09 衬砌", "分项工程": "拱墙衬砌", "条款号": "9.3.1~9.3.7", "性质": "主控项目", "核心内容": "净空断面、钢筋规格、强度、厚度及密实度符合设计要求。"},
        {"分部工程": "10 防排水", "分项工程": "防水板", "条款号": "10.3.1~10.3.5", "性质": "主控项目", "核心内容": "材质、基面平顺度、搭接宽度、焊缝质量符合设计要求。"},
        {"分部工程": "10 防排水", "分项工程": "排水盲管", "条款号": "10.7.1~10.7.4", "性质": "主控项目", "核心内容": "盲管品种规格符合设计；不应低于水沟底面高程；连接牢固、畅通无阻。"}
    ]
    return pd.DataFrame(data)

# --- 4. 默认数据生成器 ---

def create_zk_segments() -> List[TunnelSegment]:
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
        if '明挖' in method: steps, advance, frames = 1, length, 1
        elif 'CD' in method: steps, advance, frames = 4, 0.8, 1; method='CD法'
        else: steps, advance, frames = 2, 1.6, 2; method='台阶法'
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 12.0, advance, name))
    return segments

def create_yk_segments() -> List[TunnelSegment]:
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
        parts = line.replace('，', ',').split(',')
        if len(parts) < 4: continue
        start, end = parse_mileage(parts[0]), parse_mileage(parts[1])
        name = parts[2].replace('（', '').replace('）', '').replace('(', '').replace(')', '')
        method = parts[3].strip()
        length = end - start
        if '明挖' in method: steps, advance, frames = 1, length, 1
        elif 'CD' in method: steps, advance, frames = 4, 0.8, 1; method='CD法'
        else: steps, advance, frames = 2, 1.6, 2; method='台阶法'
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 12.0, advance, name))
    return segments

def create_ak_segments() -> List[TunnelSegment]:
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
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 9.0, advance, name))
    segments.sort(key=lambda x: x.start_mileage)
    return segments

def create_bk_segments() -> List[TunnelSegment]:
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
        segments.append(TunnelSegment(name, method, length, start, end, advance/frames if frames else 0, frames, steps, 9.0, advance, name))
    segments.sort(key=lambda x: x.start_mileage)
    return segments

def create_demo_project() -> Project:
    t_zk = Tunnel("ZK", "ZK左线", 1162.898, 245.102, 1408.000, "K0+245.102", "K1+408.000", True, 12.0, "正向", create_zk_segments())
    t_yk = Tunnel("YK", "YK右线", 1161.197, 244.803, 1406.000, "K0+244.803", "K1+406.000", True, 12.0, "正向", create_yk_segments())
    t_ak = Tunnel("AK", "A匝道", 338.5, 87.0, 425.5, "AK0+087", "AK0+425.5", False, 9.0, "正向", create_ak_segments())
    t_bk = Tunnel("BK", "B匝道", 591.0, 164.0, 755.0, "BK0+164", "BK0+755.0", False, 9.0, "正向", create_bk_segments())
    return Project(name="泸州老旧改造配套项目(全线)", created_at=datetime.now().strftime("%Y-%m-%d"), tunnels=[t_zk, t_yk, t_ak, t_bk])

# --- 5. 可视化绘图 ---

def draw_enhanced_profile(segments: List[TunnelSegment], tunnel_name: str, direction: str):
    if not segments: return None
    min_m = min(min(s.start_mileage, s.end_mileage) for s in segments)
    max_m = max(max(s.start_mileage, s.end_mileage) for s in segments)
    total_len = max_m - min_m
    if total_len <= 0: return None
    
    colors = {'明挖': '#FF6B6B', 'CD法': '#4ECDC4', '台阶法': '#45B7D1', '洞口': '#96CEB4'}
    fig, ax = plt.subplots(figsize=(12, 4.5), dpi=100)
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
    ax.set_title(f"{tunnel_name} 施工工法纵断面图", fontsize=16, fontweight='bold', pad=20)
    plt.tight_layout()
    return fig

# --- 6. 终极精准计算器 (含规范条文赋码) ---

class InspectionCalculator:
    DIVISIONS = {
        '01': {'name': '01 加固处理', 'items': {'01': {'name': '01 危岩处治', 'formula': '每洞口1处', 'main': '-', 'gen': '-'}}},
        '02': {'name': '02 洞口工程', 'items': {
            '01': {'name': '01 边坡、基槽(洞口开挖)', 'formula': '每洞口1批', 'main': '6.2.1~6.2.2', 'gen': '6.2.3~6.2.4'}, 
            '02': {'name': '02 支护', 'formula': '每洞口3批(锚/网/喷)', 'main': '6.6.1~6.6.2', 'gen': '-'}, 
            '03': {'name': '03 导向墙(含洞门)', 'formula': '每洞口3批(模/筋/砼)', 'main': '6.4.1~6.4.4', 'gen': '6.4.5~6.4.6'}, 
            '04': {'name': '04 回填', 'formula': '每洞口1批', 'main': '6.5.1~6.5.2', 'gen': '6.5.3'}}},
        '03': {'name': '03 超前支护', 'items': {
            '01': {'name': '01 超前锚杆', 'formula': '每洞口1批', 'main': '8.8.1~8.8.3', 'gen': '8.8.4~8.8.5'}, 
            '02': {'name': '02 超前小导管', 'formula': '每洞口1批', 'main': '8.3.1~8.3.4', 'gen': '8.3.5'}, 
            '03': {'name': '03 超前注浆', 'formula': '每洞口1批', 'main': '8.5.1~8.5.3', 'gen': '8.5.4'}}},
        '04': {'name': '04 洞身开挖', 'items': {
            '01': {'name': '01 CD法', 'formula': '循环数×4步', 'main': '7.2.1~7.2.3', 'gen': '-'}, 
            '02': {'name': '02 台阶法', 'formula': '循环数×2步', 'main': '7.2.1~7.2.3', 'gen': '-'}}},
        '05': {'name': '05 初期支护', 'items': {
            '01': {'name': '01 锚杆', 'formula': '循环数×4', 'main': '8.8.1~8.8.3', 'gen': '8.8.4~8.8.5'}, 
            '02': {'name': '02 钢架', 'formula': '循环数×4', 'main': '8.9.1~8.9.3', 'gen': '8.9.4'}, 
            '03': {'name': '03 钢筋网', 'formula': '循环数×4', 'main': '8.7.1~8.7.2', 'gen': '8.7.3'}, 
            '04': {'name': '04 喷射混凝土', 'formula': '循环数×4', 'main': '8.6.1~8.6.3', 'gen': '8.6.4'}}},
        '06': {'name': '06 衬砌工程', 'items': {
            '01': {'name': '01 仰拱(底板)和填充', 'formula': '环数×3(模/筋/砼)', 'main': '9.2.1~9.2.6', 'gen': '9.2.7~9.2.8'}, 
            '02': {'name': '02 拱墙衬砌', 'formula': '环数×3(模/筋/砼)', 'main': '9.3.1~9.3.7', 'gen': '9.3.8~9.3.10'}}},
        '07': {'name': '07 防水排水', 'items': {
            '01': {'name': '01 防水板', 'formula': '环数', 'main': '10.3.1~10.3.5', 'gen': '10.3.6~10.3.7'}, 
            '02': {'name': '02 排水管(盲管)', 'formula': '环数', 'main': '10.7.1~10.7.4', 'gen': '10.7.5'}, 
            '03': {'name': '03 止水带(施工缝)', 'formula': '环数', 'main': '10.5.1~10.5.3', 'gen': '10.5.4'}}},
        '08': {'name': '08 附属工程', 'items': {
            '01': {'name': '01 排水沟', 'formula': '环数', 'main': '10.8.1~10.8.5', 'gen': '10.8.6~10.8.7'}, 
            '02': {'name': '02 电缆沟', 'formula': '环数', 'main': '12.4.1~12.4.3', 'gen': '12.4.4~12.4.5'}, 
            '03': {'name': '03 路面装饰', 'formula': '环数', 'main': '-', 'gen': '-'}, 
            '04': {'name': '04 检修道', 'formula': '环数', 'main': '-', 'gen': '-'}}},
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
            '具体部位': remark, '里程范围': mileage_str, '长度': round(length, 3),
            '主控项目条文': self.DIVISIONS[d]['items'][i]['main'],
            '一般项目条文': self.DIVISIONS[d]['items'][i]['gen'],
            '备注': remark
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
        page = st.radio("前往:", ["📋 参数配置", "📊 检验批计算", "📉 统计看板", "📖 标准查阅"])

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

        st.markdown("##### 1. 隧道工法纵断面图")
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
                
                if not target_tunnel.segments: st_val = 0.0; ed_val = 100.0
                else:
                    st_val = min(s.start_mileage for s in target_tunnel.segments)
                    ed_val = max(s.end_mileage for s in target_tunnel.segments)

                st.text_input("总体起点桩号 (自动更新)", format_mileage(st_val), disabled=True)
                st.text_input("总体终点桩号 (自动更新)", format_mileage(ed_val), disabled=True)
                st.number_input("设计全长(m) (自动更新)", value=float(abs(ed_val-st_val)), disabled=True)
                new_trolley = st.number_input("台车长度(m)", value=float(target_tunnel.trolley_length))
                
                if st.form_submit_button("保存基础信息"):
                    target_tunnel.id = new_id
                    target_tunnel.name = new_name
                    target_tunnel.direction = "正向" if "正向" in new_dir else "反向"
                    target_tunnel.trolley_length = new_trolley
                    st.success("已更新"); st.rerun()

        with col_seg:
            st.markdown("##### 3. 施工段落表")
            st.info("💡 **自上而下连缀推算**：只需在第 1 行输入【起始桩号】，并输入各段的【长度】。点击下方保存后，系统会自动串联计算出所有的起止桩号！")
            
            expected_columns = ["部位名称", "工法", "起始桩号", "长度(m)", "终止桩号", "衬砌类型", "榀数/环", "榀距(m)", "进尺(m)", "步骤数"]
            if not target_tunnel.segments: df_seg = pd.DataFrame(columns=expected_columns)
            else:
                seg_data = []
                for s in target_tunnel.segments:
                    seg_data.append({
                        "部位名称": s.name, "工法": s.method, "起始桩号": format_mileage(s.start_mileage), 
                        "长度(m)": float(s.length), "终止桩号": format_mileage(s.end_mileage), 
                        "衬砌类型": s.lining_type, "榀数/环": int(s.frames_per_ring), 
                        "榀距(m)": float(s.frame_spacing), "进尺(m)": float(s.advance_per_cycle), "步骤数": int(s.steps)
                    })
                df_seg = pd.DataFrame(seg_data)[expected_columns]

            edited_df = st.data_editor(
                df_seg, num_rows="dynamic", use_container_width=True, height=400,
                column_config={
                    "工法": st.column_config.SelectboxColumn(options=["明挖", "CD法", "台阶法", "洞口", "其他"]),
                    "起始桩号": st.column_config.TextColumn(help="只输入第一行的起始桩号即可"),
                    "终止桩号": st.column_config.TextColumn(disabled=True, help="系统自动推算"),
                    "进尺(m)": st.column_config.NumberColumn(disabled=True, help="系统自动推算: 榀数 × 榀距"),
                    "步骤数": st.column_config.NumberColumn(disabled=True, help="随工法自动锁定 (CD=4, 台阶=2)"),
                }
            )
            
            if st.button("💾 保存段落 & 触发连缀推算", type="primary"):
                new_segs = []
                dir_sign = 1 if target_tunnel.direction == "正向" else -1
                prev_end_m = None
                
                for idx, row in edited_df.iterrows():
                    try:
                        def get_val(val, default): return default if pd.isna(val) else val
                        
                        if prev_end_m is None: 
                            start_str = str(get_val(row.get('起始桩号'), ""))
                            start_m = parse_mileage(start_str) if start_str else target_tunnel.start_mileage
                        else: start_m = prev_end_m
                            
                        length = float(get_val(row.get('长度(m)'), 100.0))
                        if length <= 0.001: length = 100.0
                        
                        end_m = start_m + (length * dir_sign)
                        prev_end_m = end_m 
                        
                        method = str(get_val(row.get('工法'), "台阶法"))
                        frames = int(get_val(row.get('榀数/环'), 2))
                        spacing = float(get_val(row.get('榀距(m)'), 0.8))
                        
                        if frames > 0 and spacing > 0: advance = round(frames * spacing, 3)
                        else: advance = 1.6
                        
                        if 'CD' in method: steps = 4
                        elif '台阶' in method: steps = 2
                        elif '明挖' in method: steps = 1
                        else: steps = 2
                        
                        name = str(get_val(row.get('部位名称'), f"段落_{idx+1}"))
                        if not name or name == 'nan': name = f"段落_{idx+1}"
                        
                        new_segs.append(TunnelSegment(
                            name=name, method=method, length=length, 
                            start_mileage=start_m, end_mileage=end_m,
                            advance_per_cycle=advance, lining_type=str(get_val(row.get('衬砌类型'), "")), 
                            steps=steps, frames_per_ring=frames, frame_spacing=spacing, trolley_length=target_tunnel.trolley_length
                        ))
                    except Exception as e:
                        st.error(f"第 {idx+1} 行数据存在错误被跳过: {e}")

                new_segs.sort(key=lambda x: min(x.start_mileage, x.end_mileage))
                target_tunnel.segments = new_segs
                if new_segs:
                    target_tunnel.start_mileage = new_segs[0].start_mileage if dir_sign == 1 else new_segs[-1].end_mileage
                    target_tunnel.end_mileage = new_segs[-1].end_mileage if dir_sign == 1 else new_segs[0].start_mileage
                    target_tunnel.total_length = sum(s.length for s in new_segs)
                
                st.success("✅ 智能计算已完成！起止桩号已自动连缀，进尺/步骤已同步。")
                st.rerun()

    # ===== 页面：检验批计算 (自动静默计算) =====
    elif page == "📊 检验批计算":
        st.markdown(f"<h2>📊 检验批计算 - {current_project.name}</h2>", unsafe_allow_html=True)
        st.info("📌 **最新验收标准适用说明**：导向墙及衬砌均按【模板、钢筋、混凝土】精确拆分；**明细表已包含规范的主控与一般项目条文号！**")
        
        with st.spinner("🚀 正在自动执行全线智能扫描与精准计算，请稍候..."):
            calc = InspectionCalculator()
            total, df_sum, df_detail = calc.calculate(current_project)
            st.session_state.last_result = (total, df_sum, df_detail)
            
        total, df_sum, df_detail = st.session_state.last_result
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card bg-blue"><div class="metric-title">全线检验批总数</div><div class="metric-value">{total:,}</div></div>', unsafe_allow_html=True)
        with c2: 
            ratio = df_sum['05 初期支护'].sum()/total if total>0 and '05 初期支护' in df_sum else 0
            st.markdown(f'<div class="metric-card bg-green"><div class="metric-title">初期支护 (占比)</div><div class="metric-value">{ratio:.1%}</div></div>', unsafe_allow_html=True)
        with c3: 
            exc_val = df_sum["04 洞身开挖"].sum() if "04 洞身开挖" in df_sum else 0
            st.markdown(f'<div class="metric-card bg-purple"><div class="metric-title">洞身开挖</div><div class="metric-value">{exc_val:,}</div></div>', unsafe_allow_html=True)
        with c4: 
            lining_val = df_sum["06 衬砌工程"].sum() if "06 衬砌工程" in df_sum else 0
            st.markdown(f'<div class="metric-card bg-orange"><div class="metric-title">二衬工程</div><div class="metric-value">{lining_val:,}</div></div>', unsafe_allow_html=True)

        st.markdown("### 1. 分部工程汇总表")
        st.dataframe(df_sum, use_container_width=True)
        
        st.markdown("### 2. 分部分项汇总表")
        df_subitem = df_detail.groupby(['隧道', '分部工程', '分项工程'], as_index=False).size()
        df_subitem.rename(columns={'size': '检验批数量'}, inplace=True)
        df_subitem = df_subitem.sort_values(by=['隧道', '分部工程', '分项工程'], ascending=[True, True, True])
        st.dataframe(df_subitem, use_container_width=True)
        
        st.markdown("### 3. 数据导出区 (含规范条文赋码)")
        c_d1, c_d2, c_d3 = st.columns(3)
        with c_d1: st.download_button("📥 导出【分部汇总表】", df_sum.to_csv(index=False, float_format='%.3f').encode('utf-8-sig'), f"{current_project.name}_分部汇总.csv", "text/csv", use_container_width=True)
        with c_d2: st.download_button("📥 导出【分部分项汇总表】", df_subitem.to_csv(index=False).encode('utf-8-sig'), f"{current_project.name}_分部分项汇总.csv", "text/csv", use_container_width=True)
        with c_d3: st.download_button("📥 导出【详细明细表】", df_detail.to_csv(index=False, float_format='%.3f').encode('utf-8-sig'), f"{current_project.name}_明细.csv", "text/csv", use_container_width=True)

    # ===== 页面：统计看板 =====
    elif page == "📉 统计看板":
        st.markdown("<h2>📉 项目质量管控数据看板</h2>", unsafe_allow_html=True)
        
        with st.spinner("🚀 正在准备可视化数据，请稍候..."):
            calc = InspectionCalculator()
            total, df_sum, df_detail = calc.calculate(current_project)
            st.session_state.last_result = (total, df_sum, df_detail)
            
        _, df_sum, df_detail = st.session_state.last_result
        color_palette = ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1']
        
        st.markdown("#### 🔹 隧道整体指标分析")
        fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), dpi=120)
        fig1.patch.set_facecolor('#F9F9F9')
        
        bars = ax1.bar(df_sum['隧道'], df_sum['合计'], color='#3498db', width=0.5, edgecolor='none')
        ax1.set_title("各隧道检验批总量对比", pad=20, fontsize=14, fontweight='bold')
        for bar in bars:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (bar.get_height()*0.02),
                     f"{int(bar.get_height()):,}", ha='center', va='bottom', fontsize=11, fontweight='bold')
        ax1.spines['top'].set_visible(False); ax1.spines['right'].set_visible(False)
        ax1.grid(axis='y', linestyle='--', alpha=0.6)

        cols_to_sum = [c for c in df_sum.columns if c not in ['隧道', '合计']]
        total_series = df_sum[cols_to_sum].sum()
        wedges, texts, autotexts = ax2.pie(total_series, labels=total_series.index, autopct='%1.1f%%', 
                                           startangle=140, pctdistance=0.85, colors=color_palette, textprops={'fontsize': 11})
        ax2.add_artist(plt.Circle((0,0), 0.65, fc='#F9F9F9'))
        ax2.set_title("全项目分部工程占比", pad=20, fontsize=14, fontweight='bold')
        plt.tight_layout(); st.pyplot(fig1)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🔹 分部分项深度透视")
        fig2, (ax3, ax4) = plt.subplots(1, 2, figsize=(16, 7), dpi=120)
        fig2.patch.set_facecolor('#F9F9F9')

        tunnels = df_sum['隧道']
        bottom = np.zeros(len(tunnels))
        for i, col in enumerate(cols_to_sum):
            ax3.bar(tunnels, df_sum[col], bottom=bottom, label=col, color=color_palette[i % len(color_palette)], width=0.45)
            bottom += df_sum[col]
        ax3.set_title("各隧道分部工程详细构成", pad=20, fontsize=14, fontweight='bold')
        ax3.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize='small')
        ax3.spines['top'].set_visible(False); ax3.spines['right'].set_visible(False)
        ax3.grid(axis='y', linestyle='--', alpha=0.6)

        df_subitem = df_detail.groupby('分项工程')['检验批编号'].count().sort_values(ascending=True)
        df_subitem_top = df_subitem.tail(10)
        bars4 = ax4.barh(df_subitem_top.index, df_subitem_top.values, color='#2ecc71', height=0.6)
        ax4.set_title("分项工程验收频次排行 (TOP 10)", pad=20, fontsize=14, fontweight='bold')
        for bar in bars4:
            ax4.text(bar.get_width() + (max(df_subitem_top.values)*0.01), bar.get_y() + bar.get_height()/2,
                     f"{int(bar.get_width()):,}", ha='left', va='center', fontsize=10)
        ax4.spines['top'].set_visible(False); ax4.spines['right'].set_visible(False)
        ax4.grid(axis='x', linestyle='--', alpha=0.6)

        plt.tight_layout(); st.pyplot(fig2)

    # ===== 页面：标准查阅 =====
    elif page == "📖 标准查阅":
        st.markdown("<h2>📖 铁路隧道工程施工质量验收标准查阅</h2>", unsafe_allow_html=True)
        st.info("💡 系统已全面内置《TB 10417-2018》正文（第1至15章）、附录A~F 以及 条文说明。提供三种查阅方式：全文在线阅读、全局关键字检索、PDF原生电子书阅览。")
        
        tab1, tab2, tab3 = st.tabs(["📚 全文在线阅读", "🔍 全局智能检索", "📄 原版 PDF 阅览"])
        
        full_text_dict = get_tb10417_full_text()
        
        # --- Tab 1: 全文在线阅读 ---
        with tab1:
            col_sel, _ = st.columns([1, 2])
            with col_sel:
                selected_chapter = st.selectbox("📌 选择章节快速跳转:", list(full_text_dict.keys()))
            st.markdown(f"<div class='standard-text'>{full_text_dict[selected_chapter]}</div>", unsafe_allow_html=True)
            
        # --- Tab 2: 全局智能检索 ---
        with tab2:
            search_query = st.text_input("🔍 输入检索词 (如: 超挖, 喷射混凝土, 附录B, 回填注浆)", "")
            if search_query:
                found = False
                for chapter, content in full_text_dict.items():
                    if search_query in content:
                        found = True
                        st.markdown(f"#### 📍 【{chapter}】")
                        # 简单高亮处理
                        highlighted_content = content.replace(search_query, f"<span class='highlight'>{search_query}</span>")
                        # 只显示包含搜索词的段落
                        paragraphs = highlighted_content.split('\n')
                        for p in paragraphs:
                            if f"<span class='highlight'>{search_query}</span>" in p:
                                st.markdown(f"<div class='standard-text' style='margin-bottom: 10px; padding: 15px;'>{p}</div>", unsafe_allow_html=True)
                if not found:
                    st.warning(f"未在内置标准库中检索到包含“{search_query}”的条款。")
            else:
                st.caption("👈 在上方输入框输入关键词，即可在全本标准中进行秒级内容定位。")
                
        # --- Tab 3: 原版 PDF 阅览 ---
        with tab3:
            st.write("📖 **原版 PDF 在线阅览** (支持缩放、打印、目录跳转)")
            
            # --- 核心更新：静默读取内置的 PDF 文件 ---
            pdf_file_path = "TB10417-2018.pdf" 
            
            if os.path.exists(pdf_file_path):
                with open(pdf_file_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ 系统未能找到内置的 PDF 文件 `{pdf_file_path}`。")
                st.info("💡 提示：请将您的规范 PDF 重命名为 `TB10417-2018.pdf` 并上传到 GitHub 仓库（与 `streamlit_app.py` 放在同一层级目录）。在文件上传并重启服务器之前，您仍可在此处手动选择文件进行查看：")
                uploaded_pdf = st.file_uploader("📥 手动上传规范原版 PDF", type=['pdf'])
                if uploaded_pdf is not None:
                    base64_pdf = base64.b64encode(uploaded_pdf.read()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)

if __name__ == "__main__":
    main()