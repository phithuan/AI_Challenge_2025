import joblib
import numpy as np

# Load model và encoders 1 lần khi import
model = joblib.load('predictor/ml_model/catboost_model.pkl')
label_encoders = joblib.load('predictor/ml_model/label_encoders.pkl')
class_mappings = joblib.load('predictor/ml_model/class_mappings.pkl')

def predict_result(input_data):
    """
    input_data: dict, ví dụ:
    {
        'Gender': 'Male',
        'Age': 20,
        ...
    }
    """
    transformed = []

    for col, value in input_data.items():
        # Nếu cột đó cần label encoding
        if col in label_encoders:
            le = label_encoders[col]
            transformed.append(le.transform([value])[0])
        else:
            transformed.append(value)

    # Convert thành mảng numpy
    input_array = np.array(transformed).reshape(1, -1)

    # Dự đoán
    prediction = model.predict(input_array)[0]
    return prediction
