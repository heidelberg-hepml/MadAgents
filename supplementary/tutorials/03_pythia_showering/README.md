# Tutorial 3: From Partons to Hadrons with Pythia

In this tutorial you will learn how to take parton-level events produced by MadGraph5_aMC@NLO (MG5_aMC) and pass them to Pythia for parton showering, hadronization, and underlying-event simulation. You will work with processes such as Drell–Yan dilepton production defined in the previous tutorial, but the concepts apply more broadly.

The focus is on:

- Understanding what Pythia adds on top of MG5’s parton-level output.
- Configuring MG5 to interface with Pythia for showering and hadronization.
- Locating and inspecting hadron-level event files produced by Pythia.
- Exploring, at a qualitative level, the impact of shower and underlying-event settings.

> **Important:** Treat this tutorial directory as read-only instructions. Do all your own work, process directories, cards, and scripts in:
>
> - `/output/tutorials/my_work/03_pythia_showering`

You can always refer back to this `README.md` while experimenting in your own workspace.

---

## 1. Prerequisites

Before starting this tutorial, you should:

- Have completed:
  - Tutorial 1 (`01_mg5_basics`), including basic MG5 usage and directory structure.
  - Tutorial 2 (`02_sm_drell_yan_parton`), including generation of a Drell–Yan parton-level sample.
- Have at least one working MG5 process directory with parton-level events, such as a Drell–Yan process (for example, a directory like `DY_ll` with LHE files under `Events/run_XX/`).
- Have access to an MG5 installation where the Pythia interface is available (for example, via `help install` inside MG5, as discussed in Tutorial 1).

All hands-on work for this tutorial should be done in your own workspace:

- `/output/tutorials/my_work/03_pythia_showering`

You may copy or symlink existing MG5 process directories there, or create new ones following the earlier tutorials.

---

## 2. Conceptual overview: what Pythia does

MG5 generates **parton-level** events based on matrix elements for a given process and model. These events list quarks, gluons, and leptons before QCD showering and hadronization. Pythia takes these events and applies several layers of physics modeling:

1. **Initial-State Radiation (ISR)**
   - Emission of additional partons from the incoming beams before the hard scattering.
   - Modifies the effective momentum fractions and introduces extra jets.

2. **Final-State Radiation (FSR)**
   - Emission of partons from outgoing colored particles after the hard scattering.
   - Produces collimated sprays of particles that will later form jets.

3. **Multiple Parton Interactions and Underlying Event**
   - Additional softer scatterings between partons in the same proton–proton collision.
   - Contributes to the overall hadronic activity in the event (soft jets, diffuse energy).

4. **Hadronization**
   - Conversion of colored partons into color-singlet hadrons (mesons, baryons, etc.).
   - Produces the stable and unstable hadrons that would enter a detector.

The result is a **hadron-level** (or particle-level) event sample that is closer to what a detector would see, though still idealized (no detector effects yet). Delphes, in the next tutorial, will then approximate how a detector responds to these hadrons.

---

## 3. Interfacing MG5 with Pythia

This section describes, at a high level, how to configure MG5 to run Pythia on parton-level events. Exact menu prompts and filenames can vary slightly between MG5 versions; use MG5’s built-in `help` and on-screen messages as the final authority for your specific setup.

### 3.1 Starting from an existing process directory

Assume you already have a process directory generated with MG5 (for example, a Drell–Yan process directory `DY_ll` created in Tutorial 2) that contains parton-level LHE events under `Events/run_XX/`.

In a shell, navigate to your work area and start MG5:

```bash
cd /path/to/your/work
./path/to/MG5_DIR/bin/mg5_aMC
```

At the `MG5_aMC >` prompt, you can launch the existing process directory:

```text
MG5_aMC > launch DY_ll
```

Replace `DY_ll` with the actual name or path of your process directory.

### 3.2 Enabling Pythia in the MG5 run interface

When you issue `launch <proc_dir>`, MG5 enters a run interface specific to that process. Depending on version and configuration, you may see prompts asking whether to:

- Run parton-level only.
- Enable parton showering and hadronization with Pythia.
- Enable detector simulation with Delphes.

To run Pythia, you typically need to:

- Indicate that you want to use a parton shower.
- Choose which shower program (for example, Pythia8) if multiple options are available.

Possible patterns (the exact wording may differ) include:

- A menu entry such as `shower = OFF/ON` or a similar toggle.
- A setting such as `shower = PYTHIA8` in a summary of configurable options.

Use the interface to turn the shower **on** and proceed with the run. If you are unsure which option corresponds to Pythia, consult `help launch` or MG5’s online documentation for your version.

### 3.3 Pythia configuration files in the process directory

In many MG5 setups, Pythia-related configuration is stored in a dedicated card inside the process directory, for example in `Cards/` as a file with a name such as:

- `pythia8_card.dat` (for a text-based configuration of Pythia8 options), or
- another Pythia-related card, depending on your MG5 version.

Typical settings controlled by this card (or by equivalent configuration mechanisms) include:

- Which processes are handled by MG5 vs. by Pythia.
- Switches for ISR, FSR, multiple parton interactions, and hadronization.
- Underlying-event tune parameters.
- Random seeds and event-record options.

You can inspect the Pythia card with a text editor to see which parameters are available. Some settings may also be adjustable from within the MG5 run interface via `set` commands; use `help set` to see what is supported.

> **Important:** Do not modify global MG5 or Pythia installations from this tutorial. Restrict yourself to editing configuration cards and settings inside your own process directories under `/output/tutorials/my_work/03_pythia_showering`.

---

## 4. Hadron-level outputs and file structure

When you run Pythia through MG5, the output typically includes:

1. **Parton-level LHE files** (as before), usually in `Events/run_XX/`.
2. **Hadron-level event files**, produced by Pythia, written alongside or near the LHE files.

The hadron-level files may appear in different formats depending on your setup. Common patterns include:

- Plain-text or compressed event files that Pythia can produce directly via MG5.
- Files in formats such as HepMC or ROOT, if configured.

Within a given run directory, you might see, for example:

```bash
cd /path/to/your/work/DY_ll/Events/run_XX
ls
```

You should be able to distinguish:

- The original LHE file produced by MG5.
- One or more Pythia-produced files that contain hadron-level events.

Consult the MG5 logs and on-screen messages during the run to see the exact filenames. These messages often state where the Pythia output was written.

### 4.1 Conceptual difference: LHE vs. hadron-level

- **LHE (parton-level) files** contain information about the hard scattering and, optionally, parton-level radiation, but they do not include hadronization or the full underlying event.
- **Hadron-level files** generated by Pythia contain:
  - Final-state hadrons (pions, kaons, protons, etc.).
  - Stable leptons and photons.
  - Possible neutrinos and other invisible particles.
  - The effect of ISR, FSR, and multiple parton interactions.

These hadron-level events are the natural input for Delphes in the next tutorial.

---

## 5. Qualitative exploration of shower and underlying-event settings

Pythia offers many parameters that control different aspects of the shower and underlying event. In this tutorial, you are not expected to master all of them, but you should develop an intuition for how major switches affect observable features.

### 5.1 Initial- and final-state radiation

- **Turning ISR off** (when possible) tends to reduce radiation from the incoming beams, which can change the distribution of extra jets and the overall activity in the forward regions.
- **Turning FSR off** tends to suppress radiation from outgoing colored particles, affecting how collimated the resulting jets are and how much soft radiation surrounds them.

By comparing samples with different ISR/FSR settings, you can qualitatively see how radiation patterns change.

### 5.2 Hadronization and underlying event

- **Hadronization** determines how quarks and gluons are turned into hadrons; different hadronization models or parameters can affect multiplicities and fragmentation patterns.
- **Underlying-event tunes** control how much additional soft activity is present beyond the primary hard scatter. Different tunes correspond to different assumptions and fits to experimental data.

Changes to these settings may manifest as differences in:

- Charged-particle multiplicities.
- Soft energy flow in the event.
- Jet shapes and low-$p_T$ radiation.

### 5.3 Random seeds and reproducibility

Pythia uses random numbers extensively. In most MG5 setups, you can control the random seed (and sometimes the seed strategy) either through the Pythia card or via `set` commands in the run interface. Keeping track of the seeds you use helps ensure reproducibility when comparing different configurations.

---

## 6. Exercises (no solutions or numeric answers in this file)

Perform all hands-on tasks in your own workspace:

- `/output/tutorials/my_work/03_pythia_showering`

Use this tutorial as a guide, but record your own commands, configuration changes, and observations elsewhere.

> **Reminder:** The exercises below are open-ended prompts. This file does not contain solutions, numeric answers, or complete scripts that exactly solve the tasks.

### Exercise 1 – Running Pythia on a Drell–Yan LHE sample

1. Take a Drell–Yan MG5 process directory created in Tutorial 2 (or regenerate one if needed) and copy or link it into your work area for this tutorial.
2. Use `launch <proc_dir>` in MG5 to enable Pythia showering and hadronization for this process.
3. Run a Pythia-enabled simulation and identify, in your notes, which files in `Events/run_XX/` correspond to:
   - The original parton-level LHE events.
   - The hadron-level events produced by Pythia.
4. Briefly describe how the hadron-level file format and contents differ from the LHE file.

### Exercise 2 – Toggling ISR or FSR

1. Locate the Pythia configuration card (or equivalent settings) for your process.
2. Identify parameters or switches that control initial-state radiation (ISR) and final-state radiation (FSR).
3. Produce at least two hadron-level samples:
   - One with default shower settings.
   - One with either ISR or FSR selectively disabled.
4. Compare the resulting samples qualitatively, focusing on features such as extra jets, soft radiation, or angular distributions of hadrons.

### Exercise 3 – Exploring underlying-event and hadronization settings

1. In the Pythia configuration, identify settings related to the underlying event and hadronization model or tune.
2. Define at least two different Pythia configurations that you expect to produce noticeably different levels of soft activity.
3. Generate hadron-level samples for each configuration.
4. Without quoting specific numbers, describe how observables such as charged-particle multiplicity or low-$p_T$ energy flow appear to change between configurations.

### Exercise 4 – Parton-level vs. hadron-level comparisons

1. Starting from the same Drell–Yan LHE sample, compare:
   - The parton-level event kinematics (e.g. dilepton invariant mass, lepton transverse momenta).
   - The corresponding quantities after showering and hadronization (for example, looking at the leptons and any jets you reconstruct from hadrons).
2. Describe qualitatively how the shower and hadronization affect these observables (for instance, broadening of distributions or additional jet activity).
3. Reflect on which observables are most stable under shower effects and which are more sensitive.

### Exercise 5 – Organizing Pythia configurations and seeds

1. Design a directory and naming convention within `/output/tutorials/my_work/03_pythia_showering` that allows you to clearly distinguish between runs with different:
   - Shower settings (ISR/FSR on or off).
   - Underlying-event tunes.
   - Random seeds.
2. Apply this convention to your existing Pythia runs by arranging the process and run directories accordingly.
3. Create a short text file (for example, `run_catalog.txt`) in your work area that summarizes:
   - Which configuration corresponds to each run.
   - Which random seed(s) were used.

### Exercise 6 – Planning jet-related observables for later analysis

1. Based on your hadron-level Drell–Yan events, choose a small set of jet-related observables that you might want to study later (for example, leading jet transverse momentum, jet multiplicity, or angular separations between jets and leptons).
2. Sketch, in pseudocode or plain language, how you would:
   - Read the hadron-level event file.
   - Cluster jets (conceptually; you do not need to implement the clustering in detail here).
   - Compute and record your chosen observables for each event.
3. Note which aspects of the Pythia configuration you expect to have the strongest impact on each observable.

---

You have now learned how to interface MG5 with Pythia and how to reason qualitatively about the impact of shower and underlying-event settings on hadron-level events. In the next tutorial you will add detector effects by running Delphes on the Pythia output.
