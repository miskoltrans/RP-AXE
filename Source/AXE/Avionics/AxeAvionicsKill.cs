using System;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Permanent avionics shutdown — the shared half of RP-1's "Disable Avionics permanently"
    /// (<c>ModuleAvionics.dead</c> / <c>KillEvent</c> / <c>KillAntennasIfLastAvionicsDead</c>), used by
    /// both <see cref="ModuleAxeAvionics"/> and <see cref="ModuleAxeFixedAvionics"/>.
    ///
    /// WHY IT EXISTS AT ALL, i.e. why a Shutdown toggle is not enough: shutting an avionics unit down
    /// still leaves it drawing its hibernate-depth trickle forever, and a probe whose mission is over is
    /// a permanent line item on a vessel's power budget. The kill is the one-way version — zero draw, no
    /// command, no control — and being irreversible is the point: it is the choice to write the spacecraft
    /// off rather than nurse it.
    ///
    /// THE ANTENNA CLAUSE is not a flourish, it is what makes the kill mean anything. RP-1's own note:
    /// disabling ModuleCommand is not sufficient, because under Kerbalism a vessel with a live antenna
    /// still has comms and is still controllable. So when the LAST live avionics unit on a vessel dies,
    /// every RealAntennas antenna on it is permanently shut down too. Without this the "dead" probe keeps
    /// flying.
    ///
    /// RealAntennas is reached by REFLECTION rather than an assembly reference: it is not in AXE.csproj
    /// and adding it would make AXE.dll fail to load outright wherever RealAntennas is absent. The two
    /// members bound here (<c>Condition</c>, a public KSPField of enum type <c>AntennaCondition</c>, and
    /// <c>PermanentShutdownAction(KSPActionParam)</c>) were verified against the shipped
    /// RealAntennas.dll. Per docs/BUG-CLASSES.md, a name that stops resolving must never fail SILENTLY —
    /// a missing member logs once at error level instead of quietly turning the antenna clause into a
    /// no-op that nobody would notice until a "dead" probe was still answering.
    /// </summary>
    internal static class AxeAvionicsKill
    {
        const string AntennaModuleName = "ModuleRealAntenna";

        /// <summary>
        /// Cut the part's command function. Ported verbatim from RP-1's <c>ModuleAvionics
        /// .DisableModuleCommand()</c>: all three enable flags, because KSP reads different ones on
        /// different paths, plus the part's own control-source level.
        /// </summary>
        public static void DisableModuleCommand(Part part)
        {
            ModuleCommand command = part?.FindModuleImplementing<ModuleCommand>();
            if (command == null) return;
            command.enabled = false;
            command.isEnabled = false;
            command.moduleIsEnabled = false;
            part.isControlSource = Vessel.ControlLevel.NONE;
        }

        /// <summary>
        /// Can this vessel still be commanded by anything? Both avionics module types count — a named bus
        /// keeps a procedural core's vessel alive and vice versa — AND SO DOES A BARE COMMAND PART.
        ///
        /// That last clause is a DELIBERATE DEVIATION from RP-1, forced by a coverage difference. RP-1
        /// counts only <c>ModuleAvionics</c>, which is safe there because RP-1's Avionics.cfg injects one
        /// onto every ModuleCommand part it doesn't already cover, crewed included — so "no live avionics"
        /// and "no command at all" are the same statement. AXE's blanket rule
        /// (`design/Parts/AxeFixedAvionics.cfg`, the `:FINAL` catch-all) is scoped to UNCREWED command
        /// modules (`~minimumCrew[>0]`), so a crewed pod outside the 38 authored entries carries no AXE
        /// avionics module at all. Porting RP-1's check literally would therefore kill the antennas of a
        /// vessel a crewed pod is still flying. AXE already treats a bare command source as authoritative —
        /// it is exactly the `bypass` case in <see cref="AxeControlLockerUtils.ShouldLock"/> — so this uses
        /// the same rule, launch-clamp exclusion included.
        /// </summary>
        public static bool VesselStillCommandable(Vessel v)
        {
            // Parts can be null/empty for a frame during scene changes and vessel splits
            // (docs: ksp-lazily-loaded-empty-not-absent). Treat "can't tell" as "still commandable" —
            // the failure we must not have is killing a live vessel's antennas on a bad read.
            if (v == null || v.parts == null || v.parts.Count == 0) return true;

            for (int i = 0; i < v.parts.Count; i++)
            {
                Part p = v.parts[i];
                if (p == null) continue;

                bool hasAvionics = false, hasCommand = false, isClamp = false;
                for (int j = 0; j < p.Modules.Count; j++)
                {
                    PartModule m = p.Modules[j];
                    if (m is ModuleAxeAvionics core)
                    {
                        hasAvionics = true;
                        if (!core.dead) return true;
                    }
                    else if (m is ModuleAxeFixedAvionics fixedUnit)
                    {
                        hasAvionics = true;
                        if (!fixedUnit.dead) return true;
                    }
                    else if (m is ModuleCommand) hasCommand = true;
                    else if (m is LaunchClamp) isClamp = true;
                }

                // A command source AXE never gave avionics to (a crewed pod outside the authored table)
                // still flies the vessel. A pad stand's ModuleCommand does not — same carve-out ShouldLock
                // makes, or every ModularLaunchPads structure would count as a command source.
                if (hasCommand && !hasAvionics && !isClamp) return true;
            }
            return false;
        }

        /// <summary>
        /// RP-1's <c>KillAntennasIfLastAvionicsDead</c>: once nothing on the vessel can command it, take
        /// the antennas down permanently too, or Kerbalism-side comms keep the vessel controllable.
        /// </summary>
        public static void KillAntennasIfLastAvionicsDead(Vessel v)
        {
            if (v == null || VesselStillCommandable(v)) return;
            if (v.parts == null) return;

            for (int i = 0; i < v.parts.Count; i++)
            {
                Part p = v.parts[i];
                if (p == null) continue;
                for (int j = 0; j < p.Modules.Count; j++)
                {
                    PartModule m = p.Modules[j];
                    if (m == null || m.GetType().Name != AntennaModuleName) continue;
                    PermanentlyShutDown(m);
                }
            }
        }

        // ---- RealAntennas reflection bridge -------------------------------------------------------
        static Type _antennaType;
        static FieldInfo _conditionField;
        static MethodInfo _shutdownMethod;
        static bool _bindLogged;

        static bool Bind(Type t)
        {
            if (_antennaType == t && _conditionField != null && _shutdownMethod != null) return true;

            _antennaType = t;
            _conditionField = t.GetField("Condition", BindingFlags.Public | BindingFlags.Instance);
            _shutdownMethod = t.GetMethod("PermanentShutdownAction",
                                          BindingFlags.Public | BindingFlags.Instance,
                                          null, new[] { typeof(KSPActionParam) }, null);

            if (_conditionField != null && _shutdownMethod != null) return true;

            // Fail LOUD, once. A silently unbound name here would leave a killed probe still flying.
            if (!_bindLogged)
            {
                _bindLogged = true;
                Debug.LogError($"[AXE][Avionics] Could not bind {t.FullName}: "
                    + $"Condition field {(_conditionField == null ? "MISSING" : "ok")}, "
                    + $"PermanentShutdownAction(KSPActionParam) {(_shutdownMethod == null ? "MISSING" : "ok")}. "
                    + "Antennas will NOT be shut down when the last avionics unit is permanently disabled.");
            }
            return false;
        }

        static void PermanentlyShutDown(PartModule antenna)
        {
            if (!Bind(antenna.GetType())) return;
            try
            {
                // RP-1 skips antennas already Disabled; PermanentShutdown is skipped too since re-running
                // it only re-fires onVesselWasModified and a CommNet antenna rediscovery for no change.
                string condition = _conditionField.GetValue(antenna)?.ToString();
                if (condition == "Disabled" || condition == "PermanentShutdown") return;
                _shutdownMethod.Invoke(antenna, new object[] { null });
            }
            catch (Exception e)
            {
                Debug.LogError($"[AXE][Avionics] Permanent antenna shutdown failed on {antenna.part?.partInfo?.name}: {e}");
            }
        }

        // ---- shared confirmation dialog ----------------------------------------------------------
        /// <summary>
        /// One-way action, so it asks first. Same shape as RP-1's KillEvent dialog and AXE's own
        /// <see cref="ModuleRangeSafety"/>.
        /// </summary>
        public static void ConfirmKill(Callback onYes)
        {
            var options = new DialogGUIBase[]
            {
                new DialogGUIButton("Yes", onYes),
                new DialogGUIButton("No", () => { })
            };
            var dialog = new MultiOptionDialog("AxeConfirmDisableAvionics",
                "Permanently disable this avionics unit?\n\n"
                + "It will stop drawing power, but it will never provide command or control again, and this "
                + "cannot be undone. If it is the last live avionics unit on the vessel, every antenna on "
                + "board is permanently shut down with it.",
                "Disable Avionics", HighLogic.UISkin, 300, options);
            PopupDialog.SpawnPopupDialog(dialog, true, HighLogic.UISkin);
        }
    }
}
