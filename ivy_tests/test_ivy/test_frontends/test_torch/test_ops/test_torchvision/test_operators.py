# global
import numpy as np
from hypothesis import strategies as st

# local
import ivy_tests.test_ivy.helpers as helpers
from ivy_tests.test_ivy.helpers import handle_frontend_test


# --- Helpers --- #
# --------------- #


@st.composite
def _nms_helper(draw):
    img_width = draw(st.integers(250, 1250))
    img_height = draw(st.integers(250, 1250))
    num_boxes = draw(st.integers(5, 50))
    bbox = {}
    for _ in range(num_boxes):
        x1 = draw(st.integers(0, img_width - 20))
        w = draw(st.integers(5, img_width - x1))
        y1 = draw(st.integers(0, img_height - 20))
        h = draw(st.integers(5, img_height - y1))
        bbox[(x1, y1, x1 + w, y1 + h)] = draw(st.floats(0.1, 0.7))
    iou_threshold = draw(st.floats(0.2, 0.5))
    return (
        ["float32", "float32"],
        np.array(list(bbox.keys()), dtype=np.float32),
        np.array(list(bbox.values()), dtype=np.float32),
        iou_threshold,
    )


@st.composite
def _roi_align_helper(draw):
    dtype = draw(helpers.get_dtypes("valid"))[0]
    N = draw(st.integers(1, 5))
    C = draw(st.integers(1, 5))
    H = W = draw(st.integers(5, 20))

    img_width = img_height = draw(st.integers(50, 100))

    spatial_scale = H / img_height

    output_size = draw(st.integers(H - 2, H + 5))

    sampling_ratio = draw(st.one_of(st.just(-1), st.integers(1, 3)))

    aligned = draw(st.booleans())
    input = draw(
        helpers.array_values(
            dtype=dtype,
            shape=(N, C, H, W),
            min_value=-3,
            max_value=3,
        )
    )
    bbox = {}
    for i in range(N):
        num_boxes = draw(st.integers(1, 5))
        for _ in range(num_boxes):
            x1 = draw(st.integers(0, img_width - 20))
            w = draw(st.integers(5, img_width - x1))
            y1 = draw(st.integers(0, img_height - 20))
            h = draw(st.integers(5, img_height - y1))
            bbox[(i, x1, y1, x1 + w, y1 + h)] = 1

    return (
        [dtype],
        input,
        np.array(list(bbox.keys()), dtype=dtype).reshape((-1, 5)),
        output_size,
        spatial_scale,
        sampling_ratio,
        aligned,
    )


# --- Main --- #
# ------------ #


# nms
@handle_frontend_test(
    fn_tree="torch.ops.torchvision.nms",
    dts_boxes_scores_iou=_nms_helper(),
    test_with_out=st.just(False),
)
def test_torch_nms(
    *,
    dts_boxes_scores_iou,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    dts, boxes, scores, iou = dts_boxes_scores_iou
    helpers.test_frontend_function(
        input_dtypes=dts,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        boxes=boxes,
        scores=scores,
        iou_threshold=iou,
    )


# roi_align
@handle_frontend_test(
    fn_tree="torch.ops.torchvision.roi_align",
    inputs=_roi_align_helper(),
    test_with_out=st.just(False),
)
def test_torch_roi_align(
    *,
    inputs,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    dtypes, input, boxes, output_size, spatial_scale, sampling_ratio, aligned = inputs
    helpers.test_frontend_function(
        input_dtypes=dtypes,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input,
        boxes=boxes,
        output_size=output_size,
        spatial_scale=spatial_scale,
        sampling_ratio=sampling_ratio,
        aligned=aligned,
        rtol=1e-5,
        atol=1e-5,
    )
