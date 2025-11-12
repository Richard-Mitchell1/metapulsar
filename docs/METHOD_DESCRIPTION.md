## Method: Direct combination (“MetaPulsar”)

### Problem statement and summary

Given multiple public PTA data sets for the **same** pulsar—each consisting of a **timing model** (a `.par` file) and **times of arrival** (a `.tim` file)—we construct a single “metapulsar” that can be analyzed with standard PTA likelihoods without first re‑deriving a common timing solution. The procedure **does not modify the TOAs**; it only organizes the **deterministic timing model** across PTAs, and then builds the **combined design matrix** and metadata needed by Enterprise/Discovery.

After analytic marginalization over timing‑model parameters, the likelihood depends on the **column space** of the design matrix ( **M** ) rather than on the specific nominal parameter values ( β₀ ). Our procedure guarantees that the relevant column space is the same as in a traditional manual combination, so (within the validity of the standard linearization) it is **statistically equivalent** to a full re‑timing while being vastly simpler and deterministic.

### Inputs and conventions

For each PTA (p) that observed a given pulsar we require:

* a `.par` file specifying the **deterministic timing model** (astrometry, spin, binary, dispersion, and instrument/telescope‑specific deterministic delays such as **JUMPs**, **FD** coefficients, and overall **phase offsets**), and
* a `.tim` file with TOAs and their formal uncertainties.

Let ( **d**_p ) denote the vector of residuals for PTA (p) when linearized about its nominal model ( β_{0,p} ), and let ( **M**_p ) be the corresponding design matrix (partial derivatives of the residuals with respect to timing‑model parameters). The full data vector is the concatenation ( **d** = ⨁_p **d**_p ). White‑ and red‑noise hyperparameters (EFAC/EQUAD/ECORR and RN/DM GP parameters) are **not** part of the deterministic timing model and are handled in the subsequent noise inference; we leave them unchanged at this stage.

We use **PINT** and **Tempo2/libstempo** to parse/realize timing models, and **Enterprise** classes to hold pulsar objects. The implementation provides two combination modes:

* **consistent** (default): make consistent astrophysical timing‑model components across PTAs while preserving detector‑specific timing‑model terms;
* **composite**: leave all `.par` files untouched and compose them as‑is (useful for diagnostics; everything remains PTA‑specific).

### Step 1: Unit normalization and reference model

We first ensure that all `.par` files are in the same time unit convention:

1. Read all `.par` files. If mixed `UNITS` are detected (TCB vs TDB), convert to **TDB**.

   * For PINT models we re‑emit the model in TDB;
   * For Tempo2 models we call the `transform tdb` plugin (both paths are implemented).
2. Align **EPHEM** and **CLOCK/CLK** keywords to those of a **reference PTA**. By default the reference is the first PTA in the (optionally user‑ordered) list; a convenience function can choose the PTA with the longest timespan. This keeps solar‑system ephemerides and clock standards coherent without altering the TOAs.

**No TOA samples are modified** in this step or any subsequent step of this method.

### Step 2: Merge astrophysical timing‑model components

We merge selected **astrophysical** components across PTAs by **copying parameter values from the reference PTA** into the other `.par` files *for those components only*. The set of components is configurable and defaults to

* `astrometry` (RAJ/DECJ or ELONG/ELAT, proper motions, etc.),
* `spindown` (F0, F1, …),
* `binary` (Keplerian and post‑Keplerian parameters),
* `dispersion` (baseline DM and its low‑order derivatives).

Concretely:

* For each component, we discover its parameters in each PTA’s timing model using PINT’s model metadata and a transparent alias resolver (e.g., `RAJ`/`ELONG`, `DECJ`/`ELAT`, `TASC`/`T0`, etc.).
* In non‑reference PTAs we **remove any existing values** for those component parameters and **insert the reference PTA’s values**. This ensures that all PTAs linearize around the same astrophysical trajectory.

#### Dispersion special handling

To avoid PTA‑specific *DMX* implementations and make the deterministic part of the dispersion model uniform, we:

* remove **DMX** parameters if present,
* ensure that **DM** is present and marked **free**,
* define a fixed **DMEPOCH** (copied from the reference; frozen), and
* optionally insert **DM1** and **DM2** (default: present and **free**, initialized at 0).

This choice keeps the deterministic dispersion expansion identical across PTAs while leaving the **stochastic DM process** (DM GP) to the noise model, as is standard practice.

> **Detector‑specific timing‑model parameters.**
> Terms that describe *deterministic* instrument/telescope‑dependent delays—e.g., **JUMPs**, **FD** coefficients, and overall **phase offsets**—are part of the timing model and are **not** made consistent. They remain **PTA/backend specific**. By contrast, **EFAC/EQUAD/ECORR** are **noise** hyperparameters (not timing‑model parameters) and are *never* touched here.

Terminology: we use the word consistent to describe model components or parameters that are common between data of different PTAs, and that we 'lock' together (i.e. they become the same parameters or model component).

### Step 3: Build Enterprise pulsars and validate identity

For each PTA we build an Enterprise pulsar object:

* PINT path: `ep.PintPulsar(TOAs, TimingModel, planets=True)`.
* Tempo2 path: `ep.Tempo2Pulsar(tempopulsar, planets=True)`.

We validate that all PTAs refer to the **same sky position** by converting names to a canonical **J‑name** derived from coordinates. “B‑vs‑J” selection is only for **display**—coordinate matching is authoritative.

### Step 4: Parameter mapping (merged vs PTA‑specific)

We now define the **meta‑parameters** that the combined design matrix will use.

* For any parameter that belongs to a consistent component and exists across PTAs, we expose **one merged meta‑parameter** (e.g., `RAJ`, `F0`, `PB`, `DM`), mapped to the corresponding parameter name in each PTA object.
* All **detector‑specific** timing‑model parameters (e.g., `JUMP`, `FD*`, per‑backend offsets) are exposed as **PTA‑specific** meta‑parameters by suffixing with the PTA label (e.g., `JUMP_XXXX_epta`, `Offset_nanograv`).
* If a per‑dataset **phase offset** is implicit in a given timing package, we explicitly include an **`Offset_<pta>`** meta‑parameter to reflect the standard constant phase term that is effectively fit in pulsar timing (this is not a noise parameter).
* NOTE: The `Offset_XXXX` parameter is effectively just a `JUMP_XXXX` parameter for that specific PTA. But the name `Offset` make it clear it is _not_ an added parameter, but merely the mapped phase offset from a specific PTA.

This mapping is produced by `ParameterManager.build_parameter_mappings()` and recorded as `fitparameters` (free) and `setparameters` (present) in the `MetaPulsar` object. It is **deterministic** given the input `.par` files and the selected consistent components.

### Step 5: Concatenate TOAs and flags (no data edits)

We concatenate the per‑PTA arrays into combined vectors:

* TOAs, residuals, TOA errors, SSB frequencies, telescope codes, etc.
* Flags include `pta`, `pta_dataset`, and `timing_package` tags for each TOA.

Again, **no TOA value is altered**; this is a pure concatenation with bookkeeping.

### Step 6: Construct the combined design matrix

Let ( **P** ) be the set of meta‑parameters (columns to be fit). For each meta‑parameter ( q ∈ **P** ):

1. For each PTA, locate the corresponding underlying parameter (using the mapping).
2. Copy the associated **design‑matrix column** from that PTA’s Enterprise object into the appropriate rows of the combined design matrix.
3. Apply **unit matching** where PINT and Tempo2 differ (e.g., RA, DEC, ecliptic longitude/latitude in hourangle/deg vs radians); these conversions are explicit and limited to astrometric columns.

After assembly we perform a **non‑identifiability check**: any column whose absolute sum is numerically zero (no support in any rows) is dropped from the fit list. This avoids singular normal matrices and is reported via warnings (note: if a parameter has zero support, this indicates an error in the inderlying data release. This happens in, e.g., IPTA-DR2 datasets).

### Step 7: Planetary and positional metadata

We adopt position vectors, SSB ephemerides, and related arrays directly from the underlying Enterprise objects and copy them into the combined structure row‑wise. This is bookkeeping only and does not alter any physical quantity.

### Statistical equivalence to a manual combination (sketch)

For each PTA (p), linearize timing residuals about the (possibly different) nominal parameter vectors ( β_{0,p} ):

**r**_p(β) ≈ **n**_p - **M**_p ε,  where ε ≡ β - β₀,  and **n**_p ~ N(0, **C**_p).

Concatenate over PTAs: ( **r** = **n** - **M** ε ), ( **C** = diag(**C**_p) ), and let ( **M** ) contain **merged** columns for consistent parameters and **block‑diagonal** columns for PTA‑specific parameters (exactly what the construction above produces).

The Gaussian likelihood marginalized over ( ε ) with flat priors depends on the **projector**

**P** = **I** - **M** ( **M**^T **C**^{-1} **M** )^{-1} **M**^T **C**^{-1}.

Any re‑timing that yields the **same column space** of ( **M** ) produces the **same marginalized likelihood** (and therefore the same posteriors for noise and GW parameters and the same frequentist quadratic statistics). Our method to make model components consistent ensures that the astrophysical columns are **shared** across PTAs and detector‑specific columns remain **PTA‑local**, which is exactly the structure a manual combined global `.par` would produce. Differences in the **nominal** parameter values ( β_{0,p} ) do not affect the marginalized likelihood (beyond negligible second‑order effects), because only the **derivatives** (the columns of ( **M** )) enter ( **P** ). Hence, under the standard linear‑response assumptions used throughout PTA analyses, this direct combination is **not less accurate** than a manual global re‑fit.

### Practical options and safeguards

* **Choice of consistent components.** The default choice `{astrometry, spindown, binary, dispersion}` fits most pulsars. For problematic sources one can drop a component from the consistent set; all parameters of that component then remain PTA‑specific.
* **DM modeling.** Removing DMX in favor of {DM, DMEPOCH, DM1, DM2} makes the deterministic DM part uniform. Stochastic DM variations are handled entirely in the noise model (e.g., a DM GP) during inference.
* **Nonlinear regimes.** If a pulsar resides in a regime where ( **M** ) varies rapidly with ( β₀ ) (high‑order binary models, poorly constrained orbital evolution), manual inspection is recommended. The factory allows a **composite** strategy (no merging model components) for such cases.
* **Name handling.** Pulsar identity is validated via **coordinates**. B‑ vs J‑name is a display convention only and does not enter any computation.
* **Determinism and provenance.** Given the set of `.par`/`.tim` inputs, the chosen reference PTA, and the list of consistent components, the output is deterministic. The code can optionally write the **consistent** `.par` files it constructs for full auditability.

### Implementation details (reproducibility pointers)

* **Factory and orchestration.** `MetaPulsarFactory.create_metapulsar(...)` loads `.par` content, validates the single‑pulsar grouping by coordinates, selects/accepts the reference PTA, and (for the **consistent** strategy) calls `ParameterManager.make_parfiles_consistent()` to emit consistent `.par` files (optionally to disk).
* **Parameter discovery and aliasing.** `ParameterManager` uses PINT’s model metadata plus a lightweight alias resolver to collect the parameter sets by *component type* and to resolve name differences between PINT and Tempo2.
* **Design‑matrix assembly.** `MetaPulsar` (a subclass of `enterprise.pulsar.BasePulsar`) builds `fitparameters`/`setparameters` from the mapping, concatenates the per‑PTA arrays, and assembles the combined `designmatrix` column‑by‑column—applying explicit unit corrections for astrometric columns where PINT and Tempo2 differ. A zero‑information column cull prevents singularities.
* **Flags and metadata.** The combined flags include `pta`, `pta_dataset`, and `timing_package`. Planetary and positional arrays are copied row‑wise from the underlying Enterprise pulsars.

### What this method does **not** do

* It **does not** change TOAs, TOA uncertainties, or back‑end flags.
* It **does not** optimize or “re‑fit” timing‑model parameters before analysis.
* It **does not** decide noise hyperparameters; EFAC/EQUAD/ECORR and the red/DM noise models are inferred in the usual way in Enterprise/Discovery after the metapulsar is constructed.

### Minimal algorithm (for reference)

1. **Parse & normalize units** for all PTAs (`UNITS → TDB`; align `EPHEM`, `CLOCK/CLK`).
2. **Make consistent** selected components by copying reference PTA values; **leave detector‑specific timing‑model parameters as PTA‑local**; for dispersion: remove DMX, set DM (free), set DMEPOCH (frozen), add DM1/DM2 (free, 0).
3. **Instantiate** Enterprise pulsars (PINT or Tempo2 path). Validate same pulsar by coordinates.
4. **Map parameters** into merged and PTA‑specific meta‑parameters (deterministic mapping).
5. **Concatenate** per‑PTA arrays (TOAs, flags, etc.) without modification.
6. **Assemble** the combined design matrix column‑by‑column using the mapping, with explicit unit conversions; drop zero‑information columns.
7. **Expose** a `MetaPulsar` object fully compatible with Enterprise/Discovery.

---

#### Notes

* **Unit conversions and ephemeris/clock alignment:** `ParameterManager._convert_units_if_needed`, `_convert_pint_to_tdb`, `_convert_tempo2_to_tdb`, and the EPHEM/CLOCK block in `_make_parameters_consistent`.
* **Component discovery/aliasing:** `get_parameters_by_type_from_models`, `resolve_parameter_alias`, `check_component_available_in_model`.
* **Dispersion handling:** `ParameterManager._handle_dm_special_cases` (remove DMX, set DM/DMEPOCH, add DM1/DM2).
* **Detector‑specific timing‑model parameters remain local:** anything not in the consistent component set becomes PTA‑suffixed in `_add_pta_specific_parameter`.
* **Phase offset exposure:** if `PHOFF` is absent we add a meta‑parameter mapped to the canonical “Offset” column so that per‑dataset constant phase terms are explicit.
* **Combined design matrix:** `MetaPulsar._build_design_matrix` (with unit corrections in `_convert_design_matrix_units`) and the zero‑information cull in `_remove_nonidentifiable_parameters`.
* **Identity validation and naming:** `bj_name_from_pulsar` and coordinate‑based checks in `_validate_pulsar_consistency`.
* **No TOA edits:** `MetaPulsar._combine_timing_data` concatenates; there are no writes or transforms of TOAs.

