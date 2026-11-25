using System.Linq;
using EchoLostAndFound.M2;
using UnityEngine;

namespace EchoStation
{
    public sealed partial class StationHud
    {
        bool chapterPage;
        bool HasCustody => !string.IsNullOrEmpty(investigation.Custody);

        const string BagReceipt = "A-0641　怀表已装袋待核。保管地点：失物招领处。";
        const string HandoverReceipt = "A-0641　林遥今夜暂收怀表，留站等候结案。结案时可由她签收，或去名公开后由她签收，也可按她今夜授权交回受限封存。";

        void ChapterPage(string title, string text)
        {
            Page(title, text);
            chapterPage = true;
            SetDialogueMode(false);
            if (freeStatus) freeStatus.gameObject.SetActive(false);
        }

        // Evidence stays accessible from the staffed package desk after the physical watch is put away.
        void ApplyCustodyPresentation()
        {
            foreach (var target in FindObjectsByType<M2Interactable>(FindObjectsSortMode.None))
            {
                if (target.DisplayName != StationTargets.WatchLabel) continue;
                foreach (var mesh in target.GetComponentsInChildren<Renderer>(true))
                    mesh.enabled = !HasCustody;
                foreach (var hit in target.GetComponentsInChildren<Collider>(true))
                    hit.enabled = !HasCustody;
            }
        }

        void ShowPackageDesk()
        {
            ChapterPage("失物包 A-0641", investigation.Custody == "sealed_pending" ? BagReceipt : HandoverReceipt);
            AddChoice("查看保管回执", OpenSettlement);
            AddChoice("查阅怀表记录", ShowWatch);
            AddChoice("查看包内夹层", ShowPackage);
            AddChoice("返回车站", ClosePanel);
        }

        void AddWatchChoices()
        {
            if (HasCustody) AddChoice("查看保管回执", OpenSettlement);
            else AddChoice("装袋待核", () => PrepareCustody(false));
            if (!investigation.OwnerProven) AddChoice("核对怀表原主", ShowReasoning);
        }

        void ShowReasoning()
        {
            if (!investigation.Evidence.HasEvidence("E03") || !investigation.Evidence.HasEvidence("E04"))
            {
                ChapterPage("核对怀表原主", "请查齐同号修表收据和指定领件联，再与怀表记录核对。");
            }
            else
            {
                ChapterPage("核对怀表原主", "对照已登记的怀表、修表收据和指定领件联，选择你的结论。");
                AddChoice("老周是怀表原主", () => SubmitReasoning(false));
                AddChoice("原主沈禾，今可由她书面指定的林遥领件", () => SubmitReasoning(true));
            }
            AddChoice("返回怀表记录", ShowWatch);
        }

        void SubmitReasoning(bool correct)
        {
            bool passed = investigation.SubmitOwner(correct);
            ChapterPage("核对怀表原主", passed ? "已核：原主沈禾，今可由她书面指定的林遥领件。" :
                correct ? "尚未记录核对结果。" : "拾表人与原主不同。请再核对收据与指定领件联。");
            AddChoice("返回怀表记录", ShowWatch);
        }

        void PrepareCustody(bool handover)
        {
            if (handover && (!investigation.CanHandover || npc != StationTargets.NpcLinyao))
            {
                ChapterPage("今夜暂收条", !investigation.OwnerProven
                    ? "请先在怀表记录中核对原主和领件人。"
                    : "请向林遥本人出示修表收据与指定领件联，完成核对。");
            }
            else
            {
                ChapterPage(handover ? "今夜暂收条" : "装袋待核", handover
                    ? HandoverReceipt + "\n确认后登记今夜暂收。"
                    : "A-0641　将怀表放回带案号的软衬袋，由招领处保管，领取资格可继续核对。");
                AddChoice(handover ? "确认暂收并登记" : "确认装袋并登记", () => ConfirmCustody(handover));
            }
            AddChoice("取消，返回调查", ClosePanel);
        }

        void ConfirmCustody(bool handover)
        {
            if (investigation.CommitCustody(handover, npc, true))
            {
                ApplyCustodyPresentation();
                OpenSettlement();
                return;
            }
            ChapterPage("未完成交接", "请核对当前调查记录及存档状态。");
            AddChoice("返回调查", ClosePanel);
        }

        void OpenSettlement()
        {
            if (!HasCustody || !Begin()) return;
            string receipt = investigation.Custody == "sealed_pending" ? BagReceipt : HandoverReceipt;
            string acquired = string.Join("、", investigation.Evidence.AcquiredEvidenceIds);
            var missing = new[] {"E01", "E02", "E03", "E04", "E05"}.Where(id => !investigation.Evidence.HasEvidence(id));
            string remaining = string.Join("、", missing);
            ChapterPage("第一章调查交接", receipt + "\n已入档：" + acquired + "　待查：" + (remaining.Length == 0 ? "无" : remaining)
                + "\n原主核对：" + (investigation.OwnerProven ? "已核" : "待核") + "　第二章资格已开放。");
            AddChoice("继续调查", ClosePanel);
            AddChoice("读取交接前检查点", AskRestore);
            AddChoice("返回菜单", ShowChapterMenu);
        }

        void AskRestore()
        {
            ChapterPage("读取交接前检查点", "读取后将恢复到确认保管选择之前。交接以后的调查记录也会回到该时点。");
            AddChoice("确认读取", () =>
            {
                if (investigation.RestorePreChoice())
                {
                    ApplyCustodyPresentation();
                    ClosePanel();
                    return;
                }
                ChapterPage("读取失败", "当前进度已保留。");
                AddChoice("返回交接页", OpenSettlement);
            });
            AddChoice("取消", OpenSettlement);
        }

        void ShowChapterMenu()
        {
            ChapterPage("回声失物招领处", "停走的怀表　第一章调查已完成");
            AddChoice("继续调查", ClosePanel);
            AddChoice("查看第一章交接", OpenSettlement);
            AddChoice("读取交接前检查点", AskRestore);
        }
    }
}
