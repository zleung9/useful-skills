# 耿同学 Skill

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![English README](https://img.shields.io/badge/README-ZH%20%7C%20EN-orange)](README_EN.md)

这是一个面向包括 Nature 在内的学术论文投稿、修回、发表后质疑和课题组内部复核场景的学术诚信自查 skill。这是一个可执行工作流，用于筛查论文是否存在数据造假、图片操纵、统计异常、方法缺口、引用与作者声明问题，并输出自查报告和纠正计划。

本 skill 的定位是“自查自纠”和“证据化风险分级”，不是替代期刊、机构或伦理委员会作出学术不端认定。


## 文件结构

```text
.
├── SKILL.md
├── README.md
├── README_EN.md
└── scripts/
    ├── blot_gel_lane_audit.py
    ├── citation_integrity_check.py
    ├── figure_manifest_builder.py
    ├── flow_plot_duplicate_screen.py
    ├── geng_numeric_screen.py
    ├── graph_source_consistency.py
    ├── image_similarity_screen.py
    ├── integrity_common.py
    ├── microscopy_reuse_screen.py
    ├── package_audit.py
    ├── report_assembler.py
    └── stats_consistency_check.py
```

## 适用场景

- 投稿包括 Nature/Nature Portfolio 在内的期刊前做内部学术诚信自查。
- 收到编辑、审稿人、PubPeer 或读者质疑后做证据化复核。
- 检查论文是否可能存在数据造假、图片复用、Western blot 拼接、统计异常、p-hacking、重复发表或引用问题。
- 课题组 PI、通讯作者、共同作者在提交修正、撤稿说明或机构调查材料前整理事实。
- 对图表提取出的 CSV/XLSX 数值做初步统计筛查。

## 审查规则

### 1. 科研配图与图片完整性

本 skill 不只做数值检查。配图审查是核心流程，重点检查：

- **图片重复使用**：同一图片或局部区域是否被用于不同样本、不同处理组、不同时间点、不同放大倍数、不同染色/通道、不同论文或补充图中。
- **变换后复用**：旋转、翻转、缩放、拉伸、裁剪、调对比度、改伪彩、局部遮盖后是否仍能看出相同细胞、组织结构、背景纹理、灰尘、气泡、划痕或噪声模式。
- **Western blot / gel 问题**：内参条带重复使用；不同实验共享同一 beta-actin/GAPDH/tubulin；泳道形状高度相同；非相邻泳道拼接未说明；泳道间有垂直分界线；背景灰度突变；曝光不一致；分子量标记缺失；裁切图无法追溯到未裁剪原图。
- **显微镜图问题**：不同组别出现同一视野、同一细胞群、同一组织结构；局部克隆细胞或组织区域；通道叠加不一致；选择性阈值、去噪、gamma、伪彩、反卷积或代表性视野选择未说明。
- **流式图问题**：散点云重复、门控线复制、象限比例与图中点云不符、补偿/门控层级缺失、同一 isotype/FMO/control 被用于不相关实验。
- **迁移、侵袭、划痕、克隆形成、动物与组织学图**：重复克隆、重复划痕边缘、重复组织纹理、重复动物图片、比例尺不一致、视野与图例不匹配。
- **图表操纵**：柱状图/折线图与源数据不一致；Y 轴不从 0 开始且夸大效应；刻度间距不等；单位缺失；误差棒定义缺失；误差棒小到不符合实验噪声；不同图中数据点或误差棒形状重复。
- **组合图披露**：所有裁切、拼接、非相邻泳道并列、亮度/对比度整体调整、代表性图片选择、伪彩和阈值处理，都应在图例或方法中说明。

审查时先建立 figure map：记录每个 panel 的样本、条件、时间点、通道、放大倍数、图例声称和源文件名；再做图内、跨图、补充材料和既往版本之间的重复比对。PDF 只能做初筛；发现疑点时必须要求未裁剪原图和原始数据。

### 2. 数据与统计异常

- 均值、SD/SEM、n、置信区间、p 值和统计检验是否数学自洽。
- 是否存在“过于完美”的剂量反应、时间趋势、组间差值恒定、所有标准差相同或过小、所有比较刚好显著。
- 是否有大量 p 值集中在 0.01-0.05 且缺少阴性结果，或多重比较未校正。
- 基线表是否异常平衡，随机分组是否“好得不真实”。
- 图中数值是否能被 source data、补充表或原始记录复现。

### 3. 方法学与可重复性

- 是否说明随机化、盲法、纳排标准、样本量/功效分析、生物重复与技术重复。
- 统计方法是否匹配数据类型，是否处理多重比较、缺失值、离群值和模型假设。
- 抗体、试剂、细胞系、动物品系、软件、代码、参数和版本是否可追溯。
- 人体、动物、临床试验或生物安全研究是否有伦理审批、注册和知情同意说明。

### 4. 引用、结构与作者声明

- 每个核心结论是否有对应数据支撑，引用是否真正支持被引用的观点。
- 是否引用撤稿论文、关注表达论文或与主题无关的填充文献。
- 是否存在过度自引、重复发表、切片发表、未披露预印本/会议论文/前序论文重叠。
- 作者贡献、利益冲突、基金角色、数据可用性、代码可用性和材料可得性是否完整。

## 使用方式

### 获取仓库

```bash
git clone https://github.com/1anj/academic-integrity-skill.git
cd academic-integrity-skill
```

### Codex

在 Codex 中将本目录作为 skill 安装或加载，或直接在 Codex 工作区打开本仓库，然后提出：

```text
请用耿同学学术诚信自查 skill 审查这篇论文，判断是否存在学术造假风险，并给出自查自纠方案。
```

### Claude Code

在 Claude Code 中打开本仓库，或把本仓库与待审查论文材料放在同一工作区：

```bash
cd academic-integrity-skill
claude
```

建议提示词：

```text
请先读取 SKILL.md，并严格按照“耿同学学术诚信自查”工作流审查我提供的论文材料。
请重点检查图片重复使用、Western blot/gel 拼接、显微镜图复用、流式图重复、数值统计异常、方法学缺口、引用与作者声明问题。
最后输出证据台账、风险分级和自查自纠计划。
```

### Antigravity

在 Antigravity 中打开 `academic-integrity-skill` 仓库作为项目目录，将 `SKILL.md`、`README.md`、`scripts/` 和待审查论文材料加入 agent 上下文，然后使用：

```text
Follow SKILL.md. Run the Geng Tongxue academic-integrity self-audit on the attached manuscript and source materials. Include figure-integrity checks, numeric/statistical screening, method/citation review, risk rating, and a self-correction plan.
```

### Cursor / Windsurf / Continue / VS Code AI

将本仓库作为工作区打开，固定或引用 `SKILL.md`，并把论文 PDF、补充材料、原始图像、数值表格放入同一项目目录。可使用同一条提示词：

```text
基于 SKILL.md 执行耿同学学术诚信自查。请不要只做摘要，要逐项检查科研配图、数据统计、方法学、引用、作者声明和期刊政策风险，并输出可执行的纠正清单。
```

### ChatGPT / Claude / Gemini 等网页 AI

上传 `SKILL.md`、论文 PDF、补充材料、原始图片或 source data，并明确要求模型“遵循 SKILL.md”。如果包含 CSV/XLSX 数值表，建议先在本地运行数值筛查脚本，再把输出报告一并上传。

建议同时提供：

- 论文 PDF 或 manuscript draft。
- Supplementary information、figure legends、Methods、Reporting Summary。
- 原始图像、未裁剪 Western blot/gel/microscopy/flow cytometry 文件。
- 从图表提取的数值表格 CSV/XLSX。
- 数据与代码仓库链接、伦理审批、临床注册号、作者贡献和利益冲突声明。
- 期刊/读者/PubPeer 的质疑原文。

## 功能介绍

`scripts/` 已提供一组低依赖、可复现、可合并报告的筛查脚本。除公共模块 `integrity_common.py` 外，各功能脚本都支持 `--format markdown|json` 和 `--output`，JSON 输出统一包含 `tool`、`input`、`findings`、`risk_level`、`evidence_files`、`limitations` 等字段。所有脚本只输出筛查信号，不直接给出学术不端定性。

### 已实现模块

| 文件 | 功能 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `package_audit.py` | 检查投稿包完整性，识别 manuscript、SI、source data、原图、伦理、代码、可用性声明等缺失项。 | 项目目录 | 缺失材料清单 |
| `figure_manifest_builder.py` | 为最终图、补充图、原始图建立 manifest，记录文件名、尺寸、哈希和类别。 | figure/source image 目录 | `figure_manifest.csv/json` |
| `image_similarity_screen.py` | 检测图片重复、旋转/翻转/裁剪后复用、跨图复用候选。 | 图片目录 | 候选重复图片对、相似度 |
| `blot_gel_lane_audit.py` | 初筛 Western blot/gel 的泳道拼接、背景突变、重复条带和重复内参。 | blot/gel 图片 | 可疑泳道、边界、重复条带候选 |
| `microscopy_reuse_screen.py` | 对显微镜图做 tile 特征匹配，筛查同视野、局部克隆、旋转/翻转复用。 | microscopy 图片目录 | 可疑区域坐标和相似度 |
| `flow_plot_duplicate_screen.py` | 筛查流式散点图重复、门控复制、象限比例与图像不一致候选。 | flow plot 图片 | 可疑 plot 对和门控问题 |
| `geng_numeric_screen.py` | 数值筛查：尾数分布、小数重复、精确重复值。 | CSV/TSV/XLSX/stdin | Markdown/JSON 风险报告 |
| `stats_consistency_check.py` | 根据原始数据重新计算均值、SD/SEM、极值和零方差风险。 | raw data | 统计自洽性报告 |
| `graph_source_consistency.py` | 比对 source data 与图中均值、SD/SEM、n 是否一致。 | source data 和 reported summary | 不一致清单 |
| `citation_integrity_check.py` | 离线检查 DOI、重复引用、撤稿/关注表达等风险关键词。 | 参考文献列表/DOI 文本 | 引用风险表 |
| `report_assembler.py` | 汇总各脚本 JSON，生成统一自查报告和证据台账。 | 多个 `*-screen.json` | `geng-integrity-report.md` |

### 流程

```bash
python3 scripts/package_audit.py manuscript_package --format json --output package_audit.json
python3 scripts/figure_manifest_builder.py manuscript_package/figures manuscript_package/source_images --csv-output figure_manifest.csv --format json --output figure_manifest.json
python3 scripts/image_similarity_screen.py manuscript_package/figures manuscript_package/source_images --format json --output image_similarity.json
python3 scripts/geng_numeric_screen.py manuscript_package/source_data.csv --format json --output numeric_screen.json
python3 scripts/report_assembler.py package_audit.json figure_manifest.json image_similarity.json numeric_screen.json --output geng-integrity-report.md
```

### 依赖建议

- 基础脚本优先使用 Python 标准库，保持离线可运行。
- 表格增强可选 `pandas`、`openpyxl`、`scipy`。
- 图片筛查可选 `Pillow`、`imagehash`、`opencv-python`、`scikit-image`、`matplotlib`。
- PDF/图像提取可选 `pymupdf` 或 `pdfplumber`。
- 引用检查如需联网，应提供 `--offline` 模式，避免网络不可用时阻塞核心审查。

### Review 结论

当前脚本集已覆盖基础材料清点、图像 manifest、图片复用候选、blot/gel、显微镜、流式、数值统计、source data 对照、引用离线检查和报告汇总。脚本结果仍是筛查证据，最终判断必须结合原始图片、原始数据、实验记录和作者解释。

## 风险分级

| 等级 | 含义 | 建议 |
| --- | --- | --- |
| Green 低 | 未发现实质性学术诚信信号。 | 常规完善报告与材料。 |
| Yellow 中 | 单点或模糊问题，可能是标注/报告不足。 | 索取原始数据/图片，修订图例、方法和声明。 |
| Orange 高 | 多处疑点或核心结果有实质风险。 | 暂停投稿或修回，启动课题组内部复核。 |
| Red 严重 | 多条独立证据指向图片/数据操纵或核心结论不可靠。 | 保存记录，咨询机构研究诚信部门并评估是否通知期刊。 |
| Black 调查阈值 | 系统性问题、无法解释的重复/不可能数据或核心证据失真。 | 进入正式调查、修正或撤稿路径。 |

## 输出内容

skill 会生成一份结构化 Markdown 报告，包含：

- 审查对象、材料清单和缺失材料。
- 总体风险评级与核心结论可靠性判断。
- 证据台账：位置、观察、适用规则、严重度、替代解释和需要验证的材料。
- 期刊政策门槛、Nature 投稿要求和五大技术域逐项审查。
- 数值筛查结果和解释限制。
- 自查自纠行动表：负责人、截止时间、需收集证据和是否需要联系期刊/机构。
- 可直接改写使用的作者询问信、期刊说明或内部记录保存措辞。

## 证据判定原则

- 单一相似图片或单个异常数值通常只构成“需要解释”，不直接等于造假。
- 多个独立证据指向同一核心结论时，应升级风险等级。
- 能用原始图片、原始数据、实验记录和合理实验设计解释的问题，应优先按纠错处理。
- 原始数据缺失、图像无法追溯、核心结果无法复现或作者解释互相矛盾时，应暂停投稿/修回并进入内部研究诚信复核。

## 期刊与 Nature 政策锚点

自查时优先对照 Nature Portfolio 的当前政策页面：

- [Nature Portfolio editorial policies](https://www.nature.com/nature-portfolio/editorial-policies)
- [Image integrity and standards](https://www.nature.com/nature-portfolio/editorial-policies/image-integrity)
- [Reporting standards and availability of data, materials, code and protocols](https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards)
- [Authorship](https://www.nature.com/nature-portfolio/editorial-policies/authorship)

政策可能更新；正式投稿或回应期刊前应再次核对目标期刊页面。

## 重要限制

- AI 不能替代专业图像取证、原始数据审计、机构调查或法律意见。
- PDF 视觉检查无法完成像素级 ELA、元数据取证和完整跨论文图像搜索。
- 单个异常通常只能说明“需要解释”，不能直接认定造假。
- 所有严重结论都应以原始数据、原始图片、实验记录、代码和作者解释为依据。

## 工作原则

做学问先做人。自查报告可以尖锐，但必须精确、克制、可复核：只审证据，不审动机；只说风险，不造舆论；只给纠正路径，不制造无依据指控。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=1anj/academic-integrity-skill&type=Date)](https://www.star-history.com/#1anj/academic-integrity-skill&Date)
