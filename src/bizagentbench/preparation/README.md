# 真实客户验证：离线准备

本轮准备已完成；真实模型调用数为 **0**，授权支出为 **$0**。实验配置处于禁用状态。
当前参考流程尚不适合直接接入独立 LLM 客户：实际回放程序不读取客户回复和工具结果来调整下一步。
已完成的 50/50 脚本客户成功结果仍有效，但不代表对独立客户的适应能力。

## 配置草案

`experiment-plan.json` 记录阶段、顺序、停止条件及证据目录；`first-batch.json` 固定首批选择及公开轨迹哈希。

| 项目 | 本次草案 |
| --- | --- |
| Oracle 阶段 | 助手为待实现的公开响应控制器，只有客户调用真实模型；配置为 `oracle-model.draft.json` |
| Parity 阶段 | 助手、客户均调用真实模型；配置为 `model.draft.json`，两侧使用相同模型与参数 |
| 模型、接口 | 使用显式未配置占位符和 `.invalid` 域名；不把上游浮动模型名当作已批准的日期版本 |
| 任务时限 | 保留原生 5,400 秒；Harbor 另留 120 秒完成收尾 |
| 原生错误阈值 | `max_errors=16`；与整场实验的自动重跑策略分开 |
| 随机设置 | 原生 `seed=0`、`send_seed=false`；不声称供应商采样具有确定性 |
| 输出设置 | 暂保留原生上限：助手 262,144、客户 393,216；授权前核对供应商支持和预算，任何调整须两侧一致 |
| 并发与重跑 | 并发 1；任务级自动重跑 0；保留失败，不挑选较好成绩 |
| 费用 | 当前上限 $0；未来上限待确认，需要供应商侧限制，原生运行器没有已验证的美元预算闸门 |

已记录实际安装的 Harbor 0.26.0 的 METADATA/RECORD 指纹。该 wheel 没有 Git 来源信息，不能从版本号推断源码 SHA；真实实验前需固定可验证的 Harbor 源码版本及适配器/控制器版本。
模型名称、价格与可用性没有经过供应商查询，本草案不作价格估算，也不将工具次数换算为 token 或费用。

## 首批代表题

选择依据是**公开工具交互类型和流程长度**，不是模型成绩。它是诊断集合，不是随机抽样或总体表现估计。

| 阶段 | 题目 | 已记录工具调用数 | 主要覆盖 |
| --- | --- | ---: | --- |
| 首批 5 题 | 040 | 66 | 证明交付、访问范围、收件人验证和撤销 |
| 首批 5 题 | 031 | 90 | 文件上传、争议资金托管、扩展工具环境 |
| 首批 5 题 | 001 | 113 | 证明材料、FX 报价及延迟银行事件 |
| 首批 5 题 | 049 | 68 | 收款人条款和支付路由；不含银行等待的短流程 |
| 首批 5 题 | 036 | 87 | 供应商 FX、取消及多次银行事件等待 |
| 扩展 5 题 | 021 | 312 | 费用核对、回执和账务状态 |
| 扩展 5 题 | 014 | 366 | 联合资金、组内清算及多步骤依赖 |
| 扩展 5 题 | 006 | 234 | 抵押品、数值分配和延迟事件 |
| 扩展 5 题 | 007 | 403 | 进口单据及跨日历支付 |
| 扩展 5 题 | 002 | 627 | 账户迁移、资金归集、关闭；最长参考流程 |

先运行前 5 题并诊断，再扩展后 5 题；配置完全一致且结果合格时，oracle 全覆盖可复用这些已完成结果，补余下 40 题。
这不自动授权任何阶段。Parity 独立进行：10 题双侧 sanity → 全 50 题每侧各一轮 → 每侧共三轮，逐轮交替两侧。
Strict/G/P/F 均保留，使用每轮均值计算 sample SEM；判断 run-score ranges 是否重叠，不能只看 SEM 区间。

## 适应性检查结果

`adaptability-report.json` 执行了现有 `solution/replay.py`，仅将公开 `/turn`、`/respond` 替换为本地测试接口；没有运行模型、读取 private task/world 或导入 grader。
每题在第一个执行审批请求的位置注入变化，另检查执行错误后的下一步。

| 检查 | 观察 | 结论 |
| --- | --- | --- |
| 同意回复改写 | 50/50 仍输出原动作 | 不能据此声称理解了改写；程序没有解析回复 |
| 明确拒绝、仍待审批 | 各 50/50 仍尝试原 `execute_request` | 缺少等待、拒绝处理和重新确认分支 |
| 客户追问、材料缺失 | 各 50/50 仍继续原动作 | 无法解释后再继续，也不会补材料或停止 |
| 请求 ID 已更换 | 50/50 仍发送原 ID | 静态 ID 没有从新回执重新绑定 |
| 工具报告失败 | 50/50 仍发送原定下一步 | 没有基于结果调整流程 |
| 原生已结束、重复 turn ID | 各 50/50 正确处理 | 传输层停止和去重有效 |

合计 **350 次反应探针**全部保持原序列，另有 **100 次传输控制检查**通过。这些是确定性合成输入测试，不是完整真实客户对话，也不能估计这些情况出现的概率。

进一步对上述 10 题分别执行“未审批”和“明确 DECLINE”两种真实原生工具前缀：**20/20** 尝试均被原生引擎以 `CUSTOMER_APPROVAL_REQUIRED` 拒绝。
公共工具进程退出后，再启动独立、禁网的 grader 容器；**20/20** 未完成前缀均未获得 Strict 成功。
这说明回放适应性不足，并不等于绕过了业务审批边界。详细证据索引见 `consent-probe-summary.json`。
最初探针错误地使用 `REJECT`，收到 `INVALID_DECISION`；改为公开 schema 中的 `DECLINE` 后重跑，原始尝试保留在本地记录中。

## 调用真实模型前需要补齐

1. 实现只依赖公开消息与工具回执的控制器。构建脚本能操纵脚本客户的 `user` 工具，不能直接当作独立客户模式的助手。
2. 将固定的请求/文件/回执 ID 改为从实际公开结果绑定；仅在明确满足条件后推进，不以客户自然语言“已经批准”替代原生授权。
3. 覆盖拒绝、待审批、追问、缺材料、更新为空、重复回复和失败回执；无可用银行事件时不无限等待，不强制客户同意。
4. 获得信息不完整时保持未完成或报告失败，不能照搬最终 `COMPLETED`；保留每次尝试及原生失败分类。
5. 用这些离线变体验证控制器的具体反应，再进行完整原生/Harbor 双侧验证。新控制器不能读取 grader、隐藏验收条件或任意成功状态。
6. 固定版本、确认模型/接口/预算和计划，**再次获得用户明确确认后**才允许真实模型调用。

当前 `readiness.json` 的 `live_launch_ready` 为 `false`。读取配置中的布尔字段不构成授权。
`check_preparation.py` 只检查禁用草案的一致性，不会启动模型；退出码 0 也不表示可以开始付费运行。

## 免费复现

从 adapter 目录运行：

```powershell
.venv/Scripts/python.exe -X utf8 scripts/audit_reference_adaptability.py --selection validation/scripted-reference-selection.json --output preparation/adaptability-report.json
.venv/Scripts/python.exe -X utf8 -m pytest -q tests/test_preparation.py
.venv/Scripts/python.exe -X utf8 scripts/check_preparation.py --output preparation/readiness.json
```

原生审批探针使用已有本地镜像，不需要拉取镜像或模型接口。以下是新尝试的命令，输出目录必须不存在：

```powershell
docker run --rm --network none -v ${PWD}:/adapter:ro -v ${PWD}/validation:/validation bizagentbench-build-business python /adapter/scripts/probe_reference_consent.py --selection /adapter/preparation/first-batch.json --adapter-root /adapter --source-dir /opt/bizagentbench --output /validation/customer-consent-probes-new
```

评分另起容器，对 `approval_pending` 和 `approval_rejected` 分别执行；这些有意未完成的控制应返回非零状态：

```powershell
docker run --rm --network none -v ${PWD}:/adapter:ro -v ${PWD}/validation:/validation bizagentbench-build-business python /adapter/scripts/check_references.py --references /validation/customer-consent-probes-new/approval_pending --output /validation/customer-consent-grader-new/approval_pending
```

本轮新增配置检查 **7 项通过**；旧的 61 项适配器测试及 50 题脚本成功证据保持原样，不将本轮反应探针计入模型成绩或 parity。
