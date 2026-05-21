# EMC Tools

A small collection of electromagnetic compatibility calculators for working engineers.
Built with Flask. Designed to deploy on Render's free tier.

## Included calculators

1. **Microstrip Characteristic Impedance** — Hammerstad–Jensen closed-form with copper-thickness correction. Returns Z₀, effective εᵣ, velocity factor, and propagation delay.
2. **Near-Field / Far-Field Boundary** — λ/2π reactive boundary, 3λ small-radiator far-field, and 2D²/λ Fraunhofer distance for apertures.
3. **Shielding Effectiveness** — Schelkunoff plane-wave model: absorption + reflection + multi-reflection correction, plus skin depth.
4. **Magnetic Field Units** — converts between flux density (T, Gauss, dBpT) and field strength (A/m, Oersted, dBµA/m), assuming air (B = µ₀·H).
5. **Skin Depth** — computes the skin-effect penetration depth and surface resistance of a conductor at high frequency.
6. **Rise Time / Bandwidth** — relates signal rise time, 3 dB bandwidth and knee frequency for EMC estimates.
7. **Field Strength / Power Density** — far-field E-field and power density of a radiator at a given distance.
8. **dB Converter** — unified tool: ratio ⇄ dB (power/voltage) plus level units (dBµV, dBµA, dBm) and their linear values (µV, µA, mW) at a reference impedance.
9. **VSWR / Return Loss Converter** — computes VSWR, return loss, and reflection coefficient.
10. **Frequency / Wavelength Converter** — converts between MHz and meters for HF planning.
11. **Coaxial Impedance Calculator** — calculates the characteristic impedance of a coaxial line from D, d and εᵣ.
12. **Quarter-Wave Transformer** — computes the matching transformer impedance and λ/4 length corrected for the line velocity factor.
13. **Attenuation Calculator** — computes total cable loss from dB/m and length, plus power/voltage ratios.
14. **Coaxial Loss Model** — estimates conductor loss, dielectric loss, and total attenuation for coaxial cable.
15. **PCB Impedance Calculator** — computes single-ended microstrip impedance and differential impedance for paired traces.
16. **LC Resonant Frequency** — resonant frequency and characteristic impedance of an LC pair, e.g. decoupling-capacitor self-resonance.
17. **HF Band & Antenna Formulas** — identifies the HF amateur band and computes λ/4 and λ/2 antenna lengths.
18. **Electrical Length Calculator** — converts electrical degrees to physical line length and vice versa for a given frequency and velocity factor.

### Graphical tools

19. **Loss vs Frequency** — plots conductor, dielectric and total coaxial-cable attenuation across a frequency sweep.
20. **Smith Chart** — plots a load impedance on the Smith chart with reflection coefficient and VSWR circle.
21. **Antenna Radiation Pattern** — polar plot of the radiation pattern of a centre-fed dipole.

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
