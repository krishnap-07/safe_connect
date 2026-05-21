from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestRegressor
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import random
import os
import sys
sys.path.insert(
    0, r"D:\SAFE_ROUTE (Disaster_management)\SAFE_ROUTE (Disaster_management)\SAFE_CONNECT\.venv311\Lib\site-packages")


# Ensure directories exist
os.makedirs("models", exist_ok=True)
os.makedirs("data", exist_ok=True)

print("1. Generating synthetic multimodal disaster dataset...")
np.random.seed(42)
random.seed(42)

NUM_SAMPLES = 5000

disaster_types = ["FIRE", "FLOOD", "EARTHQUAKE", "ACCIDENT", "OTHER"]
damage_levels = ["Intact", "Partially Collapsed", "Destroyed", "Unknown"]

# Text templates for NLP
urgent_texts = [
    "Help! People are trapped under the debris, we need immediate rescue!",
    "Massive explosion, huge fire, multiple casualties visible.",
    "The roof completely collapsed, many people are inside.",
    "Fast rising flood waters, please send boats urgently!",
    "Horrible accident, victims are bleeding and unconscious.",
    "Please hurry, building is totally destroyed and on fire."
]
medium_texts = [
    "There is a fire but it's contained for now.",
    "Water level is knee deep, some cars are stuck.",
    "Minor earthquake felt, some cracks in the walls.",
    "Car accident, everyone is out but needs checkup.",
    "Part of the wall fell down, no one seems trapped.",
    "Smoke coming from the building, people have evacuated."
]
calm_texts = [
    "A small trash fire outside, no danger to buildings.",
    "Minor flooding on the street, no homes affected.",
    "Just a fender bender, everyone is fine.",
    "Everything is okay, just reporting a broken pipe.",
    "Building is fully intact, just some debris on the road.",
    "False alarm, the smoke was just a barbecue."
]

data = []
for _ in range(NUM_SAMPLES):
    d_type = random.choice(disaster_types)
    # Right-skewed distribution for human count
    h_count = int(np.random.gamma(2, 2))
    damage = random.choice(damage_levels)

    # Determine base urgency to match text
    base_urgency = random.uniform(0, 1)
    if base_urgency > 0.7:
        text = random.choice(urgent_texts)
        urgency_score = 40
    elif base_urgency > 0.3:
        text = random.choice(medium_texts)
        urgency_score = 20
    else:
        text = random.choice(calm_texts)
        urgency_score = 5

    # Calculate Ground Truth Severity (what the AI should learn)
    severity = 10

    # Heuristics for the ground truth
    if d_type in ["FIRE", "EARTHQUAKE", "FLOOD"]:
        severity += 15

    if damage == "Destroyed":
        severity += 30
    elif damage == "Partially Collapsed":
        severity += 15

    severity += (h_count * 5)
    severity += urgency_score

    # Add some random noise
    severity += np.random.normal(0, 5)

    # Cap between 0 and 100
    severity = max(0, min(100, int(severity)))

    data.append({
        "report_text": text,
        "disaster_type": d_type,
        "human_count": h_count,
        "damage_level": damage,
        "severity_score": severity
    })

df = pd.DataFrame(data)
df.to_csv("data/synthetic_disaster_data.csv", index=False)
print(
    f"   Generated {len(df)} samples and saved to data/synthetic_disaster_data.csv")

print("\n2. Building Scikit-Learn Multimodal Pipeline...")

X = df[["report_text", "disaster_type", "human_count", "damage_level"]]
y = df["severity_score"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42)

# Create the preprocessing steps for different feature types
preprocessor = ColumnTransformer(
    transformers=[
        ('text', TfidfVectorizer(max_features=100,
         stop_words='english'), 'report_text'),
        ('cat', OneHotEncoder(handle_unknown='ignore'),
         ['disaster_type', 'damage_level']),
        ('num', StandardScaler(), ['human_count'])
    ]
)

# Combine preprocessing and the Random Forest model
model_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1))
])

print("3. Training Random Forest Regressor...")
model_pipeline.fit(X_train, y_train)

print("\n4. Evaluating Model Accuracy...")
y_pred = model_pipeline.predict(X_test)
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"   Mean Squared Error: {mse:.2f}")
print(f"   R^2 Score: {r2:.4f} (1.0 is perfect accuracy)")

print("\n5. Saving Model to models/severity_rf_model.pkl...")
model_path = Path("models/severity_rf_model.pkl")
joblib.dump(model_pipeline, model_path)
print("   Done! The AI model is ready for real-time inference in the backend.")
