import holoviews as hv
import panel as pn
import param
from bokeh.models import NumeralTickFormatter
from holoviews import dim
from utils import hide_hook

intro_txt = """
 Select an electorate from the dropdown list below to view the preference flows for each electorate. 

 If no candidate wins 50% of more of the votes in the electorate, then the 2nd preference votes for the lowest ranked canddiate are transferred to the remaining candidates. This process takes place until a candidate crosses the 50% threshold.

 The figures on the right show each such distribution, and the running total of the remaining cadidates after that distribution.
 """


class ElectoratePrefExplorer(pn.viewable.Viewer):
    electorate = param.Selector(label="Select Electorate")

    def __init__(self, distribution, first_pref, electorates, **params):
        super().__init__(**params)
        self.param.electorate.objects = electorates
        self.param.electorate.default = next(iter(electorates))
        self.electorate = self.param.electorate.objects[self.param.electorate.default]

        self.first_pref = first_pref
        self.distribution = distribution

        self.intro = pn.pane.Markdown(intro_txt)

    @pn.depends("electorate", watch=False)
    def first_pref_bars(self):
        data = self.first_pref.loc[self.electorate].copy()
        data["party"] = data["party"].cat.remove_unused_categories()

        hover_tooltips = [
            ("Candidate", "@candidate"),
            ("Votes", "@count{0,0}"),
            ("Party", "@party"),
        ]

        return hv.Bars(data, ["party"], ["count", "candidate", "colour"]).opts(
            invert_axes=True,
            color="colour",
            ylabel="",
            xlabel="",
            xformatter=NumeralTickFormatter(format="0 a"),
            axiswise="yaxis",
            xticks=5,
            title="First preference votes",
            default_tools=[],
            tools=["hover"],
            toolbar=None,
            hooks=[hide_hook],
            hover_tooltips=hover_tooltips,
            height=175,
        )

    def prefs_sankey(self, data, electorate):
        # info about the edges
        source = data["fromCandidate"].to_list()
        target = data["toCandidate"].to_list()
        value = data["preferences"].to_list()
        edges = [(s, t, v) for s, t, v in zip(source, target, value)]

        # info about the nodes
        nodes = [source[0]] + target
        candidate_data = self.first_pref.loc[
            electorate and self.first_pref["candidate"].isin(nodes)
        ]

        # colour map
        cmap = self.first_pref[["candidate", "colour"]]
        cmap = {k: v for k, v in cmap.to_records(index=False)}

        return hv.Sankey(
            (edges, candidate_data[["candidate"]]),
            ["From", "To"],
            hv.Dimension("Votes"),
        ).opts(
            labels="candidate",
            label_position="inner",
            edge_color=dim("To").str(),
            node_color=dim("ballotOrder").str(),
            cmap=cmap,
            toolbar=None,
            node_padding=50,
            default_tools=["pan"],
        )

    def vote_bars(self, data):
        # bars for running totals
        running_totals = data[["toCandidate", "toRunningTotal", "toParty"]]

        # colour map
        cmap = self.first_pref[["candidate", "colour"]]
        cmap = {k: v for k, v in cmap.to_records(index=False)}

        hover_tooltips = [
            ("Candidate", "@toCandidate"),
            ("Party", "@toParty"),
            ("Votes", "@toRunningTotal{0,0}"),
        ]

        return hv.Bars(running_totals.sort_values("toRunningTotal")).opts(
            hover_tooltips=hover_tooltips,
            ylabel="",
            xlabel="",
            invert_axes=True,
            color="toCandidate",
            cmap=cmap,
            show_legend=False,
            default_tools=["hover"],
            toolbar=None,
            axiswise="xaxis",
            xformatter=NumeralTickFormatter(format="0 a"),
            hooks=[hide_hook],
            xticks=4,
        )

    @pn.depends("electorate", watch=False)
    def sankey_and_running_totals(self):
        columns = []
        elec = self.electorate
        for exc in sorted(self.distribution.loc[self.electorate]["exclusion"].unique()):
            # columns.append(pn.pane.Markdown(f"### Distribution {exc}"))

            data = self.distribution.loc[elec]
            data = data[data["exclusion"] == exc]

            sankey = self.prefs_sankey(data, elec).opts(
                width=500, height=175, title=f"Distribution {exc}"
            )

            xrange = (0, self.distribution.loc[elec, "toRunningTotal"].max())
            bars = (
                self.vote_bars(data)
                .opts(width=300, height=175)
                .redim(y=hv.Dimension("toRunningTotal", range=xrange))
            )
            bars = pn.pane.HoloViews(bars)
            columns.append(pn.Row(sankey, bars))

        return pn.Column(*columns, sizing_mode="stretch_width")

    def __panel__(self):
        view = pn.GridSpec(sizing_mode="stretch_both", max_width=1600)
        view[:, 0:4] = pn.Column(
            self.intro,
            pn.Spacer(height=50),
            self.param.electorate,
            pn.Spacer(height=50),
            self.first_pref_bars,
        )
        view[:, 4] = pn.Spacer()
        view[:, 5:15] = self.sankey_and_running_totals
        return view
