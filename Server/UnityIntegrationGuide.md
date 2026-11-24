# Unity 客户端集成指南（NPC AI 服务 M4-B）

面向 Unity 6.3（URP/WebGL）与现有 M3-B 模块（`M3B/EvidenceSystem`、`M3B/DialogueSystem`）。本指南只描述**客户端调用方式**，不修改 Unity 场景、Prefab 或 `Packages/`。

## 1. 先决条件

- 服务已部署并可通过 HTTPS 访问；本机开发可用 `http://127.0.0.1:8787`。
- 服务端 `CORS_ALLOWED_ORIGINS` 包含 WebGL 页面实际来源（例如 `http://localhost:8080`）。Unity Editor 不走浏览器 CORS，WebGL 构建必须配置。
- 客户端内置**内容版本**常量 `story-v1.0-phase2`，并与服务端 `GET /api/v1/meta` 的 `content_version` 比对。

> 密钥只存在于服务端环境变量。Unity 客户端、WebGL 资源、`Assets/` 中不得出现 `LLM_API_KEY`、真实模型 base URL 的授权信息或任何 `sk-` 开头的字符串。客户端只与服务通信。

## 2. 网络层（UnityWebRequest）

WebGL 不支持任意套接字，使用 `UnityWebRequest` 协程最稳妥。下面是最小可用封装。

```csharp
using System;
using System.Collections;
using System.Text;
using EchoLostAndFound.Shared.Json;
using UnityEngine;
using UnityEngine.Networking;

namespace EchoLostAndFound.Net
{
    [Serializable]
    public sealed class ApiError
    {
        public string code;
        public string message;
        public bool retryable;
    }

    public sealed class NpcAiClient
    {
        private readonly string _baseUrl;
        private readonly string _tokenHeaderName;
        private readonly string _token;

        // baseUrl: "https://your-host"（末尾不要斜杠）
        public NpcAiClient(string baseUrl, string tokenHeaderName = "X-Dialogue-Token", string token = null)
        {
            _baseUrl = baseUrl.TrimEnd('/');
            _tokenHeaderName = tokenHeaderName;
            _token = token;
        }

        // 要求同工程引用了 M3B/Shared/Json（纯 C#，无 UnityEngine 依赖）。
        public IEnumerator Post(string path, string jsonBody, Action<JsonValue> onData, Action<ApiError> onError)
        {
            using (var request = new UnityWebRequest(_baseUrl + path, UnityWebRequest.kHttpVerbPOST))
            {
                var body = Encoding.UTF8.GetBytes(jsonBody);
                request.uploadHandler = new UploadHandlerRaw(body);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.timeout = 15;
                if (!string.IsNullOrEmpty(_token) && !string.IsNullOrEmpty(_tokenHeaderName))
                {
                    request.SetRequestHeader(_tokenHeaderName, _token);
                }

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    onError?.Invoke(new ApiError
                    {
                        code = "TRANSPORT_ERROR",
                        message = request.error ?? "network error",
                        retryable = true
                    });
                    yield break;
                }

                JsonValue envelope;
                try
                {
                    // 严格解析：重复键、未知结构、非法 JSON 会抛 JsonDataException。
                    envelope = JsonValue.Parse(request.downloadHandler.text);
                }
                catch (JsonDataException)
                {
                    onError?.Invoke(new ApiError { code = "INVALID_RESPONSE", message = "无法解析响应", retryable = true });
                    yield break;
                }

                var errorNode = envelope["error"];
                if (errorNode != null && !(errorNode is JsonNull))
                {
                    var e = errorNode.AsObject();
                    onError?.Invoke(new ApiError
                    {
                        code = e["code"] != null ? e["code"].AsString() : "UNKNOWN",
                        message = e["message"] != null ? e["message"].AsString() : "请求失败",
                        retryable = e["retryable"] != null && e["retryable"].AsBool()
                    });
                    yield break;
                }

                onData?.Invoke(envelope["data"]);
            }
        }
    }
}
```

`JsonValue` 是 M3-B 的严格 JSON 实现（`EchoLostAndFound.Shared.Json`），netstandard2.1/C# 9，可直接用于 Unity；它比 `JsonUtility` 更适合契约验证，也避免 `data` 结构因端点而异的问题。若不想引入该程序集，则为每个端点定义与契约完全一致的强类型 DTO（字段名不可改）。

## 3. 会话流程

```text
GET /api/v1/meta                  → 校验 content_version，拿 NPC/话题/limits
POST /api/v1/sessions             → conversation_id + opening_segments
POST /api/v1/sessions/{id}/turns  → topic_id（固定台词）或 text（自由输入）
POST /api/v1/sessions/{id}/evidence → 出示证据，返回触发台词
POST /api/v1/sessions/{id}/cancel → 主动取消
```

请求示例：

```json
{"npc_id": "npc_laozhou", "evidence_ids": ["E01"], "observed_field_ids": ["watch.dial"]}
```

```json
{"topic_id": "opt.laozhou.ask_b01"}
```

```json
{"text": "那晚灯亮着吗", "timeout_ms": 4000}
```

```json
{"evidence_ids": ["E02"]}
```

### 3.1 固定台词优先

已批准话题与关键词意图由服务端直接返回 `source=fixed_line`，不调用模型。客户端应把 `fixed_segments` 按顺序显示，并参考 `available_topic_ids` 刷新选项。

### 3.2 自由输入与回退

自由输入返回的三种情况：

- `source=external_model`/`mock`：显示 `generated_bridge`，但**不得**据此改变线索、证据、任务或好感度；
- `source=fallback`：显示 NPC 的固定不安/沉默反应（由客户端本地决定），可按 `fallback_reason` 选择提示；不要显示“AI 出错”类破坏沉浸的文案；
- HTTP 429：按 `Retry-After` 退避；HTTP 410：会话已结束，重新创建会话。

`generated_bridge` 可能为 `null`，UI 必须容忍。

### 3.3 出示证据

客户端的证据持有状态**以 M3-B EvidenceRegistry 为准**。流程：

1. 玩家选择“出示证据”；
2. 客户端取 `evidenceRegistry.AcquiredEvidenceIds` 中选择的编号；
3. `POST .../evidence` 发送 `evidence_ids`；
4. 校验响应中的 `triggered_disclosure_ids` 已在本地内容目录中登记；`fixed_segments` 逐条显示；
5. 把 `event_ids` 写入本地日志（用于调试与成就/日程，不直接改世界状态）。

服务端不会授予客户端没有的证据；如果响应出现授予字段（不应出现），客户端应视为契约违规并丢弃。

### 3.4 证据/字段的同步

会话创建与每次回合都可以可选携带 `evidence_ids`/`observed_field_ids`。服务端仅用于 D 条件判定与记录，不改变客户端状态。推荐在创建会话时带上一次，之后在出示证据时带上当前观察字段（如 `watch.back_engraving` 用于林遥的表背辨认）。

## 4. 与 M3-B 模块的关系

| M3-B 组件 | 服务端对应 | 集成方式 |
|---|---|---|
| `EvidenceRegistry` | 无（客户端权威） | 证据获取、重复获取、快照均由 Unity 端负责；服务端只接收上报 |
| `DialogueEngine.StartSession/Choose` | `POST /sessions`、`POST /turns` | 离线固定路径可继续用本地 `DialogueEngine`；在线时用服务端返回的固定段落替换本地回合 |
| `DialogueEngine.PresentEvidence` | `POST .../evidence` | D 触发规则两端一致；上线后以服务端判定为准 |
| `INpcAiProvider.Generate`（同步） | `POST /turns`（异步 HTTP） | WebGL 中必须用协程；不要把同步 Mock Provider 直接用于网络 |
| `NpcAiReply` | turn 响应 | 字段映射：`source`→ProviderKind，`fallback_reason`→FallbackReason，`generated_bridge`→Text |

M3-B 的 `INpcAiProvider` 是为无网络确定性 Mock 设计的同步接口；真实服务是异步的。集成层应提供协程 API，把结果转换为 `NpcAiReply` 后再交给 UI，而不是阻塞等待 HTTP。

## 5. 超时与重试建议

- 请求超时：10–15 s；服务端 `AI_TIMEOUT_MS` 默认 12 s，通常先于客户端返回 fallback。
- 429：按 `Retry-After` 退避，最多 2 次。
- 5xx：指数退避（0.5 s、1 s、2 s），仍失败则本地进入“网络不可用”模式，固定内容仍可离线运行。
- 410：不要重试同一会话，重建会话。
- 400/404/409/422：属于内容或请求错误，重试无意义，记录日志并显示安全文案。

## 6. WebGL 构建检查清单

- [ ] `CORS_ALLOWED_ORIGINS` 精确包含 WebGL 页面来源（协议+域名+端口）。
- [ ] 页面为 HTTPS 时，服务必须是 HTTPS（禁止混合内容）。
- [ ] 没有在 `Assets/`、`StreamingAssets/`、PlayerPrefs 或代码常量中写入 API Key。
- [ ] 请求体字段名与契约一致；未知字段会被 422 拒绝。
- [ ] UI 能处理 `generated_bridge=null`、`fallback_reason`、`429`、`410`。
- [ ] 内容版本不一致时阻止进入对话并提示更新。
- [ ] 用 WebGL 构建（非 Editor）实测一次创建会话、固定回合、出示证据、自由输入与回退。

## 7. 本机联调命令

```powershell
# 1) 启动服务（Mock，允许本机 WebGL 构建来源）
$env:MODEL_PROVIDER = "mock"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:8080"
G:\projects\EchoLostAndFound\Server\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787

# 2) 健康检查
curl.exe http://127.0.0.1:8787/api/v1/health
```

Unity 端把 `baseUrl` 设为 `http://127.0.0.1:8787`；WebGL 构建后页面来源需与 `CORS_ALLOWED_ORIGINS` 一致。

## 8. 未验证声明

本指南中的 C# 代码为真实可编译示例，但**未在 Unity 编辑器或 WebGL 构建中运行**；本次交付未修改 Unity 工程，因此 WebGL 联调属于待验证项（见 `TEST_RESULTS.md`）。接入 Codex 的场景前请遵循 `HandoffToCodex_M4B.md` 与项目协作规则，由 Game Director 分配文件所有权。
