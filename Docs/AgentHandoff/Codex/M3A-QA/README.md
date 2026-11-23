# M3-A 验收复跑

最终版 `M3A-Station` 的 Unity EditMode 通过 3/3 项，含表盘时间 9:17 回归断言。[Unity XML](../M3A-Logs/editmode-final.xml)

Chrome 157 使用 SwiftShader 建立 WebGL 2.0 上下文。12 个 HTTP 响应均为 200。一次新浏览器配置、禁用缓存的本机测试中，从导航至 Unity 默认加载条消失为 1313.1 ms，随后仍有 Unity 启动画面。指针锁定、横移、转动镜头、对话开关、读表盘均通过。已核对两条独立交互事件以及画面中的 “Lao Zhou” 和 “The hands are stopped at 9:17.”。[浏览器记录](final-01/browser.json) · [谈话截图](final-01/02-dialogue.png) · [移动截图](final-01/04-movement.png) · [镜头截图](final-01/05-look.png) · [调查截图](final-01/06-clue.png)

该次测试记录了三个隐藏着色器在软件 GPU 上不受支持（CoreCopy、StencilDitherMaskSeed、HDRDebugView），以及附加光源 Cookie 格式回退。截图中可见场景、访客、怀表及文字。真实 GPU、其他浏览器及外网下载性能尚未验证。

## Unity EditMode

先生成独立工程的 Station 场景。在同一工程关闭编辑器后，用已安装的 Unity 执行以下 PowerShell 命令。启动前设置 `$project` 为独立工程的绝对路径，`$logDir` 为已存在的本次结果目录。

```powershell
$unity = 'F:\software\unity\6000.3.29f1\Editor\Unity.exe'
& $unity -batchmode -nographics -projectPath $project -runTests -testPlatform EditMode -testFilter EchoLostAndFound.QA.StationAcceptanceTests -testResults "$logDir\tests.xml" -logFile "$logDir\tests.log" | Out-Null
```

核对 XML 的总数、通过数、失败数。三项测试分别覆盖运行场景与 URP 选择、交互射线的距离及遮挡边界、JSON 预览与两类命令的身份。正式剧情推进及 Mock 服务由 DSH 另行验收。

## 浏览器

从 HDRP 仓库根目录执行。第一条命令持续服务本机回环地址，第二条命令在另一个 PowerShell 中执行。将 `$build` 设为含 `index.html` 的产物根目录。每次取证使用新目录。

```powershell
node Tools/Build/serve-webgl.mjs $build 18743
node Docs/AgentHandoff/Codex/M3A-QA/browser-smoke.mjs http://127.0.0.1:18743/ Docs/AgentHandoff/Codex/M3A-QA/run-new
```

需要 Node 及本机 Chromium。可用环境变量 `M3A_CHROME` 指定浏览器程序。脚本以临时独立配置启动无头 Chrome，用 DevTools 发送真实键盘和鼠标事件。保留浏览器控制台、HTTP 结果、运行时异常、资源传输与解压字节数、锁定鼠标结果和连续截图。每次加载使用新 profile 并禁用网络缓存。冷启动时间从页面导航起点算至默认模板在 Unity 实例初始化回调中隐藏加载条。数值限定本机 HTTP 与软件 WebGL 渲染器。

验证操作顺序为单击进入、E 打开访客对话、E 关闭、D 向右移至怀表、向下转动镜头、E 调查。核对截图中的台面相对位置、镜头俯仰和两种面板文字，同时检查两条独立的交互日志。若实际运行失败，`browser.json` 记录失败步骤，已保存的截图可用于定位。
