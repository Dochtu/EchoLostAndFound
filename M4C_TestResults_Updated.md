# M4-C 测试结果 · 2026-11-24

| 实测对象 | 结果 | 证据 |
| --- | --- | --- |
| URP 原始基线 EditMode | 15/15 | [基线 XML](M4C/Closeout/edit.xml) |
| URP 最终编译与 EditMode | 22/22，0 失败，0 跳过。新增 7 个用例（含参数用例） | [最终 XML](M4C/Closeout/final-EditMode.xml) · [编辑器日志](M4C/Closeout/final-EditMode.log) |
| URP 最终 PlayMode | 8/8，0 失败，0 跳过。新增 2 条章末场景流程 | [最终 XML](M4C/Closeout/final-PlayMode.xml) · [编辑器日志](M4C/Closeout/final-PlayMode.log) |
| HDRP 编译、EditMode | 源资源 SHA-256 对比 743/743，一致。EditMode 2/2 | [资源对比](M4C/CloseoutQA/asset-inventory.json) · [XML](M4C/CloseoutQA/HDRP-EditMode.xml) |
| HDRP 原样 PlayMode | FAIL，2/5。无焦点批处理下移动与瞄准断言失败 | [原样 XML](M4C/CloseoutQA/HDRP-PlayMode.xml) |
| HDRP 诊断复跑 | 仅调整输入路由 3/5。隔离副本再设 60 Hz 帧步后原断言 5/5，覆盖四向移动、穿门返回、遮挡、视线和对话 | [焦点复跑](M4C/CloseoutQA/HDRP-PlayMode-focus.xml) · [60 Hz 复跑](M4C/CloseoutQA/HDRP-PlayMode-60hz.xml) · [诊断条件](M4C/CloseoutQA/HDRP-batch-input-60hz.cs.txt) |
| 引用及文件组织 | HDRP 29 个 Scene/Prefab、108 个脚本引用，URP Station 19 个脚本引用。无空脚本、扫描范围内未解析 GUID/fileID 或重复源 GUID。两个 Assets 树未见缺失或孤立 .meta，StationPlayer/HUD 共 8 个必需字段均有引用 | [引用审计](M4C/CloseoutQA/reference-audit.json) · [UI 目标](M4C/CloseoutQA/station-ui.json) |
| 后端测试 | 123 passed，1 个 Starlette 测试客户端弃用警告，6.57 秒 | [pytest 日志](M4C/Closeout/server-tests-final.txt) |
| WebGL | 构建成功，0 个构建错误，两种结算均经实际浏览器按键触发 | [构建和截图](M4C_WebGL_Verification.md) |
| Chrome 离线 | PASS。固定剧情可操作，自由输入有离线提示，刷新后保留 E01 并可向老周出示 | [完整记录](M4C/Closeout/browser-offline/browser.json) · [刷新后截图](M4C/Closeout/browser-offline/07-offline-persisted.png) |
| Chrome 在线全调查 | PASS。E01–E05、老周 D01/D02/D03、林遥 REC.engraving/D02、Mock 回复及模拟超时均经真实 HTTP 操作。8 条 mirror ok，软失败 0 | [最终在线记录](M4C/Closeout/browser-online-final/browser.json) |
| Chrome 重启与新 NPC 会话 | PASS。复用临时浏览器存档，五证均在；自由输入应答、E02 重出示和 D01 镜像通过，软失败 0 | [恢复记录](M4C/Closeout/browser-resume/browser.json) · [D01 回访画面](M4C/Closeout/browser-resume/05-resume-d01.png) |

**首次失败与修复。** 新增测试首次编译遇到 Unity NUnit 缺少 NonParallelizable 及测试脚本缺少 M2Interactable 命名空间，修复后重新构建并复跑。首次在线 Chrome 脚本误取上一回合 timeout 日志，出现 mock-reply 软失败。原日志保留，脚本现按本次发送时的日志起点取回复。[首次编译](M4C/Closeout/chapter-edit.log) · [第二次编译](M4C/Closeout/EditMode.log) · [首次在线浏览器记录](M4C/Closeout/browser-online/browser.json)

**Console。** 本轮审查 Unity 批处理日志、XML 和 Chrome 控制台。URP 离线测试有预期的本机 API 连接失败。历史 Editor.log 记录 Unity Connect 400/408；当前交互式 Console 窗口 UNVERIFIED。固定帧步诊断只存在于临时 HDRP 副本，原工程的默认批处理输入条件仍有复现风险。[历史日志摘要](M4C/CloseoutQA/historical-editor-summary.json)

**工程副本。** 检查最终 URP 的 252 个 Assets 文件，脚本、场景、Prefab 与源工程对应文件一致。Unity 导入/运行后有两处资源序列化差异，分别为 PC_RPAsset.asset 的管线资源版本/默认字段，以及 TMP 图集材质的 ScaleRatioA/C。原工程保留既有渲染配置。[资源核对与产物哈希](M4C/Closeout/build-verification.json)
