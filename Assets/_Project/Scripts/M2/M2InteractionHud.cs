using UnityEngine;

namespace EchoLostAndFound.M2
{
    internal sealed class M2InteractionHud
    {
        private static readonly Color Ink = new(0.055f, 0.085f, 0.09f, 0.97f);
        private static readonly Color Paper = new(0.91f, 0.88f, 0.79f);
        private static readonly Color Brass = new(0.79f, 0.68f, 0.46f);
        private readonly Font font;
        private GUIStyle label;
        private GUIStyle close;

        public M2InteractionHud(Font font) => this.font = font;

        public void Draw(M2Player player)
        {
            label ??= new GUIStyle(GUI.skin.label) { font = font, padding = new RectOffset() };
            close ??= new GUIStyle(GUI.skin.button) { font = font, fontSize = 18 };

            float scale = Mathf.Min(Screen.width / 1280f, Screen.height / 720f);
            float width = Screen.width / scale;
            float height = Screen.height / scale;
            Matrix4x4 original = GUI.matrix;
            GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1f));
            if (player.IsInterfaceOpen)
                DrawPanel(player, width, height);
            else
                DrawPrompt(player.FocusedTarget, width, height);
            GUI.matrix = original;
        }

        private void DrawPrompt(IInteractable target, float width, float height)
        {
            Fill(new Rect(width / 2 - 2, height / 2 - 2, 4, 4), target == null ? Paper : Brass);
            if (target == null) return;
            float x = (width - 320) / 2, y = height - 116;
            Fill(new Rect(x, y, 320, 50), Ink);
            Fill(new Rect(x + 12, y + 9, 32, 32), Brass);
            Text(new Rect(x + 12, y + 9, 32, 32), "E", 21, Ink, TextAnchor.MiddleCenter);
            string verb = target.Kind == InteractionKind.Npc ? "交谈" : "查看";
            Text(new Rect(x + 58, y, 255, 50), verb + "  " + target.DisplayName, 21, Paper);
        }

        private void DrawPanel(M2Player player, float width, float height)
        {
            var target = player.ActiveTarget;
            float x = (width - 530) / 2, y = (height - 270) / 2;
            Fill(new Rect(0, 0, width, height), new Color(0.015f, 0.035f, 0.04f, 0.54f));
            Fill(new Rect(x, y, 530, 270), Ink);
            Fill(new Rect(x, y, 530, 3), Brass);
            string section = target.Kind switch
            {
                InteractionKind.Npc => "站内交谈",
                InteractionKind.Counter => "柜台查看",
                _ => "物品预览"
            };
            Text(new Rect(x + 32, y + 22, 400, 30), section, 18, Brass);
            Text(new Rect(x + 32, y + 60, 460, 60), target.DisplayName, 38, Paper);
            string message = target.Kind switch
            {
                InteractionKind.Npc => "对话位置已就绪。",
                InteractionKind.Counter => "你正在查看失物招领柜台。",
                _ => "你正在单独查看这件物品。"
            };
            Text(new Rect(x + 32, y + 130, 465, 36), message, 20, Paper);
            if (GUI.Button(new Rect(x + 32, y + 197, 177, 45), "返回探索   Esc", close))
                player.CloseInterface();
        }

        private void Text(Rect rect, string value, int size, Color color, TextAnchor alignment = TextAnchor.MiddleLeft)
        {
            label.fontSize = size;
            label.alignment = alignment;
            label.normal.textColor = color;
            GUI.Label(rect, value, label);
        }

        private static void Fill(Rect rect, Color color)
        {
            Color previous = GUI.color;
            GUI.color = color;
            GUI.DrawTexture(rect, Texture2D.whiteTexture);
            GUI.color = previous;
        }
    }
}
