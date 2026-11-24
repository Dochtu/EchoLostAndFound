using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using EchoLostAndFound.Shared.Contracts;

namespace EchoLostAndFound.Evidence
{
    public static class EvidenceEventTypes
    {
        public const string FieldsObserved = "evidence.fields_observed";
        public const string Registered = "evidence.registered";
    }

    /// <summary>
    /// Deterministic state-change record. It is emitted only after the corresponding
    /// mutation succeeded, so a failing call never leaks a half-applied event.
    /// The record carries no story text and no rule outcome — it is journal/UI input.
    /// </summary>
    public sealed class EvidenceStateChangedEvent
    {
        public EvidenceStateChangedEvent(
            string eventId,
            string eventType,
            string evidenceId,
            IReadOnlyList<string> fieldIds,
            string contentVersion)
        {
            EventId = eventId;
            EventType = eventType;
            EvidenceId = evidenceId;
            FieldIds = fieldIds ?? Array.Empty<string>();
            ContentVersion = contentVersion;
        }

        public string EventId { get; }

        public string EventType { get; }

        /// <summary>Set for registration events; null for pure observation events.</summary>
        public string EvidenceId { get; }

        public IReadOnlyList<string> FieldIds { get; }

        public string ContentVersion { get; }
    }

    public sealed class EvidenceObservationResult
    {
        public EvidenceObservationResult(
            IReadOnlyList<string> newlyObservedFieldIds,
            IReadOnlyList<string> alreadyObservedFieldIds,
            IReadOnlyList<string> newlyRegisteredEvidenceIds,
            IReadOnlyList<string> eventIds)
        {
            NewlyObservedFieldIds = newlyObservedFieldIds ?? Array.Empty<string>();
            AlreadyObservedFieldIds = alreadyObservedFieldIds ?? Array.Empty<string>();
            NewlyRegisteredEvidenceIds = newlyRegisteredEvidenceIds ?? Array.Empty<string>();
            EventIds = eventIds ?? Array.Empty<string>();
        }

        public IReadOnlyList<string> NewlyObservedFieldIds { get; }

        public IReadOnlyList<string> AlreadyObservedFieldIds { get; }

        /// <summary>Cards that became complete because of this call (auto-register mode).</summary>
        public IReadOnlyList<string> NewlyRegisteredEvidenceIds { get; }

        public IReadOnlyList<string> EventIds { get; }

        public bool Changed => NewlyObservedFieldIds.Count > 0;
    }

    public sealed class EvidenceRegistrationResult
    {
        public EvidenceRegistrationResult(
            string evidenceId,
            bool alreadyRegistered,
            IReadOnlyList<string> registeredEvidenceIds,
            IReadOnlyList<string> eventIds)
        {
            EvidenceId = evidenceId;
            AlreadyRegistered = alreadyRegistered;
            RegisteredEvidenceIds = registeredEvidenceIds ?? Array.Empty<string>();
            EventIds = eventIds ?? Array.Empty<string>();
        }

        public string EvidenceId { get; }

        /// <summary>DataSchema duplicate-registration contract: true with empty payloads.</summary>
        public bool AlreadyRegistered { get; }

        public IReadOnlyList<string> RegisteredEvidenceIds { get; }

        public IReadOnlyList<string> EventIds { get; }
    }

    /// <summary>
    /// Pure C# evidence state machine (no UnityEngine dependency). Two distinct states
    /// are tracked, matching DataSchema: observed fields (thin observations that can be
    /// held privately) and acquired evidence cards (the player's visible records).
    /// Acquisition requires every required field of the card to be observed; a composed
    /// card such as E01 additionally has one field per watch part by construction.
    /// </summary>
    public sealed class EvidenceRegistry : IEvidenceStateView
    {
        private readonly EvidenceCatalog catalog;
        private readonly IIdGenerator idGenerator;
        private readonly bool autoRegisterOnComplete;
        private readonly List<string> observedOrder = new List<string>();
        private readonly HashSet<string> observedSet = new HashSet<string>(StringComparer.Ordinal);
        private readonly List<string> acquiredOrder = new List<string>();
        private readonly HashSet<string> acquiredSet = new HashSet<string>(StringComparer.Ordinal);
        private readonly ReadOnlyCollection<string> observedView;
        private readonly ReadOnlyCollection<string> acquiredView;

        public EvidenceRegistry(EvidenceCatalog catalog, IIdGenerator idGenerator = null, bool autoRegisterOnComplete = true)
        {
            this.catalog = catalog ?? throw new ArgumentNullException(nameof(catalog));
            this.idGenerator = idGenerator ?? GuidIdGenerator.Instance;
            this.autoRegisterOnComplete = autoRegisterOnComplete;
            observedView = new ReadOnlyCollection<string>(observedOrder);
            acquiredView = new ReadOnlyCollection<string>(acquiredOrder);
        }

        public EvidenceRegistry(
            EvidenceCatalog catalog,
            EvidenceSnapshot snapshot,
            IIdGenerator idGenerator = null,
            bool autoRegisterOnComplete = true)
            : this(catalog, idGenerator, autoRegisterOnComplete)
        {
            Restore(snapshot);
        }

        /// <summary>Raised synchronously after each successful mutation.</summary>
        public event Action<EvidenceStateChangedEvent> StateChanged;

        public EvidenceCatalog Catalog => catalog;

        public string ContentVersion => catalog.ContentVersion;

        public IReadOnlyList<string> ObservedFieldIds => observedView;

        public IReadOnlyList<string> AcquiredEvidenceIds => acquiredView;

        /// <summary>
        /// Observes one or more fields. Unknown field IDs fail the whole call with NOT_FOUND
        /// (no partial observation, no event). Re-observing is idempotent and reports the
        /// fields in <see cref="EvidenceObservationResult.AlreadyObservedFieldIds"/>.
        /// </summary>
        public EvidenceObservationResult ObserveField(string fieldId)
        {
            return ObserveFields(new[] { fieldId });
        }

        public EvidenceObservationResult ObserveFields(params string[] fieldIds)
        {
            return ObserveFields((IReadOnlyList<string>)fieldIds);
        }

        public EvidenceObservationResult ObserveFields(IReadOnlyList<string> fieldIds)
        {
            if (fieldIds == null)
                throw GameContractException.InvalidRequest("field_ids 不能为 null。");
            if (fieldIds.Count == 0)
                throw GameContractException.InvalidRequest("至少需要一个 field_id。");

            var requested = new List<string>(fieldIds.Count);
            var requestSet = new HashSet<string>(StringComparer.Ordinal);
            foreach (var fieldId in fieldIds)
            {
                if (string.IsNullOrWhiteSpace(fieldId))
                    throw GameContractException.InvalidRequest("field_id 不能为空。");
                if (!requestSet.Add(fieldId)) continue;
                if (!catalog.TryFindEvidenceForField(fieldId, out _, out _))
                    throw GameContractException.NotFound("未知观测字段 '" + fieldId + "'，不在已批准内容目录中。");
                requested.Add(fieldId);
            }

            var newlyObserved = new List<string>();
            var alreadyObserved = new List<string>();
            foreach (var fieldId in requested)
            {
                if (observedSet.Contains(fieldId)) alreadyObserved.Add(fieldId);
                else newlyObserved.Add(fieldId);
            }

            if (newlyObserved.Count == 0)
            {
                return new EvidenceObservationResult(
                    Array.Empty<string>(),
                    alreadyObserved,
                    Array.Empty<string>(),
                    Array.Empty<string>());
            }

            foreach (var fieldId in newlyObserved)
            {
                observedSet.Add(fieldId);
                observedOrder.Add(fieldId);
            }

            var events = new List<EvidenceStateChangedEvent>();
            events.Add(new EvidenceStateChangedEvent(
                idGenerator.CreateId(),
                EvidenceEventTypes.FieldsObserved,
                null,
                newlyObserved,
                catalog.ContentVersion));

            var newlyRegistered = new List<string>();
            if (autoRegisterOnComplete)
            {
                foreach (var definition in catalog.Definitions)
                {
                    if (acquiredSet.Contains(definition.EvidenceId)) continue;
                    if (!IsCompleteDefinition(definition)) continue;
                    acquiredSet.Add(definition.EvidenceId);
                    acquiredOrder.Add(definition.EvidenceId);
                    newlyRegistered.Add(definition.EvidenceId);
                    events.Add(CreateRegisteredEvent(definition));
                }
            }

            var eventIds = new List<string>(events.Count);
            foreach (var stateEvent in events)
            {
                eventIds.Add(stateEvent.EventId);
                // Raise after the state is final so handlers see a consistent registry.
                Publish(stateEvent);
            }

            return new EvidenceObservationResult(newlyObserved, alreadyObserved, newlyRegistered, eventIds);
        }

        /// <summary>
        /// Explicitly acquires a card (manual journal "登记证据" flow). Duplicate
        /// registration returns the DataSchema duplicate shape instead of throwing.
        /// Incomplete cards raise PRECONDITION_FAILED with the missing field IDs.
        /// </summary>
        public EvidenceRegistrationResult RegisterEvidence(string evidenceId)
        {
            var definition = catalog.Get(evidenceId);
            if (acquiredSet.Contains(definition.EvidenceId))
            {
                return new EvidenceRegistrationResult(definition.EvidenceId, true, Array.Empty<string>(), Array.Empty<string>());
            }

            if (!IsCompleteDefinition(definition))
            {
                var missing = new List<string>();
                foreach (var fieldId in definition.RequiredFieldIds)
                {
                    if (!observedSet.Contains(fieldId)) missing.Add(fieldId);
                }

                throw GameContractException.Precondition(
                    "证据 " + definition.EvidenceId + " 尚未完整观察，缺少字段: " + string.Join(", ", missing) + "。");
            }

            acquiredSet.Add(definition.EvidenceId);
            acquiredOrder.Add(definition.EvidenceId);
            var stateEvent = CreateRegisteredEvent(definition);
            Publish(stateEvent);
            return new EvidenceRegistrationResult(
                definition.EvidenceId,
                false,
                new[] { definition.EvidenceId },
                new[] { stateEvent.EventId });
        }

        public EvidenceStatus GetStatus(string evidenceId)
        {
            var definition = catalog.Get(evidenceId);
            if (acquiredSet.Contains(definition.EvidenceId)) return EvidenceStatus.Acquired;
            var observed = 0;
            foreach (var fieldId in definition.RequiredFieldIds)
            {
                if (observedSet.Contains(fieldId)) observed++;
            }

            if (observed == 0) return EvidenceStatus.NotObserved;
            if (observed == definition.RequiredFieldIds.Count) return EvidenceStatus.ReadyToAcquire;
            return EvidenceStatus.PartiallyObserved;
        }

        public IReadOnlyList<ObservedFieldView> GetObservedFields()
        {
            var result = new List<ObservedFieldView>(observedOrder.Count);
            foreach (var fieldId in observedOrder)
            {
                if (!catalog.TryFindEvidenceForField(fieldId, out var definition, out var field)) continue;
                result.Add(new ObservedFieldView(
                    definition.EvidenceId,
                    field.FieldId,
                    field.ItemId,
                    field.PartId,
                    field.Label,
                    field.DisplayText,
                    field.MediaRefs));
            }

            return result;
        }

        public IReadOnlyList<VisibleEvidenceRecord> GetVisibleEvidenceRecords()
        {
            var result = new List<VisibleEvidenceRecord>(acquiredOrder.Count);
            foreach (var evidenceId in acquiredOrder)
            {
                if (catalog.TryGet(evidenceId, out var definition)) result.Add(CreateVisibleRecord(definition));
            }

            return result;
        }

        /// <summary>Returns null when the card has not been acquired.</summary>
        public VisibleEvidenceRecord FindVisibleRecord(string evidenceId)
        {
            if (evidenceId == null || !acquiredSet.Contains(evidenceId)) return null;
            return catalog.TryGet(evidenceId, out var definition) ? CreateVisibleRecord(definition) : null;
        }

        public EvidenceSnapshot CreateSnapshot()
        {
            return new EvidenceSnapshot(catalog.ContentVersion, observedView, acquiredView);
        }

        public bool HasEvidence(string evidenceId)
        {
            return evidenceId != null && acquiredSet.Contains(evidenceId);
        }

        public bool IsComplete(string evidenceId)
        {
            return IsCompleteDefinition(catalog.Get(evidenceId));
        }

        public bool IsFieldObserved(string fieldId)
        {
            return fieldId != null && observedSet.Contains(fieldId);
        }

        public IReadOnlyList<string> GetObservedFieldIds(string evidenceId)
        {
            var definition = catalog.Get(evidenceId);
            var result = new List<string>();
            foreach (var fieldId in observedOrder)
            {
                if (observedSet.Contains(fieldId) && definition.TryGetField(fieldId, out _)) result.Add(fieldId);
            }

            return result;
        }

        private void Restore(EvidenceSnapshot snapshot)
        {
            if (snapshot == null) throw new ArgumentNullException(nameof(snapshot));
            snapshot.Validate(catalog);
            foreach (var fieldId in snapshot.ObservedFieldIds)
            {
                if (observedSet.Add(fieldId)) observedOrder.Add(fieldId);
            }

            foreach (var evidenceId in snapshot.AcquiredEvidenceIds)
            {
                if (acquiredSet.Add(evidenceId)) acquiredOrder.Add(evidenceId);
            }
        }

        private bool IsCompleteDefinition(EvidenceDefinition definition)
        {
            foreach (var fieldId in definition.RequiredFieldIds)
            {
                if (!observedSet.Contains(fieldId)) return false;
            }

            return true;
        }

        private EvidenceStateChangedEvent CreateRegisteredEvent(EvidenceDefinition definition)
        {
            return new EvidenceStateChangedEvent(
                idGenerator.CreateId(),
                EvidenceEventTypes.Registered,
                definition.EvidenceId,
                definition.RequiredFieldIds,
                catalog.ContentVersion);
        }

        private VisibleEvidenceRecord CreateVisibleRecord(EvidenceDefinition definition)
        {
            return new VisibleEvidenceRecord(
                definition.EvidenceId,
                definition.Title,
                EvidenceSourceKinds.ToContractValue(definition.SourceKind),
                definition.SourceId,
                definition.SourceLabel,
                definition.AreaId,
                definition.ItemId,
                definition.ProvenanceRootId,
                definition.FixedText,
                definition.ProofLimits,
                definition.MediaRefs,
                GetObservedFieldIds(definition.EvidenceId),
                definition.ContentVersion);
        }

        private void Publish(EvidenceStateChangedEvent stateEvent)
        {
            var handler = StateChanged;
            handler?.Invoke(stateEvent);
        }
    }
}
