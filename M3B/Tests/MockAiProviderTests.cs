using System;
using System.Collections.Generic;
using EchoLostAndFound.MockAi;
using EchoLostAndFound.Shared.Ai;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.Tests
{
    internal static class MockAiProviderTests
    {
        public static void Register(TestRegistry registry)
        {
            registry.Add("Mock_CompletedReplyIsSyntheticAndDeterministic", CompletedReplyIsSyntheticAndDeterministic);
            registry.Add("Mock_TimeoutAndTransportErrorFallBack", TimeoutAndTransportErrorFallBack);
            registry.Add("Mock_InvalidAndUnsafeOutputAreRejected", InvalidAndUnsafeOutputAreRejected);
            registry.Add("Mock_NoMatchAndUnknownNpcFallBack", NoMatchAndUnknownNpcFallBack);
            registry.Add("Mock_EvidenceConditionsGateScenarios", EvidenceConditionsGateScenarios);
            registry.Add("Mock_ContentVersionMismatchFallsBack", ContentVersionMismatchFallsBack);
            registry.Add("Mock_FixtureJsonRejectsAnomalies", FixtureJsonRejectsAnomalies);
            registry.Add("LlmAdapter_MapsTransportFailuresToFallbacks", LlmAdapterMapsTransportFailuresToFallbacks);
        }

        private static void CompletedReplyIsSyntheticAndDeterministic()
        {
            var provider = new MockAiProvider(TestData.MockScenarios);
            var request = Request("npc_laozhou", "灯的事情", Array.Empty<string>());

            var first = provider.Generate(request);
            var second = provider.Generate(request);

            Assert.Equal(NpcAiOutcome.Completed, first.Outcome);
            Assert.True(first.IsSuccess);
            Assert.True(first.IsSynthetic);
            Assert.Equal(NpcAiProviderKind.Mock, first.ProviderKind);
            Assert.Equal("mock-deterministic", first.ProviderId);
            Assert.Contains("模拟回复", first.Text);
            Assert.Equal("opt.laozhou.ask_b01", first.SuggestedTopicId);
            Assert.Null(first.FallbackReason);
            Assert.Equal(first.Text, second.Text, "固定测试数据必须每次一致。");
        }

        private static void TimeoutAndTransportErrorFallBack()
        {
            var provider = new MockAiProvider(TestData.MockScenarios);

            var timeout = provider.Generate(Request("npc_laozhou", "超时测试", Array.Empty<string>()));
            Assert.Equal(NpcAiOutcome.TimedOut, timeout.Outcome);
            Assert.Equal(NpcAiFallbackReasons.Timeout, timeout.FallbackReason);
            Assert.False(timeout.IsSuccess);
            Assert.Null(timeout.Text);

            var error = provider.Generate(Request("npc_laozhou", "错误测试", Array.Empty<string>()));
            Assert.Equal(NpcAiOutcome.ModelUnavailable, error.Outcome);
            Assert.Equal(NpcAiFallbackReasons.ModelUnavailable, error.FallbackReason);
            Assert.False(error.IsSuccess);
        }

        private static void InvalidAndUnsafeOutputAreRejected()
        {
            var provider = new MockAiProvider(TestData.MockScenarios);

            var invalid = provider.Generate(Request("npc_laozhou", "坏输出测试", Array.Empty<string>()));
            Assert.Equal(NpcAiOutcome.InvalidOutput, invalid.Outcome);
            Assert.Equal(NpcAiFallbackReasons.InvalidOutput, invalid.FallbackReason);
            Assert.Null(invalid.Text);

            var unsafeOutput = provider.Generate(Request("npc_laozhou", "不安全测试", Array.Empty<string>()));
            Assert.Equal(NpcAiOutcome.UnsafeOutput, unsafeOutput.Outcome);
            Assert.Equal(NpcAiFallbackReasons.UnsafeOutput, unsafeOutput.FallbackReason);
            Assert.Null(unsafeOutput.Text);
        }

        private static void NoMatchAndUnknownNpcFallBack()
        {
            var provider = new MockAiProvider(TestData.MockScenarios);

            var unknownIntent = provider.Generate(Request("npc_laozhou", "完全无关的问题", Array.Empty<string>()));
            Assert.Equal(NpcAiOutcome.UnknownIntent, unknownIntent.Outcome);
            Assert.Equal(NpcAiFallbackReasons.UnknownIntent, unknownIntent.FallbackReason);

            var reservedNpc = provider.Generate(Request("npc_xucheng", "灯", Array.Empty<string>()));
            Assert.Equal(NpcAiOutcome.UnknownIntent, reservedNpc.Outcome, "CH01 不得调用 npc_xucheng，也没有夹具。");
        }

        private static void EvidenceConditionsGateScenarios()
        {
            var provider = new MockAiProvider(TestData.MockScenarios);

            var withoutDocuments = provider.Generate(Request("npc_linyao", "凭号", Array.Empty<string>()));
            Assert.Equal(NpcAiOutcome.UnknownIntent, withoutDocuments.Outcome);

            var withOneDocument = provider.Generate(Request("npc_linyao", "凭号", new[] { "E03" }));
            Assert.Equal(NpcAiOutcome.UnknownIntent, withOneDocument.Outcome);

            var withBothDocuments = provider.Generate(Request("npc_linyao", "凭号", new[] { "E03", "E04" }));
            Assert.Equal(NpcAiOutcome.Completed, withBothDocuments.Outcome);
            Assert.Contains("模拟回复", withBothDocuments.Text);

            var laozhouWithoutBoth = provider.Generate(Request("npc_laozhou", "你记得什么", new[] { "E01" }));
            Assert.Equal(NpcAiOutcome.UnknownIntent, laozhouWithoutBoth.Outcome);

            var laozhouWithBoth = provider.Generate(Request("npc_laozhou", "你记得什么", new[] { "E01", "E02" }));
            Assert.Equal(NpcAiOutcome.Completed, laozhouWithBoth.Outcome);
        }

        private static void ContentVersionMismatchFallsBack()
        {
            var provider = new MockAiProvider(TestData.MockScenarios);
            var request = Request("npc_laozhou", "灯", Array.Empty<string>(), "story-v9");

            var reply = provider.Generate(request);
            Assert.Equal(NpcAiOutcome.ModelUnavailable, reply.Outcome);
            Assert.Equal("content_version_mismatch", reply.FailureDetail);
        }

        private static void FixtureJsonRejectsAnomalies()
        {
            Assert.Throws<JsonDataException>(() => MockAiScenarioJson.Parse("{"));
            Assert.Throws<JsonDataException>(() => MockAiScenarioJson.Parse(
                "{\"provider_id\":\"p\",\"content_version\":\"v\",\"scenarios\":[]}"));

            const string unknownBehavior = "{\"provider_id\":\"p\",\"content_version\":\"v\",\"scenarios\":[{" +
                "\"scenario_id\":\"s1\",\"npc_id\":\"npc_laozhou\",\"behavior\":\"explode\"}]}";
            Assert.Throws<JsonDataException>(() => MockAiScenarioJson.Parse(unknownBehavior));

            const string duplicateScenario = "{\"provider_id\":\"p\",\"content_version\":\"v\",\"scenarios\":[" +
                "{\"scenario_id\":\"s1\",\"npc_id\":\"npc_laozhou\",\"behavior\":\"timeout\"}," +
                "{\"scenario_id\":\"s1\",\"npc_id\":\"npc_laozhou\",\"behavior\":\"timeout\"}]}";
            Assert.Throws<JsonDataException>(
                () => MockAiScenarioJson.Parse(duplicateScenario),
                "重复 scenario_id 必须在加载期失败。");
        }

        private static void LlmAdapterMapsTransportFailuresToFallbacks()
        {
            var unconfigured = new LlmBackedNpcAiProvider(null);
            var request = Request("npc_laozhou", "灯", Array.Empty<string>());
            var missing = unconfigured.Generate(request);
            Assert.Equal(NpcAiOutcome.ModelUnavailable, missing.Outcome);
            Assert.Equal("transport_not_configured", missing.FailureDetail);

            var timingOut = new LlmBackedNpcAiProvider(new FakeTransport(_ => throw new TimeoutException()));
            Assert.Equal(NpcAiOutcome.TimedOut, timingOut.Generate(request).Outcome);

            var failing = new LlmBackedNpcAiProvider(new FakeTransport(_ => throw new InvalidOperationException()));
            Assert.Equal(NpcAiOutcome.ModelUnavailable, failing.Generate(request).Outcome);

            var httpFailure = new LlmBackedNpcAiProvider(
                new FakeTransport(_ => LlmTransportResponse.Failure("timeout")));
            var httpReply = httpFailure.Generate(request);
            Assert.Equal(NpcAiOutcome.TimedOut, httpReply.Outcome);
            Assert.Equal(NpcAiFallbackReasons.Timeout, httpReply.FallbackReason);

            var badJson = new LlmBackedNpcAiProvider(new FakeTransport(_ => LlmTransportResponse.Success("not json")));
            Assert.Equal(NpcAiOutcome.InvalidOutput, badJson.Generate(request).Outcome);

            var goodJson = new LlmBackedNpcAiProvider(new FakeTransport(
                _ => LlmTransportResponse.Success("{\"npc_id\":\"npc_laozhou\",\"text\":\"后端桥接文本\"}")));
            var reply = goodJson.Generate(request);
            Assert.Equal(NpcAiOutcome.Completed, reply.Outcome);
            Assert.False(reply.IsSynthetic, "真实适配器输出不得标记为 mock。");
            Assert.Equal(NpcAiProviderKind.ExternalModel, reply.ProviderKind);
            Assert.Equal("后端桥接文本", reply.Text);
        }

        private static NpcAiRequest Request(
            string npcId,
            string input,
            IReadOnlyList<string> evidenceIds,
            string contentVersion = "story-v1.0-phase2")
        {
            return new NpcAiRequest(
                "req-1",
                npcId,
                input,
                evidenceIds,
                new[] { "opt.laozhou.ask_b01", "opt.laozhou.leave" },
                3000,
                contentVersion);
        }

        private sealed class FakeTransport : ILlmNpcReplyTransport
        {
            private readonly Func<NpcAiRequest, LlmTransportResponse> body;

            public FakeTransport(Func<NpcAiRequest, LlmTransportResponse> body)
            {
                this.body = body;
            }

            public LlmTransportResponse Send(NpcAiRequest request) => body(request);
        }
    }
}
