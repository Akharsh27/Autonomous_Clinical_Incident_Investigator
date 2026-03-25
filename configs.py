from dataclasses import dataclass
import os
import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class FILE_PATH:
    vitals_dataset = os.path.join(BASE_DIR, 'Vital_Dataset.csv')
    vitals_dataset = os.path.abspath(vitals_dataset)
    
    treatment_dataset = os.path.join(BASE_DIR, 'TREATMEN_HISTORY_DATASET.csv')
    treatment_dataset = os.path.abspath(treatment_dataset)
    
    clinical_data = os.path.join(BASE_DIR, 'CLINICAL_NOTES_DATASET.csv')
    clinical_data = os.path.abspath(clinical_data)
    
    knowledge_base = os.path.join(BASE_DIR, 'knowledge_base.csv')
    knowledge_base = os.path.abspath(knowledge_base)


# ----------------------
# Load and Initialize DataFrames
# ----------------------
def load_datasets():
    """Load all CSV datasets with cleaned column headers."""
    
    # Load Vitals Dataset
    vitals_df = pd.read_csv(FILE_PATH.vitals_dataset)
    vitals_df.columns = vitals_df.columns.str.strip().str.lower()
    
    # Load Treatment History Dataset
    treatment_df = pd.read_csv(FILE_PATH.treatment_dataset)
    treatment_df.columns = treatment_df.columns.str.strip().str.lower()
    
    # Load Clinical Notes Dataset
    clinical_df = pd.read_csv(FILE_PATH.clinical_data)
    clinical_df.columns = clinical_df.columns.str.strip().str.lower()
    
    # Load Knowledge Base Dataset
    knowledge_base_df = pd.read_csv(FILE_PATH.knowledge_base)
    knowledge_base_df.columns = knowledge_base_df.columns.str.strip().str.lower()
    
    return {
        'vitals': vitals_df,
        'treatment': treatment_df,
        'clinical': clinical_df,
        'knowledge_base': knowledge_base_df
    }


# ----------------------
# Initialize Global Datasets
# ----------------------
DATASETS = load_datasets()

VITALS_DF = DATASETS['vitals']
TREATMENT_DF = DATASETS['treatment']
CLINICAL_DF = DATASETS['clinical']
KNOWLEDGE_BASE_DF = DATASETS['knowledge_base']