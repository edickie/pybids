from os.path import split
from bids.variables import load_variables
from collections import OrderedDict
import numpy as np


def _make_passthrough_contrast(level, contrast_names):
    block = OrderedDict(level=level, name=level,
                        model={'variables': contrast_names})
    contrasts = []
    for cn in contrast_names:
        cdict = OrderedDict(name=level + "_" + cn, condition_list=[cn],
                            weights=[1], type='T')
        contrasts.append(cdict)
    block["contrasts"] = contrasts
    return block


def auto_model(layout, scan_length=None):
    '''Create a simple default model for each of the tasks in a BIDSLayout.
    Contrasts each trial type against all other trial types and trial types
    at the run level and then uses t-tests at each other level present to
    aggregate these results up.

    Args:
        layout (BIDSLayout) A BIDSLayout instance
        scan_length (Int) Scan length for loading event varibles in cases
             where the scan length can not be read from the nifti.
             Primarily for testing.

    Returns:
        models (list) list of model dictionaries for each task
    '''

    base_name = split(layout.root)[-1]
    tasks = layout.entities['task'].unique()
    task_models = []

    for task_name in tasks:
        # Populate model meta-data
        model = OrderedDict()
        model["name"] = "_".join([base_name, task_name])
        model["description"] = ("Autogenerated model for the %s task from %s" %
                                (task_name, base_name))
        model["input"] = {"task": task_name}
        blocks = []

        # Make run level block
        transformations = OrderedDict(name='factor', input=['trial_type'])
        run = OrderedDict(level='run', name='run',
                          transformations=[transformations])

        # Get trial types
        run_nodes = load_variables(layout, task=task_name, levels=['run'],
                                   scan_length=scan_length)

        evs = []
        for n in run_nodes.nodes:
            evs.extend(n.variables['trial_type'].values.values)
        trial_types = np.unique(evs)
        trial_type_factors = ["trial_type." + tt for tt in trial_types]

        run_model = OrderedDict(HRF_variables=trial_type_factors,
                                variables=trial_type_factors)
        run["model"] = run_model

        # if there are multiple trial types, build contrasts
        contrasts = []
        for i, tt in enumerate(trial_types):
            cdict = OrderedDict()
            if len(trial_types) > 1:
                cdict["name"] = "run_" + tt + "_vs_others"
            else:
                cdict["name"] = "run_" + tt
            cdict["condition_list"] = trial_type_factors

            # Calculate weights for contrast
            weights = np.ones(len(trial_types))
            try:
                weights[trial_types != tt] = -1.0 / (len(trial_types) - 1)
            except ZeroDivisionError:
                pass
            cdict["weights"] = list(weights)

            cdict["type"] = "T"
            contrasts.append(cdict)

        run["contrasts"] = contrasts
        blocks.append(run)

        # if there are multiple sessions, t-test run level contrasts at
        # session level
        sessions = layout.get_sessions()
        if len(sessions) > 1:
            # get contrasts names from previous block
            contrast_names = [cc["name"] for cc in blocks[-1]["contrasts"]]
            blocks.append(_make_passthrough_contrast("session",
                                                     contrast_names))

        subjects = layout.get_subjects()
        if len(subjects) > 1:
            # get contrasts names from previous block
            contrast_names = [cc["name"] for cc in blocks[-1]["contrasts"]]
            blocks.append(_make_passthrough_contrast("subject",
                                                     contrast_names))

        # get contrasts names from previous block
        contrast_names = [cc["name"] for cc in blocks[-1]["contrasts"]]
        blocks.append(_make_passthrough_contrast("dataset", contrast_names))

        model["blocks"] = blocks
        task_models.append(model)

    return task_models
