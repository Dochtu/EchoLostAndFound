using EchoLostAndFound.Shared.Contracts;

namespace EchoStation
{
    /// <summary>
    /// Chapter-01 scene gates. The implementation map ties these to what the player has
    /// actually looked at, never to the model or to a cutscene: E03/E04 need the watch
    /// serial number observed first, and E05 needs the fault card's back-page index.
    /// Pure logic so EditMode tests can prove the rules without loading the scene.
    /// </summary>
    public static class StationInvestigationGates
    {
        public const string SerialNumberField = "watch.serial_number";
        public const string EngravingField = "watch.back_engraving";

        /// <summary>E03 旧修表收据 sits in the A-0641 package's liner; the serial number picks the file.</summary>
        public static bool CanReadRepairReceipt(IEvidenceStateView evidence)
        {
            return evidence != null && evidence.IsFieldObserved(SerialNumberField);
        }

        /// <summary>E04 指定领件联 is filed by number, so the same serial number opens the direct path.</summary>
        public static bool CanReadDesignatedReceipt(IEvidenceStateView evidence)
        {
            return evidence != null && evidence.IsFieldObserved(SerialNumberField);
        }

        /// <summary>E05 拾物与检点联 is only findable after the fault card's back index is read.</summary>
        public static bool CanReadPickupInspection(bool faultCardIndexRead)
        {
            return faultCardIndexRead;
        }

        /// <summary>林遥 only compares the engraving once the player has read it on the watch.</summary>
        public static bool CanAskEngraving(IEvidenceStateView evidence)
        {
            return evidence != null && evidence.IsFieldObserved(EngravingField);
        }
    }
}
