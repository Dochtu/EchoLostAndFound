using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Echo.M15
{
    internal static class HallSurfaces
    {
        internal const string Materials = "Assets/_Project/Art/Materials/M1_5/";
        const string Textures = "Assets/_Project/Art/Textures/M1_5/";

        internal static void Prepare()
        {
            if (!AssetDatabase.IsValidFolder(Materials.TrimEnd('/')))
                AssetDatabase.CreateFolder("Assets/_Project/Art/Materials", "M1_5");
            Surface("Terrazzo", "Terrazzo", .65f, new Color(.87f,.84f,.78f), .47f);
            Surface("Wood", "AgedWood", 1.67f, Color.white, .68f);
            Surface("Wood", "DarkWood", 1.67f, new Color(.67f,.58f,.48f), .61f);
            Surface("Lime", "OldPlaster", .66f, new Color(.81f,.76f,.66f), .48f);
            Surface("Iron","CastIron",.86f,new Color(.46f,.48f,.46f),.30f);
            Variant("Station Ivory Glaze","Grout",mat => {
                mat.SetTexture("_BaseColorMap",null);
                mat.SetColor("_BaseColor",new Color(.46f,.43f,.39f));
                mat.SetFloat("_Smoothness",.29f);
            });
            Variant("Station Aged Clear Glass","HallGlass",mat => {
                mat.SetFloat("_Smoothness", .56f);
                mat.SetColor("_BaseColor",new Color(.61f,.70f,.71f,.17f));
            });
            Variant("Station Warm Opal Diffuser","Opal",mat => {
                mat.SetColor("_BaseColor",new Color(.52f,.45f,.34f));
                mat.SetColor("_EmissiveColor",new Color(1f,.72f,.45f)*1.9f);
            });
        }

        internal static void Variant(string source, string name, Action<Material> adjust)
        {
            string path=Materials+name+".mat";
            var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!mat)
            {
                mat=new Material(AssetDatabase.LoadAssetAtPath<Material>("Assets/_Project/Art/Materials/"+source+".mat"));
                AssetDatabase.CreateAsset(mat,path);
            }
            adjust(mat);
            HDMaterial.ValidateMaterial(mat);
            EditorUtility.SetDirty(mat);
            AssetDatabase.SaveAssetIfDirty(mat);
        }

        static Texture2D Map(string asset, string kind, bool color = false)
        {
            string path = Textures + asset + "/" + kind + (kind == "Mask" ? ".png" : ".jpg");
            var importer = AssetImporter.GetAtPath(path) as TextureImporter;
            if (!importer) throw new FileNotFoundException(path);
            var type = kind == "Normal" ? TextureImporterType.NormalMap : TextureImporterType.Default;
            importer.textureType = type;
            importer.sRGBTexture = color;
            importer.mipmapEnabled = true;
            importer.streamingMipmaps = true;
            importer.anisoLevel = 8;
            importer.maxTextureSize = 2048;
            importer.wrapMode = TextureWrapMode.Repeat;
            if (AssetDatabase.WriteImportSettingsIfDirty(path))
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        internal static void Surface(string source, string name, float tiling, Color tint, float normalStrength)
        {
            string path = Materials + name + ".mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!mat)
            {
                mat = new Material(Shader.Find("HDRP/Lit"));
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.SetColor("_BaseColor", tint);
            mat.SetTexture("_BaseColorMap", Map(source,"Base",true));
            mat.SetTextureScale("_BaseColorMap", Vector2.one * tiling);
            mat.SetTexture("_NormalMap", Map(source,"Normal"));
            mat.SetTexture("_MaskMap", Map(source,"Mask"));
            if (source == "Terrazzo") mat.SetTexture("_HeightMap", Map(source,"Height"));
            mat.SetFloat("_NormalScale", normalStrength);
            if(source=="Terrazzo") mat.SetFloat("_SmoothnessRemapMax",.74f);
            mat.enableInstancing = true;
            HDMaterial.ValidateMaterial(mat);
            EditorUtility.SetDirty(mat);
            AssetDatabase.SaveAssetIfDirty(mat);
        }
    }
}

