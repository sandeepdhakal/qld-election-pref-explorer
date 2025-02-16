import param
import panel as pn
import pandas as pd
import holoviews as hv
from consts import colours
from bokeh.models import HoverTool
from holoviews import dim
from utils import hide_hook, label_opts


class OverallPrefExplorer(pn.viewable.Viewer):
    data = param.DataFrame(doc="Stores preference distribution data.")
    party_tally = param.Series(doc="Stores total party tally.")

    intro = """

    This dashboard is for exploring the preference flows during the [2024 QLD state elections](https://en.wikipedia.org/wiki/2024_Queensland_state_election). The data was extracted from [QLD Electoral Commission](https://results.elections.qld.gov.au/SGE2024).
    
    There are three tabs: for exploring the overall preference flows, for exploring the preference flows for each electorate, and one for exploring the preference flows from the Greens to the ALP.
    
    **Note**: Independent candidates are not included in the preference flows.
    
    More details about how this dashboard was build can be found in [this blog post](https://sandeepdhakal.xyz).
    
    """

    def __init__(self, **params):
        super().__init__(**params)
        table = self.get_table()
        sankey = self.get_sankey()
        bars = self.get_party_bars()

        self._layout = pn.GridSpec(sizing_mode="stretch_both", max_width=1600)
        self._layout[:, 0:4] = pn.Column(
            pn.pane.Markdown(self.intro), pn.Spacer(height=50), bars
        )
        self._layout[0:10, 5:15] = sankey
        self._layout[11:18, 4:15] = table

    def get_table(self):
        return self.data.pivot_table(
            index=["fromParty"],
            columns=["toParty"],
            values="preferences",
            aggfunc="sum",
            margins=True,
            margins_name="Total",
            observed=True,
            fill_value=0,
        ).style.background_gradient(axis=1, cmap="BuPu")

    def get_sankey(self):
        self.data = (
            self.data.groupby(["fromParty", "toParty"], observed=True)[["preferences"]]
            .sum()
            .reset_index()
        )

        # calculate the percentage of votes transferred
        self.data["from_pct"] = (
            self.data["preferences"]
            / self.data.groupby(["fromParty"], observed=True)["preferences"].transform(
                "sum"
            )
            * 100
        )
        self.data["to_pct"] = (
            self.data["preferences"]
            / self.data.groupby(["toParty"], observed=True)["preferences"].transform(
                "sum"
            )
            * 100
        )

        # %%
        # assign unique codes to the 'from' and 'to' parties
        # since sankey doesn't support acyclic connections, we have to assign unique codes
        # to both 'from' and 'to' parties.
        self.data["from"] = pd.Categorical(
            self.data["fromParty"].cat.remove_unused_categories()
        ).codes
        step = self.data["from"].max()
        self.data["to"] = (
            pd.Categorical(self.data["toParty"].cat.remove_unused_categories()).codes
            + step
            + 1
        )
        # code to party dict so we can construct the node dataset to be passed to hv.Sankey
        # nodes will hold information corresponding to each code
        from_codes = sorted(
            dict(zip(self.data["from"], self.data["fromParty"])).items()
        )
        to_codes = sorted(dict(zip(self.data["to"], self.data["toParty"])).items())

        nodes = [x[1] for x in from_codes + to_codes]
        nodes = hv.Dataset(enumerate(nodes), "index", "party")

        # cmap for the nodes/edges
        cmap = {str(i[0]): colours[i[1]] for i in from_codes + to_codes}

        # %%
        hover = HoverTool(
            tooltips=[
                ("From", "@fromParty (@from_pct %)"),
                ("To", "@toParty (@to_pct %)"),
                ("Transferred", "@preferences{0,0}"),
            ],
        )

        cols = [
            "from",
            "to",
            "preferences",
            "fromParty",
            "toParty",
            "from_pct",
            "to_pct",
        ]
        return hv.Sankey(
            (self.data[cols], nodes),
            kdims=["from", "to"],
            vdims=["preferences", "from_pct", "to_pct", "fromParty", "toParty"],
        ).opts(
            labels="party",
            label_position="outer",
            edge_color=dim("to").str(),
            node_color=dim("index").str(),
            cmap=cmap,
            tools=[hover],
        )

    def get_party_bars(self):
        bars = hv.Bars(self.party_tally.sort_values(), ["party"], ["Actual"]).opts(
            invert_axes=True,
            color="party",
            cmap=colours,
            xaxis=None,
            xlabel="",
            show_legend=False,
            default_tools=[],
            tools=["hover"],
            toolbar=None,
            title="Total seats won",
            hooks=[hide_hook],
            height=200,
        )

        # We'll add value labels to the bars
        # Hack for Holoviews: xoffset doesn't currently work.
        # Setting xoffset for categorical axis makes everything disappear :(
        value_dimension = hv.Dimension("Actual", value_format=lambda x: f"       {x}")
        count_labels = hv.Labels(
            self.party_tally.sort_values(),
            kdims=["party", "Actual"],
            vdims=value_dimension,
        ).opts(**label_opts)

        return bars * count_labels

    def __panel__(self):
        return self._layout
