# M3B — 核心调查逻辑（M3-B 交付）

纯 C# 模块，工作目录独立于 `Assets/`，不依赖 UnityEngine、不依赖第三方包、不联网。

| 内容 | 说明 |
| --- | --- |
| `Shared/` | JSON、错误码、证据只读视图、NPC AI 接口与 DTO |
| `EvidenceSystem/` | 证据目录/状态/快照/事件（`README.md`） |
| `DialogueSystem/` | NPC 会话/节点/选项/条件/D 规则（`README.md`） |
| `MockAIProvider/` | 确定性 Mock、输出校验、真实模型适配占位（`README.md`） |
| `Tests/` | 29 项控制台测试与运行记录（`README.md`、`RESULTS.txt`） |
| `IntegrationGuide.md` | 装配、契约映射、已知边界 |
| `HandoffToCodex_M3.md` | Unity 导入步骤、asmdef、集成点、待确认项 |
| `Tools/build-and-test.ps1` | Roslyn 构建 + 测试（无 MSBuild/NuGet） |

## 快速开始

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "G:\projects\EchoLostAndFound\M3B\Tools\build-and-test.ps1"
```

期望结尾：`Total: 29  Passed: 29  Failed: 0`，退出码 0。

## 状态

- 实现与测试：完成（2026-11-23）。
- Unity 内编译/运行：**未验证**（本会话未执行 Unity）。
- 内容待确认项：见 `HandoffToCodex_M3.md §6`。
