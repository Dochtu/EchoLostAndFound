using System;
using System.Collections;
using System.Collections.Generic;
using EchoLostAndFound.Shared.Json;
using UnityEngine;

namespace EchoStation
{
    /// <summary>
    /// A free-text reply that is ready to be shown. <see cref="Source"/> mirrors the server
    /// contract's <c>source</c> (fixed_line | mock | external_model | fallback) so the panel can
    /// label synthetic answers instead of passing them off as a real model.
    /// </summary>
    public sealed class StationReply
    {
        public bool Ok;
        public string Text;
        public string Source;
        public string FallbackReason;
        public bool IsSynthetic;
        public string Failure;

        public string Attribution
        {
            get
            {
                switch (Source)
                {
                    case "external_model":
                        return "（模型回复）";
                    case "mock":
                        return "（服务器模拟回复，非真实模型）";
                    case "fallback":
                        return FallbackLabel(FallbackReason);
                    default:
                        return string.Empty;
                }
            }
        }

        public static string FallbackLabel(string reason)
        {
            switch (reason)
            {
                case "timeout":
                    return "（模型回应超时，对方没有再说下去）";
                case "invalid_output":
                    return "（模型回复不合规，已拦下）";
                case "unsafe_output":
                    return "（模型回复被安全规则拦下）";
                case "unknown_intent":
                    return "（对方不知道该怎么接这句话）";
                default:
                    return "（模型暂不可用）";
            }
        }
    }

    /// <summary>
    /// Owns the online dialogue lifetime for one play session: probe <c>/api/v1/meta</c>, open a
    /// server conversation per NPC, mirror presented evidence, and send free text. The local
    /// <c>EvidenceRegistry</c>/<c>DialogueEngine</c> stay authoritative for story state; the
    /// server's disclosure ids are only compared and logged, never replayed into the client.
    /// </summary>
    public sealed class StationDialogueBridge
    {
        public const string OnlineTitle = "在线对话已连接。";
        public const string OfflineTitle = "离线模式：固定剧情与证据调查仍可进行，自由输入暂不可用。";
        public const string VersionMismatchTitle = "服务端内容版本不一致，已停用在线对话。";
        public const string ProbingTitle = "正在连接在线对话…";

        readonly StationApiClient api;
        readonly StationInvestigation investigation;
        readonly MonoBehaviour host;

        bool probed;
        string notice = ProbingTitle;
        sealed class RemoteSession
        {
            internal readonly string Npc;
            internal string Id;
            internal bool Opening, Sending, Mirroring;
            internal readonly Queue<string> Pending = new Queue<string>();
            internal readonly HashSet<string> Presented = new HashSet<string>(StringComparer.Ordinal);
            internal readonly HashSet<string> Disclosed = new HashSet<string>(StringComparer.Ordinal);
            internal RemoteSession(string npc) { Npc = npc; }
        }

        RemoteSession active;

        internal StationDialogueBridge(StationApiClient api, StationInvestigation investigation, MonoBehaviour host)
        {
            this.api = api ?? new StationApiClient(StationApiClient.ResolveBaseUrl());
            this.investigation = investigation;
            this.host = host;
        }

        public StationApiClient Api => api;
        public bool Online { get; private set; }
        public bool Probing { get; private set; }
        public bool Sending => active?.Sending == true;
        public bool Resolved => probed && !Probing;
        public string Notice => notice;
        public string ServerConversation => active?.Id;

        /// <summary>Probe the service once per play session; a mismatch or an outage only disables chat.</summary>
        public void Probe()
        {
            if (Probing) return;
            if (!host || !host.isActiveAndEnabled)
            {
                MarkOffline(OfflineTitle);
                return;
            }

            host.StartCoroutine(ProbeRoutine());
        }

        IEnumerator ProbeRoutine()
        {
            Probing = true;
            StationApiResult result = null;
            yield return api.GetMeta(value => result = value);
            Probing = false;
            probed = true;

            if (result == null || !result.Ok)
            {
                MarkOffline(OfflineTitle);
                yield break;
            }

            var version = StationApiClient.TryString(result.Data, "content_version");
            if (!string.Equals(version, StationApiClient.ContentVersion, StringComparison.Ordinal))
            {
                Online = false;
                probed = true;
                notice = VersionMismatchTitle + "（服务端 " + (string.IsNullOrEmpty(version) ? "未知" : version) + "）";
                Debug.LogWarning("M4C online dialogue disabled: content version " + version);
                yield break;
            }

            var provider = StationApiClient.TryObject(result.Data, "provider");
            var kind = StationApiClient.TryString(provider, "kind");
            Online = true;
            notice = kind == "mock"
                ? "在线对话已连接（服务器当前为 Mock 模拟回复，非真实模型）。"
                : OnlineTitle;
            Debug.Log("M4C online dialogue ready, provider=" + kind + " base=" + api.BaseUrl);
            EnsureOpened(active);
        }

        /// <summary>Open the server conversation that mirrors a local dialogue session.</summary>
        public void Open(string npcId)
        {
            Close();
            active = new RemoteSession(npcId);
            EnsureOpened(active);
        }

        void EnsureOpened(RemoteSession session)
        {
            if (session == null || !Online || session.Opening || session.Id != null || !host || !host.isActiveAndEnabled)
                return;
            session.Opening = true;
            host.StartCoroutine(OpenRoutine(session));
        }

        public void Close()
        {
            var previous = active;
            active = null;
            CancelRemote(previous?.Id);
        }

        void CancelRemote(string conversationId)
        {
            if (string.IsNullOrEmpty(conversationId) || !host || !host.isActiveAndEnabled) return;
            host.StartCoroutine(api.Cancel(conversationId, result =>
            {
                if (result != null && !result.Ok && !result.IsNetworkFailure)
                    Debug.Log("M4C server cancel skipped: " + result.ErrorCode);
            }));
        }

        IEnumerator OpenRoutine(RemoteSession session)
        {
            StationApiResult created = null;
            yield return api.CreateSession(session.Npc, EvidenceIds(), FieldIds(), result => created = result);
            session.Opening = false;
            string id = created != null && created.Ok ? StationApiClient.TryString(created.Data, "conversation_id") : null;
            if (active != session)
            {
                CancelRemote(id);
                yield break;
            }
            if (created == null || !created.Ok)
            {
                if (created != null && created.IsNetworkFailure) MarkOffline(OfflineTitle);
                else if (created != null)
                {
                    Online = false;
                    notice = "在线对话不可用（" + created.ErrorCode + "），固定剧情仍可继续。";
                }

                yield break;
            }

            session.Id = id;
            Debug.Log("M4C server session " + (id ?? "missing") + " for " + session.Npc);
            StartMirror(session);
        }

        /// <summary>
        /// Send free text through the online dialogue. <paramref name="npcId"/> is the local NPC id
        /// so a conversation can be opened lazily if the player started talking offline.
        /// </summary>
        public void Send(string npcId, string text, Action<StationReply> done)
        {
            if (done == null) return;
            if (!Online || active == null || active.Npc != npcId)
            {
                done(new StationReply { Failure = OfflineTitle });
                return;
            }

            if (Sending)
            {
                done(new StationReply { Failure = "上一句还在等待回应，请稍后再发。" });
                return;
            }

            if (!host || !host.isActiveAndEnabled)
            {
                done(new StationReply { Failure = OfflineTitle });
                return;
            }

            EnsureOpened(active);
            host.StartCoroutine(SendRoutine(active, text, done));
        }

        IEnumerator SendRoutine(RemoteSession session, string text, Action<StationReply> done)
        {
            session.Sending = true;
            while (session.Opening && active == session) yield return null;
            if (active != session || string.IsNullOrEmpty(session.Id))
            {
                session.Sending = false;
                done(new StationReply { Failure = notice });
                yield break;
            }

            StationApiResult turn = null;
            yield return api.TakeTurn(
                session.Id,
                text,
                EvidenceIds(),
                FieldIds(),
                StationApiClient.DefaultTurnTimeoutMs,
                result => turn = result);
            session.Sending = false;
            if (session != active)
            {
                done(new StationReply { Failure = OfflineTitle });
                yield break;
            }

            if (turn == null)
            {
                done(new StationReply { Failure = "没有收到服务端的回应。" });
                yield break;
            }

            if (!turn.Ok)
            {
                if (turn.Status == 404 || turn.Status == 410)
                {
                    session.Id = null;
                    Online = false;
                    notice = "本次交谈已过期，固定剧情仍可继续。";
                    done(new StationReply { Failure = "这次交谈已经结束了，对方不会再回应。" });
                    yield break;
                }

                if (turn.IsNetworkFailure)
                {
                    MarkOffline(OfflineTitle);
                    done(new StationReply { Failure = "连不上在线服务，对方暂时没有回应。" });
                    yield break;
                }

                Debug.LogWarning("M4C turn failed " + turn.Status + " " + turn.ErrorCode);
                done(new StationReply { Failure = "在线对话暂时不可用（" + turn.ErrorCode + "）。" });
                yield break;
            }

            done(ReadTurn(turn.Data));
        }

        /// <summary>Translate a turn payload into panel text; never trusted for story state.</summary>
        public static StationReply ReadTurn(JsonObject data)
        {
            var reply = new StationReply
            {
                Ok = true,
                Source = StationApiClient.TryString(data, "source"),
                FallbackReason = StationApiClient.TryString(data, "fallback_reason")
            };
            var provider = StationApiClient.TryObject(data, "provider");
            reply.IsSynthetic = StationApiClient.TryBool(provider, "is_synthetic");

            var lines = new List<string>();
            var fixedSegments = StationApiClient.TryArray(data, "fixed_segments");
            if (fixedSegments != null)
            {
                foreach (var item in fixedSegments.Items)
                {
                    var text = StationApiClient.TryString(item as JsonObject, "text");
                    if (!string.IsNullOrEmpty(text)) lines.Add(text);
                }
            }

            var bridge = StationApiClient.TryString(data, "generated_bridge");
            if (!string.IsNullOrEmpty(bridge)) lines.Add(bridge);

            reply.Text = string.Join("\n", lines);
            if (string.IsNullOrEmpty(reply.Text)) reply.Text = "对方没有再说下去。";
            return reply;
        }

        /// <summary>
        /// Mirror a local evidence presentation to the server and log any disclosure mismatch.
        /// Story events already fired locally; the server reply is never rendered.
        /// </summary>
        public void MirrorPresentation(string evidenceId, IReadOnlyList<string> localDisclosureIds)
        {
            // localDisclosureIds contains once-per-save events. The server compares against a
            // fresh conversation, which may legitimately rediscover a previously saved disclosure.
            if (active == null || (!Online && !Probing) || !host || !host.isActiveAndEnabled) return;
            active.Pending.Enqueue(evidenceId);
            StartMirror(active);
        }

        void StartMirror(RemoteSession session)
        {
            if (session.Id == null || session.Mirroring || session.Pending.Count == 0) return;
            session.Mirroring = true;
            host.StartCoroutine(MirrorRoutine(session));
        }

        IEnumerator MirrorRoutine(RemoteSession session)
        {
            while (active == session && Online && session.Pending.Count > 0)
            {
                var evidenceId = session.Pending.Dequeue();
                StationApiResult result = null;
                yield return api.PresentEvidence(session.Id, new[] { evidenceId }, FieldIds(), r => result = r);
                if (active != session) break;
                if (result == null || !result.Ok)
                {
                    if (result != null && result.IsNetworkFailure) MarkOffline(OfflineTitle);
                    else if (result != null) Debug.Log("M4C mirror skipped: " + result.ErrorCode);
                    continue;
                }

                session.Presented.Add(evidenceId);
                var expected = new List<string>();
                foreach (var rule in investigation.Dialogue.Catalog.Get(session.Npc).Disclosures)
                    if (rule.RequirementsMet(session.Presented, investigation.Evidence) && session.Disclosed.Add(rule.DisclosureId))
                        expected.Add(rule.DisclosureId);

                var serverIds = StationApiClient.StringArray(StationApiClient.TryArray(result.Data, "triggered_disclosure_ids"));
                if (!SameIds(expected, serverIds))
                    Debug.LogWarning("M4C disclosure mismatch local=[" + string.Join(",", expected) + "] server=[" + string.Join(",", serverIds) + "]");
                else
                    Debug.Log("M4C mirror ok " + evidenceId + " disclosures=[" + string.Join(",", serverIds) + "]");
            }
            session.Mirroring = false;
        }

        static bool SameIds(IReadOnlyList<string> left, IReadOnlyList<string> right)
        {
            if (left.Count != right.Count) return false;
            var a = new List<string>(left);
            var b = new List<string>(right);
            a.Sort(StringComparer.Ordinal);
            b.Sort(StringComparer.Ordinal);
            for (var i = 0; i < a.Count; i++)
            {
                if (!string.Equals(a[i], b[i], StringComparison.Ordinal)) return false;
            }

            return true;
        }

        void MarkOffline(string reason)
        {
            Online = false;
            probed = true;
            notice = reason;
            Debug.Log("M4C online dialogue offline: " + reason);
        }

        IReadOnlyList<string> EvidenceIds()
        {
            return investigation != null ? investigation.Evidence.AcquiredEvidenceIds : Array.Empty<string>();
        }

        IReadOnlyList<string> FieldIds()
        {
            if (investigation == null) return Array.Empty<string>();
            var views = investigation.Evidence.GetObservedFields();
            var ids = new List<string>(views.Count);
            foreach (var view in views) ids.Add(view.FieldId);
            return ids;
        }
    }
}
