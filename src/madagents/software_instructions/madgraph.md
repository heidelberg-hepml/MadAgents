"MadGraph" refers to the MadGraph event-generation toolkit in general. Specific commands, menus, and file paths are written for MadGraph5_aMC@NLO (MG5_aMC). Other MadGraph versions or setups may differ in exact syntax and available options.

# What MadGraph can do end-to-end

MadGraph can orchestrate an event-generation workflow from a process definition to generated parton-level events, and, if external tools are available, continue with shower/hadronisation, detector simulation, and generation- and prediction-level studies.

# Two ways to run MadGraph

MadGraph can be executed in two modes:

1. **Interactive mode**: you start MadGraph, `<MadGraph_Path>/bin/mg5_aMC`, and type commands at the `MG5_aMC>` prompt.
2. **Scripted mode**: you put the same commands into a text file and run them non-interactively (useful for reproducibility, batch systems, and parameter scans) via `<MadGraph_Path>/bin/mg5_aMC /path/to/my_mg_commands.txt`

Unless stated otherwise, examples below are shown in interactive form; the corresponding scripted form is usually the same commands, one per line, in a command file.

# MadGraph session stages

A typical MadGraph workflow consists of the following stages.

## 1. Choose / import a model

- You can import a model via `import model <MODEL>`. Here, `<MODEL>` is a placeholder for the model name (for example "sm" for the Standard Model).
- You can list all available models via `display modellist`.
- After importing a model, you can inspect its content via:
  - `display particles` to list all particles.
  - `display multiparticles` to list all multiparticle labels.
  - `display parameters` to list parameters.
  - `display interactions` to list interactions.

## 2. Define the process

- You can define multiparticle labels via the `define` command. Example: `define p = g u c d s u~ c~ d~ s~`
- You define a process with the `generate` command. Example: `generate p p > t t~`
- You can add additional, related channels using `add process`. Example:
  ```bash
  generate p p > z j
  add process p p > z j j
  ```
- You can include decay chains:
  - directly in the process definition. Example: `generate p p > t t~, (t > b W+, W+ > l+ vl), (t~ > b~ W-, W- > l- vl~)`
  - by first generating stable resonances and then configuring MadSpin.
- You specify the perturbative content of the process directly on the `generate` line:
  - Born (tree) level via no brackets. Example: `generate p p > t t~`
  - Restrict coupling orders appearing at Born level by adding coupling-order constraints on the `generate` line.
    Example for exactly two powers of QED and up to one power of QCD: `generate p p > e+ e- j QED=2 QCD<=1`
  - Include corrections via `[<correction>]` (when supported).
    Example for NLO QCD corrections: `generate p p > t t~ [QCD]`
  - If a process has no tree-level amplitude (in the chosen coupling expansion), you typically generate it as a loop-induced LO process using `noborn` (signaling there is no Born term).
    Example: `generate g g > z z [noborn=QCD]`
  - Virtual-only (loop amplitudes only) via `virt`. Example: `generate p p > t t~ [virt=QCD]`
  - Notes: Bracket options, coupling-order names, and allowed combinations are process/model-dependent; if unsupported, MadGraph reports this at `generate` and/or `output`.

## 3. Create the process directory

- After defining the process, you create the corresponding process directory with `output <PROC_DIR>`. `<PROC_DIR>` is a short identifier for the process directory with no spaces.
- The process directory created by `output` contains all generated code, configuration cards, log files, and stores event files produced by launches.

## 4. Launch the run

- After `output <PROC_DIR>`, you can start a run for that process with `launch`. In this case, MadGraph uses the most recently created process directory.
- During `launch`, MadGraph enters the run interface for the current process. The prompt typically changes from `MG5_aMC>` to a process-specific prompt (e.g. `>`). In this run interface you no longer issue process-definition commands (such as `import`, `generate`, or `output`); instead you answer the launch menus and adjust run settings (e.g. card choices/paths, `set` commands, and `done`). When the run finishes (or you exit the run interface), control returns to the main `MG5_aMC>` prompt.
- Hint (non-interactive invocation): If you run `launch` from a script (batch mode), include the inputs that would normally be entered during the interactive launch dialogue. Even if you want to keep all defaults, you still need to include the `continue`/`done` entries (often `0` or `done`) that advance through the menus; otherwise MadGraph may pause waiting for input.
- The launch dialogue can differ slightly between versions and configurations, but it typically follows this logical order:

### 4.1 Stage 1: Switches and high-level options

- MadGraph may ask you to set high-level run switches (exact options depend on version/configuration and installed external tools), for example:
  - Whether to run parton-level only or enable a parton shower/hadronisation step
  - Whether to enable detector simulation
  - Whether to enable spin-correlated decays via MadSpin
  - Whether to enable analysis hooks
  - For NLO-capable runs, whether to run as fixed-order vs NLO+PS (matching to a shower)
- In some modes, this stage is presented as a numbered/menu-based interface. In such cases:
  - Select items to change by entering the indicated number/key (e.g. `1`) or keyword assignment (e.g. `shower=PYTHIA8`), as shown by MadGraph.
  - Continue to the next step (often `0` or `done`) once all desired switches and flags have been set.

### 4.2 Stage 2: Card editing

After the high-level switches are fixed, MadGraph usually asks whether you want to edit any of the configuration cards:

- A menu of available cards is shown (exact entries depend on setup), for example:
  ```text
  1) run_card.dat
  2) param_card.dat
  3) pythia8_card.dat
  0) Done
  ```
- You can open a card from the menu by typing its number (e.g. `1` for `run_card.dat`).
  MadGraph normally expects the card to be edited in a text editor. However, your current environment does not provide an editor, so MadGraph may display a warning such as: "Are you really that fast? .... Please confirm that you have finished to edit the file[y]." When this appears, simply confirm with `y` to continue.
- At this stage you have two practical ways to adjust cards:
  - (a) Use the `set` command for quick value changes (when supported). Examples:
    - `set run_card ebeam1 6500`
    - `set param_card mass 6 172.5`
    Tip: Run `help set` for more information.
  - (b) Provide the path to an existing card file. MadGraph will detect the card type and copy it into the right place. Example: `/path/to/my_run_card.dat`
  - Hint: After `output <PROC_DIR>`, the input cards live in `<PROC_DIR>/Cards/`. You can prepare/edit these cards before running `launch`; `launch` will use them by default (unless you override them during the launch dialogue).
- To continue with integration and event generation, exit the card editing stage by choosing the designated option (for example `0` or `done`).

## 5. Inspecting outputs

- After the run finishes, results are stored inside the process directory created by `output <PROC_DIR>`.
- Each `launch` corresponds to a run subdirectory, typically named `run_01`, `run_02`, ... under `<PROC_DIR>/Events/`.
- The exact path(s) to the produced primary output(s) (LHE and/or shower/detector outputs) are usually printed at the end of the `launch` output.

## 6. Loading an existing process and multiple runs

- You can launch a specific, existing process directory by `launch <PROC_DIR>`. Here, `<PROC_DIR>` is the process directory (given in the `output` step).
- You can perform multiple runs for the same process using the same process directory created by `output`.
- For each new run, you can edit the cards.
- Each new launch creates a new run subdirectory under `<PROC_DIR>/Events/`, typically `run_01`, `run_02`, `run_03`, ...
- You can specify a custom name for the run via `launch <PROC_DIR> -n <RUN_NAME>`.
