"""Client for KSPTOT Connect — live vessel state from a plugin that is already installed.

KSPTOT ships `GameData/KSPTOTConnect`, which listens on 8282 and whitelists 127.0.0.1
unconditionally. It already answers everything this toolchain needs about live vessels,
so there is no reason for a second plugin to duplicate it.

Wire format, settled by probing the running game rather than by reading the source:

    request:  [32 bytes ASCII command, SPACE-padded][1 byte class][4 bytes uint32 BE length][data]
    response: raw big-endian doubles, or ASCII, then the server closes the connection

The padding is the part that has to be measured. `NetworkMessage.GetRawMessage` writes the
command into a zero-filled buffer, which reads back as NUL padding — and a NUL-padded
request gets silently dropped, zero bytes, no error. Space padding works.

    class "n"  no payload        GetUT, GetVesselIDList, GetActiveVesselOrbit
    class "s"  ASCII payload     GetVesselNameByGUID, GetVesselOrbitByGUID (a 32-hex GUID)

Two limits worth knowing: KSPTOT Connect is `[KSPAddon(Startup.Flight)]`, so it answers
only while a vessel is being flown, and `GetVesselIDList` returns *commandable* vessels
only — debris and spent stages are not in it.
"""
import math
import socket
import struct

import numpy as np

import astro

DEFAULT_PORT = 8282

# GetVesselOrbitByGUID: 19 doubles, in the order RetrieveVesselOrbitHandler packs them.
ORBIT_FIELDS = ("sma_km", "ecc", "inc_deg", "raan_deg", "argp_deg", "mna_rad", "cur_ut",
                "mna_at_epoch_rad", "epoch", "period", "start_ut", "end_ut", "ref_index",
                "ap_alt_km", "ap_r_km", "time_to_ap", "pe_alt_km", "pe_r_km", "time_to_pe")


class KspTotError(RuntimeError):
    pass


class KspTot:
    def __init__(self, host="127.0.0.1", port=DEFAULT_PORT, timeout=10.0):
        self.host, self.port, self.timeout = host, port, timeout

    def call(self, command, payload=b"", cls=None):
        if isinstance(payload, str):
            payload = payload.encode("ascii")
        if cls is None:
            cls = "s" if payload else "n"
        head = command.encode("ascii")[:32].ljust(32, b" ") + cls.encode("ascii") \
            + struct.pack(">I", len(payload))
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise KspTotError(
                f"cannot reach KSPTOT Connect at {self.host}:{self.port} ({exc}).\n"
                f"  It is [KSPAddon(Startup.Flight)] -- KSP must be running AND flying a\n"
                f"  vessel, not sitting in the Tracking Station or the main menu."
            ) from None
        try:
            sock.sendall(head + payload)
            buf = b""
            sock.settimeout(self.timeout)
            try:
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
            except socket.timeout:
                pass
        finally:
            sock.close()
        if not buf:
            raise KspTotError(
                f"{command}: no reply. KSPTOT Connect drops requests it does not recognise "
                f"without a word, so check the command spelling and that the 32-byte field "
                f"is SPACE-padded."
            )
        return buf

    # --- typed calls -----------------------------------------------------
    def doubles(self, command, payload=b""):
        raw = self.call(command, payload)
        n = len(raw) // 8
        return struct.unpack(f">{n}d", raw[:n * 8])

    def ut(self):
        return self.doubles("GetUT")[0]

    def vessel_ids(self):
        raw = self.call("GetVesselIDList")
        if len(raw) % 32:
            raise KspTotError(f"vessel id list is {len(raw)} bytes, not a multiple of 32")
        return [raw[i:i + 32].decode("ascii") for i in range(0, len(raw), 32)]

    def vessel_name(self, guid):
        return self.call("GetVesselNameByGUID", guid).decode("ascii", "replace").strip()

    def raw_orbit(self, guid=None):
        vals = self.doubles("GetVesselOrbitByGUID", guid) if guid \
            else self.doubles("GetActiveVesselOrbit")
        if len(vals) < len(ORBIT_FIELDS):
            raise KspTotError(f"orbit reply has {len(vals)} doubles, expected {len(ORBIT_FIELDS)}")
        return dict(zip(ORBIT_FIELDS, vals))

    def vessels(self, names=True):
        out = []
        for guid in self.vessel_ids():
            row = {"id": guid, "name": self.vessel_name(guid) if names else None}
            try:
                row.update(self.raw_orbit(guid))
            except KspTotError:
                pass
            out.append(row)
        return out

    def find(self, name):
        """GUID for a vessel name: exact first, then a unique case-insensitive substring."""
        pairs = [(g, self.vessel_name(g)) for g in self.vessel_ids()]
        for g, n in pairs:
            if n == name:
                return g, n
        hits = [(g, n) for g, n in pairs if name.lower() in n.lower()]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise KspTotError(f"no commandable vessel matching {name!r}. Known: "
                              + ", ".join(sorted(n for _, n in pairs)))
        raise KspTotError(f"{name!r} is ambiguous: " + ", ".join(n for _, n in hits))

    # --- the bit the planner wants ---------------------------------------
    def state(self, system, name=None, guid=None, ut=None):
        """(body, r, v, ut) about the vessel's reference body, in metres and m/s.

        KSPTOT sends the semi-major axis in km and the angles in the units KSP keeps
        them (inc/raan/argp degrees, mean anomaly radians), so the conversion happens
        exactly once, here.

        `ref_index` is KSP's RUNTIME flightGlobalsIndex, which Kopernicus renumbers to
        match FlightGlobals.Bodies order -- so it is the same number a save's ORBIT.REF
        carries, even though the value in the Kopernicus .cfg is not.
        """
        if guid is None and name:
            guid, name = self.find(name)
        d = self.raw_orbit(guid)
        body = system.by_index[int(round(d["ref_index"]))]
        at = d["cur_ut"] if ut is None else ut
        r, v = astro.state_from_save_orbit(
            body.mu, d["sma_km"] * 1e3, d["ecc"], d["inc_deg"], d["argp_deg"],
            d["raan_deg"], d["mna_at_epoch_rad"], d["epoch"], at)
        return body, np.asarray(r), np.asarray(v), at


if __name__ == "__main__":
    from rss_ephem import System, fmt_ut
    S = System()
    k = KspTot()
    print("game UT", fmt_ut(k.ut()))
    print(f"{'vessel':30s} {'body':10s} {'pe km':>12s} {'ap km':>13s} {'inc':>7s}")
    for v in k.vessels():
        if "ref_index" not in v or not math.isfinite(v.get("sma_km", math.nan)):
            print(f"{v['name'][:30]:30s} (no orbit)")
            continue
        b = S.by_index[int(round(v["ref_index"]))]
        ap = "escape" if v["ecc"] >= 1 else f"{v['ap_alt_km']:,.0f}"
        print(f"{v['name'][:30]:30s} {b.name:10s} {v['pe_alt_km']:12,.0f} {ap:>13s} "
              f"{v['inc_deg']:7.2f}")
