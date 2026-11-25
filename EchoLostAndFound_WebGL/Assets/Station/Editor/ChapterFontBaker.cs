using System;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace EchoStation
{
    public static class ChapterFontBaker
    {
        const string Output = "Assets/_Project/Resources/M4CChapterFont.asset";

        public static void Bake()
        {
            var original = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(ChineseFontBaker.Output);
            var source = AssetDatabase.LoadAssetAtPath<Font>(ChineseFontBaker.SourceFont);
            var characters = File.ReadAllText("Assets/Station/StationChapterHud.cs")
                + File.ReadAllText("Assets/Station/StationHud.cs")
                + File.ReadAllText("Assets/Station/StationInvestigation.cs");
            var additional = characters.Where(c => c > 127 && !original.HasCharacter(c)).Distinct().OrderBy(c => c);
            var required = string.Concat(additional);
            var existing = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(Output);
            if (existing != null)
            {
                if (required.All(c => existing.HasCharacter(c))) return;
                throw new InvalidOperationException("Existing chapter font needs additional glyphs.");
            }

            var asset = TMP_FontAsset.CreateFontAsset(source, 36, 2, GlyphRenderMode.SDFAA, 512, 512,
                AtlasPopulationMode.Dynamic, true);
            asset.name = "M4CChapterFont";
            if (required.Length > 0 && !asset.TryAddCharacters(required, out string missing))
                throw new InvalidOperationException("Missing chapter glyphs: " + missing);
            asset.fallbackFontAssetTable = new System.Collections.Generic.List<TMP_FontAsset> {original};
            asset.atlasPopulationMode = AtlasPopulationMode.Static;
            AssetDatabase.CreateAsset(asset, Output);
            foreach (var atlas in asset.atlasTextures)
            {
                atlas.name = "Chapter glyphs";
                AssetDatabase.AddObjectToAsset(atlas, asset);
            }
            asset.material.name = "Chapter glyphs";
            AssetDatabase.AddObjectToAsset(asset.material, asset);
            EditorUtility.SetDirty(asset);
            AssetDatabase.SaveAssets();
            Debug.Log("M4C chapter font added " + required.Length + " glyphs; original atlas is the fallback.");
        }
    }
}
