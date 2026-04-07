# Tutorial 6: Preparing Event Datasets for Simulation-Based Inference

In this tutorial you will design how to organize and document simulated event samples from the full MG5 → Pythia → Delphes chain so that they are ready for use in Simulation-Based Inference (SBI) workflows.

You will **not** implement SBI algorithms here. Instead, you will:

- Clarify what SBI needs from simulations in terms of parameters, observations, and metadata.
- Design a directory and file structure for storing simulated data across many parameter points.
- Plan how to record metadata (e.g. EFT parameters, run settings, versions, random seeds).
- Decide how to represent event-level information and/or summary statistics for later use.

> **Important:** Treat this tutorial directory as read-only instructions. Do all your own work, dataset structures, metadata files, and scripts in:
>
> - `/output/tutorials/my_work/06_sbi_dataset_preparation`

You can refer back to this `README.md` as you build your own dataset layout.

---

## 1. Prerequisites

Before starting this tutorial, you should:

- Have completed Tutorials 1–5:
  - MG5 basics and the MG5 → Pythia → Delphes pipeline.
  - Standard Model Drell–Yan at parton level.
  - Pythia showering and hadronization.
  - Delphes detector simulation.
  - EFT UFO models in MG5 and basic EFT parameter scans.
- Be able to:
  - Generate SM and EFT samples at detector level (Delphes output) for at least one process.
  - Locate and interpret key configuration cards and param cards used in your simulations.
- Have basic programming experience (e.g. Python, C++, or similar) to eventually write analysis and SBI code, though this tutorial focuses only on planning and structure.

All concrete directory and file creation for this tutorial should happen under:

- `/output/tutorials/my_work/06_sbi_dataset_preparation`

---

## 2. What SBI needs from simulations (conceptual)

Simulation-Based Inference (SBI) refers to a family of methods that use simulations to learn about parameters of a model from observed data, without requiring an explicit analytic likelihood. At a high level, SBI requires:

1. **Parameters**
   - These are the quantities you want to learn about, such as EFT Wilson coefficients, coupling strengths, or other BSM parameters.
   - Denote the parameter vector symbolically as $\theta$ (e.g. a set of coefficients $C_i$).

2. **Simulated observations**
   - These can be:
     - **Event-level data**, such as lists of reconstructed objects per event.
     - **Summary statistics**, such as histograms, low-dimensional features, or other aggregated observables.
   - For each parameter point $\theta$, you will generate one or more simulated datasets.

3. **Consistent and well-documented simulation settings**
   - All samples in an SBI study must be comparable:
     - Same or clearly documented beam energy, PDFs, and cuts.
     - Known MG5, Pythia, and Delphes versions.
     - Controlled random seeds and event counts.

4. **Dataset splits**
   - For machine-learning–based SBI, you will typically divide your simulated data into:
     - Training sets.
     - Validation sets.
     - Test sets.
   - These splits should respect coverage of parameter space and avoid leakage of the same events across splits.

The goal of this tutorial is to plan a data and metadata structure that makes all of this explicit and easy to use later.

---

## 3. Designing a dataset directory structure

A clear, hierarchical directory layout helps you keep track of many simulations across parameter points and configurations.

### 3.1 Top-level layout

Consider a top-level dataset directory in your work area, for example:

```text
/output/tutorials/my_work/06_sbi_dataset_preparation/
  datasets/
    EXPERIMENT_NAME/   # e.g. a label for this study or project
```

Within a given experiment/study directory, you might organize by:

- **Process and model** (e.g. Drell–Yan with a specific EFT model).
- **Parameter configuration** (e.g. particular EFT coefficient values).
- **Data level** (parton level, hadron level, detector level, analysis-level summaries).

### 3.2 Example hierarchical structure

One possible structure (to adapt as needed) is:

```text
datasets/EXPERIMENT_NAME/
  config/                # Shared configuration files, cards, scripts, notes
  parameters/            # Definitions of parameter grids or scans
  raw/
    theta_001/
      mg5/               # Optional: MG5 process directory or pointers
      pythia/
      delphes/
    theta_002/
      ...
  processed/
    theta_001/
      events/            # Event-level representations (e.g. ROOT, HDF5, NPY)
      summaries/         # Precomputed summaries or features
    theta_002/
      ...
  logs/
    theta_001/
    theta_002/
```

Here `theta_001`, `theta_002`, etc. are labels for specific parameter points $\theta$. You might instead use a more descriptive naming scheme that includes parameter values symbolically (for example, `C1_pos`, `C1_neg`, etc.), as long as the mapping to actual numeric values is documented.

### 3.3 Standardized locations for different data types

Within each parameter-point directory, consider standardizing:

- **Raw simulation outputs**
  - LHE files from MG5 (if you choose to keep them).
  - Pythia outputs (e.g. HepMC or ROOT files).
  - Delphes ROOT files (detector-level events).

- **Processed or reduced representations**
  - ROOT ntuples with a subset of variables.
  - HDF5/NPY/Parquet files with per-event features.
  - Precomputed summary statistics (histograms, counts, etc.).

- **Logs and metadata**
  - MG5, Pythia, and Delphes logs.
  - Metadata files capturing parameters and settings (Section 4).

The key idea is that, given a parameter-point label (such as `theta_001`), you should be able to discover all associated raw and processed data in predictable locations.

---

## 4. Metadata design for simulations

Metadata ties together parameter values, simulation settings, and produced files. Well-designed metadata makes your simulations reproducible and usable in SBI pipelines.

### 4.1 What to record in metadata

For each parameter point $\theta$ and its associated runs, consider recording at least:

- **Parameter information**
  - Model name (e.g. Standard Model, chosen EFT model).
  - Names and values of the parameters (e.g. specific Wilson coefficients $C_i$).

- **Simulation settings**
  - MG5 process definition (e.g. text description or reference to a command file).
  - Run card settings (beam energy, cuts, PDFs, number of events).
  - Pythia configuration (shower settings, tune, seeds if relevant).
  - Delphes configuration (detector card name and any modifications).

- **Technical details**
  - Versions of MG5, Pythia, and Delphes.
  - Random seeds used for each stage (MG5 integration, event generation, Pythia, Delphes).
  - Date/time of simulations.

- **File references**
  - Paths to raw LHE, Pythia, and Delphes outputs.
  - Paths to processed event-level files and summary statistics.

### 4.2 Metadata file formats

Metadata should be:

- **Human-readable** – so you can quickly inspect and debug it.
- **Machine-readable** – so scripts can parse it reliably.

Common choices include:

- **YAML** – flexible, human-friendly syntax, natively supported by many languages.
- **JSON** – widely supported, simple key–value structure.

A metadata file for a parameter point could live in, for example:

```text
processed/theta_001/metadata.yaml
```

and contain nested fields for parameters, settings, and file paths. You do not need to specify a final schema here, but you should plan for consistent structure across all parameter points.

---

## 5. From events to SBI-ready summaries (conceptual)

SBI workflows may use either event-level data or compressed summaries as inputs.

### 5.1 Event-level representations

In an event-level approach, you keep detailed per-event information, such as:

- Four-momenta of reconstructed objects (e.g. electrons, muons, jets).
- Event-level quantities (e.g. missing transverse energy, global observables).
- Possible labels or weights associated with events.

These can be stored in formats such as ROOT, HDF5, or NumPy arrays. Later, analysis or SBI code can:

- Read events.
- Apply selections.
- Construct features on the fly.

### 5.2 Summary statistics

In a summary-based approach, you precompute lower-dimensional representations, such as:

- Histograms of kinematic quantities (e.g. distributions of $p_T$, invariant masses, angular variables).
- Counts or rates of events passing specific selection criteria.
- Custom-designed features or learned embeddings.

Summary statistics can be stored in simple formats such as:

- ROOT histograms saved in ROOT files.
- Arrays or tables stored in HDF5/NPY/Parquet.

The choice of summaries is problem-dependent and should reflect the physics questions you want to address. For SBI, the important part is that you can:

- Associate each summary with the corresponding parameter point $\theta$.
- Recompute or refine summaries if needed as your analysis evolves.

### 5.3 Consistency across parameter points

Regardless of whether you keep event-level data, summaries, or both, it is crucial that:

- The same definitions of observables and selections are applied across all parameter points.
- The same binning and ranges are used for histograms where comparisons are made.
- Any changes to definitions are documented and captured in metadata.

This consistency is essential for SBI methods that rely on comparing simulations across different parameter values.

---

## 6. Exercises (no solutions or numeric answers in this file)

Perform all practical tasks in your own workspace:

- `/output/tutorials/my_work/06_sbi_dataset_preparation`

The prompts below are open-ended. This `README.md` does not include solutions, numeric results, SBI code, or “correct” schemas.

### Exercise 1 – Designing a concrete directory and naming scheme

1. Choose a specific EFT process and parameterization (for example, an EFT-extended Drell–Yan setup) to serve as your running example.
2. Propose a concrete directory layout and naming scheme under your `datasets/` directory that encodes:
   - The process and model.
   - The parameter point label (e.g. $\theta$ index).
   - The data level (raw vs. processed).
3. Implement this layout in your work area by creating empty directories and placeholder files as needed.

### Exercise 2 – Populating the structure with a small set of parameter points

1. Select a small set of EFT parameter points from Tutorial 5.
2. For each parameter point, generate (or reuse) MG5 → Pythia → Delphes samples.
3. Place the resulting outputs into your new dataset structure, ensuring that:
   - Raw and processed files are stored in their intended locations.
   - Logs are kept in an organized way.
4. Document, in a short text file, how you mapped each run to a parameter-point label.

### Exercise 3 – Designing metadata files

1. For at least one parameter point, draft a metadata file (YAML or JSON) that records:
   - The parameter values used (e.g. which EFT coefficients and their symbolic values).
   - Key MG5, Pythia, and Delphes settings and versions.
   - Paths to the relevant raw and processed files.
2. Extend this metadata design to multiple parameter points, ensuring that the structure is consistent and easy to parse.
3. In your notes, describe how analysis or SBI code would load and use this metadata.

### Exercise 4 – Planning observables and summary statistics

1. For your chosen EFT process, decide on a small set of observables that you expect to be informative for the parameters of interest (e.g. kinematic distributions, angular variables, counts of certain event types).
2. Write down, in pseudocode or plain language, how you would:
   - Read Delphes ROOT files for each parameter point.
   - Apply consistent selection cuts across all samples.
   - Compute and store these observables as either event-level features or summary statistics.
3. Reflect on how you might revise or expand this observable set as your analysis goals evolve.

### Exercise 5 – Planning dataset splits for SBI

1. Propose a strategy for splitting your simulated data into training, validation, and test sets, taking into account:
   - Coverage of parameter space (e.g. which parameter points are used for which split).
   - Avoiding reuse of the exact same events across splits.
2. Describe, in words, how you would implement these splits within your directory structure (for example, separate subdirectories or labels in metadata).
3. Note any potential pitfalls (e.g. correlated samples, imbalanced coverage) and how you might mitigate them.

### Exercise 6 – Ensuring reproducibility

1. List the minimal set of information you would need to regenerate any given dataset element (for example, a specific parameter point and data level) from scratch.
2. Compare this list to the metadata you designed in Exercise 3 and note any gaps.
3. Update your metadata design or documentation plan to close these gaps and support reproducible SBI workflows.

---

By completing this tutorial, you will have a clear plan for organizing MG5 → Pythia → Delphes simulations into structured, well-documented datasets suitable for Simulation-Based Inference. This sets the stage for implementing actual SBI methods in subsequent work.
