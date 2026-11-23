using System;
using System.Collections.Generic;
using System.IO;
using TMPro;
using UnityEditor;
using UnityEditor.Rendering.HighDefinition;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

// The scene builder owns prefab and scene serialization. These methods supply
// the original Station meshes, surface assets and unparented model hierarchies.
public static class Stage4StationArt
{
    private const string Art = "Assets/_Project/Art/";
    private static Dictionary<string, Material> materials;
    private static Mesh oval;

    public static Dictionary<string, Material> Materials()
    {
        if (materials != null && materials["wood"] != null)
            return materials;

        materials = new Dictionary<string, Material>(StringComparer.OrdinalIgnoreCase);
        Texture2D grain = Pattern("WoodGrain", (x, y) =>
        {
            float warp = Noise(x, y, 3, 7, 191) * .023f + Noise(x, y, 7, 17, 33) * .012f;
            float broad = Mathf.Sin(2f * Mathf.PI * (y + warp) * 20f);
            float thin = Mathf.Sin(2f * Mathf.PI * (y + warp) * 79f);
            return Mathf.Clamp01(.79f + .028f * broad + .023f * thin + .13f * Noise(x, y, 4, 53, 18));
        }, revision: "wood-2");
        Texture2D mineral = Pattern("MineralMottling", (x, y) =>
            .78f + .10f * Noise(x, y, 12, 12, 53) + .045f * Noise(x, y, 32, 32, 52)
            + .034f * Noise(x, y, 181, 181, 31), revision: "mineral-2");
        Texture2D fiber = Pattern("FiberWeave", (x, y) =>
            .71f + .14f * Noise(x, y, 11, 13, 65) + .06f * Noise(x, y, 97, 99, 21)
            + .08f * Mathf.Abs(Mathf.Sin(x * 384f * Mathf.PI) * Mathf.Cos(y * 384f * Mathf.PI)));
        Texture2D scratches = Pattern("MetalWear", (x, y) =>
            .57f + .15f * Noise(x, y, 18, 22, 64) + .17f * Noise(x, y, 15, 70, 102)
            + .10f * Mathf.Pow(Noise(x, y, 3, 240, 51), 9f));
        Texture2D tiles = Pattern("HallTerrazzo", (x, y) =>
        {
            float joint = Mathf.Min(Mathf.Min(x, 1 - x), Mathf.Min(y, 1 - y));
            float aggregate = Noise(x, y, 113, 113, 127);
            float chips = aggregate > .82f ? .16f : aggregate < .20f ? -.15f : 0f;
            return Mathf.Lerp(.40f, Mathf.Clamp01(.74f + .17f * Noise(x, y, 8, 8, 15) + chips),
                Mathf.SmoothStep(0, 1, Mathf.InverseLerp(.003f, .012f, joint)));
        });
        Texture2D pavingNormal = Pattern("WetSurfaceNormal", (x, y) =>
            .42f + .32f * Noise(x, y, 9, 9, 182) + .22f * Noise(x, y, 31, 31, 14), true);
        Texture2D rippleNormal = Pattern("PuddleNormal", (x, y) =>
            .42f + .3f * Noise(x, y, 4, 7, 82) + .14f * Mathf.Sin(2 * Mathf.PI * (3 * x + 4 * y)), true);

        Add("wood", "Aged Walnut", "9B6947", .0f, .46f, grain, 1f);
        Add("darkWood", "Smoked Oak", "563F33", .0f, .36f, grain, 1.2f);
        Add("iron", "Painted Dark Iron", "344445", .32f, .39f, scratches, .7f);
        Add("brass", "Worn Brass", "C7A063", .73f, .48f, scratches);
        Add("steel", "Scored Steel", "929396", .7f, .46f, scratches);
        Add("glass", "Aged Clear Glass", "BCCED7", .0f, .84f);
        materials["glass"].SetFloat("_SurfaceType", 1);
        materials["glass"].SetColor("_BaseColor", Tint("CBE6E5", .12f));
        materials["glass"].SetFloat("_DoubleSidedEnable", 1);
        Add("crystal", "Clear Watch Crystal", "ECF4F9", .0f, .9f);
        materials["crystal"].SetFloat("_SurfaceType", 1);
        materials["crystal"].SetColor("_BaseColor", Tint("EAF0F4", .035f));
        materials["crystal"].SetFloat("_EnableBlendModePreserveSpecularLighting", 0);
        Add("plaster", "Aged Oat Plaster", "CEC2A8", .0f, .29f, mineral, .96f);
        Add("concrete", "Terrazzo Paving", "A4927B", .0f, .27f, tiles, 1.43f);
        Add("wet", "Rain Darkened Concrete", "535B61", .0f, .72f, mineral, 1.2f);
        materials["wet"].SetTexture("_NormalMap", pavingNormal);
        materials["wet"].SetFloat("_NormalScale", .32f);
        Add("puddle", "Shallow Rain Pools", "37434F", .04f, .87f, mineral, .8f);
        materials["puddle"].SetTexture("_NormalMap", rippleNormal);
        materials["puddle"].SetFloat("_NormalScale", .15f);
        materials["puddle"].SetFloat("_CoatMask", .64f);
        Add("lamp", "Warm Opal Diffuser", "FFDB98", .0f, .42f);
        materials["lamp"].SetColor("_EmissiveColor", Tint("FFC77D") * 11f);
        Add("cloth", "Charcoal Felt", "414342", .0f, .22f, fiber, 3f);
        Add("paper", "Ivory Ledger Paper", "EBDBB3", .0f, .23f, fiber, 2f);
        Add("stoneTrim", "Glazed Green Wainscot", "41625D", .0f, .57f, mineral, 2f);
        Add("ceramic", "Ivory Glaze", "DFD3A8", .0f, .57f, mineral);
        Add("tactile", "Amber Safety Paving", "BA8846", .0f, .41f, mineral, 2.1f);
        Add("rubber", "Dark Rubber", "262A2C", .0f, .36f, fiber);
        Add("bag", "Waxed Canvas", "827259", .0f, .31f, fiber, 3.5f);
        Add("jacket", "Denim Blue Twill", "47606A", .0f, .25f, fiber, 15f);
        Add("lining", "Undyed Knit", "B4A58E", .0f, .27f, fiber, 16f);
        Add("seams", "Twill Seams", "627B82", .0f, .23f);
        Add("trousers", "Charcoal Slacks", "393C44", .0f, .24f, fiber, 10f);
        Add("skin", "Sample Skin", "BA8B75", .0f, .37f);
        Add("lip", "Sample Lip Tone", "8F5D57", .0f, .33f);
        Add("hair", "Sample Dark Hair", "282425", .02f, .42f);
        Add("ink", "Dark Dial Ink", "2A2D2C", .0f, .43f);
        Add("patina", "Brass Patina", "645037", .5f, .3f, scratches);

        foreach (Material material in materials.Values)
        {
            HDShaderUtils.ResetMaterialKeywords(material);
            EditorUtility.SetDirty(material);
        }

        return materials;
    }

    private static void Add(string key, string name, string hex, float metallic, float smoothness,
        Texture texture = null, float worldScale = 0)
    {
        string path = Art + "Materials/Station " + name + ".mat";
        Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (material == null)
        {
            Shader shader = Shader.Find("HDRP/Lit");
            if (shader == null)
                throw new InvalidOperationException("HDRP/Lit is unavailable.");
            material = new Material(shader);
            AssetDatabase.CreateAsset(material, path);
        }

        material.SetColor("_BaseColor", Tint(hex));
        material.SetFloat("_Metallic", metallic);
        material.SetFloat("_Smoothness", smoothness);
        material.SetFloat("_EnableGeometricSpecularAA", 1);
        if (texture != null)
            material.SetTexture("_BaseColorMap", texture);
        if (worldScale > 0)
        {
            material.SetFloat("_UVBase", 5);
            material.SetFloat("_TexWorldScale", worldScale);
        }
        materials.Add(key, material);
    }

    private static Color Tint(string hex, float alpha = 1f)
    {
        if (!ColorUtility.TryParseHtmlString("#" + hex, out Color color))
            throw new ArgumentException("Invalid station palette entry.", nameof(hex));
        color.a = alpha;
        return color;
    }

    private static Texture2D Pattern(string name, Func<float, float, float> sample, bool normal = false,
        string revision = "1")
    {
        const int resolution = 512;
        string path = Art + "Textures/Station " + name + ".png";
        var previousImporter = AssetImporter.GetAtPath(path) as TextureImporter;
        if (previousImporter == null || previousImporter.userData != revision)
        {
            var texture = new Texture2D(resolution, resolution, TextureFormat.RGB24, false);
            var pixels = new Color32[resolution * resolution];
            for (int y = 0; y < resolution; y++)
            {
                for (int x = 0; x < resolution; x++)
                {
                    float value = sample((float)x / resolution, (float)y / resolution);
                    byte channel = (byte)Mathf.Clamp(Mathf.RoundToInt(value * 255), 0, 255);
                    pixels[y * resolution + x] = new Color32(channel, channel, channel, 255);
                }
            }
            texture.SetPixels32(pixels);
            texture.Apply();
            File.WriteAllBytes(path, texture.EncodeToPNG());
            Object.DestroyImmediate(texture);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            var importer = (TextureImporter)AssetImporter.GetAtPath(path);
            importer.userData = revision;
            importer.anisoLevel = 8;
            importer.wrapMode = TextureWrapMode.Repeat;
            if (normal)
            {
                importer.textureType = TextureImporterType.NormalMap;
                importer.convertToNormalmap = true;
                importer.heightmapScale = .055f;
            }
            importer.SaveAndReimport();
        }
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    private static float Noise(float x, float y, int cellsX, int cellsY, int seed)
    {
        float scaledX = x * cellsX;
        float scaledY = y * cellsY;
        int ix = Mathf.FloorToInt(scaledX);
        int iy = Mathf.FloorToInt(scaledY);
        float tx = Mathf.SmoothStep(0f, 1f, scaledX - ix);
        float ty = Mathf.SmoothStep(0f, 1f, scaledY - iy);
        int nextX = (ix + 1) % cellsX;
        int nextY = (iy + 1) % cellsY;
        return Mathf.Lerp(
            Mathf.Lerp(NoiseCell(ix, iy, seed), NoiseCell(nextX, iy, seed), tx),
            Mathf.Lerp(NoiseCell(ix, nextY, seed), NoiseCell(nextX, nextY, seed), tx), ty);
    }

    private static float NoiseCell(int x, int y, int seed)
    {
        unchecked
        {
            uint hash = (uint)(x * 92837111 ^ y * 689287499 ^ seed * 283923481);
            hash ^= hash >> 16;
            hash *= 0x7feb352du;
            hash ^= hash >> 15;
            return (hash & 0xffff) / 65535f;
        }
    }

    // The watch lies face up on a flat surface, with XII toward +Z.
    public static GameObject PocketWatch()
    {
        Materials();
        var root = new GameObject("PocketWatch");
        Transform body = Group(root.transform, "WatchCase");
        Shape(body, "Turned Case", "brass", Profile("Props/Station Watch Case", 96,
            Ring(-.0060f, .0001f), Ring(-.0059f, .0228f), Ring(-.0054f, .0253f),
            Ring(-.0049f, .0266f), Ring(-.0033f, .0276f), Ring(+.0029f, .0276f),
            Ring(+.0040f, .0264f), Ring(+.0046f, .0256f),
            Ring(+.0046f, .0243f), Ring(+.0019f, .0240f), Ring(+.0019f, .0001f)));
        Shape(body, "Back Cover", "brass", Profile("Props/Station Watch Back Cover", 96,
            Ring(-.0071f, .0001f), Ring(-.0071f, .0210f), Ring(-.0069f, .0230f), Ring(-.0065f, .0252f),
            Ring(-.0061f, .0257f), Ring(-.0059f, .0254f), Ring(-.0058f, .0001f)));
        Shape(body, "Back Cover Seam", "patina", RingMesh("Props/Station Cover Seam", .0251f, .00035f));
        body.Find("Back Cover Seam").localPosition = new Vector3(0, -.0059f, 0);
        Shape(body, "Bezel Inlay", "patina", RingMesh("Props/Station Bezel Inlay", .0254f, .00037f),
            new Vector3(0, .0045f, 0));

        Transform dial = Group(root.transform, "Dial");
        Shape(dial, "Enamel Dial", "ceramic", Profile("Props/Station Watch Dial", 96,
            Ring(.0029f, .0001f), Ring(.0029f, .0235f), Ring(.0031f, .0243f),
            Ring(.0035f, .0240f), Ring(.0036f, .0001f)));
        Shape(dial, "Seconds Track Inlay", "patina",
            RingMesh("Props/Station Minute Track", .02235f, .00012f), new Vector3(0, .00366f, 0));
        Shape(dial, "Minute And Hour Markers", "ink", DialMarkers(), new Vector3(0, .00364f, 0));
        string[] positionLabels = { "XII", "III", "VI", "IX" };
        for (int i = 0; i < positionLabels.Length; i++)
            WatchText(dial, positionLabels[i], positionLabels[i],
                ClockVector(i * 90) * .0175f + Vector3.up * .00382f, .0039f, true);

        TurnHand(dial, "HourHand", 278.5f, .01145f, .0012f, .00420f);
        TurnHand(dial, "MinuteHand", 102f, .0178f, .00085f, .00455f);
        Oval(dial, "Central Pin", "brass", new Vector3(0, .0047f, 0), new Vector3(.0010f, .00050f, .0010f));

        Transform cover = Group(root.transform, "Crystal");
        MeshRenderer crystal = Shape(cover, "Domed Watch Crystal", "crystal",
            Profile("Props/Station Watch Crystal", 96,
                Ring(.0049f, .0239f), Ring(.0051f, .0237f), Ring(.00558f, .0220f),
                Ring(.00591f, .0150f), Ring(.00605f, .0070f), Ring(.00609f, .0001f)));
        crystal.shadowCastingMode = ShadowCastingMode.Off;

        Transform marks = Group(root.transform, "CasebackMarkings");
        Shape(marks, "Engraving Border", "patina", RingMesh("Props/Station Caseback Engraving Border", .0185f, .00014f),
            new Vector3(0, -.00713f, 0));
        WatchText(marks, "BackEngraving_0412·0916", "0412·0916", new Vector3(0, -.00721f, .002f), .0048f, false);
        WatchText(marks, "SteelStamp_QH-283", "QH-283",
            new Vector3(0, -.00721f, -.0202f), .00265f, false);

        Transform crown = Group(root.transform, "WindingCrownDamage");
        crown.localPosition = new Vector3(0, -.0001f, .0268f);
        Transform shaft = Group(crown, "BentCrownShaft");
        shaft.localRotation = Quaternion.Euler(79f, 0, -14f);
        Shape(shaft, "Exposed Shaft", "steel", Profile("Props/Station Watch Shaft", 24,
            Ring(-.0010f, .0001f), Ring(-.0010f, .00125f), Ring(.0028f, .00125f), Ring(.0028f, .0001f)));
        Shape(shaft, "Dented Knurled Crown", "brass", Profile("Props/Station Damaged Crown", 80,
            (radius, angle, section) =>
            {
                if (radius < .001f) return radius;
                float dent = Mathf.Max(0, Mathf.Cos(angle - .95f));
                return radius * (1 - .24f * Mathf.Pow(dent, 11f))
                    + (section == 2 || section == 3 ? Mathf.Cos(angle * 20f) * .00023f : 0);
            }, Ring(.0024f, .0001f), Ring(.0024f, .0037f), Ring(.0034f, .00415f),
            Ring(.00515f, .00415f), Ring(.0060f, .0038f), Ring(.0060f, .0001f)));
        GameObject bow = Shape(crown, "Bow Loop", "brass", RingMesh("Props/Station Watch Bow", .0058f, .00066f),
            new Vector3(.0009f, .0006f, .0076f)).gameObject;
        bow.transform.localScale = new Vector3(1.16f, 1, .9f);

        Transform chain = Group(root.transform, "WatchChain");
        Mesh linkMesh = RingMesh("Props/Station Chain Link", .0028f, .00054f);
        const float linkSpacing = .00445f;
        Vector3 start = new Vector3(.004f, 0, .0385f);
        Vector3 firstControl = new Vector3(.057f, 0, .066f);
        Vector3 secondControl = new Vector3(.083f, 0, .032f);
        Vector3 end = new Vector3(.050f, 0, -.019f);
        Vector3 previous = start;
        float remaining = 0;
        int links = 0;
        for (int step = 1; step <= 256; step++)
        {
            float s = step / 256f;
            float inverse = 1 - s;
            Vector3 next = start * (inverse * inverse * inverse) + firstControl * (3 * inverse * inverse * s)
                + secondControl * (3 * inverse * s * s) + end * (s * s * s);
            Vector3 direction = next - previous;
            float advance = direction.magnitude;
            if (advance >= remaining)
            {
                Vector3 position = Vector3.Lerp(previous, next, remaining / advance);
                float tilt = links % 2 == 0 ? 12f : 51f;
                position.y = -.00615f + Mathf.Sin(tilt * Mathf.Deg2Rad) * .0027f
                    + .0014f * Mathf.Exp(-links * .55f);
                float yaw = -Mathf.Atan2(direction.z, direction.x) * Mathf.Rad2Deg;
                MeshRenderer link = Shape(chain, $"Chain Link {links + 1:00}",
                    links % 5 == 2 ? "patina" : "brass", linkMesh, position);
                link.transform.localScale = new Vector3(1.52f, 1, .84f);
                link.transform.localRotation = Quaternion.Euler(tilt, yaw, 0);
                links++;
                remaining += linkSpacing;
            }
            remaining -= advance;
            previous = next;
        }
        Shape(chain, "Chain End Clasp", "brass", RingMesh("Props/Station Chain Clasp", .0037f, .00074f),
            end + new Vector3(-.0015f, -.00585f, -.004f)).transform.localScale = new Vector3(1.6f, 1, 1);
        return root;
    }

    private static Vector3 ClockVector(float clockwiseDegrees)
    {
        float angle = clockwiseDegrees * Mathf.Deg2Rad;
        return new Vector3(Mathf.Sin(angle), 0, Mathf.Cos(angle));
    }

    private static void TurnHand(Transform dial, string name, float angle, float length, float width, float height)
    {
        string path = Art + "Props/Station Watch " + name + ".asset";
        Mesh mesh = AssetDatabase.LoadAssetAtPath<Mesh>(path);
        if (mesh == null)
        {
            mesh = new Mesh { name = name };
            mesh.vertices = new[]
            {
                new Vector3(-width * .58f, 0, -.0048f), new Vector3(-width, 0, .0031f),
                new Vector3(-width * .49f, 0, length * .7f), new Vector3(0, 0, length),
                new Vector3(width * .49f, 0, length * .7f), new Vector3(width, 0, .0031f),
                new Vector3(width * .58f, 0, -.0048f), Vector3.zero
            };
            mesh.triangles = new[] { 7, 0, 1, 7, 1, 2, 7, 2, 3, 7, 3, 4, 7, 4, 5, 7, 5, 6, 7, 6, 0 };
            mesh.uv = new Vector2[mesh.vertexCount];
            mesh.RecalculateNormals();
            AssetDatabase.CreateAsset(mesh, path);
        }
        Shape(dial, name, "ink", mesh, new Vector3(0, height, 0)).transform.localRotation =
            Quaternion.Euler(0, angle, 0);
    }

    private static void WatchText(Transform parent, string name, string value, Vector3 position, float em, bool front)
    {
        var item = new GameObject(name, typeof(RectTransform), typeof(TextMeshPro));
        Transform textRoot = item.transform;
        textRoot.SetParent(parent, false);
        textRoot.localPosition = position;
        textRoot.localRotation = Quaternion.Euler(front ? 90 : -90, 0, 0);
        textRoot.localScale = Vector3.one * (10f * em);
        TextMeshPro text = item.GetComponent<TextMeshPro>();
        text.font = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>("Assets/SourceHanSansSC-Regular SDF.asset");
        text.text = value;
        text.fontSize = 1;
        text.color = Tint(front ? "342E22" : "513921");
        text.alignment = TextAlignmentOptions.Center;
        text.textWrappingMode = TextWrappingModes.NoWrap;
        text.rectTransform.sizeDelta = new Vector2(3, .42f);
        textRoot.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;
    }

    private static Mesh DialMarkers()
    {
        const string path = Art + "Props/Station Dial Markers.asset";
        Mesh mesh = AssetDatabase.LoadAssetAtPath<Mesh>(path);
        if (mesh != null) return mesh;
        var vertices = new List<Vector3>();
        var triangles = new List<int>();
        for (int tick = 0; tick < 60; tick++)
        {
            Vector3 direction = ClockVector(tick * 6);
            bool hour = tick % 5 == 0;
            Vector3 width = Vector3.Cross(Vector3.up, direction) * (hour ? .00045f : .00016f);
            Vector3 inner = direction * (hour ? .0201f : .0212f);
            Vector3 outer = direction * .0219f;
            int index = vertices.Count;
            vertices.AddRange(new[] { inner - width, outer - width, outer + width, inner + width });
            triangles.AddRange(new[] { index, index + 1, index + 2, index, index + 2, index + 3 });
        }
        return SaveMesh(path, vertices, triangles, new Vector2[vertices.Count]);
    }

    public static GameObject Npc()
    {
        Materials();
        var root = new GameObject("NPC_VisualPlaceholder");
        Animator animator = root.AddComponent<Animator>();
        animator.applyRootMotion = false;
        Transform body = Group(root.transform, "VisualPlaceholder");

        Shape(body, "Twill Work Jacket", "jacket", Profile("Characters/Station Jacket", 40,
            Ring(.81f, .10f, .074f, .018f), Ring(.85f, .152f, .099f, .013f),
            Ring(.91f, .163f, .109f, .01f), Ring(1.00f, .151f, .111f, .014f),
            Ring(1.11f, .159f, .109f, .014f), Ring(1.22f, .182f, .108f, .011f),
            Ring(1.31f, .205f, .102f, .02f), Ring(1.355f, .205f, .084f, .024f),
            Ring(1.385f, .168f, .072f, .020f), Ring(1.412f, .077f, .058f, .011f),
            Ring(1.418f, .043f, .045f, .012f)));
        Shape(body, "Jacket Hem", "seams", Profile("Characters/Station Jacket Hem", 40,
            Ring(.852f, .148f, .098f, .015f), Ring(.864f, .155f, .103f, .014f),
            Ring(.893f, .160f, .104f, .013f), Ring(.90f, .156f, .103f, .012f)));
        Shape(body, "Trouser Waist", "trousers", Profile("Characters/Station Trouser Waist", 36,
            Ring(.755f, .013f, .038f, .021f), Ring(.787f, .125f, .087f, .016f),
            Ring(.854f, .145f, .094f, .018f), Ring(.925f, .139f, .094f, .014f),
            Ring(.93f, .005f, .005f, .014f)));
        Oval(body, "Collar Inner Knit", "lining", new Vector3(0, 1.389f, -.047f), new Vector3(.088f, .037f, .041f));
        Oval(body, "Neck", "skin", new Vector3(0, 1.437f, .009f), new Vector3(.047f, .074f, .046f));

        Mesh trouserLeg = Profile("Characters/Station Trouser Leg", 28,
            Ring(0, .03f, .035f), Ring(.012f, .064f, .063f), Ring(.15f, .074f, .073f),
            Ring(.28f, .083f, .077f, .006f), Ring(.47f, .073f, .068f, -.007f),
            Ring(.59f, .075f, .071f, -.005f), Ring(.79f, .091f, .086f),
            Ring(.94f, .098f, .09f), Ring(1, .057f, .068f));
        Mesh boot = Profile("Characters/Station Boot", 32, Ring(.018f, .022f, .040f, -.039f),
            Ring(.025f, .059f, .132f, -.047f), Ring(.052f, .063f, .134f, -.048f),
            Ring(.076f, .059f, .119f, -.044f), Ring(.098f, .056f, .088f, -.021f),
            Ring(.134f, .050f, .060f, .012f), Ring(.151f, .043f, .049f, .009f), Ring(.154f, .003f));
        Mesh sole = Profile("Characters/Station Boot Sole", 32, Ring(.001f, .015f),
            Ring(.001f, .058f, .125f, -.046f), Ring(.012f, .064f, .137f, -.049f),
            Ring(.031f, .063f, .135f, -.049f), Ring(.035f, .055f, .124f, -.048f));
        Mesh upperSleeve = Profile("Characters/Station Upper Sleeve", 28,
            Ring(-.04f, .026f), Ring(.01f, .046f, .045f), Ring(.25f, .057f, .054f, -.007f),
            Ring(.62f, .065f, .062f, .004f), Ring(.91f, .072f, .066f),
            Ring(1.04f, .056f, .055f), Ring(1.15f, .021f));
        Mesh lowerSleeve = Profile("Characters/Station Lower Sleeve", 28,
            Ring(0, .032f), Ring(.15f, .041f, .042f), Ring(.45f, .047f, .046f, -.005f),
            Ring(.74f, .057f, .049f, -.006f), Ring(.99f, .052f, .049f), Ring(1.12f, .032f));
        for (int side = -1; side <= 1; side += 2)
        {
            string suffix = side < 0 ? " Left" : " Right";
            Transform leg = Group(body, "Leg" + suffix);
            Vector3 foot = new Vector3(side * .124f, .13f, side * .052f);
            Limb(leg, "Trouser Leg", "trousers", trouserLeg, foot, new Vector3(side * .082f, .84f, .021f));
            var footPosition = new Vector3(foot.x, 0, foot.z);
            Quaternion footYaw = Quaternion.Euler(0, side * -8.5f, 0);
            Shape(leg, "Leather Boot", "iron", boot, footPosition).transform.localRotation = footYaw;
            Shape(leg, "Rubber Outsole", "rubber", sole, footPosition).transform.localRotation = footYaw;

            Transform arm = Group(body, "Arm" + suffix);
            var shoulder = new Vector3(side * .177f, 1.334f, .029f);
            var elbow = new Vector3(side * .246f, 1.093f, .032f);
            var wrist = new Vector3(side * .229f, .858f + side * .036f, -.037f + side * .019f);
            Limb(arm, "Upper Sleeve", "jacket", upperSleeve, elbow, shoulder);
            Limb(arm, "Lower Sleeve", "jacket", lowerSleeve, wrist, elbow);
            Oval(arm, "Turned Sleeve Cuff", "seams", wrist + Vector3.up * .017f, new Vector3(.038f, .027f, .035f));
            Oval(arm, "Palm", "skin", wrist + new Vector3(side * .001f, -.038f, -.002f),
                new Vector3(.025f, .051f, .019f)).transform.localRotation = Quaternion.Euler(-10, 0, side * -10);
            Oval(arm, "Thumb", "skin", wrist + new Vector3(side * -.020f, -.046f, -.016f),
                new Vector3(.010f, .029f, .009f)).transform.localRotation = Quaternion.Euler(8, 0, side * 18);
            for (int finger = 0; finger < 4; finger++)
                Oval(arm, $"Finger {finger + 1}", "skin",
                    wrist + new Vector3(side * (finger - 1.4f) * .010f, -.075f - (finger == 1 ? .005f : 0), -.010f),
                    new Vector3(.0055f, .021f - finger * .0023f, .0082f));

            Oval(body, "Lapelled Edge" + suffix, "seams", new Vector3(side * .047f, 1.353f, -.063f),
                new Vector3(.019f, .063f, .012f)).transform.localRotation = Quaternion.Euler(-15, 0, side * -23);
            Oval(body, "Welt Pocket" + suffix, "seams", new Vector3(side * .104f, .991f, -.078f),
                new Vector3(.014f, .05f, .0065f)).transform.localRotation = Quaternion.Euler(0, side * -19, side * -29);
        }

        Oval(body, "Button Placket", "seams", new Vector3(0, 1.132f, -.0984f), new Vector3(.0081f, .209f, .0075f));
        for (int i = 0; i < 5; i++)
            Oval(body, $"Jacket Button {i + 1}", "rubber", new Vector3(0, .958f + i * .076f, -.1080f),
                new Vector3(.007f, .007f, .0030f));

        Transform head = Group(body, "Head");
        head.localPosition = new Vector3(0, 1.46f, .005f);
        head.localRotation = Quaternion.Euler(3, 6, -3);
        Shape(head, "Face And Cranium", "skin", Profile("Characters/Station Head", 48,
            Ring(0, .022f, .018f, -.022f), Ring(.019f, .047f, .047f, -.039f),
            Ring(.042f, .068f, .059f, -.029f), Ring(.070f, .078f, .074f, -.015f),
            Ring(.099f, .081f, .084f, -.002f), Ring(.126f, .078f, .082f, .001f),
            Ring(.153f, .080f, .084f, .005f), Ring(.185f, .075f, .077f, .012f),
            Ring(.213f, .059f, .058f, .016f), Ring(.229f, .014f, .022f, .013f), Ring(.232f, .001f)));
        Shape(head, "Shaped Hair Cap", "hair", ProfileWithHeight("Characters/Station Hair Cap", 42,
            (angle, height, section) =>
                height + (section <= 2 ? Mathf.Max(0, -Mathf.Cos(angle)) * (3 - section) * .018f : 0),
            Ring(.103f, .060f, .066f, .014f), Ring(.153f, .082f, .086f, .011f),
            Ring(.190f, .084f, .087f, .012f), Ring(.216f, .071f, .071f, .016f),
            Ring(.24f, .049f, .050f, .015f), Ring(.248f, .013f, .017f, .016f),
            Ring(.25f, .001f, .001f, .016f)));
        Oval(head, "Side Swept Fringe", "hair", new Vector3(-.028f, .175f, -.068f),
            new Vector3(.055f, .030f, .025f)).transform.localRotation = Quaternion.Euler(0, -10, -21);
        Oval(head, "Nose Bridge", "skin", new Vector3(0, .109f, -.081f), new Vector3(.012f, .031f, .012f));
        Oval(head, "Nose Tip", "skin", new Vector3(0, .091f, -.095f), new Vector3(.015f, .011f, .012f));
        Oval(head, "Mouth", "lip", new Vector3(0, .055f, -.085f), new Vector3(.025f, .0039f, .0045f));
        for (int side = -1; side <= 1; side += 2)
        {
            string suffix = side < 0 ? " Left" : " Right";
            Oval(head, "Ear" + suffix, "skin", new Vector3(side * .077f, .103f, .007f), new Vector3(.016f, .029f, .017f));
            Oval(head, "Ear Fold" + suffix, "lip", new Vector3(side * .087f, .104f, -.003f), new Vector3(.005f, .014f, .007f));
            float eyeX = side * .028f;
            Oval(head, "Eye Socket" + suffix, "lip", new Vector3(eyeX, .121f, -.075f), new Vector3(.019f, .0083f, .0078f));
            Oval(head, "Eye White" + suffix, "ceramic", new Vector3(eyeX, .121f, -.079f), new Vector3(.0148f, .0059f, .0051f));
            Oval(head, "Iris" + suffix, "ink", new Vector3(eyeX - .002f, .121f, -.084f), new Vector3(.0062f, .006f, .0028f));
            Oval(head, "Brow" + suffix, "hair", new Vector3(eyeX, .140f, -.075f),
                new Vector3(.021f, .0035f, .0047f)).transform.localRotation = Quaternion.Euler(0, 0, side * -9);
        }
        Group(root.transform, "ControllerMount");
        return root;
    }

    private static void Limb(Transform parent, string name, string material, Mesh mesh, Vector3 from, Vector3 to)
    {
        Vector3 span = to - from;
        Transform limb = Shape(parent, name, material, mesh, from).transform;
        limb.localRotation = Quaternion.FromToRotation(Vector3.up, span.normalized);
        limb.localScale = new Vector3(1, span.magnitude, 1);
    }

    private static Transform Group(Transform parent, string name)
    {
        var item = new GameObject(name);
        item.transform.SetParent(parent, false);
        return item.transform;
    }

    private static MeshRenderer Shape(Transform parent, string name, string material, Mesh mesh, Vector3 position = default)
    {
        Transform item = Group(parent, name);
        item.localPosition = position;
        item.gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
        var renderer = item.gameObject.AddComponent<MeshRenderer>();
        renderer.sharedMaterial = materials[material];
        return renderer;
    }

    private static MeshRenderer Oval(Transform parent, string name, string material, Vector3 position, Vector3 radii)
    {
        if (oval == null)
        {
            Vector4[] sections = new Vector4[19];
            for (int i = 0; i < sections.Length; i++)
            {
                float angle = Mathf.PI * i / (sections.Length - 1);
                sections[i] = Ring(Mathf.Cos(angle) * -1, Mathf.Max(Mathf.Sin(angle), .00001f));
            }
            oval = Profile("Station Soft Ellipsoid", 32, sections);
        }
        MeshRenderer renderer = Shape(parent, name, material, oval, position);
        renderer.transform.localScale = radii;
        return renderer;
    }

    private static Vector4 Ring(float height, float radius) => Ring(height, radius, radius, 0);

    private static Vector4 Ring(float height, float radiusX, float radiusZ, float centerZ = 0) =>
        new Vector4(radiusX, height, radiusZ, centerZ);

    private static Mesh RingMesh(string path, float radius, float thickness)
    {
        var rings = new Vector4[13];
        for (int i = 0; i < rings.Length; i++)
        {
            float angle = i * 2f * Mathf.PI / (rings.Length - 1);
            rings[i] = Ring(-Mathf.Cos(angle) * thickness, radius + Mathf.Sin(angle) * thickness);
        }
        return Profile(path, radius < .01f ? 32 : 72, rings);
    }

    private static Mesh Profile(string path, int slices, params Vector4[] rings) =>
        Profile(path, slices, null, null, rings);

    private static Mesh Profile(string path, int slices, Func<float, float, int, float> radius, params Vector4[] rings) =>
        Profile(path, slices, radius, null, rings);

    private static Mesh ProfileWithHeight(string path, int slices, Func<float, float, int, float> height,
        params Vector4[] rings) => Profile(path, slices, null, height, rings);

    private static Mesh Profile(string name, int slices, Func<float, float, int, float> radius,
        Func<float, float, int, float> height, Vector4[] rings)
    {
        string path = Art + (name.Contains("/") ? name : "Props/" + name) + ".asset";
        Mesh existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
        if (existing != null) return existing;
        var vertices = new List<Vector3>();
        var uv = new List<Vector2>();
        var triangles = new List<int>();
        int stride = slices + 1;
        for (int ring = 0; ring < rings.Length; ring++)
        {
            Vector4 section = rings[ring];
            for (int slice = 0; slice <= slices; slice++)
            {
                float fraction = (float)slice / slices;
                float angle = fraction * Mathf.PI * 2f;
                float radiusX = radius == null ? section.x : radius(section.x, angle, ring);
                float radiusZ = radius == null ? section.z : radius(section.z, angle, ring);
                float y = height == null ? section.y : height(angle, section.y, ring);
                vertices.Add(new Vector3(Mathf.Sin(angle) * radiusX, y, section.w + Mathf.Cos(angle) * radiusZ));
                uv.Add(new Vector2(fraction, (float)ring / (rings.Length - 1)));

                if (ring + 1 == rings.Length || slice == slices) continue;
                int current = ring * stride + slice;
                triangles.AddRange(new[] { current, current + 1, current + stride,
                    current + 1, current + stride + 1, current + stride });
            }
        }

        Mesh mesh = SaveMesh(path, vertices, triangles, uv);
        Vector3[] normals = mesh.normals;
        for (int ring = 0; ring < rings.Length; ring++)
        {
            int first = ring * stride;
            int last = first + slices;
            Vector3 seam = (normals[first] + normals[last]).normalized;
            normals[first] = seam;
            normals[last] = seam;
        }
        mesh.normals = normals;
        mesh.RecalculateTangents();
        EditorUtility.SetDirty(mesh);
        return mesh;
    }

    private static Mesh SaveMesh(string path, List<Vector3> vertices, List<int> triangles, IReadOnlyCollection<Vector2> uv)
    {
        var mesh = new Mesh { name = Path.GetFileNameWithoutExtension(path) };
        mesh.SetVertices(vertices);
        mesh.SetTriangles(triangles, 0);
        mesh.SetUVs(0, new List<Vector2>(uv));
        mesh.RecalculateNormals();
        mesh.RecalculateTangents();
        AssetDatabase.CreateAsset(mesh, path);
        return mesh;
    }
}
