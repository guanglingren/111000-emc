"""
EMC Tools — a small collection of electromagnetic compatibility calculators.
Built with Flask, deployed on Render.
"""

import math
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

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


@app.route("/api/microstrip", methods=["POST"])
def api_microstrip():
    """
    Characteristic impedance of a microstrip line (Hammerstad-Jensen, simplified).
    Inputs: w (mm), h (mm), t (mm), er (dielectric constant)
    """
    try:
        data = request.get_json()
        w = float(data["w"])
        h = float(data["h"])
        t = float(data["t"])
        er = float(data["er"])

        if w <= 0 or h <= 0 or er <= 0:
            return jsonify({"error": "Breite, Höhe und εᵣ müssen positiv sein."}), 400

        z0, er_eff = microstrip_characteristic(w, h, t, er)
        vp = C0 / math.sqrt(er_eff)
        delay_ps_per_mm = 1e9 / vp  # ps/mm

        return jsonify({
            "z0": round(z0, 2),
            "er_eff": round(er_eff, 3),
            "vp_fraction": round(vp / C0, 3),
            "delay": round(delay_ps_per_mm, 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/nearfield", methods=["POST"])
def api_nearfield():
    """
    Near-field / far-field boundary.
    Inputs: freq (MHz), optional D (m) for aperture/antenna size
    """
    try:
        data = request.get_json()
        freq_mhz = float(data["freq"])
        d = float(data.get("d") or 0)

        if freq_mhz <= 0:
            return jsonify({"error": "Frequenz muss positiv sein."}), 400

        freq_hz = freq_mhz * 1e6
        wavelength = C0 / freq_hz  # m

        # Reactive near-field boundary (lambda / 2*pi)
        reactive = wavelength / (2 * math.pi)
        # Radiating near-field outer / Fraunhofer (far-field) boundary
        # For small radiators: 3 * lambda. For larger apertures: 2*D^2/lambda
        far_small = 3 * wavelength
        far_large = (2 * d**2 / wavelength) if d > 0 else None

        return jsonify({
            "wavelength_m": round(wavelength, 4),
            "wavelength_mm": round(wavelength * 1000, 2),
            "reactive_m": round(reactive, 4),
            "far_small_m": round(far_small, 4),
            "far_large_m": round(far_large, 4) if far_large is not None else None,
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


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
        # R ≈ 168 - 10*log10(mu_r * f / sigma_r)  [approx, far-field plane wave]
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
    dB / Verhältniskonverter.
    Inputs: value, mode ("db_to_ratio" or "ratio_to_db"), kind ("power" or "voltage")
    """
    try:
        data = request.get_json()
        value = float(data["value"])
        mode = data.get("mode", "db_to_ratio")
        kind = data.get("kind", "power")

        if mode == "db_to_ratio":
            if kind == "voltage":
                ratio = 10 ** (value / 20)
            else:
                ratio = 10 ** (value / 10)
            return jsonify({
                "ratio": round(ratio, 6),
                "db": round(value, 4),
            })
        elif mode == "ratio_to_db":
            if value <= 0:
                return jsonify({"error": "Verhältnis muss positiv sein."}), 400
            if kind == "voltage":
                db = 20 * math.log10(value)
            else:
                db = 10 * math.log10(value)
            return jsonify({
                "db": round(db, 4),
                "ratio": round(value, 6),
            })
        else:
            return jsonify({"error": "Ungültiger Modus."}), 400
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/power", methods=["POST"])
def api_power():
    """
    dBm <-> mW Konverter.
    Inputs: value, direction ("dbm_to_mw" or "mw_to_dbm")
    """
    try:
        data = request.get_json()
        value = float(data["value"])
        direction = data.get("direction", "dbm_to_mw")

        if direction == "dbm_to_mw":
            mw = 10 ** (value / 10)
            return jsonify({
                "mw": round(mw, 6),
                "dbm": round(value, 4),
            })
        elif direction == "mw_to_dbm":
            if value <= 0:
                return jsonify({"error": "Leistung muss positiv sein."}), 400
            dbm = 10 * math.log10(value)
            return jsonify({
                "dbm": round(dbm, 4),
                "mw": round(value, 6),
            })
        else:
            return jsonify({"error": "Ungültige Richtung."}), 400
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/dbunit", methods=["POST"])
def api_dbunit():
    """
    dB-Einheiten-Konverter: dBµV, dBµA, dBm und ihre Linearwerte (µV, µA, mW).
    Eingaben: value, unit, z (Bezugsimpedanz in Ohm).
    """
    try:
        data = request.get_json()
        value = float(data["value"])
        unit = data.get("unit", "dbuv")
        z = float(data.get("z") or 50)

        if z <= 0:
            return jsonify({"error": "Bezugsimpedanz muss positiv sein."}), 400

        if unit in ("uv", "ua", "mw") and value <= 0:
            return jsonify({"error": "Linearwerte müssen positiv sein."}), 400

        if unit == "dbm":
            p_w = 10 ** (value / 10) / 1000
        elif unit == "mw":
            p_w = value / 1000
        elif unit == "dbuv":
            volt = 10 ** (value / 20) * 1e-6
            p_w = volt**2 / z
        elif unit == "uv":
            p_w = (value * 1e-6) ** 2 / z
        elif unit == "dbua":
            amp = 10 ** (value / 20) * 1e-6
            p_w = amp**2 * z
        elif unit == "ua":
            p_w = (value * 1e-6) ** 2 * z
        else:
            return jsonify({"error": "Ungültige Einheit."}), 400

        volt = math.sqrt(p_w * z)
        amp = math.sqrt(p_w / z)

        return jsonify({
            "dbuv": round(20 * math.log10(volt / 1e-6), 2),
            "dbua": round(20 * math.log10(amp / 1e-6), 2),
            "dbm": round(10 * math.log10(p_w * 1000), 2),
            "uv": round(volt / 1e-6, 4),
            "ua": round(amp / 1e-6, 4),
            "mw": round(p_w * 1000, 6),
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

        # Convert input to magnetic flux density B in tesla
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


@app.route("/api/electrical", methods=["POST"])
def api_electrical():
    """
    Electrical length calculator for RF lines.
    Inputs: freq (MHz), vf, degrees or length_mm.
    """
    try:
        data = request.get_json()
        freq_mhz = float(data["freq"])
        vf = float(data.get("vf") or 1)
        degrees_raw = data.get("degrees")
        length_mm_raw = data.get("length_mm")

        if freq_mhz <= 0 or vf <= 0 or vf > 1:
            return jsonify({"error": "Frequenz muss positiv sein und vf muss im Bereich 0..1 liegen."}), 400

        wavelength = C0 / (freq_mhz * 1e6)
        degrees = float(degrees_raw) if degrees_raw not in (None, "") else None
        length_mm = float(length_mm_raw) if length_mm_raw not in (None, "") else None

        if degrees is None and length_mm is None:
            return jsonify({"error": "Bitte entweder Grad oder Länge eingeben."}), 400

        if degrees is not None:
            length_m = wavelength * vf * degrees / 360
            length_mm = length_m * 1000
        else:
            length_m = length_mm / 1000
            degrees = length_m / (wavelength * vf) * 360

        return jsonify({
            "frequency_mhz": round(freq_mhz, 4),
            "velocity_factor": round(vf, 4),
            "wavelength_m": round(wavelength, 4),
            "length_m": round(length_m, 4),
            "length_mm": round(length_mm, 2),
            "degrees": round(degrees, 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/coax", methods=["POST"])
def api_coax():
    """
    Koaxialkabel-Charakteristische Impedanz.
    Eingaben: D (Außendurchmesser mm), d (Innendurchmesser mm), er.
    """
    try:
        data = request.get_json()
        D = float(data["D"])
        d = float(data["d"])
        er = float(data["er"])

        if D <= 0 or d <= 0 or er <= 0 or D <= d:
            return jsonify({"error": "D und d müssen positiv sein und D > d."}), 400

        z0 = 60.0 / math.sqrt(er) * math.log(D / d)
        vp = C0 / math.sqrt(er)

        return jsonify({
            "z0": round(z0, 2),
            "er": round(er, 3),
            "vp_fraction": round(vp / C0, 3),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/quarter", methods=["POST"])
def api_quarter():
    """
    Viertelwellen-Transformator.
    Eingaben: Zs, Zl, optional freq (MHz).
    """
    try:
        data = request.get_json()
        zs = float(data["zs"])
        zl = float(data["zl"])
        freq_mhz = float(data.get("freq") or 0)
        vf = float(data.get("vf") or 1)

        if zs <= 0 or zl <= 0:
            return jsonify({"error": "Zs und Zl müssen positiv sein."}), 400
        if vf <= 0 or vf > 1:
            return jsonify({"error": "Geschwindigkeitsfaktor muss im Bereich 0..1 liegen."}), 400

        z0 = math.sqrt(zs * zl)
        length_m = None
        if freq_mhz > 0:
            wavelength = C0 / (freq_mhz * 1e6)
            length_m = wavelength * vf / 4

        return jsonify({
            "z0": round(z0, 2),
            "frequency_mhz": round(freq_mhz, 4) if freq_mhz > 0 else None,
            "velocity_factor": round(vf, 4),
            "length_m": round(length_m, 4) if length_m is not None else None,
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/attenuation", methods=["POST"])
def api_attenuation():
    """
    Dämpfungsrechner.
    Eingaben: alpha (dB/m), Länge (m).
    """
    try:
        data = request.get_json()
        alpha = float(data["alpha"])
        length = float(data["length"])

        if alpha < 0 or length < 0:
            return jsonify({"error": "Dämpfung und Länge müssen nicht-negativ sein."}), 400

        total_db = alpha * length
        power_ratio = 10 ** (-total_db / 10)
        voltage_ratio = 10 ** (-total_db / 20)

        return jsonify({
            "total_db": round(total_db, 3),
            "power_ratio": round(power_ratio, 6),
            "voltage_ratio": round(voltage_ratio, 6),
            "alpha": round(alpha, 3),
            "length": round(length, 3),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400

@app.route("/api/coaxloss", methods=["POST"])
def api_coaxloss():
    """
    Koaxialkabel-Dämpfungsmodell.
    Eingaben: freq (MHz), D (mm), d (mm), er, tan_delta, sigma (S/m)
    """
    try:
        data = request.get_json()
        freq_mhz = float(data["freq"])
        D = float(data["D"])
        d = float(data["d"])
        er = float(data["er"])
        tan_delta = float(data.get("tan_delta") or 0)
        sigma = float(data.get("sigma") or 5.8e7)

        if freq_mhz <= 0 or D <= 0 or d <= 0 or er <= 0 or sigma <= 0 or D <= d:
            return jsonify({"error": "Ungültige Eingabe, prüfen Sie Werte."}), 400

        freq_hz = freq_mhz * 1e6
        D_m = D / 1000
        d_m = d / 1000
        z0 = 60.0 / math.sqrt(er) * math.log(D_m / d_m)
        rs = math.sqrt(math.pi * freq_hz * MU0 / sigma)
        r_in = d_m / 2
        r_out = D_m / 2
        alpha_c = 8.686 * rs / (4 * math.pi * z0) * (1 / r_in + 1 / r_out)
        alpha_d = 8.686 * math.pi * freq_hz * math.sqrt(MU0 * EPS0 * er) * tan_delta
        alpha_total = alpha_c + alpha_d

        return jsonify({
            "z0": round(z0, 2),
            "alpha_conductor": round(alpha_c, 4),
            "alpha_dielectric": round(alpha_d, 4),
            "alpha_total": round(alpha_total, 4),
            "frequency_mhz": round(freq_mhz, 4),
        })
    except (KeyError, ValueError, TypeError) as e:
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
