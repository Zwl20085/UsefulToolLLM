import streamlit as st

from utils import load_image
from color_extractor import extract_colors, sort_colors
from cmap_builder import build_cmap, preview_cmap, build_swatch_image
from exporter import to_py_snippet, to_pickle

st.set_page_config(page_title="Image → Colormap", layout="wide")
st.title("Image to Matplotlib Colormap Generator")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    uploaded = st.file_uploader(
        "Upload image", type=["png", "jpg", "jpeg", "bmp", "webp", "tiff"]
    )

    n_colors = st.slider("Number of colors", min_value=3, max_value=16, value=8)

    sort_strategy = st.selectbox(
        "Color sort order",
        options=["luminance", "hue", "none"],
        index=0,
    )

    cmap_type = st.radio(
        "Colormap type",
        options=["linear", "listed"],
        index=0,
        help=(
            "**linear** – smooth interpolation between colors\n\n"
            "**listed** – discrete color blocks (good for categorical data)"
        ),
    )

    cmap_name = st.text_input("Colormap name", value="my_cmap")

    generate = st.button("Generate Colormap", type="primary")

# ── Main area ─────────────────────────────────────────────────────────────────
if uploaded is None:
    st.info("Upload an image in the sidebar to get started.")
    st.stop()

image = load_image(uploaded)

col_img, col_swatch = st.columns([1, 2])
with col_img:
    st.subheader("Uploaded Image")
    st.image(image, use_container_width=True)

# Run extraction immediately so swatches update with slider changes
colors = extract_colors(image, n_colors=n_colors, method="kmeans")
colors = sort_colors(colors, strategy=sort_strategy)

with col_swatch:
    st.subheader("Extracted Color Swatches")
    swatch_img = build_swatch_image(colors)
    st.image(swatch_img, use_container_width=True)

    st.caption(" | ".join(f"rgb{c}" for c in colors))

# ── Generate on button press (persist via session_state) ──────────────────────
if generate:
    cmap = build_cmap(colors, name=cmap_name, cmap_type=cmap_type)
    st.session_state["cmap"] = cmap
    st.session_state["colors"] = colors
    st.session_state["cmap_name"] = cmap_name
    st.session_state["cmap_type"] = cmap_type

if "cmap" in st.session_state:
    cmap = st.session_state["cmap"]
    saved_colors = st.session_state["colors"]
    saved_name = st.session_state["cmap_name"]
    saved_type = st.session_state["cmap_type"]

    st.subheader("Colormap Preview")
    fig = preview_cmap(cmap)
    st.pyplot(fig)

    st.subheader("Export")
    dl_col1, dl_col2 = st.columns(2)

    with dl_col1:
        snippet = to_py_snippet(saved_colors, saved_name, saved_type)
        st.download_button(
            label="Download .py snippet",
            data=snippet,
            file_name=f"{saved_name}.py",
            mime="text/x-python",
        )
        with st.expander("Preview snippet"):
            st.code(snippet, language="python")

    with dl_col2:
        pickle_bytes = to_pickle(cmap)
        st.download_button(
            label="Download .pickle",
            data=pickle_bytes,
            file_name=f"{saved_name}.pkl",
            mime="application/octet-stream",
        )
        st.caption(
            "Load with: `import pickle; cmap = pickle.load(open('file.pkl','rb'))`"
        )
