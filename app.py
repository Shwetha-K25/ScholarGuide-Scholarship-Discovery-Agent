
import streamlit as st

st.set_page_config(
    page_title="ScholarGuide",
    page_icon="🎓",
    layout="centered"
)

st.title("🎓 ScholarGuide")
st.subheader("Your AI-Powered Scholarship Discovery Assistant")

st.write(
    "Find scholarships that match your academic profile."
)

st.divider()

st.header("Student Details")

name = st.text_input("Enter your name")

state = st.selectbox(
    "Select your state",
    ["Tamil Nadu", "Kerala", "Karnataka", "Other"]
)

education = st.selectbox(
    "Current education level",
    ["School", "Diploma", "Undergraduate", "Postgraduate"]
)

course = st.text_input("Enter your course")

year = st.selectbox(
    "Current year of study",
    ["1st Year", "2nd Year", "3rd Year", "4th Year"]
)

income = st.selectbox(
    "Annual family income",
    ["Below ₹1 lakh", "₹1–2.5 lakh", "₹2.5–5 lakh", "Above ₹5 lakh", "Prefer not to say"]
)

if st.button("Find Scholarships"):
    if name and course:
        st.success("Your student profile has been submitted!")
        st.write("Name:", name)
        st.write("State:", state)
        st.write("Education:", education)
        st.write("Course:", course)
        st.write("Year:", year)
        st.write("Income:", income)
    else:
        st.warning("Please enter your name and course.")
