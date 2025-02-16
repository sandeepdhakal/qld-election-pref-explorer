# Bokeh hook to hide frame around the plots
def hide_hook(plot, element):
    plot.handles["plot"].border_fill_color = None
    plot.handles["plot"].outline_line_color = None


label_opts = dict(text_color="black", text_font_size="12px")
