from random import choice

import holoviews as hv
import matplotlib.pyplot as plt
import pandas as pd
import panel as pn
import param
from bokeh.models import NumeralTickFormatter
from consts import colours, other_colours
from pywaffle import Waffle
from utils import hide_hook

pn.config.throttled = True

intro_txt = """
 Select an electorate from the dropdown list below to view the preference flows for each electorate. 

 If no candidate wins 50% of more of the votes in the electorate, then the 2nd preference votes for the lowest ranked canddiate are transferred to the remaining candidates. This process takes place until a candidate crosses the 50% threshold.

 The figures on the right show each such distribution, and the running total of the remaining cadidates after that distribution.
 """

num_cols = 4


def make_waffle(data, title):
    legend = {
        "loc": "lower left",
        "bbox_to_anchor": (0, -0.5),
        "ncol": 2,
        "framealpha": 0,
        "fontsize": 15,
    }

    return plt.figure(
        FigureClass=Waffle,
        rows=6,
        values=data,
        labels=[f"{k} ({v})" for k, v in data.items()],
        colors=[colours.get(k, choice(other_colours)) for k in data],
        legend=legend,
        title={"label": title, "loc": "left", "fontsize": 15},
    )


class GreensPrefExplorer(pn.viewable.Viewer):
    green_pref = param.Integer(label="Greens to ALP pref. %", bounds=(0, 100))

    @staticmethod
    def greens_decider(df):
        x, y = df["toRunningTotal"] - df["preferences"]
        return df["votesDistributed"].iloc[0] >= abs(x - y)

    def __init__(self, distribution, party_tally, electorates, **params):
        super().__init__(**params)

        self.party_tally = party_tally.copy(deep=True)
        self.new_party_tally = self.party_tally.copy(deep=True)
        self.new_party_tally.name = "New"

        self.electorates = electorates
        self.prepare_data(distribution)

        self.num_cols = 4

        self.intro = pn.pane.Markdown(intro_txt)

        data_old = self.party_tally.sort_values(ascending=False).to_dict()
        actual_waffle = make_waffle(data_old, title="Actual Results")
        self.actual_waffle = pn.pane.Matplotlib(
            actual_waffle, sizing_mode="stretch_width", tight=True, format="svg"
        )

    def prepare_data(self, distribution):
        self.data = distribution
        max_exclusion = self.data.groupby("electorate")["exclusion"].max("exclusion")

        # then for each electorate, check if both 'The Greens' and 'ALP' were part of the distribution
        # this will give us those electorates where greens' 2nd prefs were transferred last.
        self.greens_third = []
        for electorate, exclusion in max_exclusion.items():
            df = self.data.loc[electorate]
            df = df[df["exclusion"] == exclusion]
            if (
                (df["fromParty"].unique()[0] == "The Greens")
                and ("ALP" in self.data["toParty"].unique())
                and GreensPrefExplorer.greens_decider(df)
            ):
                self.greens_third.append((electorate, exclusion))

        all_data = []
        for electorate, exclusion in self.greens_third:
            df = self.data.loc[electorate]
            df = df[df["exclusion"] == exclusion].copy(deep=True)
            all_data.append(df)
        self.data = pd.concat(all_data)

        # total and percentage of votes transferred from greens to ALP
        labor = self.data["toParty"] == "ALP"
        total_transferred = self.data[labor]["votesDistributed"].sum()
        total_labor = self.data[labor]["preferences"].sum()

        self.data = self.data.reset_index().set_index(["electorate", "exclusion"])
        self.data = self.data.loc[self.greens_third][
            [
                "toParty",
                "toCandidate",
                "preferences",
                "toRunningTotal",
                "votesDistributed",
            ]
        ].droplevel(level="exclusion")
        self.data["origTotal"] = self.data["toRunningTotal"] - self.data["preferences"]

        idx = self.data.reset_index().groupby("electorate")["toRunningTotal"].idxmax()
        self.old_tally = self.data.reset_index().loc[idx].value_counts("toParty")
        self.new_tally = self.old_tally.copy(deep=True)

        self.data = self.data.astype(
            {"preferences": "int32", "toRunningTotal": "int32", "origTotal": "int32"}
        )

        self.green_pref = int((total_labor / total_transferred) * 100)

    def new_waffle(self):
        data_new = self.new_tally.sort_values(ascending=False).to_dict()
        new_waffle = make_waffle(data_new, title="New Results")
        new_waffle = pn.pane.Matplotlib(
            new_waffle, sizing_mode="stretch_width", tight=True, format="svg"
        )
        return new_waffle

    @staticmethod
    def vote_bars(data, electorate):
        # bars for running totals
        running_totals = data[["toCandidate", "toRunningTotal", "toParty"]]

        hover_tooltips = [
            ("Candidate", "@toCandidate"),
            ("Party", "@toParty"),
            ("Votes", "@toRunningTotal{0,0}"),
        ]

        return hv.Bars(running_totals.sort_values("toRunningTotal")).opts(
            hover_tooltips=hover_tooltips,
            invert_axes=True,
            show_legend=False,
            default_tools=["hover"],
            toolbar=None,
            axiswise="xaxis",
            xformatter=NumeralTickFormatter(format="0 a"),
            hooks=[hide_hook],
        )

    @pn.depends("green_pref", watch=True)
    def pref_changed(self):
        labor = self.data["toParty"] == "ALP"

        pct = self.green_pref / 100
        self.data.loc[labor, "preferences"] = (
            self.data.loc[labor, "votesDistributed"] * pct
        ).astype("int32")

        self.data.loc[~labor, "preferences"] = (
            self.data.loc[~labor, "votesDistributed"]
            - self.data.loc[labor, "preferences"]
        )
        self.data["toRunningTotal"] = self.data["preferences"] + self.data["origTotal"]

        idx = self.data.reset_index().groupby("electorate")["toRunningTotal"].idxmax()
        self.new_tally = self.data.reset_index().loc[idx].value_counts("toParty")
        self.new_tally = (
            (self.party_tally + (self.new_tally - self.old_tally))
            .dropna()
            .astype("int")
        )
        self.new_tally.index.name = "party"
        self.new_tally.name = "New"

    def electorate_bars(self):
        bars = []
        for electorate, rows in self.data.groupby("electorate"):
            options = dict(
                width=200,
                height=80,
                ylabel="",
                yaxis=None,
                fontsize=dict(title=10),
                color="toParty",
                cmap=colours,
                xaxis="bare",
            )
            bars.append(
                GreensPrefExplorer.vote_bars(rows, electorate).opts(
                    **options, title=self.electorates[electorate]
                )
            )
        return pn.FlexBox(*bars, align_items="center")

    # return hv.Layout(bars).cols(num_cols)

    def __panel__(self):
        view = pn.GridSpec(sizing_mode="stretch_both", max_width=1600)
        view[:, 0:4] = pn.Column(
            self.intro,
            pn.Spacer(height=50),
            self.param.green_pref,
            pn.Spacer(height=50),
            self.actual_waffle,
            pn.Spacer(height=20),
            self.new_waffle,
        )
        view[:, 4] = pn.Spacer()
        view[:, 5:15] = self.electorate_bars
        return view
