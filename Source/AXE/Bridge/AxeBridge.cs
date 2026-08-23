using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEngine;

namespace RPAxe.Bridge
{
    /// <summary>
    /// Query-and-command bridge: lets <c>tools/mission/plan.py</c> ask the RUNNING game for state,
    /// ask KSP's own patched-conic solver where a proposed burn ends up, and — once the answer is
    /// trusted — place that burn as a maneuver node and set an alarm for it.
    ///
    /// The mission tools reimplement KSP's orbital mechanics outside the game. That replica has
    /// been checked against a lot of things, but until now not against the only authority that
    /// matters. Every historical bug in it (the B1950 epoch, ORBIT.REF indexing, MNA in radians)
    /// was a state-interpretation error that simply cannot happen when the game hands you the
    /// numbers. <c>/predict</c> closes the last gap: same burn, KSP's solver, diff the answers.
    ///
    /// OFF BY DEFAULT. It opens a listening socket, and a shipped mod has no business doing that
    /// uninvited. Turn it on with the <c>-axe-bridge</c> command-line flag, the AXE_BRIDGE
    /// environment variable, or <c>enabled = true</c> in Plugins/PluginData/Bridge.cfg.
    ///
    /// It is NOT read-only any more. <c>/node</c>, <c>/node/clear</c>, <c>/alarm</c> and
    /// <c>/alarm/delete</c> change the game. They are POST-only and the listener is still bound to
    /// loopback, so nothing off this machine can reach them and nothing that merely follows a link
    /// can trip them — but the single <c>-axe-bridge</c> opt-in now covers writes as well as
    /// reads, and that is worth knowing before leaving it enabled in a config file.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Instantly, true)]
    public class AxeBridge : MonoBehaviour
    {
        public const string CmdFlag = "-axe-bridge";
        public const string EnvVar = "AXE_BRIDGE";
        private const string CfgPath = "GameData/RP-AXE/Plugins/PluginData/Bridge.cfg";

        private static bool _enabled;
        private static int _port = 8284;
        private AxeBridgeServer _server;

        private void Awake()
        {
            DontDestroyOnLoad(this);
            LoadConfig();
            if (!_enabled)
            {
                Debug.Log("[AXE][Bridge] disabled. Enable with " + CmdFlag + ", " + EnvVar
                          + "=1, or enabled = true in " + CfgPath + ".");
                return;
            }
            try
            {
                _server = new AxeBridgeServer(_port, AxeBridgeHandlers.Handle);
                _server.Start();
                Debug.Log("[AXE][Bridge] listening on http://127.0.0.1:" + _port
                          + "/  (try /ping; POST /node and /alarm CHANGE THE GAME)");
            }
            catch (Exception e)
            {
                // A port collision must not take the plugin down with it.
                Debug.LogError("[AXE][Bridge] could not start on port " + _port + ": " + e.Message);
                _server = null;
            }
        }

        private void Update()
        {
            if (_server != null && _server.Running) _server.Pump();
        }

        private void OnDestroy()
        {
            if (_server != null)
            {
                _server.Stop();
                Debug.Log("[AXE][Bridge] stopped.");
                _server = null;
            }
        }

        private static void LoadConfig()
        {
            _enabled = false;
            string path = Path.Combine(KSPUtil.ApplicationRootPath, CfgPath);
            try
            {
                if (File.Exists(path))
                {
                    ConfigNode node = ConfigNode.Load(path);
                    if (node != null)
                    {
                        // ConfigNode.Load wraps the file in an unnamed root, so accept either shape.
                        ConfigNode n = node.GetNode("AXE_BRIDGE") ?? node;
                        bool b;
                        if (bool.TryParse(n.GetValue("enabled") ?? "", out b)) _enabled = b;
                        int p;
                        if (int.TryParse(n.GetValue("port") ?? "", NumberStyles.Integer,
                                         CultureInfo.InvariantCulture, out p) && p > 0 && p < 65536)
                            _port = p;
                    }
                }
                else
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    File.WriteAllText(path,
                        "// RP-AXE query bridge for tools/mission/plan.py --live.\n"
                        + "// Read-only, bound to 127.0.0.1 only. Off unless you turn it on.\n"
                        + "AXE_BRIDGE\n{\n\tenabled = false\n\tport = 8284\n}\n");
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning("[AXE][Bridge] could not read " + CfgPath + ": " + e.Message);
            }

            foreach (string arg in Environment.GetCommandLineArgs())
                if (string.Equals(arg, CmdFlag, StringComparison.OrdinalIgnoreCase)) _enabled = true;
            string env = Environment.GetEnvironmentVariable(EnvVar);
            if (!string.IsNullOrEmpty(env) && env != "0" && !env.Equals("false", StringComparison.OrdinalIgnoreCase))
                _enabled = true;
        }
    }
}
