\# Drift-Sense: Navigation-Error Recovery for Wafer Inspection Tools



\## Problem



Wafer inspection tools must repeatedly return to the same microscopic site on a wafer. Due to stage drift and vibration, the tool may not land exactly at the correct location.



The task is to locate a Reference Image pattern inside a larger Search Image and return the center coordinates `(x, y)` of the matching region.



This is difficult because semiconductor layouts are highly periodic, so many incorrect locations may look similar to the correct one.



\## Current Status



This repository contains:



\- Synthetic data generation pipeline

\- Ground-truth coordinate generation

\- Basic project structure for matching and evaluation



\## Setup



Install dependencies:



```bash

pip install -r requirements.txt

