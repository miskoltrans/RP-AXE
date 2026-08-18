"""RealAntennas link budget, transcribed from the installed RealAntennas.dll.

Every formula here is the decompiled one, not a textbook approximation:

    GainFromDishDiameter = 10log10(9.87 * eff * D^2 / lambda^2)
    PathLoss(d, f)       = 20log10(d*f) - 147.55242919921875      [dB]
    RxPower              = TxPower_dBm + Gtx - PathLoss + Grx     [dBm]
    N0                   = -198.59917 + 10log10(Tsys)             [dBm/Hz]
    maxBitRate           = 10^((RxPower - (RequiredEbN0 + N0))/10)

and the rate ladder from SelectBitRateJob: a link exists only when maxBitRate >= the pair's
minSymbolRate, where minSymbolRate = ChannelWidth / 2^(2*TL+3) and the PAIR takes the *higher*
of the two ends' floors. That floor is what kills long-range links at low tech level, not the
signal strength on its own.
"""
import math

AU = 1.495978707e11

# RealAntennasCommNetParams.cfg, as patched by RealismOverhaul.cfg
BANDS = {  # name: (frequency Hz, channel width = max symbol rate, min TL)
    "UHF": (430e6, 31.5e3, 0),
    "S": (2.25e9, 0.330e6, 3),
    "X": (8.45e9, 1.36e6, 7),
}
# TL: (PowerEfficiency, ReflectorEfficiency, MaxPower dBm, RxNoiseTemp K, BaseMass kg, MassPerWatt)
TL = {
    2: (0.1, 0.54, 37, 7000, 28, 1.16),
    3: (0.1304, 0.56, 37, 5800, 25, 1.0),
    4: (0.1667, 0.58, 40, 4500, 22, 0.86),
    5: (0.2222, 0.60, 43, 3000, 19, 0.75),
    6: (0.25, 0.62, 43, 1540, 16, 0.6444),
}
# EncoderInfo: (name, TL, coding rate, required Eb/N0 dB)
ENCODERS = [("None", 0, 1.0, 10.0), ("RS 255/223", 3, 0.8745, 6.1),
            ("Conv 7 1/2", 6, 0.5, 4.5), ("Turbo 1/2", 8, 0.5, 1.0)]
# DSN S-band ground antenna by ground TL (RealismOverhaul.cfg City2[DSNTrackingStation])
DSN_S = {0: (49.0, 290), 1: (52.5, 290), 2: (52.5, 290), 3: (52.5, 125), 4: (60.5, 125),
         5: (60.5, 80), 6: (62.5, 80), 7: (62.5, 40), 8: (63.6, 40), 9: (63.6, 17.6)}


def gain_dish(D, freq, eff):
    lam = 299800000.0 / freq
    return 10 * math.log10(9.87 * eff * D * D / (lam * lam))


def path_loss(d, freq):
    return 20 * math.log10(max(d * freq, 0.1)) - 147.55242919921875


def encoder_for(tl):
    best = ENCODERS[0]
    for e in ENCODERS:
        if e[1] <= tl:
            best = e
    return best


def link(distance_m, craft_tl, ground_tl, dish_m, tx_dbm=None, band="S",
         ground_extra_noise_K=15.0, verbose=False):
    """Downlink craft -> DSN. Returns dict with rate (bps) or 0 when the link cannot form."""
    freq, chan_width, band_tl = BANDS[band]
    pe, refl, maxp, rx_noise, base_mass, mass_per_w = TL[craft_tl]
    if tx_dbm is None:
        tx_dbm = maxp
    tx_dbm = min(tx_dbm, maxp)
    g_tx = gain_dish(dish_m, freq, refl)
    g_rx, amw = DSN_S[ground_tl]
    pl = path_loss(distance_m, freq)
    rx_power = tx_dbm + g_tx - pl + g_rx
    tsys = amw + ground_extra_noise_K
    n0 = -198.59917 + 10 * math.log10(tsys)
    enc = encoder_for(min(craft_tl, ground_tl))
    min_eb = enc[3] + n0
    max_bit_rate = 10 ** ((rx_power - min_eb) / 10)
    # symbol-rate ladder: pair floor is the *higher* of the two ends
    floor_craft = chan_width / 2 ** (2 * craft_tl + 3)
    floor_ground = chan_width / 2 ** (2 * ground_tl + 3)
    floor = max(floor_craft, floor_ground)
    if max_bit_rate < floor:
        rate = 0.0
    elif max_bit_rate <= chan_width:
        steps = math.floor(math.log2(max_bit_rate / chan_width))
        rate = chan_width * 2 ** steps * enc[2]
    else:
        rate = chan_width * enc[2]
    watts = 10 ** (tx_dbm / 10) / 1000
    out = dict(rate=rate, max_bit_rate=max_bit_rate, floor=floor, rx_power=rx_power,
               g_tx=g_tx, g_rx=g_rx, path_loss=pl, encoder=enc[0], tx_w=watts,
               dc_watts=watts / pe, mass_kg=base_mass + mass_per_w * watts,
               margin_db=10 * math.log10(max_bit_rate / floor) if floor else 0)
    if verbose:
        for k, v in out.items():
            print(f"   {k:14s} {v}")
    return out


if __name__ == "__main__":
    print("Downlink from Jupiter (5.2 AU), S-band, 5 W unless noted\n")
    print(f"{'dish':>6s} {'craftTL':>7s} {'gndTL':>6s} {'txW':>5s} {'rate bps':>9s} {'cap bps':>8s} "
          f"{'floor':>7s} {'margin dB':>9s} {'DC W':>6s} {'kg':>5s}")
    for dish in (1.25, 2.0, 3.0, 4.0):
        for ctl, gtl in ((3, 3), (3, 4), (4, 4), (5, 5)):
            r = link(5.2 * AU, ctl, gtl, dish)
            print(f"{dish:6.2f} {ctl:7d} {gtl:6d} {r['tx_w']:5.1f} {r['rate']:9.0f} "
                  f"{r['max_bit_rate']:8.0f} {r['floor']:7.0f} {r['margin_db']:9.1f} "
                  f"{r['dc_watts']:6.0f} {r['mass_kg']:5.0f}")
