"""
EMC Tools — a small collection of electromagnetic compatibility calculators.
Built with Flask, deployed on Render.
"""

import math
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
# Preserve key insertion order in JSON responses so the frontend can treat
# the first key as the primary result.
app.json.sort_keys = False

# Speed of light in vacuum (m/s)
C0 = 2.99792458e8
# Free-space impedance (ohms)
ETA0 = 376.730313668
# Free-space permeability (H/m)
MU0 = 4 * math.pi * 1e-7
# Free-space permittivity (F/m)
EPS0 = 8.8541878128e-12

HF_BANDS = [
    {"name": "160 m", "min": 1.8, "max": 2.0, "range": "1.8–2.0 MHz"},
    {"name": "80 m", "min": 3.5, "max": 4.0, "range": "3.5–4.0 MHz"},
    {"name": "60 m", "min": 5.06, "max": 5.45, "range": "5.06–5.45 MHz"},
    {"name": "40 m", "min": 7.0, "max": 7.3, "range": "7.0–7.3 MHz"},
    {"name": "30 m", "min": 10.1, "max": 10.15, "range": "10.1–10.15 MHz"},
    {"name": "20 m", "min": 14.0, "max": 14.35, "range": "14.0–14.35 MHz"},
    {"name": "17 m", "min": 18.068, "max": 18.168, "range": "18.068–18.168 MHz"},
    {"name": "15 m", "min": 21.0, "max": 21.45, "range": "21.0–21.45 MHz"},
    {"name": "12 m", "min": 24.89, "max": 24.99, "range": "24.89–24.99 MHz"},
    {"name": "10 m", "min": 28.0, "max": 29.7, "range": "28.0–29.7 MHz"},
    {"name": "6 m",  "min": 50.0, "max": 54.0, "range": "50.0–54.0 MHz"},
]


def microstrip_characteristic(w, h, t, er):
    if t > 0:
        if w / h >= 1 / (2 * math.pi):
            w_eff = w + (t / math.pi) * (1 + math.log(2 * h / t))
        else:
            w_eff = w + (t / math.pi) * (1 + math.log(4 * math.pi * w / t))
    else:
        w_eff = w

    u = w_eff / h
    a = 1 + (1 / 49) * math.log((u**4 + (u / 52) ** 2) / (u**4 + 0.432)) \
        + (1 / 18.7) * math.log(1 + (u / 18.1) ** 3)
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    er_eff = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)

    f = 6 + (2 * math.pi - 6) * math.exp(-((30.666 / u) ** 0.7528))
    z0_air = (ETA0 / (2 * math.pi)) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))
    z0 = z0_air / math.sqrt(er_eff)
    return z0, er_eff


def find_hf_band(freq_mhz):
    for band in HF_BANDS:
        if band["min"] <= freq_mhz <= band["max"]:
            return band
    return None


# ---------- Calculator routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/shielding", methods=["POST"])
def api_shielding():
    """
    Shielding effectiveness of a solid metal sheet (plane-wave, Schelkunoff).
    Inputs: freq (MHz), thickness (mm), sigma_r (relative to copper), mu_r
    """
    try:
        data = request.get_json()
        freq_mhz = float(data["freq"])
        t_mm = float(data["t"])
        sigma_r = float(data["sigma_r"])  # relative to copper
        mu_r = float(data["mu_r"])

        if freq_mhz <= 0 or t_mm <= 0 or sigma_r <= 0 or mu_r <= 0:
            return jsonify({"error": "Alle Eingaben müssen positiv sein."}), 400

        freq_hz = freq_mhz * 1e6
        t_m = t_mm / 1000
        sigma_cu = 5.8e7  # S/m
        sigma = sigma_r * sigma_cu
        mu = mu_r * MU0
        omega = 2 * math.pi * freq_hz

        # Skin depth
        skin = math.sqrt(2 / (omega * mu * sigma))

        # Absorption loss (dB)
        A = 8.686 * t_m / skin

        # Reflection loss for plane wave (dB)
        R = 168 - 10 * math.log10(mu_r * freq_hz / sigma_r)

        # Multiple reflection correction (negligible if A > 10 dB)
        if A < 10:
            B = 20 * math.log10(abs(1 - 10 ** (-A / 10)))
        else:
            B = 0

        SE = A + R + B

        return jsonify({
            "se_total": round(SE, 1),
            "absorption": round(A, 1),
            "reflection": round(R, 1),
            "multi_refl": round(B, 1),
            "skin_depth_um": round(skin * 1e6, 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/db", methods=["POST"])
def api_db():
    """
    dB-Einheiten-Konverter: rechnet einen Pegel in alle dB- und Linearwerte
    für Spannung, Strom und Leistung um.
    Eingaben: value, unit, z (Bezugsimpedanz in Ohm).
    """
    try:
        data = request.get_json()
        value = float(data["value"])
        unit = data.get("unit", "dbuv")
        z = float(data.get("z") or 50)

        if z <= 0:
            return jsonify({"error": "Bezugsimpedanz muss positiv sein."}), 400

        linear = {"uv", "mv", "v", "ua", "ma", "a", "mw", "w"}
        if unit in linear and value <= 0:
            return jsonify({"error": "Linearwerte müssen positiv sein."}), 400

        volt_units = {"dbuv": 1e-6, "dbmv": 1e-3, "dbv": 1.0}
        amp_units = {"dbua": 1e-6, "dbma": 1e-3}
        lin_volt = {"uv": 1e-6, "mv": 1e-3, "v": 1.0}
        lin_amp = {"ua": 1e-6, "ma": 1e-3, "a": 1.0}

        if unit in volt_units:
            volt = 10 ** (value / 20) * volt_units[unit]
            p_w = volt * volt / z
        elif unit in lin_volt:
            volt = value * lin_volt[unit]
            p_w = volt * volt / z
        elif unit in amp_units:
            amp = 10 ** (value / 20) * amp_units[unit]
            p_w = amp * amp * z
        elif unit in lin_amp:
            amp = value * lin_amp[unit]
            p_w = amp * amp * z
        elif unit == "dbm":
            p_w = 10 ** (value / 10) / 1000
        elif unit == "dbw":
            p_w = 10 ** (value / 10)
        elif unit == "mw":
            p_w = value / 1000
        elif unit == "w":
            p_w = value
        else:
            return jsonify({"error": "Ungültige Einheit."}), 400

        volt = math.sqrt(p_w * z)
        amp = math.sqrt(p_w / z)

        return jsonify({
            "dbuv": round(20 * math.log10(volt / 1e-6), 2),
            "dbmv": round(20 * math.log10(volt / 1e-3), 2),
            "dbv": round(20 * math.log10(volt), 2),
            "dbua": round(20 * math.log10(amp / 1e-6), 2),
            "dbma": round(20 * math.log10(amp / 1e-3), 2),
            "dbm": round(10 * math.log10(p_w * 1000), 2),
            "dbw": round(10 * math.log10(p_w), 2),
            "uv": round(volt / 1e-6, 4),
            "mv": round(volt / 1e-3, 6),
            "v": round(volt, 9),
            "ua": round(amp / 1e-6, 4),
            "ma": round(amp / 1e-3, 6),
            "a": round(amp, 9),
            "mw": round(p_w * 1000, 6),
            "w": round(p_w, 9),
            "impedance": round(z, 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/magfield", methods=["POST"])
def api_magfield():
    """
    Magnetfeld-Einheiten-Konverter (Annahme Luft/Vakuum, B = µ0·H).
    Flussdichte: T, mT, µT, nT, Gauss, mGauss, dBpT.
    Feldstärke: A/m, Oersted, dBµA/m.
    Eingaben: value, unit.
    """
    try:
        data = request.get_json()
        value = float(data["value"])
        unit = data.get("unit", "ut")

        if value <= 0:
            return jsonify({"error": "Feldwert muss positiv sein."}), 400

        to_tesla = {
            "t": 1.0, "mt": 1e-3, "ut": 1e-6, "nt": 1e-9,
            "g": 1e-4, "mg": 1e-7, "oe": 1e-4,
        }
        if unit in to_tesla:
            b = value * to_tesla[unit]
        elif unit == "am":          # A/m -> B = µ0·H
            b = MU0 * value
        elif unit == "dbpt":        # dB picotesla
            b = 10 ** (value / 20) * 1e-12
        elif unit == "dbuam":       # dBµA/m
            b = MU0 * (10 ** (value / 20) * 1e-6)
        else:
            return jsonify({"error": "Ungültige Einheit."}), 400

        h = b / MU0  # A/m

        return jsonify({
            "microtesla": round(b * 1e6, 6),
            "tesla": round(b, 12),
            "millitesla": round(b * 1e3, 9),
            "nanotesla": round(b * 1e9, 4),
            "gauss": round(b * 1e4, 8),
            "milligauss": round(b * 1e7, 4),
            "oersted": round(b * 1e4, 8),
            "am": round(h, 6),
            "dbpt": round(20 * math.log10(b / 1e-12), 2),
            "dbuam": round(20 * math.log10(h / 1e-6), 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/vswr", methods=["POST"])
def api_vswr():
    """
    VSWR / Rückflussdämpfung (Return Loss) Konverter.
    Inputs: vswr or rl
    """
    try:
        data = request.get_json()
        vswr_raw = data.get("vswr")
        rl_raw = data.get("rl")

        if vswr_raw not in (None, ""):
            vswr = float(vswr_raw)
            if vswr < 1:
                return jsonify({"error": "VSWR muss >= 1 sein."}), 400
            gamma = (vswr - 1) / (vswr + 1)
            rl = -20 * math.log10(gamma)
        elif rl_raw not in (None, ""):
            rl = float(rl_raw)
            if rl <= 0:
                return jsonify({"error": "Return Loss muss positiv sein."}), 400
            gamma = 10 ** (-rl / 20)
            if gamma >= 1:
                return jsonify({"error": "Ungültiger Return Loss."}), 400
            vswr = (1 + gamma) / (1 - gamma)
        else:
            return jsonify({"error": "Bitte VSWR oder Return Loss eingeben."}), 400

        mismatch_loss = -10 * math.log10(1 - gamma**2)
        return jsonify({
            "vswr": round(vswr, 3),
            "return_loss": round(rl, 2),
            "gamma": round(gamma, 4),
            "mismatch_loss": round(mismatch_loss, 2),
        })
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/wavelength", methods=["POST"])
def api_wavelength():
    """
    Frequenz / Wellenlänge Konverter.
    Inputs: freq (MHz) or wavelength (m)
    """
    try:
        data = request.get_json()
        freq_mhz = float(data.get("freq") or 0)
        wavelength = float(data.get("wavelength") or 0)

        if freq_mhz > 0:
            wavelength_m = C0 / (freq_mhz * 1e6)
            return jsonify({
                "wavelength_m": round(wavelength_m, 4),
                "frequency_mhz": round(freq_mhz, 4),
            })
        if wavelength > 0:
            freq_mhz = C0 / wavelength / 1e6
            return jsonify({
                "frequency_mhz": round(freq_mhz, 4),
                "wavelength_m": round(wavelength, 4),
            })
        return jsonify({"error": "Bitte Frequenz oder Wellenlänge eingeben."}), 400
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/pcb", methods=["POST"])
def api_pcb():
    """
    PCB Spurimpedanz und differentielle Impedanz.
    Eingaben: w (mm), h (mm), t (mm), er, s (mm)
    """
    try:
        data = request.get_json()
        w = float(data["w"])
        h = float(data["h"])
        t = float(data["t"])
        er = float(data["er"])
        s = float(data["s"])

        if w <= 0 or h <= 0 or t < 0 or er <= 0 or s < 0:
            return jsonify({"error": "Ungültige Eingabe, prüfen Sie Werte."}), 400

        z0, er_eff = microstrip_characteristic(w, h, t, er)
        coupling = 0.48 * math.exp(-0.96 * s / h) if h > 0 else 0
        z_diff = 2 * z0 * max(0.0, 1 - coupling)

        return jsonify({
            "z0": round(z0, 2),
            "z_diff": round(z_diff, 2),
            "coupling": round(coupling, 4),
            "er_eff": round(er_eff, 3),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/hfband", methods=["POST"])
def api_hfband():
    """
    HF-Band und Antennenformeln.
    Eingaben: freq (MHz)
    """
    try:
        data = request.get_json()
        freq_mhz = float(data["freq"])

        if freq_mhz <= 0:
            return jsonify({"error": "Frequenz muss positiv sein."}), 400

        wavelength = C0 / (freq_mhz * 1e6)
        band = find_hf_band(freq_mhz)

        return jsonify({
            "frequency_mhz": round(freq_mhz, 4),
            "wavelength_m": round(wavelength, 4),
            "quarter_wave_m": round(wavelength / 4, 4),
            "half_wave_m": round(wavelength / 2, 4),
            "band_name": band["name"] if band else "Außerhalb gängiger HF-Bänder",
            "band_range": band["range"] if band else None,
            "bands": HF_BANDS,
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/skindepth", methods=["POST"])
def api_skindepth():
    """
    Hauttiefe (Skin-Effekt) und Oberflächenwiderstand eines Leiters.
    Eingaben: freq (MHz), sigma_r (rel. Cu), mu_r.
    """
    try:
        data = request.get_json()
        freq_mhz = float(data["freq"])
        sigma_r = float(data["sigma_r"])
        mu_r = float(data["mu_r"])

        if freq_mhz <= 0 or sigma_r <= 0 or mu_r <= 0:
            return jsonify({"error": "Alle Eingaben müssen positiv sein."}), 400

        freq_hz = freq_mhz * 1e6
        sigma = sigma_r * 5.8e7
        mu = mu_r * MU0
        omega = 2 * math.pi * freq_hz

        skin = math.sqrt(2 / (omega * mu * sigma))
        rs = 1 / (sigma * skin)  # surface resistance, Ohm/square

        return jsonify({
            "skin_depth_um": round(skin * 1e6, 4),
            "skin_depth_mm": round(skin * 1e3, 6),
            "surface_resistance_mohm": round(rs * 1000, 4),
            "frequency_mhz": round(freq_mhz, 4),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/risetime", methods=["POST"])
def api_risetime():
    """
    Anstiegszeit <-> Bandbreite für Signalintegrität / EMV.
    Eingaben: rise_time (ns) oder bandwidth (MHz).
    """
    try:
        data = request.get_json()
        tr_raw = data.get("rise_time")
        bw_raw = data.get("bandwidth")

        if tr_raw not in (None, ""):
            tr_ns = float(tr_raw)
            if tr_ns <= 0:
                return jsonify({"error": "Anstiegszeit muss positiv sein."}), 400
            bw_mhz = 350.0 / tr_ns  # 0.35 / tr
        elif bw_raw not in (None, ""):
            bw_mhz = float(bw_raw)
            if bw_mhz <= 0:
                return jsonify({"error": "Bandbreite muss positiv sein."}), 400
            tr_ns = 350.0 / bw_mhz
        else:
            return jsonify({"error": "Bitte Anstiegszeit oder Bandbreite eingeben."}), 400

        knee_mhz = 500.0 / tr_ns  # 0.5 / tr — Knickfrequenz

        return jsonify({
            "bandwidth_mhz": round(bw_mhz, 3),
            "rise_time_ns": round(tr_ns, 4),
            "knee_freq_mhz": round(knee_mhz, 3),
        })
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/lcres", methods=["POST"])
def api_lcres():
    """
    LC-Resonanzfrequenz, z.B. Eigenresonanz eines Abblockkondensators.
    Eingaben: l (nH), c (pF).
    """
    try:
        data = request.get_json()
        l_nh = float(data["l"])
        c_pf = float(data["c"])

        if l_nh <= 0 or c_pf <= 0:
            return jsonify({"error": "L und C müssen positiv sein."}), 400

        l = l_nh * 1e-9
        c = c_pf * 1e-12
        f_hz = 1 / (2 * math.pi * math.sqrt(l * c))
        z_char = math.sqrt(l / c)

        return jsonify({
            "frequency_mhz": round(f_hz / 1e6, 4),
            "char_impedance": round(z_char, 3),
            "l_nh": round(l_nh, 4),
            "c_pf": round(c_pf, 4),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/fieldstrength", methods=["POST"])
def api_fieldstrength():
    """
    Fernfeld-Feldstärke und Leistungsdichte eines Strahlers.
    Eingaben: power (W), gain (dBi), distance (m).
    """
    try:
        data = request.get_json()
        power_w = float(data["power"])
        gain_dbi = float(data.get("gain") or 0)
        distance = float(data["distance"])

        if power_w <= 0 or distance <= 0:
            return jsonify({"error": "Leistung und Abstand müssen positiv sein."}), 400

        eirp = power_w * 10 ** (gain_dbi / 10)
        e_field = math.sqrt(30 * eirp) / distance  # V/m
        power_density = eirp / (4 * math.pi * distance**2)  # W/m^2
        e_dbuvm = 20 * math.log10(e_field / 1e-6)

        return jsonify({
            "e_field_vm": round(e_field, 4),
            "e_field_dbuvm": round(e_dbuvm, 2),
            "power_density_wm2": round(power_density, 6),
            "power_density_mwcm2": round(power_density * 0.1, 6),
            "eirp_w": round(eirp, 4),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/smith", methods=["POST"])
def api_smith():
    """
    Smith-Diagramm: Reflexionsfaktor einer Lastimpedanz.
    Eingaben: r (Ω), x (Ω), z0 (Ω).
    """
    try:
        data = request.get_json()
        r = float(data["r"])
        x = float(data["x"])
        z0 = float(data.get("z0") or 50)

        if z0 <= 0 or r < 0:
            return jsonify({"error": "Z0 muss positiv und R nicht-negativ sein."}), 400

        zl = complex(r, x)
        gamma = (zl - z0) / (zl + z0)
        mag = abs(gamma)

        vswr = round((1 + mag) / (1 - mag), 3) if mag < 1 else None
        rl = round(-20 * math.log10(mag), 2) if mag > 0 else None

        return jsonify({
            "gamma_re": round(gamma.real, 4),
            "gamma_im": round(gamma.imag, 4),
            "gamma_mag": round(mag, 4),
            "vswr": vswr,
            "return_loss": rl,
            "r_norm": round(r / z0, 4),
            "x_norm": round(x / z0, 4),
        })
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/pattern", methods=["POST"])
def api_pattern():
    """
    Strahlungsdiagramm eines mittengespeisten Dipols.
    Eingabe: length (Dipollänge in Wellenlängen).
    """
    try:
        data = request.get_json()
        l_lambda = float(data["length"])

        if l_lambda <= 0:
            return jsonify({"error": "Länge muss positiv sein."}), 400

        beta = math.pi * l_lambda  # k·L/2
        raw = []
        amax = 0.0
        for deg in range(0, 361, 2):
            th = math.radians(deg)
            s = math.sin(th)
            if abs(s) < 1e-6:
                amp = 0.0
            else:
                amp = abs((math.cos(beta * math.cos(th)) - math.cos(beta)) / s)
            raw.append((deg, amp))
            amax = max(amax, amp)

        if amax == 0:
            amax = 1.0
        points = [{"angle": deg, "amp": round(amp / amax, 4)} for deg, amp in raw]

        amp_at = {p["angle"]: p["amp"] for p in points}
        hpbw = None
        deg = 90
        while deg >= 0 and amp_at.get(deg, 0) >= 0.7071:
            deg -= 2
        if deg < 90:
            hpbw = 2 * (90 - deg)

        return jsonify({"points": points, "hpbw": hpbw})
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/filter", methods=["POST"])
def api_filter():
    """
    Filter-Rechner: Grenzfrequenz und Amplitudengang von RC-, RL- und LC-Filtern.
    Eingaben: type, r (Ω), l (µH), c (nF).
    """
    try:
        data = request.get_json()
        ftype = data.get("type", "rc_lp")
        r = float(data.get("r") or 0)
        l = float(data.get("l") or 0) * 1e-6   # µH -> H
        c = float(data.get("c") or 0) * 1e-9   # nF -> F

        if ftype in ("rc_lp", "rc_hp"):
            if r <= 0 or c <= 0:
                return jsonify({"error": "R und C müssen positiv sein."}), 400
            fc = 1 / (2 * math.pi * r * c)
            order = 1
        elif ftype in ("rl_lp", "rl_hp"):
            if r <= 0 or l <= 0:
                return jsonify({"error": "R und L müssen positiv sein."}), 400
            fc = r / (2 * math.pi * l)
            order = 1
        elif ftype in ("lc_lp", "lc_hp"):
            if l <= 0 or c <= 0:
                return jsonify({"error": "L und C müssen positiv sein."}), 400
            fc = 1 / (2 * math.pi * math.sqrt(l * c))
            order = 2
        else:
            return jsonify({"error": "Ungültiger Filtertyp."}), 400

        highpass = ftype.endswith("_hp")
        f0, f1 = fc / 100, fc * 100
        n = 90
        step = (f1 / f0) ** (1 / (n - 1))
        points = []
        f = f0
        for _ in range(n):
            ratio = f / fc
            if order == 1:
                num = ratio if highpass else 1.0
                h = num / math.sqrt(1 + ratio ** 2)
            else:
                num = ratio ** 2 if highpass else 1.0
                h = num / math.sqrt(1 + ratio ** 4)
            points.append({"f": f, "db": round(20 * math.log10(h), 3)})
            f *= step

        return jsonify({
            "ftype": ftype,
            "fc": fc,
            "order": order,
            "slope": 40 if order == 2 else 20,
            "highpass": highpass,
            "points": points,
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
