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
            return jsonify({"error": "Width, height, and Er must be positive."}), 400

        # Effective width correction for trace thickness
        if t > 0:
            if w / h >= 1 / (2 * math.pi):
                w_eff = w + (t / math.pi) * (1 + math.log(2 * h / t))
            else:
                w_eff = w + (t / math.pi) * (1 + math.log(4 * math.pi * w / t))
        else:
            w_eff = w

        u = w_eff / h
        # Effective dielectric constant
        a = 1 + (1 / 49) * math.log((u**4 + (u / 52) ** 2) / (u**4 + 0.432)) \
            + (1 / 18.7) * math.log(1 + (u / 18.1) ** 3)
        b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
        er_eff = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)

        # Characteristic impedance
        f = 6 + (2 * math.pi - 6) * math.exp(-((30.666 / u) ** 0.7528))
        z0_air = (ETA0 / (2 * math.pi)) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))
        z0 = z0_air / math.sqrt(er_eff)

        # Propagation delay (ps/mm) and velocity factor
        vp = C0 / math.sqrt(er_eff)
        delay_ps_per_mm = 1e9 / vp  # ps/mm

        return jsonify({
            "z0": round(z0, 2),
            "er_eff": round(er_eff, 3),
            "vp_fraction": round(vp / C0, 3),
            "delay": round(delay_ps_per_mm, 2),
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400


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
            return jsonify({"error": "Frequency must be positive."}), 400

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
        return jsonify({"error": f"Invalid input: {e}"}), 400


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
            return jsonify({"error": "All inputs must be positive."}), 400

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
        return jsonify({"error": f"Invalid input: {e}"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
