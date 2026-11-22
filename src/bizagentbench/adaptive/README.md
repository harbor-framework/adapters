# 首批五题：根据公开回复推进的参考控制器

本目录记录新的控制器版本；`preparation/` 保留此前对旧线性回放的审计快照。
支持范围是 **001、031、036、040、049**。它是业务专用参考控制器，不是通用对话模型，也没有覆盖余下 45 题。
真实模型调用仍为 **0**；本轮不会请求、读取或配置真实供应商凭据。

## 行为变化

业务计划每一步取得实际公开工具结果后再继续，不再从成功轨迹中取出固定的下一条消息。

- 新请求、报价、上传回执及业务对象的 ID 来自本次响应。更换 ID 后的后续操作绑定实际返回值。
- 客户追问或暂未审批时，保留当前提案，提供具体操作参数并请求可核实的回执；不会直接执行下一项。
- 客户明确拒绝、撤销、返回错误请求 ID、材料不可用或工具失败时，停止后续流程，且不提交 `COMPLETED`。
- 不将自然语言“同意”直接当作已完成的原生审批。即使客户伪造 `APPROVED` 回执，原生引擎仍会拒绝未实际获批的执行，控制器随即停止。
- 银行更新前后通过助手可用的 `get_clock` 核对进展；连续两次无进展则停止，避免无限等待。
- 第 001 题的客户金额、保留余额与费用上限由客户实际回复提供；不再将构建阶段写好的客户答案放进助手程序。
- 第 036 题按真实公开字段中的退款到账金额和费用核对退款，不再等待不存在的布尔标记。
- 第 040 题确认收件人验证完成、实际指定收件人已读后，再推进证明与撤销流程。

## 隔离边界

`adaptive.py` 和 `adaptive_plans.py` 不导入原生私有合同或 grader，不读取 world 文件。
助手只发送助手工具调用，或请求客户操作的普通消息。客户的文件、审批和等待工具由独立的客户侧执行。
脚本客户的已知答案仅存在于测试 fixture，未复制进 Harbor 助手的 `/solution`。

所有状态变化均经原生工具发生。控制器停止后，另起禁网容器检查变化测试的业务状态。
完整 Harbor 运行沿用“停止 main → 从 business 收集 → 新容器重新评分”的边界，没有调整上游评分规则。

## 免费验证

最终汇总见 `validation.json`，原始尝试保留在 adapter 的 `validation/` 下。

| 层级 | 范围 | 结果与含义 |
| --- | --- | --- |
| 原生工具变化测试 | 47 个控制 | 25 个正常/可恢复流程完成；22 个预期停止流程未记录完成；独立 grader 检查对应成功或失败分支 |
| 可恢复变化 | 正常、JSON 外带改写、一次待审批、一次追问、额外提案导致 ID 位移；各 5 题 | 这些变化下仍应达到完整 G/P/F/Strict 成功 |
| 预期停止 | 拒绝 5、伪造批准 5、错误请求 ID 5、缺材料 2、无更新 4、需求变化 1 | 应停止且无 `COMPLETED`；不是把失败当成功，也不是要求拒绝场景拿满分 |
| 完整原生/Harbor | 首批 5 题，各一组脚本客户运行 | 比较完整 verdict、reward、termination、classification 和工具调用数；结果以汇总文件为准 |
| 回归测试 | Linux 全套 | 79 项通过，包含原有隔离测试、准备配置检查和新增控制器检查 |

两处开发问题保留了原始证据：第 036 题旧字段判断导致停止；第一次 Harbor 运行的测试服务在浅目录中导入失败。
两者分别通过公开回执修正和容器内导入检查解决。它们是离线开发尝试，不作为真实模型样本。

## 使用限制与下一阶段

控制器要求客户提供可解析的实际 JSON 回执；允许前后说明或 Markdown 包裹，但不理解任意自然语言。
最多请求三次澄清/回执；明确拒绝立即停止。每个提案最多检查三次 `PENDING` 状态。
这些限制属于参考控制器策略，未改动 benchmark 的原生时限或错误预算。不能将这种有限规则处理宣称为完整对话智能。
未知业务条件、无法核实的需求或持续缺少信息会停止，当前不会自动探索任意替代方案。

新的控制器是可选参考入口，旧 50 题脚本结果及默认生成器没有被替换。后续 parity 仍使用原生 HTTPAgent 与对应 Harbor relay，不会将此参考控制器的成绩混入模型 parity。
真实客户阶段需要单独配置独立用户模型、纯本地助手控制器入口、准确版本和预算，并再次获得用户确认；当前 `prepare_adaptive.py` 和 `native_adaptive.py` 仅用于本地脚本 fixture。

## 复现入口

全部命令在 adapter 目录执行。使用新的输出目录，保留原始尝试。

```powershell
# 公共工具控制测试：不调用模型、不调用 grader。
docker run --rm --network none -v ${PWD}:/adapter:ro -v ${PWD}/validation:/validation bizagentbench-build-business python /adapter/scripts/check_adaptive_controls.py --source-dir /opt/bizagentbench --output /validation/adaptive-controls-new

# 控制器进程退出后，在另一个容器评分。
docker run --rm --network none -v ${PWD}:/adapter:ro -v ${PWD}/validation:/validation bizagentbench-build-business python /adapter/scripts/grade_adaptive_controls.py --controls /validation/adaptive-controls-new --output /validation/adaptive-grader-new

# 完整原生运行仍只用本地 fixture。
docker run --rm --network none -v ${PWD}:/adapter:ro -v ${PWD}/validation:/validation bizagentbench-build-business python /adapter/scripts/native_adaptive.py --output /validation/adaptive-native-new --task-ids case_040 case_031 case_001 case_049 case_036

# 另建 Harbor 脚本客户数据集，不覆盖原始 50 题数据集。
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -X utf8 scripts/prepare_adaptive.py --source-dir ../../../research/bizagentbench-upstream --output ../../../datasets/bizagentbench-adaptive-new
harbor run -p ../../../datasets/bizagentbench-adaptive-new -a oracle --jobs-dir validation/harbor --job-name adaptive-new -n 1 --n-concurrent 1
```
