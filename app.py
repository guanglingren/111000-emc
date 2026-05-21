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
# Free-space permeability (H/m)
MU0 = 4 * math.pi * 1e-7


# ---------- Calculator routes ----------

@app.route("/")
def index():
    return render_template("index.html")


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


@app.route("/api/chain", methods=["POST"])
def api_chain():
    """
    Messkette für Störaussendung (gestrahlt / leitungsgebunden).
    Rekonstruiert aus der Empfängeranzeige den tatsächlichen Störpegel.
    Eingaben: mode, v_rx (dBµV), factor (AF in dB/m bzw. Wandlerfaktor in dB),
              cable (dB), preamp (dB), atten (dB).
    """
    try:
        data = request.get_json()
        mode = data.get("mode", "radiated")
        v_rx = float(data["v_rx"])
        factor = float(data.get("factor") or 0)
        cable = float(data.get("cable") or 0)
        preamp = float(data.get("preamp") or 0)
        atten = float(data.get("atten") or 0)

        if mode not in ("radiated", "conducted"):
            return jsonify({"error": "Ungültige Messart."}), 400

        result = v_rx + cable + atten + factor - preamp

        out = {
            "mode": mode,
            "v_rx": round(v_rx, 2),
            "factor": round(factor, 2),
            "cable": round(cable, 2),
            "preamp": round(preamp, 2),
            "atten": round(atten, 2),
            "result": round(result, 2),
        }
        if mode == "radiated":
            out["result_label"] = "E-Feld"
            out["result_unit"] = "dBµV/m"
            out["result_linear"] = round(10 ** (result / 20) * 1e-6, 6)
            out["result_linear_unit"] = "V/m"
        else:
            out["result_label"] = "Störspannung"
            out["result_unit"] = "dBµV"
            out["result_linear"] = round(10 ** (result / 20), 4)
            out["result_linear_unit"] = "µV"
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/ri", methods=["POST"])
def api_ri():
    """
    Radiated Immunity, Antennenmethode (ISO 11452-2).
    Erforderliche Verstärkerleistung für eine Ziel-Feldstärke.
    Eingaben: e_target (V/m), gain (dBi), distance (m), cable (dB).
    """
    try:
        data = request.get_json()
        e_target = float(data["e_target"])
        gain_dbi = float(data.get("gain") or 0)
        distance = float(data["distance"])
        cable = float(data.get("cable") or 0)

        if e_target <= 0 or distance <= 0:
            return jsonify({"error": "Feldstärke und Abstand müssen positiv sein."}), 400

        g = 10 ** (gain_dbi / 10)
        p_net = e_target ** 2 * distance ** 2 / (30 * g)   # W
        p_net_dbm = 10 * math.log10(p_net * 1000)
        p_amp_dbm = p_net_dbm + cable
        p_amp = 10 ** (p_amp_dbm / 10) / 1000

        return jsonify({
            "e_target": round(e_target, 3),
            "distance": round(distance, 3),
            "gain": round(gain_dbi, 2),
            "cable": round(cable, 2),
            "p_net_w": round(p_net, 4),
            "p_net_dbm": round(p_net_dbm, 2),
            "p_amp_w": round(p_amp, 4),
            "p_amp_dbm": round(p_amp_dbm, 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


@app.route("/api/bci", methods=["POST"])
def api_bci():
    """
    BCI — Bulk Current Injection (ISO 11452-4).
    Wandelt Injektionsstrom, Vorlaufleistung und Zangen-Transferimpedanz.
    Eingaben: current (mA), r (Kalibrier-Impedanz Ω), zt (dBΩ).
    """
    try:
        data = request.get_json()
        current_ma = float(data["current"])
        r = float(data.get("r") or 50)
        zt_db = float(data.get("zt") or 0)

        if current_ma <= 0 or r <= 0:
            return jsonify({"error": "Strom und Impedanz müssen positiv sein."}), 400

        i_a = current_ma / 1000.0
        p_w = i_a ** 2 * r
        p_dbm = 10 * math.log10(p_w * 1000)
        i_dbua = 20 * math.log10(i_a / 1e-6)
        zt_lin = 10 ** (zt_db / 20)
        v_dbuv = i_dbua + zt_db
        v_uv = i_a * zt_lin / 1e-6

        return jsonify({
            "current_ma": round(current_ma, 4),
            "current_dbua": round(i_dbua, 2),
            "r": round(r, 2),
            "power_w": round(p_w, 6),
            "power_dbm": round(p_dbm, 2),
            "zt_dbohm": round(zt_db, 2),
            "zt_ohm": round(zt_lin, 4),
            "monitor_dbuv": round(v_dbuv, 2),
            "monitor_uv": round(v_uv, 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Ungültige Eingabe: {e}"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
