# EMC Tools

A small collection of electromagnetic compatibility calculators for working engineers.
Built with Flask. Designed to deploy on Render's free tier.

## Included calculators

1. **Microstrip Characteristic Impedance** — Hammerstad–Jensen closed-form with copper-thickness correction. Returns Z₀, effective εᵣ, velocity factor, and propagation delay.
2. **Near-Field / Far-Field Boundary** — λ/2π reactive boundary, 3λ small-radiator far-field, and 2D²/λ Fraunhofer distance for apertures.
3. **Shielding Effectiveness** — Schelkunoff plane-wave model: absorption + reflection + multi-reflection correction, plus skin depth.

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
