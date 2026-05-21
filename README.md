# EMC Tools

A small collection of electromagnetic compatibility calculators for working engineers.
Built with Flask. Designed to deploy on Render's free tier.

## Included calculators

1. **Shielding Effectiveness** — Schelkunoff plane-wave model: absorption + reflection + multi-reflection correction, plus skin depth.
2. **Magnetic Field Units** — converts between flux density (T, Gauss, dBpT) and field strength (A/m, Oersted, dBµA/m), assuming air (B = µ₀·H).
3. **Skin Depth** — computes the skin-effect penetration depth and surface resistance of a conductor at high frequency.
4. **Rise Time / Bandwidth** — relates signal rise time, 3 dB bandwidth and knee frequency for EMC estimates.
5. **Field Strength / Power Density** — far-field E-field and power density of a radiator at a given distance.
6. **dB Unit Converter** — converts a level into all common dB and linear units for voltage (dBµV, dBmV, dBV), current (dBµA, dBmA) and power (dBm, dBW), at a reference impedance.
7. **VSWR / Return Loss Converter** — computes VSWR, return loss, and reflection coefficient.
8. **Frequency / Wavelength Converter** — converts between MHz and meters for HF planning.
9. **PCB Impedance Calculator** — computes single-ended microstrip impedance and differential impedance for paired traces.
10. **LC Resonant Frequency** — resonant frequency and characteristic impedance of an LC pair, e.g. decoupling-capacitor self-resonance.
11. **HF Band & Antenna Formulas** — identifies the HF amateur band and computes λ/4 and λ/2 antenna lengths.

### Graphical tools

12. **Smith Chart** — plots a load impedance on the Smith chart with reflection coefficient and VSWR circle.
13. **Antenna Radiation Pattern** — polar plot of the radiation pattern of a centre-fed dipole.
14. **Filter Calculator** — cutoff frequency, schematic and magnitude response of RC, RL and LC low-/high-pass filters.
15. **Measurement Chain** — reconstructs the actual emission level from the receiver reading via antenna factor, cable loss, preamplifier and attenuator, with a signal-chain block diagram.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

## Deploy to Render

1. Push this repo to GitHub.
2. On Render: **New +** → **Web Service** → connect your GitHub repo.
3. Render will detect `render.yaml` and configure everything. Otherwise set:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
   - **Plan:** Free
4. Click **Deploy**. First build takes 2–4 minutes.
5. After deploy, add your custom domain under **Settings → Custom Domains**, then point your DNS as Render instructs.

## Adding a new calculator

1. Add a new `@app.route("/api/yourcalc", methods=["POST"])` function in `app.py`.
2. Add a corresponding `<section>` in `templates/index.html` with `data-form="yourcalc"` on its `<form>` and matching `data-key` attributes on result fields.
3. The JS at the bottom of the template handles the rest automatically.

## Notes

Formulas are first-order engineering approximations suitable for teaching and rough estimates. For production EMC design, validate with full-wave simulation and chamber measurement.
