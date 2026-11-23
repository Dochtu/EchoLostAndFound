using EchoLostAndFound.WebGL.Contracts;
using TMPro;
using UnityEngine;

namespace EchoStation
{
    public sealed class StationHud : MonoBehaviour
    {
        [SerializeField] TMP_Text prompt, heading, description;
        [SerializeField] GameObject sheet, reticle;
        StationPreview preview;
        public void Configure(TMP_Text focus, TMP_Text title, TMP_Text body, GameObject panel, GameObject crosshair)
        {
            prompt = focus; heading = title; description = body; sheet = panel; reticle = crosshair;
        }

        void Awake()
        {
            preview = JsonUtility.FromJson<StationPreview>(Resources.Load<TextAsset>("M3A/StationPreview").text);
        }

        public void ShowFocus(string target)
        {
            if (sheet.activeSelf) sheet.SetActive(false);
            if (!reticle.activeSelf) reticle.SetActive(true);
            string label = string.IsNullOrEmpty(target) ? "" : target == "Click to explore" ? target : "[E]  " + target;
            if (prompt.text != label) prompt.text = label;
        }

        public void Inspect(bool evidence)
        {
            prompt.text = "";
            reticle.SetActive(false);
            heading.text = evidence ? preview.evidence.title : preview.dialogue.speaker_name;
            description.text = evidence ? preview.evidence.observation_text : preview.dialogue.display_text;
            sheet.SetActive(true);
        }
    }
}
