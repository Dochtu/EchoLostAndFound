using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using EchoLostAndFound.Shared.Ai;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.MockAi
{
    public enum MockAiBehavior
    {
        /// <summary>Validate the fixture's raw JSON and return its completed reply.</summary>
        Reply,

        /// <summary>Deterministic simulated timeout; returns fallback_reason timeout.</summary>
        Timeout,

        /// <summary>Deterministic simulated transport error; returns model_unavailable.</summary>
        TransportError
    }

    /// <summary>
    /// One fixture scenario. Matching is deterministic and ordered: the first scenario
    /// whose NPC, evidence conditions and keywords match wins. Fixture text is explicitly
    /// test data and is always marked IsSynthetic=true by the provider.
    /// </summary>
    public sealed class MockAiScenario
    {
        public MockAiScenario(
            string scenarioId,
            string npcId,
            MockAiBehavior behavior,
            IReadOnlyList<string> inputKeywords,
            IReadOnlyList<string> requiresEvidenceIds,
            IReadOnlyList<string> excludesEvidenceIds,
            string rawReplyJson)
        {
            if (string.IsNullOrWhiteSpace(scenarioId)) throw GameContractException.Validation("mock scenario 缺少 scenario_id。");
            if (string.IsNullOrWhiteSpace(npcId)) throw GameContractException.Validation("mock scenario " + scenarioId + " 缺少 npc_id。");
            if (behavior == MockAiBehavior.Reply && string.IsNullOrWhiteSpace(rawReplyJson))
                throw GameContractException.Validation("mock scenario " + scenarioId + " 为 reply 行为时必须提供 raw_reply_json。");

            ScenarioId = scenarioId;
            NpcId = npcId;
            Behavior = behavior;
            InputKeywords = inputKeywords ?? Array.Empty<string>();
            RequiresEvidenceIds = requiresEvidenceIds ?? Array.Empty<string>();
            ExcludesEvidenceIds = excludesEvidenceIds ?? Array.Empty<string>();
            RawReplyJson = rawReplyJson;
        }

        public string ScenarioId { get; }

        public string NpcId { get; }

        public MockAiBehavior Behavior { get; }

        public IReadOnlyList<string> InputKeywords { get; }

        public IReadOnlyList<string> RequiresEvidenceIds { get; }

        public IReadOnlyList<string> ExcludesEvidenceIds { get; }

        public string RawReplyJson { get; }

        public bool Matches(NpcAiRequest request)
        {
            if (!string.Equals(request.NpcId, NpcId, StringComparison.Ordinal)) return false;

            foreach (var evidenceId in RequiresEvidenceIds)
            {
                if (!Contains(request.AcquiredEvidenceIds, evidenceId)) return false;
            }

            foreach (var evidenceId in ExcludesEvidenceIds)
            {
                if (Contains(request.AcquiredEvidenceIds, evidenceId)) return false;
            }

            if (InputKeywords.Count == 0) return true;
            foreach (var keyword in InputKeywords)
            {
                if (request.PlayerInput.IndexOf(keyword, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            }

            return false;
        }

        private static bool Contains(IReadOnlyList<string> values, string value)
        {
            for (var i = 0; i < values.Count; i++)
            {
                if (string.Equals(values[i], value, StringComparison.Ordinal)) return true;
            }

            return false;
        }
    }

    public sealed class MockAiScenarioSet
    {
        private readonly ReadOnlyCollection<MockAiScenario> scenarios;

        public MockAiScenarioSet(
            string providerId,
            string contentVersion,
            IReadOnlyList<MockAiScenario> scenarios)
        {
            if (string.IsNullOrWhiteSpace(providerId)) throw GameContractException.Validation("mock provider_id 不能为空。");
            if (string.IsNullOrWhiteSpace(contentVersion)) throw GameContractException.Validation("mock content_version 不能为空。");
            if (scenarios == null || scenarios.Count == 0) throw GameContractException.Validation("mock 场景集不能为空。");

            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var scenario in scenarios)
            {
                if (scenario == null) throw GameContractException.Validation("mock 场景集包含 null。");
                if (!seen.Add(scenario.ScenarioId))
                    throw GameContractException.Validation("重复的 mock scenario_id '" + scenario.ScenarioId + "'。");
            }

            ProviderId = providerId;
            ContentVersion = contentVersion;
            this.scenarios = new ReadOnlyCollection<MockAiScenario>(new List<MockAiScenario>(scenarios));
        }

        public string ProviderId { get; }

        public string ContentVersion { get; }

        public IReadOnlyList<MockAiScenario> Scenarios => scenarios;

        public MockAiScenario FindMatch(NpcAiRequest request)
        {
            if (request == null) throw new ArgumentNullException(nameof(request));
            foreach (var scenario in scenarios)
            {
                if (scenario.Matches(request)) return scenario;
            }

            return null;
        }
    }

    /// <summary>
    /// Strict parser for the mock provider fixture file. It accepts either a completed
    /// reply payload or a deliberately malformed payload (used to prove that the
    /// validator rejects invalid/unsafe model output).
    /// </summary>
    public static class MockAiScenarioJson
    {
        private static readonly Func<string, MockAiBehavior?> BehaviorResolver = raw =>
        {
            switch (raw)
            {
                case "reply": return MockAiBehavior.Reply;
                case "timeout": return MockAiBehavior.Timeout;
                case "transport_error": return MockAiBehavior.TransportError;
                default: return null;
            }
        };

        public static MockAiScenarioSet Parse(string json)
        {
            if (json == null) throw new JsonDataException("Mock AI fixture JSON is null.", "$");
            var root = JsonContract.RequireObject(JsonValue.Parse(json), "$");
            JsonContract.RejectUnknownFields(root, "$", "provider_id", "content_version", "scenarios");

            var providerId = JsonContract.RequireString(root, "provider_id", "$");
            var contentVersion = JsonContract.RequireString(root, "content_version", "$");
            var array = JsonContract.RequireArrayMember(root, "scenarios", "$");
            var scenarios = new List<MockAiScenario>(array.Count);
            for (var i = 0; i < array.Count; i++)
            {
                var path = JsonContract.IndexPath("$.scenarios", i);
                scenarios.Add(ReadScenario(JsonContract.RequireObject(array[i], path), path));
            }

            try
            {
                return new MockAiScenarioSet(providerId, contentVersion, scenarios);
            }
            catch (GameContractException ex)
            {
                throw new JsonDataException(ex.Message, "$.scenarios", ex.Code);
            }
        }

        private static MockAiScenario ReadScenario(JsonObject obj, string path)
        {
            JsonContract.RejectUnknownFields(obj, path, "scenario_id", "npc_id", "behavior", "input_keywords", "requires_evidence_ids", "excludes_evidence_ids", "raw_reply_json");
            var behavior = JsonContract.ParseEnum(
                JsonContract.RequireString(obj, "behavior", path),
                JsonContract.MemberPath(path, "behavior"),
                BehaviorResolver,
                "reply, timeout, transport_error");

            return new MockAiScenario(
                JsonContract.RequireString(obj, "scenario_id", path),
                JsonContract.RequireString(obj, "npc_id", path),
                behavior,
                JsonContract.OptionalStringArray(obj, "input_keywords", path),
                JsonContract.OptionalStringArray(obj, "requires_evidence_ids", path),
                JsonContract.OptionalStringArray(obj, "excludes_evidence_ids", path),
                JsonContract.OptionalString(obj, "raw_reply_json", path));
        }
    }
}
