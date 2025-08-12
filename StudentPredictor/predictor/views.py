from django.shortcuts import render
from .forms import PredictForm
from .ml_model.predict import predict_result

def predict_view(request):
    result = None  # Khởi tạo kết quả dự đoán ban đầu

    if request.method == 'POST':
        form = PredictForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Chuẩn bị đúng dict input_data (khớp với model)
            input_data = {
                'Gender': cd['Gender'],
                'Age': cd['Age'],
                'Department': cd['Department'],
                'Attendance (%)': cd['Attendance'],
                'Study_Hours_per_Week': cd['Study_Hours_per_Week'],
                'Extracurricular_Activities': cd['Extracurricular_Activities'],
                'Internet_Access_at_Home': cd['Internet_Access_at_Home'],
                'Parent_Education_Level': cd['Parent_Education_Level'],
                'Family_Income_Level': cd['Family_Income_Level'],
                'Stress_Level (1-10)': cd['Stress_Level'],
                'Sleep_Hours_per_Night': cd['Sleep_Hours_per_Night'],
                'Assignments_Avg': cd['Assignments_Avg'],
                'Quizzes_Avg': cd['Quizzes_Avg'],
                'Participation_Score': cd['Participation_Score'],
            }
            # Gọi hàm dự đoán
            result = predict_result(input_data)
    else:
        form = PredictForm()  # GET request thì render form rỗng

    return render(request, 'predictor/predict.html', {'form': form, 'result': result})
