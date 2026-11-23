# M3-A 验收报告 · 2026-11-23

M3-A 已产出可在桌面 Chrome 运行的 WebGL 车站原型，供用户验收。工程入口为 EchoLostAndFound_WebGL，启用场景为 Assets/Station/Scenes/Station.unity。本轮的改动集中在独立工程、根 .gitignore、M3A-Backups 与 Docs/AgentHandoff/Codex。对备份中的根 Assets、Packages、ProjectSettings、DSH 交接及构建工具共 784 个文件复核，其内容与快照一致。

## 交付与操作

- EchoLostAndFound_WebGL/Builds/M3A-Station.zip 可解压部署，index.html 位于压缩包根目录。已逐文件核对 ZIP 与发布目录的 SHA-256。
- 单击画面锁定鼠标。WASD 移动，鼠标环视，准星对准访客或怀表时按 E 打开，再按 E 关闭。Esc 释放鼠标。
- 英文界面采用项目已有的 Liberation Sans SDF。模型来自原工程的 StationVisitor、EvidenceWatch 和 HallSettee_LOD2。新生成车站和五种材质使用 URP，复用 M2 移动、视角、射线和输入动作。
- 使用 Unity 6000.3.29f1 的 URP 模板，URP 17.3.0、Input System 1.20.1 和 uGUI 2.0.0。最终版本由独立工程的 Packages/packages-lock.json 固定。采用默认 Web 模板和 gzip。
- M3A-Contracts.md 规定 DSH 的四类接口。访客和怀表是本地可玩的交互入口，后续接入 DSH 的状态、对话和证据服务。表盘单独检查只显示 9:17。

## 验证结果

| 项目 | 结果 | 同目录证据 |
| --- | --- | --- |
| 首次导入与生成 | 独立工程 WebGL 目标导入成功；通过 Unity API 生成并保存唯一启用场景 | M3A-Logs/import.log、scene.log |
| Unity EditMode | 3/3 通过，零失败、零跳过。验证 URP 与场景连接、遮挡/距离/禁用边界，以及 JSON、9:17 读数和两个交互事件 | M3A-Logs/editmode-final.xml、tests-final.log |
| WebGL BuildPipeline | 首包用时 8 分 45.6 秒；最终增量构建用时 11.0 秒，均为 Unity BuildReport 口径，均报告 0 错误 | M3A-Logs/build-first.log、build-final.log |
| 桌面浏览器 | Chrome 157.0.8103.79、WebGL 2、SwiftShader，指针锁定、横移、环视、访客面板、关闭、怀表调查全部通过。12 个 HTTP 响应均为 200，无页面异常或弹窗 | M3A-QA/final-01/browser.json 及 6 张连续截图 |
| 加载 | 全新浏览器配置、禁用网络缓存、本机 HTTP，单次从导航到默认模板隐藏加载条 1.313 秒；开场画面与首个可输入帧未单独计时 | M3A-QA/final-01/browser.json |
| 版本基线 | 快照内 999 个文件逐字节比对通过。原仓库索引仍为空 | M3A-Recovery.md、M3A-Backups/HDRP-before-M3A.sha256 |

## 文件体积

| 内容 | 实际字节 |
| --- | ---: |
| 独立工程 Assets，含 .meta | 9,055,497 |
| 三个源 FBX 合计 | 5,237,444 |
| gzip 后的 Wasm | 11,080,381 |
| gzip 后的 data | 9,376,307 |
| gzip 后的框架 JS | 88,398 |
| 发布目录全部 17 个文件 | 20,591,622 |
| ZIP | 20,064,883 |

逐文件清单和校验和见 M3A-Size.json。

## 复现命令

从仓库根目录运行 PowerShell。选用空的新副本目录可独立重建；F 盘为本机已验证的位置。构建入口沿用 DSH 的方法名、环境变量、压缩配置与 BuildReport 检查，并验证实际 URP 类型和输出目录。脚本会拒绝已存在的输出路径。

```powershell
$src = (Resolve-Path EchoLostAndFound_WebGL).Path
$project = 'F:\EchoBuilds\M3A-' + (Get-Date -Format yyyyMMdd-HHmmss)
if (Test-Path $project) { throw 'Choose a new build project directory' }
New-Item -ItemType Directory $project | Out-Null
Copy-Item "$src/Assets","$src/Packages","$src/ProjectSettings" -Destination $project -Recurse
$unity = 'F:\software\unity\6000.3.29f1\Editor\Unity.exe'
$out = Join-Path $project 'Builds/Station'
& "$src/Build-WebGL.ps1" -UnityPath $unity -ProjectPath $project -OutputDir $out
node Tools/Build/serve-webgl.mjs $out 18746
```

在浏览器打开 http://127.0.0.1:18746/ 。运行现成交付包时可直接用原仓库的服务器。

```powershell
node Tools/Build/serve-webgl.mjs EchoLostAndFound_WebGL/Builds/M3A-Station 18746
```

## 待解决与验证边界

- 实测 G 盘空间低于 DSH 的 20 GiB 构建门槛，本轮构建与 QA 均在 F 盘完成。回滚快照位于 G 盘，只覆盖源码恢复，不覆盖物理磁盘故障。
- Chromium 软件渲染路径报告三种隐藏 shader 不支持，并将附加灯光 cookie 格式回退。已检查本场景及交互截图。真机 GPU、其他浏览器、公网带宽与移动设备尚未验收。
- 浏览器版当前采用英文预览文本。正式中文字体、持续游戏状态和 DSH Mock 联调留待后续获批范围。
- 访客当前背向玩家出生点，长椅单独使用 LOD2 网格，导入器提示缺少成组 LOD 命名。当前场景中的对话触发和网格显示通过。
