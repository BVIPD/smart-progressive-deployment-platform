import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

p = Path(__file__).resolve().parent.parent

df = pd.read_csv(p / "dataset" / "deployment_metrics.csv")

x = df.drop("deployment_success", axis=1)
y = df["deployment_success"]

x_train, x_test, y_train, y_test = train_test_split(
    x, y, test_size=0.2, random_state=42, stratify=y
)

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    class_weight="balanced"
)

model.fit(x_train, y_train)

pred = model.predict(x_test)

print("Model Training Completed!")
print("Accuracy:", accuracy_score(y_test, pred))
print("\nClassification Report:")
print(classification_report(y_test, pred))
print("\nConfusion Matrix:")
print(confusion_matrix(y_test, pred))

joblib.dump(model, p / "ml" / "deployment_model.pkl")

print("\nModel saved successfully!")
