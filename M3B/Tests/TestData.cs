using System;
using System.Collections.Generic;
using System.IO;
using EchoLostAndFound.Dialogue;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.MockAi;
using EchoLostAndFound.Shared.Ai;
using EchoLostAndFound.Shared.Contracts;

namespace EchoLostAndFound.Tests
{
    internal static class TestData
    {
        private static EvidenceCatalog evidenceCatalog;
        private static DialogueCatalog dialogueCatalog;
        private static MockAiScenarioSet mockScenarios;

        public static string Root { get; set; }

        public static string EvidenceJson => File.ReadAllText(PathOf("EvidenceSystem", "Content", "ch01_evidence.json"));

        public static string DialogueJson => File.ReadAllText(PathOf("DialogueSystem", "Content", "ch01_dialogue.json"));

        public static string MockFixturesJson => File.ReadAllText(PathOf("MockAIProvider", "Content", "mock_ai_fixtures.json"));

        public static EvidenceCatalog EvidenceCatalog =>
            evidenceCatalog ?? (evidenceCatalog = EvidenceCatalogJson.Parse(EvidenceJson));

        public static DialogueCatalog DialogueCatalog =>
            dialogueCatalog ?? (dialogueCatalog = DialogueCatalogJson.Parse(DialogueJson));

        public static MockAiScenarioSet MockScenarios =>
            mockScenarios ?? (mockScenarios = MockAiScenarioJson.Parse(MockFixturesJson));

        public static EvidenceRegistry CreateRegistry(params string[] evidenceIds)
        {
            var registry = new EvidenceRegistry(EvidenceCatalog, new SequentialIdGenerator());
            foreach (var evidenceId in evidenceIds)
            {
                registry.ObserveFields(EvidenceCatalog.Get(evidenceId).RequiredFieldIds);
            }

            return registry;
        }

        public static DialogueEngine CreateEngine(IEvidenceStateView evidence, INpcAiProvider ai = null)
        {
            return new DialogueEngine(DialogueCatalog, evidence, new SequentialIdGenerator(), ai);
        }

        public static string PathOf(params string[] parts)
        {
            var all = new List<string> { Root };
            all.AddRange(parts);
            return Path.Combine(all.ToArray());
        }
    }

    internal sealed class SequentialIdGenerator : IIdGenerator
    {
        private int next;

        public string CreateId()
        {
            next++;
            return "test-id-" + next;
        }
    }
}
