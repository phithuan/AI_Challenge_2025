import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from predictor.ml_model.predict import predict_result

sample_input = {
    'Gender': 'Male',
    'Age': 20,
    'Department': 'Business',
    'Attendance (%)': 85,
    'Study_Hours_per_Week': 10,
    'Extracurricular_Activities': 'Yes',
    'Internet_Access_at_Home': 'Yes',
    'Parent_Education_Level': 'High School',
    'Family_Income_Level': 'Medium',
    'Stress_Level (1-10)': 5,
    'Sleep_Hours_per_Night': 7,
    'Assignments_Avg': 75,
    'Quizzes_Avg': 70,
    'Participation_Score': 80,
}

result = predict_result(sample_input)
print("Kết quả dự đoán:", result)
