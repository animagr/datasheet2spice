# datasheet2spice 开源工具包规划

## 目标定位

`datasheet2spice` 不是一开始就追求“上传 PDF 后 AI 一键生成完美模型”的黑箱工具，而是一个半自动、可追溯、可扩展的工程工具包：

1. 从器件 datasheet 提取表格参数和曲线数据。
2. 生成结构化参数数据库。
3. 输出快速 VDMOS 紧凑模型和简单 ABM 行为模型。
4. 自动跑基础验证网表，给出误差和收敛报告。
5. 后续逐步支持电热模型、Verilog-A、实验波形拟合和更复杂器件。

核心原则：

- schema first：先定义统一参数结构，再做提取/拟合/导出。
- provenance first：每个参数都记录来源页码、图号、提取方式和置信度。
- plugin first：PDF 解析、曲线提取、模型拟合、SPICE 导出都用插件式接口。
- validation first：模型生成后必须能跑验证 deck，并生成误差报告。
- human-in-the-loop：早期不要幻想全自动，允许人工校正坐标轴、曲线和参数。

## 软件分层

```text
datasheet2spice/
  ingest/          # PDF、图片、CSV、厂商模型导入
  extract/         # 表格参数、曲线、矢量路径、OCR
  schema/          # 器件参数数据模型
  fit/             # 参数拟合、曲线平滑、物理约束
  emit/            # VDMOS、ABM、LTspice、ngspice、Verilog-A
  validate/        # DC/CV/Qg/双脉冲验证
  report/          # Markdown/HTML/JSON 报告
  cli/             # 命令行入口
  gui/             # 后续可选 Web UI
```

## 数据模型

每个器件一个 YAML/JSON 项目文件：

```yaml
device:
  vendor: ROHM
  part_number: S4661
  type: n_sic_mosfet
  datasheet: TK-S4661_Rev.T17.2.pdf

ratings:
  vdss_v:
    value: 1200
    source: {page: 1, table: "Absolute maximum ratings"}

static:
  vgs_th:
    points:
      - {temp_c: 25, typ_v: 3.8}
  rds_on:
    points:
      - {temp_c: 25, id_a: 68, vgs_v: 18, typ_ohm: 0.011}

curves:
  capacitance:
    x: vds_v
    y: [ciss_pf, coss_pf, crss_pf]
    source: {page: 11, figure: 19, method: pdf_vector}

models:
  vdmos:
    status: generated
  abm_dynamic:
    status: generated
```

参数来源建议分级：

- `datasheet_table`: datasheet 表格直接给出。
- `pdf_vector`: 从 PDF 矢量曲线提取。
- `manual_digitized`: WebPlotDigitizer/StarryDigitizer 手工取点。
- `fit`: 从曲线拟合得到。
- `lab_fitted`: 由实验波形反推。
- `assumed`: 工程假设，必须显式标红。

## 模型等级设计

不要直接叫 `L1/L2/L3`，容易和 SPICE `LEVEL=`、ROHM 等级混淆。建议用清晰的二元标签：

```text
model_class:
  vdmos
  abm
  verilog_a

fidelity:
  static
  dynamic
  electrothermal
  lab_fitted
```

第一阶段支持：

- `vdmos/static-fast`
  - 目标：快速、稳定、能扫电路。
  - 参数：`Vto/Kp/Rd/Rs/Rg/Cgs/Cgdmin/Cgdmax/Cjo/Is/Rs/BV/Tt`。

- `abm/dynamic-basic`
  - 目标：贴合 `Ciss/Coss/Crss`、`Qg`、`RDS(on)`、体二极管，能跑双脉冲。
  - 参数：`RDS(on)(T)`、`Vth(T)`、`Idsat(Vgs,T)`、`C(V)`、二极管和寄生。

后续支持：

- `abm/electrothermal`
  - 加热网络、功耗积分、温度反馈。

- `verilog_a/dynamic`
  - 用 OpenVAF/ngspice 编译，减少大量 ABM 源的开销。

- `lab_fitted`
  - 用实测双脉冲波形自动拟合寄生和电容倍率。

## MVP 功能

MVP 只支持 N-channel power MOSFET / SiC MOSFET。

### 输入

- PDF datasheet。
- 手动补充 YAML。
- 曲线 CSV：允许导入 WebPlotDigitizer/StarryDigitizer 格式。

### 提取

- PDF 文本表格初步抽取：`VDS/VGS/ID/RDS(on)/Vth/Qg/Ciss/Coss/Crss/Qrr/trr`。
- PDF 矢量曲线提取：优先支持干净 datasheet。
- 手动曲线坐标轴校正：自动提不出来时使用。

### 拟合

- `RDS(on)(T)` 线性/二次插值。
- `Vth(T)` 插值。
- `Ciss/Coss/Crss(VDS)` 平滑插值。
- VDMOS 初值拟合。
- ABM 初值拟合。

### 输出

- `part.params.yml`
- `part_vdmos_ltspice.lib`
- `part_vdmos_ngspice.lib`
- `part_abm_common.lib`
- `part_abm_ltspice.lib`
- `part_abm_ngspice.lib`
- `double_pulse_*.cir`
- `report.md`

### 验证

- DC transfer check：`ID-VGS`。
- capacitance check：重构 `Ciss/Coss/Crss`。
- gate charge check：重构 `Qg` 曲线。
- LTspice/ngspice 双脉冲 smoke test。
- 报告运行时间、点数、是否有收敛警告。

## CLI 设计

```powershell
datasheet2spice init S4661 TK-S4661_Rev.T17.2.pdf
datasheet2spice extract S4661.yml --auto
datasheet2spice extract-curve S4661.yml --page 11 --figure 19 --kind capacitance
datasheet2spice fit S4661.yml --model vdmos
datasheet2spice fit S4661.yml --model abm-basic
datasheet2spice emit S4661.yml --dialect ltspice --model abm-basic
datasheet2spice validate S4661.yml --sim ltspice --deck double-pulse
datasheet2spice report S4661.yml
```

## Python API 设计

```python
from datasheet2spice import Project

p = Project.from_pdf("TK-S4661_Rev.T17.2.pdf", part_number="S4661")
p.extract_tables()
p.extract_curve(page=11, figure=19, kind="capacitance")
p.fit("vdmos")
p.fit("abm-basic")
p.emit(model="abm-basic", dialect="ltspice")
p.validate(sim="ltspice", deck="double-pulse")
p.write_report()
```

## 拟合策略

VDMOS 初版：

- `Vto`: datasheet `VGS(th)`。
- `Kp`: 由 `ID-VGS` 曲线拟合；没有曲线时由 `gfs` 或 Miller 平台估算。
- `Rd/Rs`: 用 `RDS(on)` 分摊。
- `Rg`: datasheet 内部栅电阻。
- `Cgs`: `Ciss - Crss`。
- `Cgdmin`: 高压端 `Crss`。
- `Cgdmax`: 低压端 `Crss` 或由 `Qgd` 反推。
- `Cjo`: `Coss - Crss`。
- `BV/Ibv`: `VDSS/IDSS`。
- `Tt`: `Qrr/IF` 或 `trr` 初值。

ABM 初版：

- 连续 `Idsat(Vgs)` + `RDS(on)` 沟道。
- `Cgs/Cgd/Cds` 电压依赖。
- 体二极管 + 简单反向恢复初值。
- `Ld/Ls/Lg/Rg` 寄生参数作为拟合旋钮。

后续提高精度：

- 从查表 `C(V)` 改成平滑解析函数或 `Q(V)` 电荷模型。
- 数字化 `ID-VGS`、`ID-VDS`、第三象限曲线。
- 加电热 RC 网络。
- 加实验波形自动拟合。

## 版本路线

### v0.1: S4661 单器件原型

- 整理现有脚本为包结构。
- 固定支持 S4661。
- 输出 ABM LTspice/ngspice/common。
- 生成报告。

### v0.2: 通用 MOSFET schema

- 支持任意 N-channel MOSFET 项目文件。
- 支持 CSV 曲线导入。
- 支持 VDMOS 初版导出。

### v0.3: PDF 半自动提取

- 自动识别常见参数表。
- PDF 矢量曲线提取接口通用化。
- 图像曲线手动坐标轴校正。

### v0.4: 验证闭环

- LTspice/ngspice 自动跑验证 deck。
- 生成误差表和收敛报告。
- 支持参数 sweep。

### v0.5: 模型质量提升

- `ID-VGS/ID-VDS` 拟合。
- 平滑电容或电荷模型。
- 热网络。

### v1.0: 可发布工具

- 文档、示例库、测试集。
- 支持常见 MOSFET/SiC datasheet 格式。
- 允许第三方插件扩展器件类型和仿真器。

## 测试策略

单元测试：

- 单位解析：`mΩ`, `nC`, `pF`, `µJ`。
- 曲线坐标映射。
- VDMOS 参数映射。
- SPICE emitter 语法。

集成测试：

- S4661 fixture。
- 一个硅 MOSFET fixture。
- 一个 GaN HEMT fixture，后续扩展。

仿真测试：

- 有 LTspice/ngspice 时跑 smoke test。
- CI 中优先用 ngspice，因为开源可安装。
- LTspice 测试作为本地/Windows 可选项。

## 开源工程建议

许可证：

- Python 工具包可以用 MIT 或 Apache-2.0。
- 若嵌入/改造 AGPL 工具代码要谨慎；建议只支持导入 WebPlotDigitizer 导出的 CSV，不直接复制其代码。

仓库结构：

```text
datasheet2spice/
  src/datasheet2spice/
  tests/
  examples/
    rohm_s4661/
  docs/
  pyproject.toml
  README.md
```

README 第一屏要明确：

- 这是半自动工程工具。
- 输出模型是起点，不是厂商签核模型。
- 所有拟合参数都可追溯。
- 使用者必须用实验或官方模型验证关键设计。
