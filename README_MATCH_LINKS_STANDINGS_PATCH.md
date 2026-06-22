Patch: match links and group standings in cards

Replace these files:
- main.py
- db.py
- formatting.py
- match_card.py

What changed:
- every text match list now includes a clickable command link like /match_123
- /match_123 opens the match card
- /match 123 also works
- match card image now shows current group position and points for both teams
- personal match post also shows current group position and points
- standings are calculated from scores saved in the local PostgreSQL matches table
- points are calculated as 3 for win, 1 for draw, 0 for loss
- ranking uses points, goal difference, goals for, then team name

Important:
- standings will be accurate only after scores are synced into the database
- use /sync_scores to update played match scores

Expected /source version:
local-schedule-2026-06-19-v24-match-links-standings
