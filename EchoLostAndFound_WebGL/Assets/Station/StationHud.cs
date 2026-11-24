using System;
using System.Collections.Generic;
using System.Linq;
using EchoLostAndFound.Dialogue;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.M2;
using EchoLostAndFound.Shared.Contracts;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace EchoStation
{
    public sealed partial class StationHud : MonoBehaviour
    {
        public const string ChineseFontPath = "Assets/_Project/Resources/M4A/StationChinese.ttf";
        [SerializeField] TMP_Text prompt, heading, description;
        [SerializeField] GameObject sheet, reticle;
        readonly List<Action> choices = new List<Action>();
        readonly List<Button> buttons = new List<Button>();
        StationInvestigation investigation;
        StationDialogueBridge bridge;
        TMP_InputField freeInput;
        Button freeSend;
        TMP_Text freeStatus;
        GameObject freeRow;
        bool turnInFlight;
        string conversation;
        string npc;
        string lastWatchPart;
        TMP_FontAsset font, runtimeFont;
        TMP_Text closeHint;
        public bool IsOpen => sheet != null && sheet.activeSelf;
        public bool IsTyping => freeInput != null && freeInput.isFocused;
        public bool Online => bridge != null && bridge.Online;
        public StationDialogueBridge Bridge => bridge;
        public bool IsFreeTextVisible => freeRow != null && freeRow.activeSelf;
        public bool WaitingForReply => turnInFlight;
        public string FreeTextStatus => freeStatus != null ? freeStatus.text : null;
        public string CurrentSpeaker => SpeakerName();
        public void SetFreeText(string text) { if (freeInput) freeInput.text = text ?? string.Empty; }

        public void Configure(TMP_Text focus, TMP_Text title, TMP_Text body, GameObject panel, GameObject crosshair)
        {
            prompt = focus; heading = title; description = body; sheet = panel; reticle = crosshair;
        }

        void Awake()
        {
            font = Resources.Load<TMP_FontAsset>("M4CChapterFont") ?? Resources.Load<TMP_FontAsset>("M4A/StationChinese SDF");
            if (font == null)
            {
                var source = Resources.Load<Font>("M4A/StationChinese");
                if (source)
                {
                    font = TMP_FontAsset.CreateFontAsset(source);
                    runtimeFont = font;
                }
            }
            foreach (var label in GetComponentsInChildren<TMP_Text>(true))
            {
                if (font) label.font = font;
                if (label.text.Contains("WASD")) label.text = "WASD 移动     鼠标 环视     E 调查     Esc 释放鼠标";
            }
            Debug.Log($"M4A font {(font ? font.name : "missing")} 怀={font && font.HasCharacter('怀', true)} 证据={font && font.HasCharacter('证', true)}");
            var panelLabels = sheet.GetComponentsInChildren<TMP_Text>(true);
            closeHint = panelLabels.FirstOrDefault(t => t != heading && t != description);
            if (closeHint)
            {
                closeHint.text = "E 返回车站";
                Position(closeHint.rectTransform, 0, -210, 260, 24);
            }
            ((RectTransform)sheet.transform).sizeDelta = new Vector2(560, 470);
            Position(heading.rectTransform, 0, 210, 520, 34);
            heading.fontSize = 26;
            Position(description.rectTransform, 0, 148, 520, 96);
            description.fontSize = 16;
            description.alignment = TextAlignmentOptions.Top;
            if (!GetComponent<GraphicRaycaster>()) gameObject.AddComponent<GraphicRaycaster>();
            // The auto-created UI module ships without an actions asset, which would leave
            // every panel button unclickable with the new Input System. Bind the defaults.
            var module = EnsureUiInputModule();
            if (module != null && module.actionsAsset == null) module.AssignDefaultActions();
            try { investigation = new StationInvestigation(); }
            catch (Exception ex) { Debug.LogError("M4A initialization: " + ex); }
            if (investigation != null)
            {
                bridge = new StationDialogueBridge(new StationApiClient(StationApiClient.ResolveBaseUrl()), investigation, this);
                bridge.Probe();
                ApplyCustodyPresentation();
            }
            BuildFreeTextControls();
            SetStatus(StatusText());
        }

        static InputSystemUIInputModule EnsureUiInputModule()
        {
            if (EventSystem.current != null)
            {
                var existing = EventSystem.current.GetComponent<InputSystemUIInputModule>();
                if (existing != null) return existing;
                if (EventSystem.current.GetComponent<BaseInputModule>() == null)
                    return EventSystem.current.gameObject.AddComponent<InputSystemUIInputModule>();
                return null;
            }
            var events = new GameObject("Station UI input", typeof(EventSystem), typeof(InputSystemUIInputModule));
            return events.GetComponent<InputSystemUIInputModule>();
        }

        static void Position(RectTransform rect, float x, float y, float w, float h)
        {
            rect.anchorMin = rect.anchorMax = new Vector2(.5f,.5f);
            rect.anchoredPosition = new Vector2(x,y);
            rect.sizeDelta = new Vector2(w,h);
        }

        void Update()
        {
            if (!IsOpen || IsTyping || Keyboard.current == null) return;
            for (int i = 0; i < choices.Count && i < 9; i++)
                if (Keyboard.current[(Key)((int)Key.Digit1 + i)].wasPressedThisFrame)
                {
                    ActivateChoice(i + 1);
                    return;
                }
        }

        public void ShowFocus(string target)
        {
            if (IsOpen || prompt == null) return;
            if (reticle) reticle.SetActive(true);
            prompt.text = target switch {
                "Click to explore" => "单击进入车站",
                "Talk to the visitor" => "E 与老周交谈",
                "Inspect pocket watch" => "E 检查怀表",
                StationTargets.LaozhouLabel => "E 与老周交谈",
                StationTargets.LinyaoLabel => "E 与林遥交谈",
                StationTargets.WatchLabel => "E 查看怀表",
                StationTargets.CabinetLabel => "E 打开维修柜",
                StationTargets.LostPackageLabel => "E 查看失物包",
                StationTargets.BinderLabel => "E 翻失物副联册",
                null or "" => "",
                _ => "E " + target
            };
        }

        /// <summary>
        /// Entry point for every scene interaction. Routing is by approved label and
        /// interaction kind (see <see cref="StationTargets"/>); the model never decides it.
        /// </summary>
        public void Interact(IInteractable target)
        {
            var resolved = StationTargets.Resolve(target?.DisplayName, target?.Kind ?? InteractionKind.Counter);
            switch (resolved)
            {
                case StationTarget.Watch: InspectWatch(); break;
                case StationTarget.Cabinet: InspectCabinet(); break;
                case StationTarget.LostPackage: InspectPackage(); break;
                case StationTarget.Binder: InspectBinder(); break;
                case StationTarget.Laozhou:
                case StationTarget.Linyao: Converse(StationTargets.NpcId(resolved)); break;
                default: InspectUnknown(target); break;
            }
        }

        bool Begin()
        {
            ClosePanel();
            sheet.SetActive(true);
            if (reticle) reticle.SetActive(false);
            prompt.text = "";
            if (investigation != null) return true;
            Page("调查暂不可用", "内容载入失败，请返回车站后重新加载。");
            return false;
        }

        void InspectUnknown(IInteractable target)
        {
            if (!Begin()) return;
            Page(string.IsNullOrEmpty(target?.DisplayName) ? "站台" : target.DisplayName, "这里暂时看不出更多。");
            AddChoice("返回车站", ClosePanel);
        }

        void Converse(string npcId)
        {
            if (!Begin()) return;
            try
            {
                RenderTurn(investigation.Dialogue.StartSession(npcId));
                if (conversation != null) bridge?.Open(npcId);
            }
            catch (GameContractException error)
            {
                Debug.LogWarning("M4A conversation rejected: " + error.Code);
                Page("暂时无法交谈", "现在不是合适的时机。");
                AddChoice("返回车站", ClosePanel);
            }
        }

        // ---- E01 停表与编号: five parts observed one by one ----

        public void InspectWatch()
        {
            if (!Begin()) return;
            ShowWatch();
        }

        void ShowWatch()
        {
            var registry = investigation.Evidence;
            var record = registry.FindVisibleRecord("E01");
            if (record != null) { Record(record); return; }
            var definition = registry.Catalog.Get("E01");
            int observed = definition.Fields.Count(field => registry.IsFieldObserved(field.FieldId));
            var body = string.IsNullOrEmpty(lastWatchPart)
                ? "表还在 A-0641 包里。盘面、背刻、编号和侧冠要分开看清。"
                : lastWatchPart + "\n已经看清 " + observed + "/" + definition.Fields.Count + " 处。";
            Page("怀表 · 逐步查看", body);
            foreach (var field in definition.Fields.OrderBy(item => registry.IsFieldObserved(item.FieldId) ? 1 : 0))
            {
                var fieldId = field.FieldId;
                bool seen = registry.IsFieldObserved(fieldId);
                AddChoice((seen ? "重看 " : "查看 ") + field.Label, () => ObserveWatchPart(fieldId));
            }
            AddChoice("返回车站", ClosePanel);
        }

        void ObserveWatchPart(string fieldId)
        {
            var registry = investigation.Evidence;
            investigation.Observe(registry.ObserveField(fieldId));
            var record = registry.FindVisibleRecord("E01");
            if (record != null) { Record(record); return; }
            var field = registry.Catalog.Get("E01").Fields.First(item => item.FieldId == fieldId);
            lastWatchPart = field.Label + "：" + field.DisplayText;
            ShowWatch();
        }

        // ---- E03 旧修表收据: package liner, gated by the observed serial number ----

        public void InspectPackage()
        {
            if (!Begin()) return;
            if (HasCustody) ShowPackageDesk();
            else ShowPackage();
        }

        void ShowPackage()
        {
            var registry = investigation.Evidence;
            var record = registry.FindVisibleRecord("E03");
            if (record != null) { Record(record); return; }
            if (!StationInvestigationGates.CanReadRepairReceipt(registry))
            {
                Page("失物包 A-0641", "包口封条已经拆开，表被取出来放在旁边。夹层里还压着纸，得先看清表背的钢印编号，才知道该查哪一档。");
                AddChoice("返回车站", ClosePanel);
                return;
            }
            Page("失物包 A-0641", "夹层里是一张旧修表收据，编号栏与表背钢印对得上。");
            AddChoice("查同号单据", () => RevealEvidence("E03", "失物包 · 旧修表收据"));
            AddChoice("返回车站", ClosePanel);
        }

        // ---- E04 指定领件联: counter binder, filed by the observed serial number ----

        public void InspectBinder()
        {
            if (!Begin()) return;
            ShowBinder();
        }

        void ShowBinder()
        {
            var registry = investigation.Evidence;
            var record = registry.FindVisibleRecord("E04");
            if (record != null) { Record(record); return; }
            if (!StationInvestigationGates.CanReadDesignatedReceipt(registry))
            {
                Page("失物副联册", "副联按编号顺序装订。要先确认怀表后盖上的钢印编号，才能翻到对应档位。");
                AddChoice("返回车站", ClosePanel);
                return;
            }
            Page("失物副联册", "按表背钢印的编号翻到对应档位，里面夹着一联指定领件。");
            AddChoice("取出指定领件联", () => RevealEvidence("E04", "副联册 · 指定领件联"));
            AddChoice("返回车站", ClosePanel);
        }

        // ---- E02 配电故障卡 + E05 拾物与检点联: one cabinet, index first ----

        public void InspectCabinet()
        {
            if (!Begin()) return;
            ShowCabinet();
        }

        void ShowCabinet()
        {
            var registry = investigation.Evidence;
            var pickup = registry.FindVisibleRecord("E05");
            if (pickup != null) { Record(pickup); return; }
            Page("维修柜", "柜面贴着配电故障卡，卡背面还有一行索引。");
            if (registry.HasEvidence("E02"))
                AddChoice("重看配电故障卡", () => Record(investigation.Evidence.FindVisibleRecord("E02")));
            else
                AddChoice("看配电故障卡正面", () => RevealEvidence("E02", "维修柜 · 配电故障卡"));
            if (investigation.IndexRead)
                AddChoice("照索引取拾物与检点联", () => RevealEvidence("E05", "维修柜 · 拾物与检点联"));
            else
                AddChoice("翻看故障卡背面的索引", ReadFaultCardIndex);
            AddChoice("返回车站", ClosePanel);
        }

        void ReadFaultCardIndex()
        {
            if (!investigation.ReadIndex())
            {
                Page("维修柜", "未能记录索引。");
                AddChoice("返回车站", ClosePanel);
                return;
            }
            Page("维修柜 · 背面索引", "卡背印着一行索引：该时段拾物联。");
            AddChoice("照索引取拾物与检点联", () => RevealEvidence("E05", "维修柜 · 拾物与检点联"));
            AddChoice("返回车站", ClosePanel);
        }

        void RevealEvidence(string evidenceId, string title)
        {
            var registry = investigation.Evidence;
            investigation.Observe(registry.ObserveFields(registry.Catalog.Get(evidenceId).RequiredFieldIds));
            var record = registry.FindVisibleRecord(evidenceId);
            if (record != null) { Record(record); return; }
            Page(title, "线索尚不完整。");
            AddChoice("返回车站", ClosePanel);
        }

        void Record(VisibleEvidenceRecord record)
        {
            if (record == null) { Page("未登记证据", "线索尚不完整。"); AddChoice("返回车站", ClosePanel); return; }
            Page(record.EvidenceId + " · " + record.Title, record.FixedText + "\n" + string.Join("。", record.ProofLimits));
            if (record.EvidenceId == "E01") AddWatchChoices();
            if (record.EvidenceId == "E03") AddChoice("翻副联册的对应档位", InspectBinder);
            AddChoice("返回车站", ClosePanel);
        }

        void RenderTurn(DialogueTurnResult turn)
        {
            conversation = turn.ConversationId;
            npc = turn.NpcId;
            if (turn.SessionStatus != DialogueSessionStatus.Open) { ClosePanel(); return; }
            RenderDialogue(string.Join("\n", turn.Segments.Select(s => s.Text)));
        }

        void RenderDialogue(string body)
        {
            Page(SpeakerName(), body);
            foreach (var option in investigation.Dialogue.GetAvailableOptions(conversation))
                AddChoice(option.Label, () => RenderTurn(investigation.Dialogue.Choose(conversation, option.OptionId)));
            foreach (var card in investigation.Evidence.GetVisibleEvidenceRecords())
                AddChoice("出示 " + card.EvidenceId + " " + card.Title, () => Present(card.EvidenceId));
            if (npc == StationTargets.NpcLinyao && investigation.Evidence.HasEvidence("E01"))
            {
                if (HasCustody) AddChoice("查看保管回执", OpenSettlement);
                else AddChoice("办理今夜暂收", () => PrepareCustody(true));
            }
        }

        string SpeakerName()
        {
            if (investigation == null || string.IsNullOrEmpty(npc)) return "对方";
            return investigation.Dialogue.Catalog.TryGet(npc, out var profile) ? profile.DisplayName : "对方";
        }

        void Present(string id)
        {
            string message;
            IReadOnlyList<string> disclosures = Array.Empty<string>();
            try
            {
                var result = investigation.Dialogue.PresentEvidence(conversation, new[] { id });
                message = string.Join("\n", result.Segments.Select(s => s.Text));
                if (message.Length == 0)
                    message = result.AlreadyPresented ? "本次交谈中已出示过这份证据。" : "证据已出示，" + SpeakerName() + "没有补充。";
                disclosures = result.TriggeredDisclosureIds ?? Array.Empty<string>();
                bridge?.MirrorPresentation(id, disclosures);
            }
            catch (GameContractException error)
            {
                Debug.LogWarning("M4A presentation rejected: " + error.Code);
                message = "现在不适合出示这份证据（" + error.Code + "）。";
            }
            RenderDialogue(message);
        }

        void Page(string title, string body)
        {
            chapterPage = false;
            choices.Clear();
            foreach (var button in buttons) button.gameObject.SetActive(false);
            if (heading) heading.text = title;
            if (description) description.text = body + (string.IsNullOrEmpty(investigation?.SaveNotice) ? "" : "\n" + investigation.SaveNotice);
            if (freeStatus) freeStatus.gameObject.SetActive(true);
            SetDialogueMode(!string.IsNullOrEmpty(conversation));
            SetStatus(StatusText());
            Debug.Log("M4A page " + title + " | " + body);
        }

        void AddChoice(string label, Action action)
        {
            int index = choices.Count;
            choices.Add(action);
            if (buttons.Count == index)
            {
                var go = new GameObject("Option " + (index + 1), typeof(RectTransform), typeof(Image), typeof(Button));
                go.transform.SetParent(sheet.transform, false);
                Position((RectTransform)go.transform, 0, 24-index*26, 500, 24);
                go.GetComponent<Image>().color = new Color(.14f,.27f,.28f,1f);
                var button = go.GetComponent<Button>();
                button.targetGraphic = go.GetComponent<Image>();
                button.onClick.AddListener(() => ActivateChoice(index+1));
                var text = Instantiate(description, go.transform);
                Position(text.rectTransform, 0, 0, 480, 22);
                text.fontSize = 15;
                text.alignment = TextAlignmentOptions.Left;
                text.raycastTarget = false;
                buttons.Add(button);
            }
            buttons[index].gameObject.SetActive(true);
            buttons[index].GetComponentInChildren<TMP_Text>().text = (index+1) + "   " + label;
            Debug.Log("M4A choice " + (index+1) + " " + label);
        }

        public void ActivateChoice(int oneBased)
        {
            if (IsOpen && oneBased > 0 && oneBased <= choices.Count)
            {
                var action = choices[oneBased-1];
                action();
            }
        }

        // ---- C3 自由输入: one line of Chinese text per turn, never a duplicate submit ----

        void BuildFreeTextControls()
        {
            var row = new GameObject("Free text", typeof(RectTransform));
            row.SetActive(false);
            var rowRect = (RectTransform)row.transform;
            rowRect.SetParent(sheet.transform, false);
            row.AddComponent<Image>().color = new Color(.07f,.15f,.16f,1f);
            row.AddComponent<RectMask2D>();
            var input = row.AddComponent<TMP_InputField>();
            Position(rowRect, -55, 78, 400, 30);
            freeInput = input;

            var text = Instantiate(description, rowRect);
            Position(text.rectTransform, 0, 0, 376, 24);
            text.fontSize = 16;
            text.alignment = TextAlignmentOptions.Left;
            text.raycastTarget = false;
            text.text = string.Empty;
            input.textComponent = text;
            input.textViewport = rowRect;
            input.lineType = TMP_InputField.LineType.SingleLine;
            input.characterLimit = 200;
            input.caretWidth = 2;
            input.onSubmit.AddListener(_ => SubmitFreeText());

            var placeholder = Instantiate(description, rowRect);
            Position(placeholder.rectTransform, 0, 0, 376, 24);
            placeholder.fontSize = 15;
            placeholder.alignment = TextAlignmentOptions.Left;
            placeholder.raycastTarget = false;
            placeholder.color = new Color(1f,1f,1f,.38f);
            placeholder.text = "点这里，用中文说出你的问题…";
            input.placeholder = placeholder;

            var send = new GameObject("Send", typeof(RectTransform));
            send.SetActive(false);
            var sendRect = (RectTransform)send.transform;
            sendRect.SetParent(sheet.transform, false);
            send.AddComponent<Image>().color = new Color(.14f,.27f,.28f,1f);
            Position(sendRect, 205, 78, 100, 30);
            freeSend = send.AddComponent<Button>();
            freeSend.targetGraphic = send.GetComponent<Image>();
            freeSend.onClick.AddListener(SubmitFreeText);
            var sendLabel = Instantiate(description, sendRect);
            Position(sendLabel.rectTransform, 0, 0, 92, 24);
            sendLabel.fontSize = 16;
            sendLabel.alignment = TextAlignmentOptions.Center;
            sendLabel.raycastTarget = false;
            sendLabel.text = "发送";

            var status = Instantiate(description, sheet.transform);
            Position(status.rectTransform, 0, 50, 520, 22);
            status.fontSize = 13;
            status.alignment = TextAlignmentOptions.Left;
            status.raycastTarget = false;
            status.color = new Color(1f,.83f,.54f,.9f);
            freeStatus = status;

            freeRow = row;
            freeRow.SetActive(false);
            if (freeSend) freeSend.gameObject.SetActive(false);
        }

        void SetDialogueMode(bool dialogue)
        {
            if (freeRow) freeRow.SetActive(dialogue);
            if (freeSend) freeSend.gameObject.SetActive(dialogue);
            if (!dialogue && freeInput) freeInput.text = string.Empty;
        }

        public void SubmitFreeText()
        {
            if (turnInFlight) return;
            if (string.IsNullOrEmpty(conversation) || investigation == null)
            {
                SetStatus("先和对方开始交谈，再输入要说的话。");
                return;
            }

            var text = freeInput != null ? (freeInput.text ?? string.Empty).Trim() : string.Empty;
            if (text.Length == 0)
            {
                SetStatus("先说点什么，再发送。");
                return;
            }
            if (text.Length > 200) text = text.Substring(0, 200);
            if (bridge == null || !bridge.Online)
            {
                Debug.Log("M4C free text offline npc=" + npc);
                SetStatus(StationDialogueBridge.OfflineTitle);
                return;
            }

            if (freeInput) freeInput.text = string.Empty;
            turnInFlight = true;
            if (freeSend) freeSend.interactable = false;
            SetStatus("正在等待对方回应…");
            var speaker = SpeakerName();
            var npcId = npc;
            Debug.Log("M4C free text submit npc=" + npcId + " chars=" + text.Length);
            var submittedSession = conversation;
            var submittedEngine = investigation.Dialogue;
            bridge.Send(npcId, text, reply =>
            {
                if (conversation != submittedSession || investigation.Dialogue != submittedEngine) return;
                turnInFlight = false;
                if (freeSend) freeSend.interactable = true;
                if (chapterPage) return;
                Debug.Log("M4C free text reply ok=" + (reply != null && reply.Ok)
                    + " source=" + (reply != null ? reply.Source : "none")
                    + " synthetic=" + (reply != null && reply.IsSynthetic)
                    + " reason=" + (reply != null ? reply.FallbackReason : "none")
                    + " failure=" + (reply != null ? reply.Failure : "none"));
                if (reply == null || !reply.Ok)
                {
                    SetStatus(reply != null && !string.IsNullOrEmpty(reply.Failure) ? reply.Failure : "对方暂时没有回应。");
                    return;
                }
                var body = "你：" + text + "\n" + speaker + "：" + reply.Text;
                if (!string.IsNullOrEmpty(reply.Attribution)) body += "\n" + reply.Attribution;
                RenderDialogue(body);
            });
        }

        void SetStatus(string text)
        {
            if (freeStatus) freeStatus.text = text ?? string.Empty;
        }

        string StatusText()
        {
            if (turnInFlight) return "正在等待对方回应…";
            if (bridge == null) return "在线对话不可用，固定剧情与证据调查仍可进行。";
            return string.IsNullOrEmpty(bridge.Notice) ? StationDialogueBridge.ProbingTitle : bridge.Notice;
        }

        public void ClosePanel()
        {
            bridge?.Close();
            turnInFlight = false;
            if (freeSend) freeSend.interactable = true;
            if (investigation != null && conversation != null)
            {
                var session = investigation.Dialogue.GetSession(conversation);
                if (session != null && session.IsOpen) investigation.Dialogue.CloseSession(conversation);
            }
            conversation = null;
            npc = null;
            lastWatchPart = null;
            choices.Clear();
            SetDialogueMode(false);
            if (sheet) sheet.SetActive(false);
            if (reticle) reticle.SetActive(true);
        }

        void OnDestroy()
        {
            bridge?.Close();
            if (investigation != null) investigation.Dialogue.ExpireOpenSessions();
            if (runtimeFont) Destroy(runtimeFont);
        }
    }
}
