using System;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Load-time sentinel so a log reader can confirm AXE.dll is present and which build it is
    /// (look for the "[AXE]" prefix in KSP.log). The version is read from the KSP-AVC file,
    /// GameData/RP-AXE/RP-AXE.version, which is the one place the release version lives
    /// (docs/RELEASE.md) -- never a literal here, or the banner lies after every bump.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Instantly, true)]
    public class AxeBootstrap : MonoBehaviour
    {
        private const string AvcPath = "GameData/RP-AXE/RP-AXE.version";

        private void Awake()
        {
            Debug.Log("[AXE] plugin loaded — RP-AXE " + Version() + " online.");
        }

        /// <summary>"v1.0.0" from the AVC file, or the assembly version if the file is unreadable.</summary>
        internal static string Version()
        {
            try
            {
                string path = Path.Combine(KSPUtil.ApplicationRootPath, AvcPath);
                if (File.Exists(path))
                {
                    // {"VERSION": { "MAJOR": 1, "MINOR": 0, "PATCH": 0, "BUILD": 0 }} -- no JSON parser in
                    // stock KSP worth pulling in for three integers.
                    var m = Regex.Match(File.ReadAllText(path),
                        "\"VERSION\"\\s*:\\s*\\{[^}]*\"MAJOR\"\\s*:\\s*(\\d+)[^}]*\"MINOR\"\\s*:\\s*(\\d+)[^}]*\"PATCH\"\\s*:\\s*(\\d+)");
                    if (m.Success)
                        return "v" + m.Groups[1].Value + "." + m.Groups[2].Value + "." + m.Groups[3].Value;
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning("[AXE] could not read " + AvcPath + ": " + e.Message);
            }
            return "v" + typeof(AxeBootstrap).Assembly.GetName().Version + " (assembly)";
        }
    }
}
