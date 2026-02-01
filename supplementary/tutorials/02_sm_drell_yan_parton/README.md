# Tutorial 2: Standard Model Drell–Yan at Parton Level

In this tutorial you will use MadGraph5_aMC@NLO (MG5_aMC) to generate Standard Model Drell–Yan events at parton level, focusing on dilepton final states such as

$$pp \to \ell^+ \ell^-,$$

where $\ell$ is a charged lepton (for example, an electron or muon). Drell–Yan production is a classic benchmark at hadron colliders: it is theoretically clean, experimentally well measured, and sensitive to both Standard Model parameters and many Beyond-the-Standard-Model (BSM) or Effective Field Theory (EFT) effects.

Here you will:

- Define a Drell–Yan process in MG5 using the Standard Model.
- Understand the meaning of beam setup, parton distribution functions (PDFs), and center-of-mass energy.
- Learn about the key configuration cards `run_card.dat` and `param_card.dat`.
- Run a parton-level simulation and identify where the output (LHE files, logs) is stored.

> **Important:** Keep this tutorial directory read-only for yourself. Do all your own work and experiments in:
>
> - `/output/tutorials/my_work/02_sm_drell_yan_parton`

Use this `README.md` as a reference and record your own commands, modifications, and observations separately.

---

## 1. Prerequisites

Before starting this tutorial, you should:

- Have completed Tutorial 1 (`01_mg5_basics`) and be comfortable:
  - Starting MG5.
  - Importing a model.
  - Generating a simple process and launching a basic run.
  - Navigating the process directory structure (especially `Cards/` and `Events/`).
- Have a conceptual understanding of:
  - Proton–proton collisions at the LHC.
  - Parton distribution functions (PDFs): the idea that the proton’s momentum is shared among quarks and gluons.
  - The difference between parton-level, hadron-level, and detector-level events (from Tutorial 1).

All hands-on work for this tutorial should be done in:

- `/output/tutorials/my_work/02_sm_drell_yan_parton`

You can set up your own process directories from there.

---

## 2. Physics overview: Drell–Yan at the LHC

The Drell–Yan process refers to the production of a lepton pair from a quark–antiquark initial state, mediated by a virtual photon or $Z$ boson in the Standard Model. At a proton–proton collider like the LHC, the quarks and antiquarks come from the partonic structure of the proton.

At the level of partonic subprocesses, examples include

- $u \bar{u} \to \ell^+ \ell^-$,
- $d \bar{d} \to \ell^+ \ell^-$,

and similar channels for other quark flavors. MG5 will automatically sum over the relevant initial states according to the PDFs when you generate a hadron-level process such as

$$p p \to \ell^+ \ell^-.$$

This process is an excellent playground for learning MG5 because:

- It has a relatively simple final state (two leptons) with clean signatures.
- It is dominated by electroweak interactions but still sensitive to QCD effects through PDFs and higher-order corrections.
- It is widely used as a calibration and benchmark channel in LHC analyses.

In this tutorial you restrict yourself to **parton-level** Drell–Yan and basic cuts. Showering, hadronization (Pythia) and detector simulation (Delphes) will be added in later tutorials.

---

## 3. Defining a Drell–Yan process in MG5

This section walks through how to define a Drell–Yan-like process in MG5 using the Standard Model.

### 3.1 Starting MG5 and importing the Standard Model

Open a terminal, navigate to your MG5 installation, and start MG5:

```bash
cd /path/to/MG5_DIR
./bin/mg5_aMC
```

At the `MG5_aMC >` prompt, import the Standard Model:

```text
MG5_aMC > import model sm
```

You can optionally inspect the particles and interactions as a reminder:

```text
MG5_aMC > display particles
MG5_aMC > display interactions
```

### 3.2 Defining multiparticle labels for hadron initial states

To describe proton–proton collisions, MG5 commonly uses a *multiparticle label* `p` that collects the partons inside the proton. A simple example is

```text
MG5_aMC > define p = g u c d s u~ c~ d~ s~
```

This defines `p` to represent a proton beam made from gluons and the light quarks and antiquarks. (Heavier quarks can be added as needed; this basic definition is sufficient for the purposes of this tutorial.)

### 3.3 Defining lepton multiparticle labels

You can also define convenient multiparticle labels for the final-state leptons. For example, for electrons and muons:

```text
MG5_aMC > define l+ = e+ mu+
MG5_aMC > define l- = e- mu-
```

Now `l+` and `l-` each represent a set of lepton flavors. MG5 will automatically sum over the possibilities.

### 3.4 Generating a Drell–Yan process

With these definitions, a generic Drell–Yan process at the LHC can be written as

```text
MG5_aMC > generate p p > l+ l-
```

This tells MG5 to consider proton–proton collisions with initial-state partons given by `p`, and a final state consisting of an oppositely charged lepton pair selected from `l+` and `l-`.

You can choose a descriptive name for the process directory, for example:

```text
MG5_aMC > output DY_ll
```

This will create a directory named `DY_ll` in your current working directory, containing all the code and configuration necessary to simulate this process.

> **Note:** The commands above are an example walkthrough. The exercises at the end of this tutorial will ask you to define and modify similar, but not identical, processes and settings.

---

## 4. Beams, PDFs, and center-of-mass energy

Drell–Yan production at the LHC involves several key concepts that appear in the MG5 configuration cards.

### 4.1 Beams: proton–proton collisions

MG5 uses *beam types* and *beam energies* to describe the collider setup. In a proton–proton collider:

- Both beams are protons.
- Each beam has a certain energy in the laboratory frame.
- The total center-of-mass energy is related to the beam energies.

These quantities are configured in `run_card.dat` (see Section 5).

### 4.2 PDFs: parton distribution functions

Because protons are composite, the initial quarks and gluons involved in the hard scattering each carry a fraction of the proton’s momentum. PDFs encode the probability of finding a parton of a given type with a given momentum fraction.

In MG5, the choice of PDF set and the associated settings are also controlled by parameters in `run_card.dat`. Typical entries specify

- Which PDF library or set to use.
- How factorization and renormalization scales are defined.

For this introductory tutorial, you will simply identify where these settings live; detailed PDF choices will be explored later.

### 4.3 Center-of-mass energy

The hadronic center-of-mass energy $\sqrt{s}$ is determined by the beam energies. In `run_card.dat`, the beam energies are specified (for each beam) and MG5 uses these values to interpret the collider setup.

Changing these energies (for example, to mimic different LHC running conditions) will affect the kinematics and rates of the Drell–Yan process. One of the exercises will have you vary the beam energy and observe qualitative differences.

---

## 5. Understanding `run_card.dat` and `param_card.dat`

When you generated the process with `output DY_ll`, MG5 created a new directory `DY_ll` (or whatever name you chose). Inside that directory is a `Cards/` subdirectory containing several important files.

### 5.1 `run_card.dat` – run-level settings

`run_card.dat` controls how MG5 performs the integration and event generation. Typical categories of parameters include:

- **Collider setup**
  - Beam types (e.g. proton beams).
  - Beam energies.
- **Event generation settings**
  - Number of events to generate.
  - Number of integration channels and related technical parameters.
- **Phase-space cuts**
  - Lower and upper cuts on transverse momenta ($p_T$).
  - Pseudorapidity ($\eta$) acceptance ranges.
  - Invariant mass cuts on dilepton systems, etc.
- **PDF and scale choices**
  - PDF set identifiers.
  - Factorization and renormalization scales.

To locate the card, from a shell:

```bash
cd /path/to/your/work/DY_ll
ls Cards
```

You should see `run_card.dat` among the files. You can open it in any text editor to inspect its contents.

### 5.2 `param_card.dat` – model parameters

`param_card.dat` contains the parameters of the underlying physics model, in this case the Standard Model. These include, for example:

- Particle masses (leptons, quarks, gauge bosons, Higgs).
- Couplings (gauge couplings, Yukawa couplings, etc.).
- Decay widths.

For Drell–Yan, relevant parameters include the masses and widths of the photon and $Z$ boson (as implemented in the model) and the lepton masses. While you will not change these in detail in this introductory tutorial, it is important to know where they are stored and how to recognize them.

Open `param_card.dat` and look for blocks corresponding to masses and couplings. The exact formatting may depend on the model version, but the structure is typically well documented in comments inside the card.

### 5.3 Editing cards

There are two common ways to adjust settings:

1. **Editing the files directly** using a text editor.
2. **Using MG5 `set` commands** inside the run interface (see Section 6), for accessible parameters that MG5 exposes.

In this tutorial, you will mostly inspect the cards and make a few controlled modifications for the exercises. Keep careful notes about which parameters you change and why.

---

## 6. Walkthrough: running Drell–Yan at parton level

This section outlines a typical workflow to generate parton-level Drell–Yan events using MG5. You should adapt directory names and minor details to your own setup.

### 6.1 Defining and outputting the process

Inside MG5, after importing the Standard Model and defining multiparticle labels as in Section 3, define and output the process:

```text
MG5_aMC > generate p p > l+ l-
MG5_aMC > output DY_ll
```

You can then either stay inside MG5 and launch directly, or exit MG5, inspect the `DY_ll` directory, and later restart MG5 to launch from that directory. For simplicity, let us assume you stay in the same MG5 session.

### 6.2 Launching the run

From the MG5 prompt, launch the process:

```text
MG5_aMC > launch DY_ll
```

MG5 will now enter a run interface specifically for this process. You will typically see prompts asking you whether to:

- Change run-level settings (associated with `run_card.dat`).
- Change model parameters (associated with `param_card.dat`).
- Enable or disable various interfaces (such as Pythia and Delphes).

For a first test, you can choose to keep the default settings and proceed to generate a modest number of parton-level events. Follow the on-screen instructions to move past the card-editing stage and start the integration and event generation.

> **Note:** Exact menus and prompts may vary slightly between MG5 versions. The essential steps are: confirm (or edit) cards, then proceed to run.

During the run, MG5 will display integration progress and, at the end, will print a cross section and other run information. You are not required to record the numeric results for this tutorial; instead, focus on understanding how to locate the outputs.

### 6.3 Locating the output files

After the run finishes, leave MG5 (if you wish) and inspect the process directory in a shell:

```bash
cd /path/to/your/work/DY_ll
ls
```

Inside the `Events/` subdirectory you should find run-specific folders, for example:

```bash
cd Events
ls
```

Typical names are `run_01`, `run_02`, and so on, corresponding to different launches. Inside a given run directory, you will find:

- The primary LHE event file, often named something like `unweighted_events.lhe` or a compressed variant.
- Logs and additional information about the run.

These LHE events are the **parton-level** Drell–Yan events produced by MG5. They will later be used as input for Pythia.

### 6.4 Inspecting events qualitatively

To get a feeling for the event structure, you can open the LHE file with a text viewer, for example:

```bash
cd /path/to/your/work/DY_ll/Events/run_XX
less unweighted_events.lhe
```

(or the appropriate filename in your case).

Look for:

- The header, which contains information about the process, cuts, and run settings.
- Individual event blocks, each listing particles with:
  - Particle IDs (typically PDG codes).
  - Status codes (incoming, outgoing, intermediate).
  - Mothers (which particles they originated from).
  - Four-momenta and other kinematic information.

For Drell–Yan, you should see two incoming partons and an outgoing lepton pair for each event, along with any additional particles required by the parton-level configuration.

You can also write simple scripts (in Python, ROOT, or another language) to parse the LHE file and inspect distributions such as the dilepton invariant mass or lepton transverse momenta. Designing such scripts is an excellent exercise, but keep them separate from this tutorial file.

---

## 7. Exercises (no solutions in this file)

Perform these tasks in your own workspace directory:

- `/output/tutorials/my_work/02_sm_drell_yan_parton`

The prompts below are intentionally open-ended. This `README.md` does not contain solutions, numeric answers, or fully worked-out MG5 command files that correspond exactly to the tasks.

### Exercise 1 – Basic Drell–Yan generation

1. In your work directory, start MG5 and import the Standard Model.
2. Define multiparticle labels for proton beams and for at least one charged-lepton flavor pair of your choice.
3. Generate a Drell–Yan process with proton–proton initial states and your chosen lepton final state.
4. Output the process to a new directory with a descriptive name and launch a parton-level run using default or modestly adjusted settings.
5. Locate the resulting LHE event file and briefly describe, in your notes, its directory path and filename.

### Exercise 2 – Varying the collider energy or PDF set

1. Identify the parameters in `run_card.dat` that control the beam energies and the choice of PDF set.
2. Create at least two different run configurations that differ in either the beam energy, the PDF set, or both.
3. For each configuration, run a parton-level Drell–Yan simulation.
4. Without quoting specific numbers, compare qualitatively:
   - How the overall event yields and kinematic distributions (e.g. dilepton invariant mass) appear to change.
   - How sensitive you expect Drell–Yan observables to be to these settings.

### Exercise 3 – Introducing kinematic cuts

1. In `run_card.dat`, locate parameters corresponding to basic kinematic cuts, such as:
   - Minimum lepton transverse momentum $p_T$.
   - Maximum lepton pseudorapidity $|\eta|$.
   - Lower and/or upper cuts on the dilepton invariant mass.
2. Define at least two distinct sets of cuts (for example, a loose and a tight selection).
3. For each set of cuts, run a Drell–Yan simulation.
4. Compare, in qualitative terms and without quoting numeric results, how the event samples differ (for example, in terms of the typical lepton kinematics or the relative size of different regions of phase space).

### Exercise 4 – Exploring different lepton flavors and neutrino final states

1. Modify your process definition to generate Drell–Yan events with a different charged-lepton flavor (for example, switching from electrons to muons, or including both together).
2. Optionally, define and generate a related process that includes neutrinos in the final state (for example, a charged-current–like topology with a charged lepton and missing energy).
3. Run simulations for at least two different final-state choices.
4. Inspect the LHE files and describe, in your notes, qualitative differences in:
   - The visible final-state particles.
   - The presence or absence of invisible particles (such as neutrinos) and how this would manifest at detector level.

### Exercise 5 – Comparing parton-level kinematics for different cuts

1. Choose two of your Drell–Yan samples that differ only by their kinematic cuts (for example, loose vs. tight cuts on $p_T$ or $\eta$).
2. Using a simple analysis script or manual inspection of a subset of events, compare the parton-level kinematics between the two samples (for example, lepton transverse momenta, rapidities, or the dilepton invariant mass distribution shape).
3. Summarize your observations qualitatively:
   - Which regions of phase space are most affected by tightening the cuts?
   - How might these differences translate into acceptance effects at detector level in later tutorials?

### Exercise 6 – Organizing Drell–Yan runs for later use

1. Design a directory and naming convention under your work directory that allows you to clearly distinguish between Drell–Yan samples with different:
   - Beam energies.
   - PDF sets.
   - Kinematic cuts.
   - Final-state lepton choices.
2. Apply this convention to your existing runs by organizing the process directories and/or run subdirectories accordingly.
3. Document your convention in a short text file in your work area, so that you (and collaborators) can easily understand which configuration produced each event sample.

---

You have now set up and run Standard Model Drell–Yan simulations at parton level, and you have explored how changes in collider setup, PDFs, cuts, and final states affect the samples. In subsequent tutorials you will feed these LHE events into Pythia for showering and hadronization, and then into Delphes for fast detector simulation.
