import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

print("Loading investor_data.csv ...")
data = pd.read_csv("investor_data.csv")

X = data[["age", "income", "horizon", "loss_tolerance", "experience"]]
y = data["risk_type"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = DecisionTreeClassifier(max_depth=6, min_samples_split=5, random_state=42)
model.fit(X_train, y_train)

predictions = model.predict(X_test)
accuracy    = accuracy_score(y_test, predictions)

print(f"\nModel Accuracy: {accuracy * 100:.2f}%")
print("\nClassification Report:")
print(classification_report(y_test, predictions))

def predict_investor(age, income, horizon, loss_tolerance, experience):
    input_data = pd.DataFrame(
        [[age, income, horizon, loss_tolerance, experience]],
        columns=["age", "income", "horizon", "loss_tolerance", "experience"]
    )
    return model.predict(input_data)[0]

print("Sample predictions:")
print("Age 25, income 50000, horizon 15, loss 25, exp 2 →", predict_investor(25, 50000, 15, 25, 2))
print("Age 45, income 80000, horizon 8,  loss 12, exp 1 →", predict_investor(45, 80000, 8, 12, 1))
print("Age 65, income 30000, horizon 3,  loss 3,  exp 0 →", predict_investor(65, 30000, 3, 3, 0))

joblib.dump(model, "risk_model.pkl")
print("\n risk_model.pkl saved successfully!")