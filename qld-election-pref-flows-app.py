# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.4
#   kernelspec:
#     display_name: Python (data-science)
#     language: python
#     name: data-science
# ---

# %%
import json

import holoviews as hv
import pandas as pd
import panel as pn
from bokeh.models import NumeralTickFormatter
from consts import IND, colours, other_colours
from electorate_pref_explorer import ElectoratePrefExplorer
from overall_pref_explorer import OverallPrefExplorer
from greens_pref_explorer import GreensPrefExplorer
from utils import hide_hook

# %%
hv.extension("bokeh")
hv.opts.defaults(active_tools=["pan"])

pn.extension(
    defer_load=True,
    loading_spinner="arc",
    loading_indicator=True,
    throttled=True,
    # loading_color="#0000ff",
)


# %%
# # Read data
with open("electorates.json", "r") as f:
    electorates = json.load(f)
electorates = {x["stub"]: x["electorateName"] for x in electorates}

distribution = pd.read_parquet("qld_2024_distributions.parq")
first_pref = pd.read_parquet("qld_2024_first_prefs.parq")
final_tally = pd.read_parquet("qld_2024_final_tally.parq")


# %%
# the actual party tally
idx = final_tally.groupby("electorate")["count"].idxmax()
actual_party_tally = final_tally.loc[idx].value_counts("party")
actual_party_tally = actual_party_tally[actual_party_tally > 0]
actual_party_tally.name = "Actual"

distribution_party = distribution[
    (distribution["fromParty"] != IND) & (distribution["toParty"] != IND)
]

# %% [markdown]
# # The 1st tab
tab_overall_flows = OverallPrefExplorer(
    data=distribution_party, party_tally=actual_party_tally
)

# %% [markdown]
# # 2nd tab: pref distribution explorer for each electorate
tab_electorate_explorer = ElectoratePrefExplorer(
    distribution, first_pref, {v: k for k, v in electorates.items()}
)

# %% [markdown]
# # Greens as 3rd party explorer

# %%
tab_greens_explorer = GreensPrefExplorer(distribution, actual_party_tally, electorates)
tabs = pn.Tabs(
    ("Overall Preference Flows", tab_overall_flows),
    ("Electorate Explorer", tab_electorate_explorer),
    ("Greens Pref Explorer", tab_greens_explorer),
)

# %%
template = pn.template.BootstrapTemplate(
    title="Queensland Election Preference Flow Explorer",
    sidebar=[],
)
template.main.append(tabs)
template.servable()

# %%
