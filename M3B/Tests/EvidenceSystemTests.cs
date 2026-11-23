using System;
using System.Collections.Generic;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.Tests
{
    internal static class EvidenceSystemTests
    {
        public static void Register(TestRegistry registry)
        {
            registry.Add("Evidence_CompleteCardIsAcquiredWithEvents", CompleteCardIsAcquiredWithEvents);
            registry.Add("Evidence_ObservationIsIdempotent", ObservationIsIdempotent);
            registry.Add("Evidence_DuplicateRegistrationIsIdempotent", DuplicateRegistrationIsIdempotent);
            registry.Add("Evidence_IncompleteRegistrationFails", IncompleteRegistrationFails);
            registry.Add("Evidence_InvalidIdsAreRejected", InvalidIdsAreRejected);
            registry.Add("Evidence_SnapshotRoundTrips", SnapshotRoundTrips);
            registry.Add("Evidence_SnapshotRejectsCorruption", SnapshotRejectsCorruption);
            registry.Add("Evidence_CatalogJsonRejectsAnomalies", CatalogJsonRejectsAnomalies);
            registry.Add("Evidence_SnapshotJsonRejectsAnomalies", SnapshotJsonRejectsAnomalies);
        }

        private static void CompleteCardIsAcquiredWithEvents()
        {
            var catalog = TestData.EvidenceCatalog;
            var registry = new EvidenceRegistry(catalog, new SequentialIdGenerator());
            var events = new List<EvidenceStateChangedEvent>();
            registry.StateChanged += events.Add;

            var definition = catalog.Get("E01");
            var result = registry.ObserveFields(definition.RequiredFieldIds);

            Assert.Equal(5, result.NewlyObservedFieldIds.Count, "E01 应有 5 个字段。");
            Assert.SequenceEqual(new[] { "E01" }, result.NewlyRegisteredEvidenceIds);
            Assert.True(result.Changed);
            Assert.Equal(2, events.Count, "应产生观察事件与登记事件。");
            Assert.Equal(EvidenceEventTypes.FieldsObserved, events[0].EventType);
            Assert.Equal(EvidenceEventTypes.Registered, events[1].EventType);
            Assert.Equal("E01", events[1].EvidenceId);
            Assert.Equal(2, result.EventIds.Count);

            Assert.True(registry.HasEvidence("E01"));
            Assert.Equal(EvidenceStatus.Acquired, registry.GetStatus("E01"));
            Assert.Equal(EvidenceStatus.NotObserved, registry.GetStatus("E02"));

            var record = registry.FindVisibleRecord("E01");
            Assert.NotNull(record);
            Assert.Equal("停表与编号", record.Title);
            Assert.Contains("21:17", record.FixedText);
            Assert.Equal(5, record.ObservedFieldIds.Count);
            Assert.Equal(3, record.MediaRefs.Count);
            Assert.Equal(1, registry.AcquiredEvidenceIds.Count);
        }

        private static void ObservationIsIdempotent()
        {
            var catalog = TestData.EvidenceCatalog;
            var registry = new EvidenceRegistry(catalog, new SequentialIdGenerator());
            var eventCount = 0;
            registry.StateChanged += _ => eventCount++;

            registry.ObserveField("watch.dial");
            var second = registry.ObserveField("watch.dial");

            Assert.Equal(0, second.NewlyObservedFieldIds.Count);
            Assert.SequenceEqual(new[] { "watch.dial" }, second.AlreadyObservedFieldIds);
            Assert.False(second.Changed);
            Assert.Equal(1, eventCount, "重复观察不得再次发事件。");
            Assert.Equal(EvidenceStatus.PartiallyObserved, registry.GetStatus("E01"));

            registry.ObserveFields("watch.back_engraving", "watch.serial_number");
            var completion = registry.ObserveFields("watch.side_crown", "watch.crown_shaft_damage");
            Assert.SequenceEqual(new[] { "E01" }, completion.NewlyRegisteredEvidenceIds);
        }

        private static void DuplicateRegistrationIsIdempotent()
        {
            var registry = TestData.CreateRegistry("E01");
            var eventCount = 0;
            registry.StateChanged += _ => eventCount++;

            var duplicate = registry.RegisterEvidence("E01");
            Assert.True(duplicate.AlreadyRegistered);
            Assert.Equal(0, duplicate.RegisteredEvidenceIds.Count);
            Assert.Equal(0, duplicate.EventIds.Count);
            Assert.Equal(0, eventCount, "重复登记不得产生事件。");
            Assert.Equal(1, registry.AcquiredEvidenceIds.Count);
        }

        private static void IncompleteRegistrationFails()
        {
            var registry = new EvidenceRegistry(TestData.EvidenceCatalog, new SequentialIdGenerator());
            registry.ObserveField("power_fault.timestamp");
            var error = Assert.ThrowsContract(() => registry.RegisterEvidence("E02"));
            Assert.Equal(ErrorCodes.PreconditionFailed, error.Code);
            Assert.Contains("power_fault.branch_fault", error.Message);
            Assert.False(registry.HasEvidence("E02"));
        }

        private static void InvalidIdsAreRejected()
        {
            var registry = new EvidenceRegistry(TestData.EvidenceCatalog, new SequentialIdGenerator());
            Assert.ContractCode(() => registry.ObserveField("watch.not_a_real_field"), ErrorCodes.NotFound);
            Assert.Equal(0, registry.ObservedFieldIds.Count, "失败的调用不得部分写入。");

            Assert.ContractCode(() => registry.ObserveField(""), ErrorCodes.InvalidRequest);
            Assert.ContractCode(() => registry.GetStatus("E99"), ErrorCodes.NotFound);
            Assert.ContractCode(() => registry.RegisterEvidence("E99"), ErrorCodes.NotFound);
            Assert.ContractCode(() => registry.RegisterEvidence("not-an-id"), ErrorCodes.InvalidRequest);

            var partial = Assert.ThrowsContract(() => registry.ObserveFields("watch.dial", "watch.does_not_exist"));
            Assert.Equal(ErrorCodes.NotFound, partial.Code);
            Assert.Equal(0, registry.ObservedFieldIds.Count);
        }

        private static void SnapshotRoundTrips()
        {
            var catalog = TestData.EvidenceCatalog;
            var source = TestData.CreateRegistry("E01", "E02");
            var json = source.CreateSnapshot().ToJson();

            var snapshot = EvidenceSnapshot.ParseAndValidate(catalog, json);
            var restored = new EvidenceRegistry(catalog, snapshot, new SequentialIdGenerator());

            Assert.True(restored.HasEvidence("E01"));
            Assert.True(restored.HasEvidence("E02"));
            Assert.Equal(9, restored.ObservedFieldIds.Count);
            Assert.SequenceEqual(source.AcquiredEvidenceIds, restored.AcquiredEvidenceIds);
            Assert.Equal(source.CreateSnapshot().ToJson(false), restored.CreateSnapshot().ToJson(false));
        }

        private static void SnapshotRejectsCorruption()
        {
            var catalog = TestData.EvidenceCatalog;

            var duplicateObserved = new EvidenceSnapshot(catalog.ContentVersion, new[] { "watch.dial", "watch.dial" }, Array.Empty<string>());
            Assert.ContractCode(() => duplicateObserved.Validate(catalog), ErrorCodes.SaveCorrupt);

            var wrongVersion = new EvidenceSnapshot("story-v9", new[] { "watch.dial" }, Array.Empty<string>());
            Assert.ContractCode(() => wrongVersion.Validate(catalog), ErrorCodes.SaveIncompatible);

            var unknownField = new EvidenceSnapshot(catalog.ContentVersion, new[] { "nope.nope" }, Array.Empty<string>());
            Assert.ContractCode(() => unknownField.Validate(catalog), ErrorCodes.SaveCorrupt);

            var evidenceWithoutFields = new EvidenceSnapshot(catalog.ContentVersion, Array.Empty<string>(), new[] { "E01" });
            Assert.ContractCode(() => evidenceWithoutFields.Validate(catalog), ErrorCodes.SaveCorrupt);

            Assert.ContractCode(
                () => EvidenceSnapshot.Parse("{\"schema_version\":\"2\",\"content_version\":\"x\"}"),
                ErrorCodes.SaveIncompatible);
        }

        private static void CatalogJsonRejectsAnomalies()
        {
            Assert.Throws<JsonDataException>(() => EvidenceCatalogJson.Parse("{"));
            Assert.Throws<JsonDataException>(() => EvidenceCatalogJson.Parse("[]"));
            Assert.Throws<JsonDataException>(() => EvidenceCatalogJson.Parse("{\"content_version\":\"v\",\"evidence\":[]}"));

            const string unknownField = "{\"content_version\":\"story-v1.0-phase2\",\"evidence\":[{" +
                "\"evidence_id\":\"E01\",\"title\":\"t\",\"source_kind\":\"physical\",\"source_id\":\"s\"," +
                "\"area_id\":\"lost_property\",\"composed_from_parts\":false,\"fixed_text\":\"x\"," +
                "\"fields\":[{\"field_id\":\"watch.dial\",\"label\":\"l\",\"display_text\":\"d\"}],\"bogus\":true}]}";
            Assert.Throws<JsonDataException>(() => EvidenceCatalogJson.Parse(unknownField));

            const string unknownEnum = "{\"content_version\":\"story-v1.0-phase2\",\"evidence\":[{" +
                "\"evidence_id\":\"E01\",\"title\":\"t\",\"source_kind\":\"hologram\",\"source_id\":\"s\"," +
                "\"area_id\":\"lost_property\",\"composed_from_parts\":false,\"fixed_text\":\"x\"," +
                "\"fields\":[{\"field_id\":\"watch.dial\",\"label\":\"l\",\"display_text\":\"d\"}]}]}";
            Assert.Throws<JsonDataException>(() => EvidenceCatalogJson.Parse(unknownEnum));

            const string missingFieldText = "{\"content_version\":\"story-v1.0-phase2\",\"evidence\":[{" +
                "\"evidence_id\":\"E01\",\"title\":\"t\",\"source_kind\":\"physical\",\"source_id\":\"s\"," +
                "\"area_id\":\"lost_property\",\"composed_from_parts\":false,\"fixed_text\":\"x\"," +
                "\"fields\":[{\"field_id\":\"watch.dial\"}]}]}";
            Assert.Throws<JsonDataException>(() => EvidenceCatalogJson.Parse(missingFieldText));
        }

        private static void SnapshotJsonRejectsAnomalies()
        {
            Assert.Throws<JsonDataException>(() => EvidenceSnapshot.Parse("{"));
            Assert.Throws<JsonDataException>(() => EvidenceSnapshot.Parse("{\"observed_field_ids\":[]}"));
            Assert.Throws<JsonDataException>(
                () => EvidenceSnapshot.Parse("{\"content_version\":\"v\",\"observed_field_ids\":\"watch.dial\"}"));
            Assert.Throws<JsonDataException>(
                () => EvidenceSnapshot.Parse("{\"content_version\":\"v\",\"unknown\":true}"));
        }
    }
}
