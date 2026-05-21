# EMC Tools

A small collection of electromagnetic compatibility calculators for working engineers.
Built with Flask. Designed to deploy on Render's free tier.

## Included calculators

1. **Magnetic Field Units** — converts between flux density (T, Gauss, dBpT) and field strength (A/m, Oersted, dBµA/m), assuming air (B = µ₀·H).
2. **Rise Time / Bandwidth** — relates signal rise time, 3 dB bandwidth and knee frequency for EMC estimates.
3. **Field Strength / Power Density** — far-field E-field and power density of a radiator at a given distance.
4. **dB Unit Converter** — converts a level into all common dB and linear units for voltage (dBµV, dBmV, dBV), current (dBµA, dBmA) and power (dBm, dBW), at a reference impedance.
5. **VSWR / Return Loss Converter** — computes VSWR, return loss, and reflection coefficient.
6. **Frequency / Wavelength Converter** — converts between MHz and meters for HF planning.
7. **Filter Calculator** — cutoff frequency, schematic and magnitude response of RC, RL and LC low-/high-pass filters.
8. **Measurement Chain** — reconstructs the actual emission level from the receiver reading via antenna factor, cable loss, preamplifier and attenuator, with a signal-chain block diagram.
9. **RI Antenna Method** — required amplifier power for a target field strength in radiated immunity testing (ISO 11452-2).
10. **BCI** — bulk current injection: converts injected current, forward power and probe transfer impedance (ISO 11452-4).
11. **Measurement Uncertainty** — CISPR 16-4-2 uncertainty budget builder with editable contributions per automotive EMC test method (CISPR 25, ISO 11452), giving combined and expanded uncertainty (k = 2).

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
