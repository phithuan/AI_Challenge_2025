from django import forms

class PredictForm(forms.Form):
    Gender = forms.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')])
    Age = forms.IntegerField(min_value=15, max_value=30, initial=20)
    Department = forms.ChoiceField(choices=[('Mathematics', 'Mathematics'), ('Business', 'Business'), ('CS', 'CS')])
    Attendance = forms.IntegerField(label="Attendance (%)", min_value=0, max_value=100, initial=85)
    Study_Hours_per_Week = forms.IntegerField(min_value=0, max_value=60, initial=10)
    Extracurricular_Activities = forms.ChoiceField(choices=[('Yes', 'Yes'), ('No', 'No')])
    Internet_Access_at_Home = forms.ChoiceField(choices=[('Yes', 'Yes'), ('No', 'No')])
    Parent_Education_Level = forms.ChoiceField(choices=[('High School', 'High School'), ('Unknown', 'Unknown'), ('PhD', 'PhD')])
    Family_Income_Level = forms.ChoiceField(choices=[('Medium', 'Mediuml'), ('Low', 'Low'), ('High', 'High')])
    Stress_Level = forms.IntegerField(label="Stress Level (1-10)", min_value=1, max_value=10, initial=5)
    Sleep_Hours_per_Night = forms.IntegerField(min_value=0, max_value=12, initial=7)
    Assignments_Avg = forms.IntegerField(label="Assignments Avg (0-100)", min_value=0, max_value=100, initial=75)
    Quizzes_Avg = forms.IntegerField(label="Quizzes Avg (0-100)", min_value=0, max_value=100, initial=70)
    Participation_Score = forms.IntegerField(label="Participation Score (0-100)", min_value=0, max_value=100, initial=80)
