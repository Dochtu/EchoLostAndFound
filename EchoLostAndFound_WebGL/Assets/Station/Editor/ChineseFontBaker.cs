using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace EchoStation
{
    /// <summary>
    /// Bakes a static TMP font asset for the Chinese HUD.
    /// A dynamic font asset would need FreeType to rasterise CJK glyphs inside the
    /// WebGL player, so the atlas is generated once in the editor instead.
    /// The character set is collected from the station HUD code and the M3-B content,
    /// which keeps the baked atlas in sync with what the station actually prints.
    /// </summary>
    public static class ChineseFontBaker
    {
        public const string SourceFont = "Assets/_Project/Resources/M4A/StationChinese.ttf";
        public const string Output = "Assets/_Project/Resources/M4A/StationChinese SDF.asset";
        const int SamplingPointSize = 36;
        const int AtlasPadding = 2;
        const int AtlasSize = 1024;

        [MenuItem("Echo/Bake Chinese font asset")]
        public static void Bake()
        {
            var font = AssetDatabase.LoadAssetAtPath<Font>(SourceFont);
            if (font == null) throw new FileNotFoundException("Missing Chinese font", SourceFont);
            string characters = CharacterSet();
            AssetDatabase.DeleteAsset(Output);
            var asset = TMP_FontAsset.CreateFontAsset(font, SamplingPointSize, AtlasPadding, GlyphRenderMode.SDFAA,
                AtlasSize, AtlasSize, AtlasPopulationMode.Dynamic, true);
            asset.name = "StationChinese SDF";
            asset.TryAddCharacters(characters, out string missing);
            Debug.Log($"FONT bake chars={characters.Length} glyphs={asset.characterTable.Count} " +
                      $"atlases={asset.atlasTextures.Length} missing={(missing.Length == 0 ? "none" : missing)}");
            asset.atlasPopulationMode = AtlasPopulationMode.Static;
            AssetDatabase.CreateAsset(asset, Output);
            for (int i = 0; i < asset.atlasTextures.Length; i++)
            {
                var texture = asset.atlasTextures[i];
                if (texture == null) continue;
                texture.name = "StationChinese Atlas " + i;
                AssetDatabase.AddObjectToAsset(texture, Output);
            }
            if (asset.material)
            {
                asset.material.name = "StationChinese Material";
                AssetDatabase.AddObjectToAsset(asset.material, Output);
            }
            EditorUtility.SetDirty(asset);
            AssetDatabase.SaveAssets();
            AssetDatabase.ImportAsset(Output, ImportAssetOptions.ForceUpdate);
            var saved = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(Output);
            int uncovered = characters.Count(c => !saved.HasCharacter(c));
            Debug.Log($"FONT saved={(saved != null)} glyphs={saved.characterTable.Count} uncovered={uncovered}");
        }

        static string CharacterSet()
        {
            var set = new SortedSet<char>();
            for (char c = (char)0x20; c < (char)0x7f; c++) set.Add(c);
            set.Add('…');
            set.Add('·');
            foreach (string path in Sources())
                foreach (char c in File.ReadAllText(path, Encoding.UTF8))
                    if (c == '\n' || c == '\r' || c == '\t' || char.IsControl(c)) continue;
                    else if (c > 0x7f) set.Add(c);
            return new string(set.ToArray());
        }

        static IEnumerable<string> Sources()
        {
            var files = new List<string>();
            foreach (string directory in new[] {"Assets/Station", "Assets/_Project/Scripts"})
                if (Directory.Exists(directory))
                    files.AddRange(Directory.GetFiles(directory, "*.cs", SearchOption.AllDirectories));
            string content = "Assets/_Project/Resources/M3B";
            if (Directory.Exists(content)) files.AddRange(Directory.GetFiles(content, "*.json", SearchOption.AllDirectories));
            return files.Where(f => !f.EndsWith(".asmdef"));
        }
    }
}
