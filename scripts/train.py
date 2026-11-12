from pathlib import Path
import numpy as np
from ml.feature_pipeline.vision import train_vocabulary

if __name__ == "__main__":
    centers, version = train_vocabulary()
    destination = Path("ml/feature_pipeline/codebook.npz")
    np.savez_compressed(destination, centers=centers)
    print(f"Saved {version} to {destination}. Reprocess existing pages after changing the vocabulary.")
