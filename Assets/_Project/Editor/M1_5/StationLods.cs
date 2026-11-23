using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Echo.M15
{
    internal static class StationLods
    {
        const string Models = "Assets/_Project/Art/Environment/M1_5/";
        const string Prefabs = "Assets/_Project/Prefabs/Environment/M1_5/";

        internal static void Apply()
        {
            foreach (var name in new[] { "HallColumn", "HallSettee", "HallPendant" })
                ApplyToPrefab(name);
        }

        static MeshRenderer ModelRenderer(string path)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            var renderer = model ? model.GetComponentInChildren<MeshRenderer>() : null;
            if (!renderer || !renderer.GetComponent<MeshFilter>())
                throw new FileNotFoundException("Missing fixture mesh", path);
            return renderer;
        }

        static void ApplyToPrefab(string name)
        {
            string path = Prefabs + name + ".prefab";
            var source = ModelRenderer(Models + name + ".fbx");
            var reduced = new[] {
                ModelRenderer(Models + "Detail/" + name + "_LOD1.fbx"),
                ModelRenderer(Models + "Detail/" + name + "_LOD2.fbx")
            };
            var root = PrefabUtility.LoadPrefabContents(path);
            try
            {
                var high = root.GetComponentInChildren<MeshRenderer>();
                var lod1 = AddDetail(root, high, source, reduced[0], 1);
                var lod2 = AddDetail(root, high, source, reduced[1], 2);
                var group = root.GetComponent<LODGroup>();
                if (!group) group = root.AddComponent<LODGroup>();
                group.SetLODs(new[] {
                    new LOD(.29f, new Renderer[] { high }),
                    new LOD(.115f, new Renderer[] { lod1 }),
                    new LOD(.008f, new Renderer[] { lod2 })
                });
                group.RecalculateBounds();
                if (!PrefabUtility.SaveAsPrefabAsset(root, path))
                    throw new IOException("Could not save fixture LODs for " + name);
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(root);
            }
        }

        static MeshRenderer AddDetail(GameObject root, MeshRenderer high, MeshRenderer source,
            MeshRenderer reduced, int level)
        {
            // FBX roots can either bake their axis conversion or carry it as a transform.
            // Place the reduced geometry in the original model's mesh coordinate space.
            Matrix4x4 alignment = source.transform.worldToLocalMatrix * reduced.transform.localToWorldMatrix;
            Vector3 offset = alignment.GetColumn(3);
            Vector3 scale = alignment.lossyScale;
            if (offset.sqrMagnitude > .0001f || scale.x <= 0 || scale.y <= 0 || scale.z <= 0)
                throw new InvalidDataException("Invalid LOD pivot for " + root.name);

            string childName = "Detail LOD" + level;
            var child = high.transform.Find(childName);
            if (!child)
            {
                child = new GameObject(childName, typeof(MeshFilter), typeof(MeshRenderer)).transform;
                child.SetParent(high.transform, false);
            }
            child.localPosition = offset;
            child.localRotation = alignment.rotation;
            child.localScale = scale;
            child.gameObject.layer = high.gameObject.layer;
            child.GetComponent<MeshFilter>().sharedMesh = reduced.GetComponent<MeshFilter>().sharedMesh;

            var renderer = child.GetComponent<MeshRenderer>();
            var sourceSlots = source.sharedMaterials;
            var finalSlots = high.sharedMaterials;
            renderer.sharedMaterials = reduced.sharedMaterials.Select(mat => {
                int index = Array.FindIndex(sourceSlots, original => original.name == mat.name);
                if (index < 0 || index >= finalSlots.Length || !finalSlots[index])
                    throw new InvalidDataException("LOD material alignment failed for " + root.name + " / " + mat.name);
                return finalSlots[index];
            }).ToArray();
            renderer.shadowCastingMode = high.shadowCastingMode;
            renderer.receiveShadows = high.receiveShadows;
            renderer.lightProbeUsage = high.lightProbeUsage;
            renderer.reflectionProbeUsage = high.reflectionProbeUsage;
            renderer.renderingLayerMask = high.renderingLayerMask;
            return renderer;
        }
    }
}
