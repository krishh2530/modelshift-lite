\# ModelShift-Lite



ModelShift-Lite is a lightweight, label-free monitoring system for detecting silent reliability degradation in deployed machine learning models.



\## Problem Statement

Deployed machine learning models often degrade silently over time due to changes in data distribution, while ground-truth labels are unavailable for continuous evaluation.



\## Objective

To design a behavior-centric monitoring system that tracks data drift and prediction instability to indicate model reliability degradation without modifying the deployed model.



\## Scope

This project focuses exclusively on post-deployment monitoring and does NOT perform:

\- model retraining

\- model correction

\- accuracy computation on production data



\## Key Components

\- Reference baseline data handling

\- Live inference data monitoring

\- Feature drift detection

\- Prediction behavior analysis

\- Model health scoring

\- Visualization dashboard



\## Technology Stack

\- Python

\- NumPy, Pandas, SciPy

\- Streamlit

\- SQLite (local storage)



\## Project Status

Project Phase-2 – Initial setup completed.



\## Disclaimer

This is a research-oriented academic prototype intended for controlled experimentation and evaluation.



