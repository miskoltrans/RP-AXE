using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace RPAxe.Bridge
{
    /// <summary>
    /// Reflection binding to Kerbal Alarm Clock, plus a fallback onto the stock alarm clock.
    ///
    /// Reflection rather than an assembly reference because KAC is optional: a hard reference
    /// makes AXE.dll fail to load outright on an install without it, and a plugin that does not
    /// load takes the tech tree with it.
    ///
    /// This is deliberately a fraction of RP-1's <c>KACWrapper.cs</c> — it binds only what the
    /// bridge writes (create, list, delete, and the handful of fields worth setting). If AXE ever
    /// grows a career feature that needs alarms properly, port RP-1's wrapper wholesale rather
    /// than growing this one; it already handles the events and the version gate.
    ///
    /// One thing worth stating because it is not obvious from the field names: KAC's alarm-type
    /// and alarm-action fields are enums declared inside KAC's own assembly, so a value cannot be
    /// passed as an int chosen from a list written here — such a list silently drifts when KAC
    /// reorders its enum. Names are resolved against the LIVE enum type instead, and an unknown
    /// name is reported with the full set of valid ones rather than defaulted.
    /// </summary>
    public static class AxeKac
    {
        private const string Tag = "[AXE][Bridge][KAC] ";

        private static bool _tried;
        private static Type _kacType;                  // KerbalAlarmClock.KerbalAlarmClock
        private static Type _alarmType;                // KerbalAlarmClock.KACAlarm
        private static object _instance;               // KerbalAlarmClock.APIInstance
        private static FieldInfo _apiReady;            // static bool APIReady
        private static FieldInfo _alarmsField;         // static KACAlarmList alarms
        private static MethodInfo _createAlarm;        // string CreateAlarm(int type, string name, double ut)
        private static MethodInfo _deleteAlarm;        // bool DeleteAlarm(string id)

        private static FieldInfo _fID, _fName, _fNotes, _fTypeOfAlarm, _fVesselID,
                                 _fMargin, _fAction, _fRemaining, _fXferOrigin, _fXferTarget;
        private static PropertyInfo _pAlarmTimeUT;

        /// <summary>Why the binding failed, for the client. Null once bound.</summary>
        public static string Unavailable { get; private set; }

        public static bool Bind()
        {
            if (_tried) return _kacType != null && Ready;
            _tried = true;
            try
            {
                // TypeOperation walks every loaded assembly's types. Matching on the full name
                // rather than the assembly name matters here: KAC is a normal .dll, but the
                // habit of trusting assembly names has bitten this project before (Kerbalism
                // ships as a .kbin and answers name checks with the inverse of the truth).
                AssemblyLoader.loadedAssemblies.TypeOperation(t =>
                {
                    if (t.FullName == "KerbalAlarmClock.KerbalAlarmClock") _kacType = t;
                    else if (t.FullName == "KerbalAlarmClock.KACAlarm") _alarmType = t;
                });
                if (_kacType == null || _alarmType == null)
                {
                    Unavailable = "Kerbal Alarm Clock is not installed (no KerbalAlarmClock.KerbalAlarmClock type)";
                    return false;
                }

                _apiReady = _kacType.GetField("APIReady", BindingFlags.Public | BindingFlags.Static);
                FieldInfo inst = _kacType.GetField("APIInstance", BindingFlags.Public | BindingFlags.Static);
                _instance = inst != null ? inst.GetValue(null) : null;
                if (_instance == null)
                {
                    // KAC v2 dropped APIInstance. Say which it is; "KAC not found" would be a lie
                    // that sends someone off to reinstall a mod they already have.
                    Unavailable = "KAC is installed but exposes no APIInstance (KAC v2?); "
                                + "the bridge needs KAC v3's API";
                    return false;
                }

                _alarmsField = _kacType.GetField("alarms", BindingFlags.Public | BindingFlags.Static);
                _createAlarm = _kacType.GetMethod("CreateAlarm", BindingFlags.Public | BindingFlags.Instance);
                _deleteAlarm = _kacType.GetMethod("DeleteAlarm", BindingFlags.Public | BindingFlags.Instance);
                if (_createAlarm == null)
                {
                    Unavailable = "KAC exposes no CreateAlarm method";
                    return false;
                }

                _fID = _alarmType.GetField("ID");
                _fName = _alarmType.GetField("Name");
                _fNotes = _alarmType.GetField("Notes");
                _fTypeOfAlarm = _alarmType.GetField("TypeOfAlarm");
                _fVesselID = _alarmType.GetField("VesselID");
                _fMargin = _alarmType.GetField("AlarmMarginSecs");
                _fAction = _alarmType.GetField("AlarmAction");
                _fRemaining = _alarmType.GetField("Remaining");
                _fXferOrigin = _alarmType.GetField("XferOriginBodyName");
                _fXferTarget = _alarmType.GetField("XferTargetBodyName");
                _pAlarmTimeUT = _alarmType.GetProperty("AlarmTimeUT");

                Unavailable = null;
                Debug.Log(Tag + "bound to KAC " + _kacType.Assembly.GetName().Version);
                return Ready;
            }
            catch (Exception e)
            {
                Unavailable = e.GetType().Name + " binding KAC: " + e.Message;
                Debug.LogWarning(Tag + Unavailable);
                return false;
            }
        }

        /// <summary>
        /// KAC is bound AND has finished starting up. These are two different things: the type
        /// exists from load, but APIReady only goes true once KAC's own addon has run for the
        /// scene, so a request that arrives during a scene change must be told "not yet" rather
        /// than "not installed".
        /// </summary>
        public static bool Ready
        {
            get
            {
                if (_kacType == null || _instance == null) return false;
                if (_apiReady == null) return true;
                try { return (bool)_apiReady.GetValue(null); }
                catch (Exception) { return false; }
            }
        }

        public static bool Present { get { return _kacType != null && _instance != null; } }

        // --- enums -----------------------------------------------------------
        public static string[] AlarmTypeNames { get { return EnumNames(_fTypeOfAlarm); } }
        public static string[] AlarmActionNames { get { return EnumNames(_fAction); } }

        private static string[] EnumNames(FieldInfo f)
        {
            if (f == null || !f.FieldType.IsEnum) return new string[0];
            return Enum.GetNames(f.FieldType);
        }

        private static object ParseEnum(FieldInfo f, string name, string what)
        {
            if (f == null || !f.FieldType.IsEnum)
                throw new InvalidOperationException("KAC exposes no " + what + " enum");
            foreach (string n in Enum.GetNames(f.FieldType))
                if (string.Equals(n, name, StringComparison.OrdinalIgnoreCase))
                    return Enum.Parse(f.FieldType, n);
            throw new ArgumentException("unknown " + what + " \"" + name + "\"; KAC accepts: "
                                        + string.Join(", ", Enum.GetNames(f.FieldType)));
        }

        // --- create ----------------------------------------------------------
        public sealed class AlarmSpec
        {
            public string Type = "Raw";
            public string Name = "AXE alarm";
            public string Notes;
            public double UT;
            public double Margin;                       // seconds before UT that it fires
            public string Action = "KillWarp";
            public string VesselId;                     // Guid, dashed or not
            public string XferOrigin;                   // Transfer alarms only
            public string XferTarget;
        }

        /// <summary>
        /// Create an alarm and return its ID. Throws with a usable message rather than returning
        /// a bare false: every failure here has a distinct cause and the client can act on none
        /// of them if they all read the same.
        /// </summary>
        public static string Create(AlarmSpec spec, out string backend)
        {
            backend = "kac";
            Bind();
            if (!Ready)
            {
                backend = "stock";
                return CreateStock(spec);
            }

            // RP-1 learned this the expensive way and it is worth carrying: KAC deletes a
            // Contract/ContractAuto alarm the instant it is created unless the contract system
            // owns it. Refuse loudly instead of handing back an ID for an alarm that is gone.
            if (spec.Type.StartsWith("Contract", StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("KAC immediately deletes Contract/ContractAuto alarms "
                                          + "it did not create itself; use Raw");

            object typeVal = ParseEnum(_fTypeOfAlarm, spec.Type, "alarm type");
            object actionVal = string.IsNullOrEmpty(spec.Action) ? null
                             : ParseEnum(_fAction, spec.Action, "alarm action");

            string id = (string)_createAlarm.Invoke(_instance,
                new object[] { Convert.ToInt32(typeVal), spec.Name ?? "AXE alarm", spec.UT });
            if (string.IsNullOrEmpty(id))
                throw new InvalidOperationException("KAC refused to create the alarm (it returned no ID)");

            object alarm = FindActual(id);
            if (alarm == null)
            {
                // The ID is real but the alarm is not in the list: KAC dropped it. Report the ID
                // anyway so the caller can see what happened rather than guessing.
                Debug.LogWarning(Tag + "created alarm " + id + " but it is not in KAC's list");
                return id;
            }

            SetField(alarm, _fNotes, spec.Notes ?? "");
            if (actionVal != null) SetField(alarm, _fAction, actionVal);
            if (spec.Margin > 0.0) SetField(alarm, _fMargin, spec.Margin);
            if (!string.IsNullOrEmpty(spec.VesselId)) SetField(alarm, _fVesselID, spec.VesselId);
            if (!string.IsNullOrEmpty(spec.XferOrigin)) SetField(alarm, _fXferOrigin, spec.XferOrigin);
            if (!string.IsNullOrEmpty(spec.XferTarget)) SetField(alarm, _fXferTarget, spec.XferTarget);
            return id;
        }

        /// <summary>
        /// Stock alarm clock, used when KAC is absent. Note that AlarmTypeRaw.Id is only assigned
        /// by AddAlarm, so the ID must be read AFTER the add, not before.
        /// </summary>
        private static string CreateStock(AlarmSpec spec)
        {
            if (AlarmClockScenario.Instance == null)
                throw new InvalidOperationException(
                    (Unavailable ?? "KAC is not ready") + ", and the stock alarm clock is not "
                    + "loaded either (no game in progress?)");
            var alarm = new AlarmTypeRaw
            {
                title = spec.Name ?? "AXE alarm",
                description = spec.Notes ?? "",
                ut = spec.UT,
            };
            AlarmClockScenario.AddAlarm(alarm);
            alarm.actions.warp = AlarmActions.WarpEnum.KillWarp;
            if (alarm.Id == 0u)
                throw new InvalidOperationException("the stock alarm clock refused to create the alarm");
            return alarm.Id.ToString();
        }

        private static void SetField(object alarm, FieldInfo f, object value)
        {
            if (f == null || alarm == null) return;
            try { f.SetValue(alarm, value); }
            catch (Exception e) { Debug.LogWarning(Tag + "could not set " + f.Name + ": " + e.Message); }
        }

        // --- read / delete ---------------------------------------------------
        private static IList ActualAlarms()
        {
            if (_alarmsField == null) return null;
            try { return _alarmsField.GetValue(_instance) as IList; }
            catch (Exception) { return null; }
        }

        private static object FindActual(string id)
        {
            IList list = ActualAlarms();
            if (list == null) return null;
            foreach (object a in list)
                if (string.Equals(Get(a, _fID) as string, id, StringComparison.Ordinal))
                    return a;
            return null;
        }

        private static object Get(object alarm, FieldInfo f)
        {
            if (f == null || alarm == null) return null;
            try { return f.GetValue(alarm); }
            catch (Exception) { return null; }
        }

        public sealed class AlarmInfo
        {
            public string Id, Name, Notes, Type, Action, VesselId, XferOrigin, XferTarget;
            public double UT, Margin, Remaining;
        }

        public static List<AlarmInfo> List()
        {
            var outList = new List<AlarmInfo>();
            Bind();
            if (!Ready)
            {
                if (AlarmClockScenario.Instance == null || AlarmClockScenario.Instance.alarms == null)
                    return outList;
                // DictionaryValueList is not foreach-able -- its GetEnumerator returns the
                // DICTIONARY's, so `var kv` would be a KeyValuePair and the compiler rejects it.
                // At(i) walks the backing list, which is what is wanted here anyway.
                var stock = AlarmClockScenario.Instance.alarms;
                double now = Planetarium.fetch != null ? Planetarium.GetUniversalTime() : 0.0;
                for (int i = 0; i < stock.Count; i++)
                {
                    AlarmTypeBase a = stock.At(i);
                    if (a == null) continue;
                    outList.Add(new AlarmInfo
                    {
                        Id = a.Id.ToString(),
                        Name = a.title,
                        Notes = a.description,
                        Type = "stock:" + a.TypeName,
                        UT = a.ut,
                        Remaining = a.ut - now,
                        // Stock keys vessels by persistentId (a uint), not by the Guid KAC uses.
                        // 0 means "not bound to a vessel"; reporting it as an id would be a lie.
                        VesselId = a.vesselId != 0u ? a.vesselId.ToString() : null,
                    });
                }
                return outList;
            }

            IList list = ActualAlarms();
            if (list == null) return outList;
            foreach (object a in list)
            {
                object t = Get(a, _fTypeOfAlarm);
                object act = Get(a, _fAction);
                outList.Add(new AlarmInfo
                {
                    Id = Get(a, _fID) as string,
                    Name = Get(a, _fName) as string,
                    Notes = Get(a, _fNotes) as string,
                    Type = t != null ? t.ToString() : null,
                    Action = act != null ? act.ToString() : null,
                    VesselId = Get(a, _fVesselID) as string,
                    XferOrigin = Get(a, _fXferOrigin) as string,
                    XferTarget = Get(a, _fXferTarget) as string,
                    UT = _pAlarmTimeUT != null ? ToDouble(_pAlarmTimeUT.GetValue(a, null)) : 0.0,
                    Margin = ToDouble(Get(a, _fMargin)),
                    Remaining = ToDouble(Get(a, _fRemaining)),
                });
            }
            return outList;
        }

        public static bool Delete(string id)
        {
            Bind();
            if (Ready && _deleteAlarm != null)
            {
                try { return (bool)_deleteAlarm.Invoke(_instance, new object[] { id }); }
                catch (Exception e) { Debug.LogWarning(Tag + "DeleteAlarm threw: " + e.Message); return false; }
            }
            uint stockId;
            if (AlarmClockScenario.Instance != null && uint.TryParse(id, out stockId))
                return AlarmClockScenario.DeleteAlarm(stockId);
            return false;
        }

        private static double ToDouble(object o)
        {
            if (o == null) return 0.0;
            try { return Convert.ToDouble(o); }
            catch (Exception) { return 0.0; }
        }
    }
}
