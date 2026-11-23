using System;
using System.Threading;
using System.Threading.Tasks;

namespace EchoLostAndFound.WebGL.Contracts
{
    // These public fields also define the JsonUtility fixture format.
    [Serializable]
    public sealed class EvidenceObservation
    {
        public string field_id;
        public string title;
        public string observation_text;
    }

    [Serializable]
    public sealed class DialoguePreview
    {
        public string npc_id;
        public string speaker_name;
        public string display_text;
    }

    [Serializable]
    public sealed class StationPreview
    {
        public EvidenceObservation evidence;
        public DialoguePreview dialogue;
    }

    // A physical action in the station. A listener maps it to a DSH command.
    [Serializable]
    public sealed class InteractionEvent
    {
        public string request_id;
        public string kind;
        public string target_id;
        public string part_id;

        public static InteractionEvent InspectDial()
        {
            return Create("inspect_part", "item_pocket_watch", "dial");
        }

        public static InteractionEvent OpenDialogue()
        {
            return Create("open_dialogue", "npc_laozhou", string.Empty);
        }

        private static InteractionEvent Create(string kind, string target, string part)
        {
            return new InteractionEvent
            {
                request_id = Guid.NewGuid().ToString("D"),
                kind = kind,
                target_id = target,
                part_id = part
            };
        }
    }

    public interface IStationInteractionSource
    {
        event Action<InteractionEvent> Interacted;
    }

    [Serializable]
    public sealed class DialogueState
    {
        public string conversation_id;
        public string npc_id;
        public string status;
        public string[] available_topic_ids = Array.Empty<string>();
    }

    [Serializable]
    public sealed class StationGameState
    {
        public string save_id;
        public string runtime_id;
        public long state_version;
        public string chapter_id;
        public string[] evidence_ids = Array.Empty<string>();
        public EvidenceObservation[] observed_fields = Array.Empty<EvidenceObservation>();
        public DialogueState dialogue;
    }

    // Adapter supplied by DSH. One instance is bound to one activated save.
    public interface IStationGameSession
    {
        Task<StationGameState> ReadAsync(CancellationToken cancellation);
        Task<StationGameState> InteractAsync(InteractionEvent intent, string runtimeId,
            long expectedStateVersion, CancellationToken cancellation);
    }
}
