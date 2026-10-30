# Smart Grid Threat Detection - Render Deployment

## What is included
- Existing project source code and model architecture
- Existing trained PyTorch checkpoints in `saved_models/`
- `app.py`: Streamlit dashboard for synthetic-data demonstration
- `requirements.txt`: application dependencies
- `render.yaml`: Render deployment configuration
- `.python-version`: Python 3.11.11

## Run locally
1. Create and activate a Python virtual environment.
2. Install CPU PyTorch:
   `pip install --index-url https://download.pytorch.org/whl/cpu torch==2.10.0`
3. Install remaining dependencies:
   `pip install -r requirements.txt`
4. Start the dashboard:
   `streamlit run app.py`

## Deploy on Render
1. Upload this folder's contents to a GitHub repository.
2. In Render, choose New -> Blueprint and connect the repository,
   or create a Python Web Service manually.
3. If creating manually, use:
   - Build command:
     `pip install --index-url https://download.pytorch.org/whl/cpu torch==2.10.0 && pip install -r requirements.txt`
   - Start command:
     `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
4. Select a compute plan appropriate for PyTorch memory usage.

## Important notes
- The dashboard generates synthetic data using the repository's own generator.
- The repository does not include a saved StandardScaler, so the demo fits a
  scaler on each generated synthetic batch. This is a demonstration pipeline,
  not a validated production inference pipeline.
- The supplied source implements an AutoEncoder-GAN with a CNN-LSTM encoder
  and classifier. It does not include a GNN implementation.
- Render Free services have 512 MB RAM and may run out of memory when loading
  PyTorch. A service with more memory may be required.
