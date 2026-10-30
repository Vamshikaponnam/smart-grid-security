import streamlit as st
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

from model.autoencoder_gan import SmartGridSecurityModel
from utils.data_loader import generate_synthetic_data

st.set_page_config(
    page_title="Smart Grid Threat Detection",
    page_icon="🛡️",
    layout="wide",
)

CLASS_NAMES = {
    0: "Normal",
    1: "DDoS",
    2: "Data Injection",
    3: "Command Injection",
    4: "Scanning",
}


@st.cache_resource
def load_trained_model():
    """Load the existing trained PyTorch checkpoints once per app instance."""
    torch.set_num_threads(1)
    model = SmartGridSecurityModel(device=torch.device("cpu"))
    model.load_model("saved_models/smart_grid_model")
    return model


def create_demo_data(n_samples=1000):
    """Create the same kind of synthetic data supported by this repository."""
    np.random.seed(42)
    raw_df = generate_synthetic_data(
        n_samples=n_samples,
        time_steps=24,
        n_features=10,
        n_classes=5,
    )

    feature_columns = raw_df.columns[:-1]
    features = raw_df.loc[:, feature_columns].to_numpy(dtype=np.float32)
    true_labels = raw_df["label"].to_numpy(dtype=int)

    # The original project does not save its training StandardScaler.
    # Fit a scaler on this synthetic demonstration batch before inference.
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    sequences = scaled.reshape(-1, 24, 10)

    return raw_df, sequences, true_labels


st.title("🛡️ Smart Grid Cyber Threat Detection")
st.write(
    "Demonstration dashboard for the project's trained PyTorch "
    "AutoEncoder-GAN, CNN-LSTM encoder, and classifier."
)

st.info(
    "This demo uses synthetically generated data. Results demonstrate the "
    "application workflow and are not evidence of performance on real smart-grid traffic."
)

with st.sidebar:
    st.header("Demo settings")
    sample_count = st.selectbox("Number of synthetic records", [200, 500, 1000], index=1)
    st.caption("The model expects 24 time steps × 10 features per record.")

if st.button("Generate synthetic data and detect threats", type="primary"):
    try:
        with st.spinner("Generating data and running the trained models..."):
            model = load_trained_model()
            raw_df, sequences, true_labels = create_demo_data(sample_count)

            anomalies, reconstruction_errors, threshold = model.detect_anomalies(sequences)
            probabilities = model.classify_attacks(sequences)
            predicted_labels = np.argmax(probabilities, axis=1)

            results_df = pd.DataFrame({
                "actual_synthetic_label": [CLASS_NAMES[int(x)] for x in true_labels],
                "predicted_class": [CLASS_NAMES[int(x)] for x in predicted_labels],
                "anomaly_detected": anomalies.astype(bool),
                "reconstruction_error": reconstruction_errors,
                "prediction_confidence": probabilities.max(axis=1),
            })

            st.session_state["raw_demo"] = raw_df
            st.session_state["results_demo"] = results_df
            st.session_state["threshold_demo"] = float(threshold)

    except Exception as exc:
        st.error(f"Could not run the model: {exc}")
        st.exception(exc)

if "results_demo" in st.session_state:
    results = st.session_state["results_demo"]
    raw = st.session_state["raw_demo"]

    total = len(results)
    anomaly_total = int(results["anomaly_detected"].sum())
    normal_predictions = int((results["predicted_class"] == "Normal").sum())
    attack_predictions = total - normal_predictions

    st.subheader("Detection summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records analyzed", f"{total}")
    c2.metric("Anomalies flagged", f"{anomaly_total}")
    c3.metric("Predicted normal", f"{normal_predictions}")
    c4.metric("Predicted attacks", f"{attack_predictions}")

    left, right = st.columns(2)
    with left:
        st.subheader("Predicted attack classes")
        counts = results["predicted_class"].value_counts().reindex(
            list(CLASS_NAMES.values()), fill_value=0
        )
        st.bar_chart(counts)
    with right:
        st.subheader("Anomaly detection")
        st.write(f"Reconstruction-error threshold: `{st.session_state['threshold_demo']:.6f}`")
        st.write(
            f"{anomaly_total} of {total} records were flagged by the "
            "autoencoder reconstruction-error rule."
        )

    st.subheader("Prediction results")
    st.dataframe(results.head(100), use_container_width=True)

    st.download_button(
        "Download prediction results (CSV)",
        data=results.to_csv(index=False).encode("utf-8"),
        file_name="smart_grid_detection_results.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download generated synthetic dataset (CSV)",
        data=raw.to_csv(index=False).encode("utf-8"),
        file_name="smart_grid_synthetic_dataset.csv",
        mime="text/csv",
    )

st.divider()
st.caption(
    "Model architecture in the supplied repository: AutoEncoder-GAN with a "
    "CNN-LSTM encoder and a multi-class classifier. The supplied code does not "
    "contain a Graph Neural Network (GNN) implementation."
)
