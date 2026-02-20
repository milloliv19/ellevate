# ellevate
🤝 MatchMaker Pro
A human-in-the-loop automation tool for generating high-quality pairings within organizations.

🚀 The Workflow
Data Sync: Pulls participants and match history from Google Sheets.

Review: Streamlit UI allows for manual exclusion of participants (e.g., those on PTO).

Optimized Matching: A Python engine using Maximum Weight Matching (NetworkX) calculates the best pairings to ensure no one is left out and no matches are repeated.

Automated Handoff: Pushes results to a Tray.io webhook to trigger Braze email campaigns and update the Google Sheet history.

🛠 Tech Stack
Python: Core matching logic and graph theory.

NetworkX: Maximum cardinality matching.

Streamlit: Dashboard and control center.

Tray.io / Braze: Integration and communication layers.
