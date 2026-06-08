import streamlit as st

from utils import load_image
from strip_detector import detect_strip, inset_bbox, draw_bbox_overlay
from sampler import sample_gradient, build_swatch_preview
from ticks import make_ticks, format_ticks
from svg_builder import build_svg, render_preview_png

st.set_page_config(page_title="Colorbar → SVG", layout="wide")
st.title("Colorbar Screenshot to Clean SVG")
st.caption(
    "Upload a captured colorbar from FE/CAE software (Abaqus, ANSYS, COMSOL). "
    "The tool finds the colored strip, you enter the value range, and it returns "
    "a clean SVG with a handful of evenly-spaced labels."
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    uploaded = st.file_uploader(
        "Upload colorbar screenshot",
        type=["png", "jpg", "jpeg", "bmp", "webp", "tiff"],
    )

    orientation_mode = st.radio(
        "Orientation", ["Auto", "Vertical", "Horizontal"], index=0
    )

    st.subheader("Value range")
    vmin = st.number_input("Min value", value=0.0, format="%g")
    vmax = st.number_input("Max value", value=100.0, format="%g")
    scale = st.radio("Scale", ["linear", "log"], index=0, horizontal=True)

    tick_count = st.slider("Number of tick labels", 4, 8, 5)
    flip = st.checkbox("Flip gradient direction")

    st.subheader("SVG style")
    mode = st.radio(
        "Fill",
        ["gradient", "discrete"],
        index=0,
        help="**gradient** – smooth interpolation\n\n**discrete** – banded blocks",
    )
    bar_length = st.slider("Bar length (px)", 120, 600, 320, step=20)
    bar_thickness = st.slider("Bar thickness (px)", 10, 80, 30, step=2)
    border = st.checkbox("Draw border", value=True)
    title = st.text_input("Title")
    units = st.text_input("Units")

    generate = st.button("Generate SVG", type="primary")

# ── Main area ─────────────────────────────────────────────────────────────────
if uploaded is None:
    st.info("Upload a colorbar screenshot in the sidebar to get started.")
    st.stop()

image = load_image(uploaded)

# Validate the value range early.
range_ok = True
if vmax == vmin:
    st.error("Max value must differ from Min value.")
    range_ok = False
if scale == "log" and (vmin <= 0 or vmax <= 0):
    st.error("Log scale requires both Min and Max to be > 0.")
    range_ok = False

# Auto-detect once per uploaded file; cache so slider edits don't re-trigger it.
file_id = f"{uploaded.name}:{uploaded.size}"
if st.session_state.get("cb_file_id") != file_id:
    st.session_state["cb_file_id"] = file_id
    st.session_state["cb_detection"] = detect_strip(image)
det = st.session_state["cb_detection"]

if orientation_mode == "Auto":
    orientation = det.orientation
else:
    orientation = orientation_mode.lower()

if det.confidence < 0.5:
    st.warning(
        "Strip auto-detection was uncertain — check the red box and adjust the "
        "region sliders below if needed."
    )

# Region sliders (seeded from detection; keyed per-file so a new upload resets them).
with st.expander("Adjust strip region", expanded=det.confidence < 0.5):
    W, H = image.size
    left = st.slider("Left", 0, W, int(det.left), key=f"left_{file_id}")
    right = st.slider("Right", 0, W, int(det.right), key=f"right_{file_id}")
    top = st.slider("Top", 0, H, int(det.top), key=f"top_{file_id}")
    bottom = st.slider("Bottom", 0, H, int(det.bottom), key=f"bottom_{file_id}")

if right <= left or bottom <= top:
    st.error("Invalid region: Right must be > Left and Bottom must be > Top.")
    st.stop()

bbox = (left, top, right, bottom)
sample_box = inset_bbox(bbox)
colors = sample_gradient(
    image, sample_box, n_samples=64, orientation=orientation, flip=flip
)

# ── Live previews ─────────────────────────────────────────────────────────────
col_img, col_preview = st.columns([1, 1])
with col_img:
    st.subheader("Detected region")
    st.image(draw_bbox_overlay(image, bbox), use_container_width=True)

with col_preview:
    st.subheader("Sampled gradient")
    st.image(
        build_swatch_preview(colors, orientation), use_container_width=False,
        caption="min → max (bottom→top for vertical, left→right for horizontal)",
    )
    if range_ok:
        ticks = format_ticks(make_ticks(vmin, vmax, tick_count, scale))
        st.subheader("Live preview")
        st.image(
            render_preview_png(
                colors, ticks, orientation=orientation, mode=mode,
                title=title, units=units, bar_length=bar_length,
                bar_thickness=bar_thickness, border=border,
            )
        )

# ── Generate + export ─────────────────────────────────────────────────────────
if generate and range_ok:
    ticks = format_ticks(make_ticks(vmin, vmax, tick_count, scale))
    svg = build_svg(
        colors, ticks, orientation=orientation, mode=mode, title=title,
        units=units, bar_length=bar_length, bar_thickness=bar_thickness, border=border,
    )
    st.session_state["cb_svg"] = svg

if "cb_svg" in st.session_state:
    svg = st.session_state["cb_svg"]
    st.subheader("Export")
    st.download_button(
        label="Download SVG",
        data=svg,
        file_name="colorbar.svg",
        mime="image/svg+xml",
    )
    with st.expander("Preview SVG source"):
        st.code(svg, language="xml")
