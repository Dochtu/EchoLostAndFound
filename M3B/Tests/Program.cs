using System;
using System.IO;

namespace EchoLostAndFound.Tests
{
    /// <summary>
    /// Zero-dependency console test runner. The build script compiles this namespace against
    /// the net10.0 reference assemblies and the module DLLs, then invokes it with the M3B
    /// directory as the only argument (content JSON paths are resolved beneath it).
    /// </summary>
    internal static class Program
    {
        private static int Main(string[] args)
        {
            var root = args.Length > 0 ? args[0] : Directory.GetCurrentDirectory();
            if (!Directory.Exists(root))
            {
                Console.Error.WriteLine("Content root not found: " + root);
                return 2;
            }

            TestData.Root = Path.GetFullPath(root);
            Console.WriteLine("Content root: " + TestData.Root);

            try
            {
                Console.WriteLine("Evidence catalog: " + TestData.EvidenceCatalog.Count + " cards (" + TestData.EvidenceCatalog.ContentVersion + ")");
                Console.WriteLine("Dialogue catalog: " + TestData.DialogueCatalog.Npcs.Count + " NPCs (" + TestData.DialogueCatalog.ContentVersion + ")");
                Console.WriteLine("Mock fixtures: " + TestData.MockScenarios.Scenarios.Count + " scenarios (" + TestData.MockScenarios.ProviderId + ")");
                Console.WriteLine();
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Content load failed: " + ex.GetType().Name + ": " + ex.Message);
                Console.Error.WriteLine(ex.StackTrace);
                return 2;
            }

            var registry = new TestRegistry();
            EvidenceSystemTests.Register(registry);
            DialogueSystemTests.Register(registry);
            MockAiProviderTests.Register(registry);
            IntegrationTests.Register(registry);
            return registry.RunAll();
        }
    }
}
