# M1.5 零预算视觉升级执行记录

本次在原 Station 上替换视觉引用并保存。正式入口为 [Station.unity](../Assets/_Project/Scenes/Station.unity)。Unity 版本为 6000.3.29f1，HDRP 17.3.0。总支出人民币 0 元，未使用外部生成式 AI。用户仍为阶段验收方。

## 原型替换与工程保护

| 部位 | 当前实物 |
| --- | --- |
| 候车厅 | Blender 制作的拱顶、连续工字拱肋、扇窗、柱头与柱脚、透空托架、长椅、分缝水磨石地面和吊灯。六张木椅面向过道，端窗与灯具沿用原布局。 |
| 失物招领处 | 柜台增加压线框板、抽屉和拉手。布包经过 22 帧 Cloth 模拟，最大顶点位移约 7.4 厘米，保留提手、缝线与 A-0641 包签。登记册、档案盒、捆扎文件与台灯均为新模型。 |
| 怀表 | 直径约 55.2 mm。短针 278.5°、长针 102°。背盖和侧冠另有运行时检查图，可辨「0412·0916」「QH-283」、侧冠凹陷和偏轴。保留原证据 Prefab 用于兼容。 |
| 人物 | MakeHuman CC0 人体、日常衣鞋、眉睫、头发、眼与牙齿。Unity 验证有效 Humanoid Avatar、八个蒙皮网格和四秒循环 Idle。新人物为通用外观样板，正式角色肖像仍待用户确认。原程序化人物在场景中停用。 |
| 站台 | 七段金属雨棚、檐槽、四米钢轨单元、轨夹、枕木、棚内外地面及湿度变化。保留安全隔离和原雨幕，增加了檐滴落点水花。 |

既有有效 Prefab 均保留，以新 Prefab 和场景实例覆盖视觉。大厅机位、其余四个镜位与区域连通关系沿用基线。没有执行旧 Build Station。建筑部分保留原墙体与远景背景，旧资源的隐藏、保留和序列化依赖可在工程清单中核对。纸面、柜背等远景与主道具的精度仍有差距。

## 材质、许可与证据

木纹、水磨石、灰泥、金属、织物、皮革、纸和混凝土使用免费 PBR。表面根据材质输入设置 Base Color、Normal、线性 Mask，水磨石附高度贴图；站台湿度改变颜色、法线与平滑度。人物使用肤色分区平滑度、HDRP 皮肤扩散与独立服装 AO。逐文件尺寸、三角数、LOD、来源、许可和 SHA-256 在两份 CSV 内。[工程清单](M1_5_AssetManifest.csv) · [免费清单](M1_5_FreeAssetManifest.csv) · [许可说明](M1_5_Licenses.md)

五镜位最终图为未放大的 1920×1080 Unity HDRP Play Mode 截图。[大厅](Evidence/Stage4_M1_5/06_MainHall_Final.png) · [柜台](Evidence/Stage4_M1_5/07_LostFound_Final.png) · [怀表](Evidence/Stage4_M1_5/08_PocketWatch_Final.png) · [人物](Evidence/Stage4_M1_5/09_NPC_Final.png) · [站台](Evidence/Stage4_M1_5/10_Platform_Final.png)

对照图并排保留两张完整 1080p 图，每张图顶端附阶段标签。14 号细节页裁自运行时实拍。背面和侧冠是五镜位之后在 Play Mode 临时旋转怀表进行的检查，退出播放后场景仍使用正面姿态。[表背](Evidence/Stage4_M1_5/Watch_Caseback.png) · [侧冠](Evidence/Stage4_M1_5/Watch_Crown.png) · [细节](Evidence/Stage4_M1_5/14_AssetQuality_Samples.png)

## 复现与验收

在现有工程中打开 Station，按 Play 查看大厅。需要复测全套证据时，在已保存且空闲的编辑器中执行 Tools → Echo → M1.5 → Integrate station and capture five shots。此入口会更新 M1.5 专用资产、原场景中的实例覆盖和截图。仅查看成果时直接打开已保存场景。交付 ZIP 为本工程的增量包，应与同一份阶段四工程配套使用。

本轮已通过 Unity 重新打开新 Prefab、验证网格、材质、剧本证据、镜位和人物 Avatar。阶段进入条件由实拍质量、性能与用户验收共同决定。[磁盘重载检查](Evidence/Stage4_M1_5/AssetValidation.log) · [独立 QA](Evidence/Stage4_M1_5/IndependentQA.md) · [视觉评分](M1_5_VisualQA.md) · [性能报告](M1_5_PerformanceReport.md)

### 从源文件重做资产

场景、Prefab、FBX 和贴图可以直接在上述 Unity 版本中打开。若要重新生成模型，制作脚本位于 [Tools/M1_5](../Tools/M1_5/)。模型使用 Blender 4.5.3 LTS。角色额外使用 MPFB 2.0.18，安装在 Blender 的 user_default 扩展库；将 MakeHuman CC0 系统包解压，并用环境变量 `M15_MH_ASSETS` 指向解包目录。重做 LOD 时先生成柱、椅、吊灯的高模。湿地贴图脚本需要 NumPy、Pillow 以及工程中的 Concrete031 派生贴图。重做布包、档案和站台时保留同目录的 build_counter.py 共用建模函数。

保留下来的美术样板包括通用人物、早期墙面材质试样、旧版造型和部分远景围墙。旧版人物及已被替换的家具、屋顶等对应渲染器已停用。人物骨架、皮肤与服装来自 MakeHuman 系统包；新增的建筑、家具与道具均由项目制作。没有商业资源采购或需要用户补交的素材费用。

## 10:45 中间复评

2026-11-22 10:45 这轮实拍达到 Art Director 的固定镜位门槛。美术评分依次为大厅 12→20、柜台 12→20、怀表 15→20、人物 10→20、站台 13→20，满分 25。独立 QA 对同组图分别评为 20、20、21、17 和 20。人物的差异集中在发际线、眼部边缘和面部细节。该轮状态为 **PARTIAL**，M2 尚待视觉问题复核及用户验收。

同轮 Editor 五镜位 P95 均低于 25 ms。大厅平均 54.8 FPS，较旧基线 49.2 FPS 增加 5.6 FPS，仍低于 60 FPS 目标。10:27 批次记录过超过 3 秒的长帧，长时间运行的稳定性尚不能由这次短采样确定。人物 331 个采样帧内鞋底估计高度 1.0–2.3 mm，眨眼权重最高 99.8，最低 -1.9。鞋底高度按两侧脚趾骨和鞋底偏移估算。[动画实测](Evidence/Stage4_M1_5/IdleValidation.log) · [性能报告](M1_5_PerformanceReport.md)

## 最终交付与验收

**阶段结论为 PARTIAL。** 15:37 的实机证据与 20:32 完成构建的 Windows Player 均来自当前 Station。独立 QA 的最终评分见下表，每镜满分 25。柜台物件、怀表证据、雨夜站台及大厅在五个原固定机位中有四个已通过独立视觉门槛。人物的头发体块、面颊层次、站姿仍限制近景表现，人物身份与肖像待用户审定。M2 的视觉和性能进入条件仍未满足。[独立 QA](Evidence/Stage4_M1_5/IndependentQA.md) · [Art Director 评分](M1_5_VisualQA.md)

| 镜位 | 原图 | 最终图 |
| --- | ---: | ---: |
| 大厅 | 14 | 20 |
| 失物招领处 | 13 | 20 |
| 怀表 | 17 | 21 |
| 人物 | 12 | 18 |
| 站台 | 15 | 20 |

最终人物有 64 根骨、8 个蒙皮网格、48,556 个三角面。新皮肤贴图将原 CC0 眉、睫及发际投影到皮肤 UV，并用原肤色亮度生成局部浅法线。原眉睫卡片保留且停用，眼球与眼睑仍参与动画。离线重制可使用 Tools/M1_5/refine_portrait.py 的 --help 查看 Blender、人物 FBX、CC0 素材包和输出目录参数，需要 NumPy、SciPy、Pillow 及同目录 project_portrait_uv.py。最后 311 帧内，脚趾骨估算鞋底离地 1.0–2.3 mm。当前免费样板的写实近景仍有差距。

最终 Editor 大厅为 55.5 FPS，P95 18.9 ms。独立 Player 大厅两次分别为 43.0、54.4 FPS，两次 P95 均为 33.3 ms，目标为 25 ms。Player 其余四镜位复测约 60 FPS。较早 Editor 批次及 Player 首轮的长帧均保留在报告中。[性能报告](M1_5_PerformanceReport.md)

140 个工程文件与 152 条许可资料覆盖此次新增和修改的内容。采用的外部美术来源均有 CC0 依据，预算为 0 元。Unity 从磁盘重开 17 个新 Prefab，遍历含原资产在内的 681 个场景节点，记录 0 项问题。对照 446 个原始文件的 SHA-256，除了有意更新的 Station 场景，另外 445 个文件均与备份逐字节一致。增量 ZIP 保留相应 .meta、备份、制作脚本、14 张指定截图及两轮 Player 的数据。[工程保护记录](Evidence/Stage4_M1_5/Protection.log) · [资源清单](M1_5_AssetManifest.csv) · [许可清单](M1_5_FreeAssetManifest.csv)
