import napari
import numpy as np

from magicgui import magicgui
from napari import Viewer

from .. import util
from ..segment_from_prompts import segment_from_points
from ..visualization import compute_pca
from .util import create_prompt_menu, prompt_layer_to_points

COLOR_CYCLE = ["#00FF00", "#FF0000"]


#
# the widgets
#


@magicgui(call_button="Segment Frame [S]")
def segment_frame_wigdet(v: Viewer):
    position = v.cursor.position
    t = int(position[0])

    this_prompts = prompt_layer_to_points(v.layers["prompts"], t)
    points, labels = this_prompts
    seg = segment_from_points(PREDICTOR, points, labels, image_embeddings=IMAGE_EMBEDDINGS, i=t)

    v.layers["current_track"].data[t] = seg.squeeze()
    v.layers["current_track"].refresh()


@magicgui(call_button="Track Object [V]", method={"choices": ["bounding_box", "mask"]})
def track_objet_widget(v: Viewer, iou_threshold: float = 0.8, method: str = "bounding_box"):
    pass


def annotator_tracking(raw, embedding_path=None, show_embeddings=False):
    # for access to the predictor and the image embeddings in the widgets
    global PREDICTOR, IMAGE_EMBEDDINGS, NEXT_ID
    NEXT_ID = 1
    _, PREDICTOR = util.get_sam_model()
    IMAGE_EMBEDDINGS = util.precompute_image_embeddings(PREDICTOR, raw, save_path=embedding_path)

    #
    # initialize the viewer and add layers
    #

    v = Viewer()

    v.add_image(raw)
    v.add_labels(data=np.zeros(raw.shape, dtype="uint32"), name="committed_tracks")
    v.add_labels(data=np.zeros(raw.shape, dtype="uint32"), name="current_track")

    # show the PCA of the image embeddings
    if show_embeddings:
        embedding_vis = compute_pca(IMAGE_EMBEDDINGS["features"])
        # FIXME don't hard-code the scale
        v.add_image(embedding_vis, name="embeddings", scale=(1, 8, 8))

    #
    # add the widgets
    #
    # TODO add the division labels
    labels = ["positive", "negative"]
    prompts = v.add_points(
        data=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],  # FIXME workaround
        name="prompts",
        properties={"label": labels},
        edge_color="label",
        edge_color_cycle=COLOR_CYCLE,
        symbol="o",
        face_color="transparent",
        edge_width=0.5,  # FIXME workaround
        size=12,
        ndim=3,
    )
    prompts.edge_color_mode = "cycle"

    #
    # add the widgets
    #

    # TODO add (optional) auto-segmentation functionality

    prompt_widget = create_prompt_menu(prompts, labels)
    v.window.add_dock_widget(prompt_widget)

    v.window.add_dock_widget(segment_frame_wigdet)
    v.window.add_dock_widget(track_objet_widget)

    #
    # key bindings
    #

    @v.bind_key("s")
    def _seg_slice(v):
        segment_frame_wigdet(v)

    @v.bind_key("v")
    def _track_object(v):
        track_objet_widget(v)

    @v.bind_key("t")
    def toggle_label(event=None):
        # get the currently selected label
        current_properties = prompts.current_properties
        current_label = current_properties["label"][0]
        new_label = "negative" if current_label == "positive" else "positive"
        current_properties["label"] = np.array([new_label])
        prompts.current_properties = current_properties
        prompts.refresh()
        prompts.refresh_colors()

    @v.bind_key("Shift-C")
    def clear_prompts(v):
        prompts.data = []
        prompts.refresh()

    #
    # start the viewer
    #

    # go to t=0
    v.dims.current_step = (0,) + tuple(sh // 2 for sh in raw.shape[1:])

    # clear the initial points needed for workaround
    clear_prompts(v)
    napari.run()
