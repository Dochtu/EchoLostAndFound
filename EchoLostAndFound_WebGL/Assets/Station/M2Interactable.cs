using UnityEngine;

namespace EchoLostAndFound.M2
{
    // Values are serialized into the scene: append new kinds, never renumber.
    public enum InteractionKind { Counter, Item, Npc, Document }

    public interface IInteractable
    {
        string DisplayName { get; }
        InteractionKind Kind { get; }
    }

    [DisallowMultipleComponent]
    public sealed class M2Interactable : MonoBehaviour, IInteractable
    {
        [SerializeField] private string displayName;
        [SerializeField] private InteractionKind kind;

        public string DisplayName => displayName;
        public InteractionKind Kind => kind;

        public void Configure(string targetName, InteractionKind interactionKind)
        {
            displayName = targetName;
            kind = interactionKind;
        }
    }

    public static class M2InteractionProbe
    {
        private static readonly RaycastHit[] hits = new RaycastHit[64];

        public static IInteractable Find(Ray ray, float maxDistance, Transform ignoreRoot = null)
        {
            if (!Physics.Raycast(ray, out var hit, maxDistance, Physics.AllLayers, QueryTriggerInteraction.Ignore))
                return null;

            if (ignoreRoot && hit.collider.transform.IsChildOf(ignoreRoot))
            {
                // Do not advance the origin past the capsule. A thin wall can touch it.
                int count = Physics.RaycastNonAlloc(ray, hits, maxDistance, Physics.AllLayers, QueryTriggerInteraction.Ignore);
                if (count == hits.Length) return null;
                float nearest = float.PositiveInfinity;
                for (int i = 0; i < count; i++)
                {
                    var candidate = hits[i];
                    if (candidate.distance >= nearest || candidate.collider.transform.IsChildOf(ignoreRoot)) continue;
                    nearest = candidate.distance;
                    hit = candidate;
                }
                if (float.IsPositiveInfinity(nearest)) return null;
            }

            // Resolve only the nearest solid surface. A wall never yields a target behind it.
            var target = hit.collider.GetComponentInParent<IInteractable>();
            return target is Behaviour component && !component.isActiveAndEnabled ? null : target;
        }
    }
}
