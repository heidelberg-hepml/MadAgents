# Tutorial 4: Fast Detector Simulation with Delphes

In this tutorial you will learn how to perform fast detector simulation with Delphes, starting from hadron-level events produced by Pythia. Delphes approximates the response of a collider detector, turning stable particles into reconstructed objects such as electrons, muons, jets, and missing transverse energy.

You will:

- Understand the role of detector simulation in the MG5 → Pythia → Delphes chain.
- Learn what Delphes detector cards are and what they control.
- Run Delphes (via MG5’s interface or conceptually in standalone mode) on hadron-level events.
- Inspect the resulting ROOT files and identify the main physics object collections.

> **Important:** Treat this tutorial directory as read-only instructions. Do all your own work, detector cards, scripts, and analyses in:
>
> - `/output/tutorials/my_work/04_delphes_detector`

Keep this `README.md` as a reference while working in your own area.

---

## 1. Prerequisites

Before starting this tutorial, you should:

- Have completed Tutorials 1–3:
  - `01_mg5_basics` – MG5 basics and event-generation pipeline.
  - `02_sm_drell_yan_parton` – Parton-level Drell–Yan generation.
  - `03_pythia_showering` – Pythia showering and hadronization.
- Have at least one hadron-level event sample, for example:
  - A Drell–Yan sample where Pythia has been run through MG5, producing hadron-level events in `Events/run_XX/`.
- Have access to a setup where the Delphes interface is available to MG5, or where Delphes can be run standalone on an event file.

All hands-on tasks for this tutorial should be carried out in:

- `/output/tutorials/my_work/04_delphes_detector`

You may copy or link Pythia output files there for use with Delphes.

---

## 2. Where Delphes fits in the simulation chain

By this point, you have seen:

1. **MG5 (matrix elements and parton-level events)** – generates parton-level LHE files for processes such as $pp \to \ell^+ \ell^- + X$.
2. **Pythia (showering and hadronization)** – turns parton-level events into hadron-level events with parton showers, hadronization, and underlying event.

Delphes adds the final step:

3. **Delphes (fast detector simulation)**
   - Takes hadron-level events as input.
   - Simulates tracking, calorimetry, and other detector subsystems in a parametrized way.
   - Reconstructs physics objects (e.g. electrons, muons, jets, missing transverse energy) and writes them to a ROOT file.

This detector-level output is what you typically use for physics analyses that aim to mimic real experimental conditions.

---

## 3. Delphes basics and detector cards

Delphes is driven by **detector cards**, which are configuration files (often with a `.tcl` extension) describing the characteristics of an idealized detector.

### 3.1 What a Delphes card controls

A detector card typically specifies:

- **Detector geometry and acceptance**
  - Coverage in pseudorapidity ($\eta$) for tracking and calorimetry.
  - Segmentation of calorimeter cells.

- **Resolutions and efficiencies**
  - Momentum and energy resolution for charged particles and calorimeter deposits.
  - Identification efficiencies and fake rates for electrons, muons, and other objects.

- **Object reconstruction algorithms**
  - How jets are clustered (e.g. choice of algorithm and radius parameter).
  - How missing transverse energy (MET) is calculated.

- **Trigger or selection emulation** (when included)
  - Simple thresholds or object requirements that approximate triggers.

Small changes in the card can lead to noticeable differences in reconstructed objects, so it is important to know which parameters you have changed.

### 3.2 Standard detector cards

Delphes comes with example cards intended to resemble generic detector setups, such as:

- A generic LHC-like detector.
- Cards inspired by specific experiments (e.g. ATLAS-like or CMS-like), though they are not official experiment configurations.

In MG5-integrated workflows, these cards may live inside the Delphes installation directory or be copied into your process directory (for example under `Cards/`) when you enable Delphes through MG5.

---

## 4. Running Delphes through the MG5 interface

In many setups, the simplest way to use Delphes is via MG5’s run interface. This assumes that Delphes is installed and that MG5 has been configured to know where to find it.

### 4.1 Enabling Delphes in a MG5 launch

Start MG5 and launch an existing process directory that already produces hadron-level events with Pythia (for example, your Drell–Yan process from Tutorial 3):

```bash
cd /path/to/your/work
./path/to/MG5_DIR/bin/mg5_aMC
```

At the MG5 prompt:

```text
MG5_aMC > launch YOUR_PROC_DIR
```

Replace `YOUR_PROC_DIR` with the path to your process directory.

When the run interface starts, you may be presented with options to:

- Enable or disable Pythia showering.
- Enable or disable Delphes detector simulation.

The exact wording of the options may vary, but common patterns include:

- A summary line indicating whether Delphes is currently `ON` or `OFF`.
- A menu entry that toggles Delphes or selects a particular detector card.

Use these options to:

1. Turn on Pythia showering (if not already enabled).
2. Turn on Delphes detector simulation.
3. Choose or confirm which Delphes card will be used (either a default card or a card you supply).

Then proceed through the remaining prompts to start the run.

> **Note:** If MG5 cannot find Delphes or the interface is not available, consult your local installation notes or official documentation. The exact steps to install and connect Delphes are system dependent and are not covered in this tutorial.

### 4.2 Delphes cards in the process directory

When you enable Delphes for a process, MG5 may copy a default Delphes card into the process directory, often under `Cards/` with a name such as:

- `delphes_card.dat`, or
- a specific card name indicating the detector type (for example, a generic LHC-like card).

You can inspect this file with a text editor to see the detector configuration being used. For the purposes of this tutorial, you can:

- Start with a default card.
- Make controlled changes (for example, adjusting a resolution or efficiency parameter) for exploratory studies.

Keep careful track of any changes you make so you can compare different configurations later.

---

## 5. Running Delphes in standalone mode (conceptual)

In some workflows, you may prefer to run Delphes as a standalone program, independently of MG5’s run interface. The basic idea is:

1. Use MG5 and Pythia to produce hadron-level events in a format Delphes can read (for example, a HepMC or ROOT-based format, depending on your Delphes version).
2. Run a Delphes executable from the command line, specifying:
   - The detector card to use.
   - The input event file.
   - The output ROOT file to be produced.

The exact command-line syntax depends on your Delphes version and setup and is therefore not specified in detail here. Consult the Delphes manual and any local documentation if you wish to use standalone mode.

For this tutorial, it is sufficient to understand that such a mode exists and that MG5-integrated runs are a convenient way to start.

---

## 6. Delphes outputs and how to inspect them

After running Delphes (either through MG5 or standalone), you will obtain a ROOT file containing detector-level events.

### 6.1 Typical output location

If you ran Delphes through MG5, the Delphes ROOT file is usually written into the same run directory that contains the LHE and Pythia output, for example:

```bash
cd /path/to/your/work/YOUR_PROC_DIR/Events/run_XX
ls
```

You should see:

- The original parton-level LHE file(s).
- Hadron-level event file(s) from Pythia.
- One or more ROOT files produced by Delphes.

The MG5 run log and on-screen messages typically indicate the exact name and path of the Delphes ROOT file.

### 6.2 Contents of the Delphes ROOT file

The Delphes ROOT file contains one or more trees with branches corresponding to reconstructed physics objects. Common collections include (names may vary by version and card):

- **Electrons** – reconstructed electron candidates.
- **Muons** – reconstructed muon candidates.
- **Jets** – reconstructed jets using a specified clustering algorithm and radius.
- **Missing transverse energy (MET)** – an estimate of momentum imbalance in the transverse plane.
- **Tracks and towers** – lower-level detector signals that feed into higher-level objects.

Each object type typically has branches for kinematic quantities (e.g. transverse momentum $p_T$, pseudorapidity $\eta$, azimuthal angle $\phi$) and other attributes (e.g. identification quality flags).

### 6.3 Inspecting Delphes output with ROOT or Python

There are several ways to explore the contents of the Delphes ROOT file:

- **ROOT interactive session**
  - Start ROOT and use a browser to inspect trees and branches.
  - Draw quick histograms of basic quantities (e.g. lepton $p_T$) to check that the output looks reasonable.

- **Python-based tools**
  - Use libraries such as `uproot` to open the ROOT file in Python.
  - Inspect branch names and structures.
  - Write short scripts to loop over events and extract observables.

In this tutorial you are not required to implement a full analysis; the main goal is to become comfortable locating and examining the detector-level objects that Delphes provides.

---

## 7. Exercises (no solutions or numeric answers in this file)

Carry out all hands-on tasks in your own workspace:

- `/output/tutorials/my_work/04_delphes_detector`

This `README.md` provides prompts only. It does not contain solutions, numeric answers, or fully worked-out analysis scripts.

### Exercise 1 – Running Delphes on a Pythia-showered Drell–Yan sample

1. Choose a Drell–Yan process directory from Tutorial 3 that already produces hadron-level events with Pythia.
2. Use MG5’s `launch` interface to enable Delphes for this process, selecting an appropriate default detector card.
3. Run a Delphes-enabled simulation and identify, in your notes, which ROOT file(s) in `Events/run_XX/` correspond to the detector-level output.
4. Record the detector card used for this run and where it is stored in your process directory.

### Exercise 2 – Inspecting reconstructed object collections

1. Open the Delphes ROOT file from Exercise 1 using either ROOT or a Python-based tool.
2. List the main collections (trees or branches) corresponding to reconstructed electrons, muons, jets, and missing transverse energy.
3. For each collection, identify a few key kinematic variables (e.g. $p_T$, $\eta$, $\phi$) and note how they are stored (for example, as arrays per event).
4. In your notes, describe how you would select events containing at least one reconstructed dilepton pair.

### Exercise 3 – Comparing detector-level objects to hadron-level expectations

1. For a subset of events, conceptually match detector-level objects (e.g. reconstructed leptons and jets) to the hadron-level information from Pythia.
2. Compare, in qualitative terms, how:
   - Lepton momenta and directions change due to detector effects.
   - Jet multiplicities and kinematics differ between hadron level and detector level.
3. Reflect on which observables you expect to be most robust against detector effects and which are more sensitive.

### Exercise 4 – Exploring different detector cards

1. Identify at least two different Delphes detector cards available in your setup (for example, a generic LHC-like card and an alternative with different assumptions).
2. Run Delphes on the same Pythia-showered Drell–Yan sample using each card separately.
3. Without quoting specific histograms or numbers, describe qualitatively how the reconstructed objects differ between the two cards (e.g. in terms of acceptance, resolutions, or object multiplicities).
4. Summarize, in words, what kinds of physics analyses might be sensitive to these differences.

### Exercise 5 – Sketching an analysis flow

1. Choose a detector-level observable of interest, such as the dilepton invariant mass, leading lepton transverse momentum, or jet multiplicity.
2. Write down, in pseudocode or plain language, the steps needed to:
   - Open the Delphes ROOT file.
   - Loop over events.
   - Apply basic selection criteria (for example, lepton $p_T$ and $\eta$ cuts).
   - Fill a histogram of your chosen observable.
3. Note any additional information (such as object identification flags or event weights) that you would need for a realistic physics analysis.

### Exercise 6 – Organizing detector-level datasets for later use

1. Design a directory and naming convention under `/output/tutorials/my_work/04_delphes_detector` that distinguishes samples by:
   - Underlying parton-level process (e.g. Drell–Yan).
   - Pythia configuration (shower and tune settings).
   - Delphes detector card and version.
2. Apply this convention to your existing Delphes outputs by organizing the ROOT files and associated metadata accordingly.
3. Create a short documentation file in your work area that explains your convention and how to locate specific samples.

---

By completing this tutorial, you will have a full path from MG5-generated parton-level events through Pythia showering and Delphes detector simulation to detector-level objects. This forms the basis for more advanced studies, including BSM/EFT scenarios and simulation-based inference workflows in later tutorials.
