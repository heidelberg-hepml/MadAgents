# Tutorial 1: Getting Started with MadGraph5_aMC@NLO and the Event Generation Pipeline

This tutorial introduces the basics of MadGraph5_aMC@NLO (often shortened to MG5_aMC or just MG5) and the overall simulation chain

$$pp \to \text{partons (MG5)} \;\to\; \text{hadrons (Pythia)} \;\to\; \text{detector objects (Delphes)}.$$

The goal is to get you comfortable starting MG5, issuing basic commands, understanding the structure of a generated process directory, and seeing where Pythia and Delphes will later fit into the workflow. You will not yet run Pythia or Delphes in this tutorial; that comes later.

> **Important:** Keep this tutorial directory read-only for yourself. Do all your own work and experiments in:
>
> - `/output/tutorials/my_work/01_mg5_basics`

You can always come back to this `README.md` as a reference.

---

## 1. Prerequisites

### 1.1 Physics prerequisites

You should be comfortable with the following basic concepts:

- Particle physics process notation, such as $pp \to \ell^+ \ell^-$ or $e^+ e^- \to \mu^+ \mu^-$.
- Qualitative understanding of Feynman diagrams (you know that amplitudes are built from diagrams, but you do not need to compute them).
- Conceptual idea of a Monte Carlo event generator: it samples events according to a probability distribution derived from a cross section.

### 1.2 Software prerequisites

- Basic command-line usage:
  - Navigating directories: `cd`, `pwd`, `ls`.
  - Running executables in a shell: `./some_program`.
  - Editing text files using whichever editor you prefer (e.g. `vim`, `emacs`, `nano`, VS Code, etc.).
- A POSIX-like shell environment (Linux, macOS, or similar) or equivalent.

For all hands-on steps and exercises, **work in your own directory**:

- `/output/tutorials/my_work/01_mg5_basics`

You may copy small pieces from this tutorial (for example, a command snippet) into your work area, but avoid editing this reference file.

---

## 2. Obtaining and launching MadGraph5_aMC@NLO

This section gives OS-agnostic guidance on how to obtain MG5_aMC, unpack it, and start the main executable. Exact details can vary slightly between versions; always check the official documentation for your setup.

### 2.1 Downloading MG5_aMC

1. Visit the official MadGraph webpage in a web browser (search for "MadGraph5_aMC@NLO" or navigate to the official CERN/HEP hosting).
2. Download a recent publicly available version of MG5_aMC as a compressed archive (for example, a `.tar.gz` file).
3. Place the downloaded archive in a convenient directory, such as `~/software/` or a project directory.

### 2.2 Unpacking MG5_aMC

In a terminal, navigate to the directory where you downloaded the archive and unpack it. For example:

```bash
cd /path/to/where/you/downloaded/mg5_archive

# Replace the filename with the one you actually downloaded
tar -xzf MG5_aMC_vX_Y_Z.tar.gz

# Enter the newly created directory
cd MG5_aMC_vX_Y_Z
```

The extracted directory (referred to here as `MG5_DIR`) will contain a `bin` subdirectory with the main executable script `mg5_aMC` and various support files.

### 2.3 Launching the MG5_aMC shell

From inside `MG5_DIR` (or after adding its `bin` directory to your `PATH`), run:

```bash
./bin/mg5_aMC
```

You should see something like:

```text
*******************************************
*                                         *
*       MadGraph5_aMC@NLO  (version ...)  *
*                                         *
*******************************************

MG5_aMC >
```

The `MG5_aMC >` prompt indicates that you are in the MG5 command-line interface (CLI). You will type MG5-specific commands here.

To exit MG5 at any time, use:

```text
MG5_aMC > exit
```

or press `Ctrl-D`.

---

## 3. Checking for Pythia and Delphes interfaces

In later tutorials, MG5 will be interfaced to Pythia (for parton showering and hadronization) and Delphes (for fast detector simulation). Here you will only **check** whether the necessary interfaces are available; do **not** install or modify anything as part of this tutorial.

> Installation details are system dependent and should be coordinated with your local setup or documentation. The instructions below are only for **verification**, not for performing an installation.

### 3.1 Checking Pythia interface from within MG5

Start MG5 if it is not already running:

```bash
cd /path/to/MG5_DIR
./bin/mg5_aMC
```

At the `MG5_aMC >` prompt, type:

```text
MG5_aMC > help install
```

Scroll through the help text and look for entries mentioning Pythia (for example, `pythia8`). If you see an option like `install pythia8`, it indicates that MG5 knows about the Pythia interface.

You can also try:

```text
MG5_aMC > install --help
```

and look for Pythia-related entries. Do **not** actually run `install pythia8` unless you have explicit instructions to do so from your local setup.

### 3.2 Checking Delphes interface

Similarly, at the MG5 prompt, search for Delphes-related options:

```text
MG5_aMC > help install
```

Look for references to `delphes` or `Delphes`. Again, this confirms that MG5 is aware of the interface. Actual installation, if needed, should follow the official documentation and your local environment policies.

### 3.3 External installations

In some setups, Pythia and Delphes might be installed separately and MG5 may be configured to use them through environment variables or configuration files. Typical checks include:

- Running `pythia8-config --help` or similar commands in a shell to see whether Pythia is on your system path.
- Checking whether a `Delphes` directory or executable is available in your analysis software area.

These checks are optional for this tutorial; the main point is to understand that Pythia and Delphes will connect to MG5 but are logically separate programs.

---

## 4. First steps in the MG5 command-line interface

This section gives you a tour of the MG5 CLI, focusing on a small set of core commands and the structure of a typical process directory.

### 4.1 Basic navigation and help inside MG5

Once you see the `MG5_aMC >` prompt, you can:

- Get general help:

  ```text
  MG5_aMC > help
  ```

- Get help on a specific command, such as `generate`:

  ```text
  MG5_aMC > help generate
  ```

- List the available models:

  ```text
  MG5_aMC > display modellist
  ```

- Display particles and interactions of the current model (after importing a model, see below):

  ```text
  MG5_aMC > display particles
  MG5_aMC > display interactions
  ```

MG5 also supports tab completion and command history (using the arrow keys) in many setups, which can save time as you experiment.

### 4.2 Importing a model

MG5 works with "models" that define particles, parameters, and interactions. The default Standard Model is typically called `sm`.

To import it:

```text
MG5_aMC > import model sm
```

After this, `display particles` and `display interactions` will show the content of the Standard Model implementation used by MG5.

### 4.3 Defining and generating a simple process

As a first illustrative example, consider a simple lepton collider process such as $e^+ e^- \to \mu^+ \mu^-$. The following sequence (typed at the MG5 prompt) is a minimal example of how to define and generate this process at tree level:

```text
MG5_aMC > import model sm
MG5_aMC > generate e+ e- > mu+ mu-
MG5_aMC > output ee_mumu
```

- `generate e+ e- > mu+ mu-` defines the scattering process at parton level.
- `output ee_mumu` tells MG5 to create a process directory named `ee_mumu` in your current working directory.

After `output` finishes, you can leave MG5 (`exit`) and explore the new directory from your shell, or you can proceed directly to launching a run from within MG5 (next subsection).

### 4.4 Launching a basic run (parton level)

To run the default integration and generate parton-level events for your test process, you can continue from the same MG5 session:

```text
MG5_aMC > launch ee_mumu
```

MG5 will open a run interface for the `ee_mumu` process. The prompt may change (for example, to `>` with additional text), and you will see menus for configuration. For this first test you can simply accept the defaults by following the on-screen instructions (typically choosing the option that continues without editing cards).

At the end of the run, MG5 will report a value for the cross section and generate an event file in the process directory. You do **not** need these numeric values for this tutorial; treat them as outputs to be explored rather than as targets.

### 4.5 Exploring the process directory structure

In a shell, move into your process directory (for the example above):

```bash
cd /path/to/where/you/runs/are/ee_mumu
ls
```

You should see several subdirectories. Typical ones include:

- `Cards/` – configuration input files.
  - `run_card.dat` – run-level settings (number of events, beam energies, basic cuts, etc.).
  - `param_card.dat` – model parameters (masses, couplings, widths, etc.).
- `Events/` – results of your launches.
  - Subdirectories like `run_01/`, `run_02/`, ... for different runs.
  - Within each run directory, one or more event files, often in LHE format (e.g. `unweighted_events.lhe.gz`).
- `SubProcesses/` – matrix-element code generated by MG5 for the process.
- `bin/` – helper scripts related to this process.
- `HTML/` or `index.html` – optional HTML report describing the process and runs.

You do not need to understand every file at this stage. The main goal is to recognize where to look for:

- Configuration inputs (in `Cards/`).
- Event outputs (in `Events/`).

---

## 5. Conceptual overview: MG5 → Pythia → Delphes

Before going further with MG5, it is helpful to understand how it will later be chained with Pythia and Delphes. The workflow can be summarized as follows:

1. **MG5 (matrix elements and parton-level events)**
   - MG5 takes a theoretical model and a process definition (e.g. $pp \to \ell^+ \ell^-$) and computes parton-level scattering amplitudes.
   - It generates **parton-level events** and writes them to files, typically in the Les Houches Event (LHE) format. Each event lists particles with their four-momenta and other attributes, but they are still quarks, gluons, and leptons before QCD showering and hadronization.

2. **Pythia (showering and hadronization)**
   - Pythia reads LHE files and performs the QCD and QED parton shower, hadronization, and underlying-event modeling.
   - The output is a set of **hadron-level events**, where you see hadrons (pions, kaons, protons, etc.) and possibly stable leptons and photons.

3. **Delphes (fast detector simulation)**
   - Delphes takes hadron-level events (often in formats like HepMC or ROOT, depending on your setup) and simulates how a collider detector would respond.
   - The output is a **detector-level** event sample in ROOT format, containing reconstructed objects such as electrons, muons, jets, and missing transverse energy.

4. **Analysis**
   - Analysis scripts (typically in ROOT, Python, or another language) read the Delphes output and construct physics observables, histograms, and summary statistics.

In this tutorial you work purely at step 1. Pythia and Delphes will be introduced in later tutorials, but it is helpful to know from the beginning where their inputs and outputs will appear in the MG5 directory structure.

---

## 6. Exercises (no solutions in this file)

Perform these tasks in your own workspace directory:

- `/output/tutorials/my_work/01_mg5_basics`

Treat this `README.md` as a reference only.

> **Reminder:** The exercises below are open-ended prompts. This file does not contain solutions, numeric answers, or complete command scripts. You are expected to explore MG5 interactively and record your own findings.

### Exercise 1 – Starting MG5 and exploring help

1. Open a terminal and navigate to the directory where MG5 is installed.
2. Start MG5 using the `mg5_aMC` executable.
3. Use the built-in `help` system to discover at least three commands that look useful to you (for example, for displaying models, particles, or parameters).
4. In your notes, briefly describe when you might use each command.

### Exercise 2 – Importing the Standard Model and inspecting its content

1. In MG5, import the Standard Model.
2. Use display commands to list the particles and interactions in the loaded model.
3. Identify a few particles and interactions that are relevant for simple lepton or quark scattering processes.
4. Record your observations (for example, which particle names MG5 uses for electrons, muons, quarks, and gauge bosons).

### Exercise 3 – Generating a simple test process and running it

1. Choose a simple Standard Model process of your own (it does not have to be the example shown in this tutorial, but it can be if you wish).
2. In MG5, generate this process and output it to a new process directory with a descriptive name.
3. Launch a basic parton-level run using MG5’s default settings.
4. After the run finishes, locate the process directory and its `Events/` subdirectory in your filesystem.
5. Note which files appear in the `Events/` subdirectory and how they are organized into runs.

### Exercise 4 – Exploring configuration cards

1. For the process you generated in Exercise 3, locate the `Cards/` subdirectory.
2. Open `run_card.dat` and `param_card.dat` in a text editor.
3. Identify (by name and short description) a few parameters in each file that seem particularly important for collider simulations (for example, beam energies, number of events, or key masses).
4. Write a short explanation, in words only, of the *role* of each parameter you selected (do not change any values yet unless you want to experiment).

### Exercise 5 – Inspecting an LHE event file

1. Take one of the LHE event files produced in your process directory (for example, an `unweighted_events.lhe` or compressed version).
2. Open it with a text viewer of your choice.
3. Identify:
   - The header section (metadata and run information).
   - The event blocks (each representing a single event).
4. For a small number of events, examine the particle lines and note which entries correspond to incoming particles, outgoing particles, and any intermediate states.
5. In your notes, describe which parts of this information you expect to be important inputs for Pythia and Delphes in later tutorials.

### Exercise 6 – Mapping the MG5 → Pythia → Delphes pipeline

1. Based on what you have learned, draw (on paper or in a text document) a simple flow diagram that shows:
   - MG5 producing parton-level LHE files.
   - Pythia reading LHE files and producing hadron-level events.
   - Delphes reading hadron-level events and producing detector-level ROOT files.
2. Annotate your diagram with filenames or directory locations that you expect to be involved at each step (for example, where LHE files and later detector-level files might live).
3. Keep this diagram handy; you will refine it in subsequent tutorials as you learn more details.

---

You have now completed Tutorial 1. In the next tutorial you will apply these basics to a concrete Standard Model benchmark process: Drell–Yan production of dileptons at parton level.
