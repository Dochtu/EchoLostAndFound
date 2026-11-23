using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Echo.M15
{
    internal static class R1Environment
    {
        const string Models = "Assets/_Project/Art/Environment/M1_5/";
        const string Materials = "Assets/_Project/Art/Materials/M1_5/";
        const string Textures = "Assets/_Project/Art/Textures/M1_5/";

        internal static void Apply()
        {
            var hall = Find("Station/Environment/WaitingHall");
            var platform = Find("Station/Environment/Platform");
            var weather = Find("Station/Weather");
            Hall(hall);
            Platform(platform, weather);
        }

        static Transform Find(string path)
        {
            var obj = GameObject.Find(path);
            if (!obj) throw new InvalidDataException("Missing scene object " + path);
            return obj.transform;
        }

        static T Asset<T>(string path) where T : UnityEngine.Object
        {
            var asset = AssetDatabase.LoadAssetAtPath<T>(path);
            if (!asset) throw new FileNotFoundException(path);
            return asset;
        }

        static Texture2D Map(string name, bool linear, bool clampU)
        {
            string path = Textures + name + ".png";
            if (!(AssetImporter.GetAtPath(path) is TextureImporter importer))
                throw new FileNotFoundException(path);
            importer.sRGBTexture = !linear;
            importer.mipmapEnabled = true;
            importer.streamingMipmaps = true;
            importer.anisoLevel = 8;
            importer.wrapModeU = clampU ? TextureWrapMode.Clamp : TextureWrapMode.Repeat;
            importer.wrapModeV = TextureWrapMode.Repeat;
            if (AssetDatabase.WriteImportSettingsIfDirty(path))
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            return Asset<Texture2D>(path);
        }

        static Material Variant(string source, string name, Action<Material> edit)
        {
            var basis = Asset<Material>(Materials + source + ".mat");
            string path = Materials + name + ".mat";
            var variant = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!variant)
            {
                variant = new Material(basis);
                AssetDatabase.CreateAsset(variant, path);
            }
            variant.CopyPropertiesFromMaterial(basis);
            edit(variant);
            if (variant.shader.name.StartsWith("HDRP/", StringComparison.Ordinal))
                HDMaterial.ValidateMaterial(variant);
            EditorUtility.SetDirty(variant);
            AssetDatabase.SaveAssetIfDirty(variant);
            return variant;
        }

        static void Use(Renderer renderer, string original, Material replacement)
        {
            var current = renderer.sharedMaterials;
            bool changed = false;
            for (int i = 0; i < current.Length; i++)
            {
                if (!current[i] || current[i].name != original) continue;
                current[i] = replacement;
                changed = true;
            }
            if (!changed) return;
            renderer.sharedMaterials = current;
            PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
        }

        static void SetDressing(Transform area, string name, Vector3 position, Dictionary<string,Material> palette)
        {
            var present = area.Find(name);
            var obj = present ? present.gameObject :
                (GameObject)PrefabUtility.InstantiatePrefab(Asset<GameObject>(Models + name + ".fbx"), area);
            obj.transform.localPosition = position;
            PrefabUtility.RecordPrefabInstancePropertyModifications(obj.transform);
            var source = Asset<GameObject>(Models + name + ".fbx");
            var names = source.GetComponentInChildren<MeshRenderer>().sharedMaterials;
            var renderer = obj.GetComponentInChildren<MeshRenderer>();
            renderer.sharedMaterials = names.Select(slot => palette[slot.name]).ToArray();
            // Distant facings and thin wall dressings receive the existing shadow pass.
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
        }

        static void Hall(Transform hall)
        {
            var nearFloor = Variant("Terrazzo","R1Terrazzo",m => {
                m.SetTexture("_BaseColorMap", Map("R1MutedTerrazzo",false,false));
                m.SetFloat("_NormalScale",.23f);
                m.SetFloat("_SmoothnessRemapMax",.68f);
            });
            var oak = Variant("PolishedWood","R1ThresholdOak",m => {
                m.SetColor("_BaseColor",new Color(.67f,.55f,.43f));
                m.SetFloat("_SmoothnessRemapMax",.70f);
            });
            var iron = Variant("CastIron","R1HallIron",m => {
                m.SetColor("_BaseColor",new Color(.54f,.55f,.52f));
                m.SetFloat("_MetallicRemapMax",.76f);
                m.SetFloat("_SmoothnessRemapMin",.25f);
            });
            var plaster = Variant("OldPlaster","R1LimeMasonry",m => {
                m.SetColor("_BaseColor",new Color(.73f,.69f,.61f));
                m.SetFloat("_NormalScale",.34f);
            });
            foreach (var r in hall.GetComponentsInChildren<MeshRenderer>())
            {
                Use(r,"Terrazzo",nearFloor);
                Use(r,"CastIron",iron);
            }
            SetDressing(hall,"R1HallThreshold",new Vector3(0,0,9.61f),
                new Dictionary<string,Material> {
                    {"R1ThresholdOak",oak},{"R1HallIron",iron},
                    {"R1LimeMasonry",plaster},{"R1BrassFittings",Asset<Material>(Materials+"WornBrass.mat")}
                });

            var lights = Find("Station/Lighting/InteriorLights");
            foreach (var light in lights.GetComponentsInChildren<Light>())
            {
                if (light.name != "Window bounce") continue;
                light.intensity = light.transform.position.z < 1 ? 425 : 365;
                var hd = light.GetComponent<HDAdditionalLightData>();
                hd.affectSpecular = false;
                hd.volumetricDimmer = 0;
                PrefabUtility.RecordPrefabInstancePropertyModifications(light);
                PrefabUtility.RecordPrefabInstancePropertyModifications(hd);
            }

            var rake = lights.Find("R1 end wall bounce");
            if (!rake)
            {
                rake = new GameObject("R1 end wall bounce",typeof(Light)).transform;
                rake.SetParent(lights,false);
            }
            rake.position = hall.TransformPoint(new Vector3(1.3f,3.36f,6.59f));
            rake.LookAt(hall.TransformPoint(new Vector3(.20f,1.3f,9.64f)));
            var focal = rake.GetComponent<Light>();
            focal.type = LightType.Spot;
            focal.range = 5.25f;
            focal.spotAngle = 85;
            focal.innerSpotAngle = 36;
            focal.color = new Color(1f,.83f,.60f);
            focal.intensity = 300;
            focal.shadows = LightShadows.None;
            if (!rake.TryGetComponent<HDAdditionalLightData>(out var spot))
                spot = rake.gameObject.AddComponent<HDAdditionalLightData>();
            spot.shapeRadius = .45f;
            spot.volumetricDimmer = 0;
            spot.affectSpecular = false;
        }

        static void Platform(Transform platform, Transform weather)
        {
            var apron = Variant("WetConcrete","R1WetApron",m => {
                m.SetTexture("_MaskMap", Map("R1WetApronMask",true,true));
                m.SetFloat("_NormalScale",.34f);
                m.SetFloat("_SmoothnessRemapMin",.04f);
                m.SetFloat("_SmoothnessRemapMax",.96f);
            });
            var boundary = Variant("OldPlaster","R1RailBoundary",m =>
                m.SetColor("_BaseColor",new Color(.24f,.29f,.34f)));
            var coping = Variant("WeatheredConcrete","R1ConcreteCoping",m =>
                m.SetColor("_BaseColor",new Color(.45f,.48f,.50f)));
            var roof = Variant("CastIron","R1DistantRoof",m =>
                m.SetColor("_BaseColor",new Color(.29f,.35f,.41f)));
            var deck = platform.Find("Platform_CopingAndDrains").GetComponent<MeshRenderer>();
            Use(deck,"WetConcrete",apron);
            SetDressing(platform,"R1RailBoundary",new Vector3(27.88f,0,0),
                new Dictionary<string,Material> {
                    {"R1RailBoundary",boundary},{"R1ConcreteCoping",coping},{"R1DistantRoof",roof}
                });

            var near = weather.Find("OpenPlatformRain").GetComponent<ParticleSystem>();
            var other = weather.Find("R1 distant rain");
            var far = other ? other.GetComponent<ParticleSystem>() :
                UnityEngine.Object.Instantiate(near.gameObject,weather).GetComponent<ParticleSystem>();
            far.name = "R1 distant rain";
            RainLayer(near, new Vector3(14.72f,7.2f,0), 5.3f,1810,.023f,.182f,.84f);
            RainLayer(far, new Vector3(22.6f,7.2f,0),10.44f,1550,.021f,.154f,.52f);
        }

        static void RainLayer(ParticleSystem rain, Vector3 at, float width,
            float rate, float thickness, float length, float alpha)
        {
            rain.Stop(true,ParticleSystemStopBehavior.StopEmittingAndClear);
            rain.transform.position = at;
            var shape = rain.shape;
            shape.scale = new Vector3(width,.03f,36);
            var emission = rain.emission;
            emission.rateOverTime = rate;
            var main = rain.main;
            main.startSizeX = new ParticleSystem.MinMaxCurve(thickness*.44f,thickness);
            main.startSizeY = new ParticleSystem.MinMaxCurve(length*.61f,length);
            main.startSizeZ = thickness;
            main.startColor = new Color(.89f,.93f,1f,alpha);
            main.maxParticles = Mathf.CeilToInt(rate*1.10f);
            PrefabUtility.RecordPrefabInstancePropertyModifications(rain);
            PrefabUtility.RecordPrefabInstancePropertyModifications(rain.transform);
        }
    }
}
