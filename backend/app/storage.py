"""
Handles reading/writing dataframes to disk under data/uploads and
data/generated. Kept separate from db.py because SQLite stores metadata
only, never raw record content (privacy-by-design requirement).
"""
import pandas as pd

from app.config import UPLOAD_DIR, GENERATED_DIR


def save_dataframe(df: pd.DataFrame, dataset_id: str, generated: bool = False) -> str:
    target_dir = GENERATED_DIR if generated else UPLOAD_DIR
    path = target_dir / f"{dataset_id}.parquet"
    df.to_parquet(path, index=False)
    return str(path)


def load_dataframe(file_path: str) -> pd.DataFrame:
    return pd.read_parquet(file_path)
