# Schengen Clock

A Python Streamlit app to track your Schengen visa entry and exit dates, calculate total stay in the last 180 days, and visualize your usage with a progress bar and color-coded status alerts.

## Features

- Set a control date (default: today)
- Add trips with entry and exit dates
- Calculate total days spent in Schengen area within the 180-day window
- Progress bar showing usage out of 90 days
- Color-coded alerts: Safe (<75 days), Warning (75-90 days), Danger (>90 days)

## Installation

1. Install dependencies:
   pip install -r requirements.txt

2. Run the app:
   streamlit run main.py

## Usage

- Open the app in your browser
- Set the control date if needed
- Add your trips using the form
- View the calculations and visualizations
