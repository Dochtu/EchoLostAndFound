# M4-C 验收矩阵更新 · 2026-11-24

本表补充 [DSH 逐项矩阵](M4C_CompletionMatrix.md)。历史通过只说明旧版本有对应运行证据。

| 项目 | 本轮判定 | 依据 |
| --- | --- | --- |
| C1 会话、Mock、接口 | 保留原实现 | [原始服务端测试](M4C/Logs/pytest-m4c-verbose.txt)，本轮结果见[测试报告](M4C_TestResults_Updated.md) |
| C2 证据与 NPC 场景入口 | PASS | 最终 PlayMode 8/8，Station 真实装载，五证与林遥核对经 UI 测试 |
| R01 与暂交守卫 | PASS | 正确命题、三证缺一、错误答案、错误 NPC、无会话、未签收等路径见 [EditMode XML](M4C/Closeout/final-EditMode.xml) |
| A02 装袋 / 暂交 / 取消 / 防重 | PASS（本地） | [PlayMode XML](M4C/Closeout/final-PlayMode.xml) 与 [Chrome 操作记录](M4C/Closeout/browser-01/browser.json) |
| E01 + A02 结算、回访、读档 | PASS（本地） | Chrome 从最短装袋回退后改选暂交，刷新复查。PlayMode 检查原件显隐、证据和待查状态 |
| NPC 知识和索引恢复 | PASS（本地） | 每 NPC 保存已出示字段及已触发披露。编辑器用例覆盖旧档、林遥与老周分离、回退前后证据和索引 |
| C3 对话服务镜像 | 集成；验证范围见测试报告 | 重开对话使用独立会话上下文，排队镜像按本会话出示集合比对。远程模型文本无保管写入口 |
| C4 URP 编译、编辑器测试、构建、Chrome | PASS | [最终 WebGL 实测](M4C_WebGL_Verification.md) |
| HDRP 质量检查 | 条件通过 | EditMode 2/2。原样批处理 PlayMode 2/5，隔离副本固定帧步并路由输入后 5/5 |
| C5 部署、同源与公网 | 本地同源实测，容器沿用历史，公网 UNVERIFIED | [旧部署预检](M4C_ModelScope_Preflight.md) |
| 后端章末事务、演出、A01/R02 | 未完成 | [遗留事项与保管表现](M4C_Remaining_Tasks_Report.md) |
| 真实模型、真实输入法组合窗、新包硬件 GPU、实时 Editor Console 窗口 | UNVERIFIED | 本轮使用本机 Mock、批处理日志与 headless Chrome SwiftShader |

本轮可提交用户验收。阶段切换仍需用户明确批准。
