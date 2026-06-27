Patch: visual playoff bracket image

Replace/add these files:
- main.py
- db.py
- keyboards.py
- playoff_bracket.py

What changed:
- the Плей-офф button now sends a generated image bracket, not just a text list
- /playoffs and /playoff also send the visual bracket
- the bracket is built from current PostgreSQL matches at the moment of request
- the bracket uses the current scores and teams from the database
- every match box contains /match_123 so the user can open the match card
- if playoff matches are not published yet, the bot sends an image with an explanation
- under the image, bot still attaches buttons for the matches that are currently in the playoff list

Before using:
- press /sync to refresh schedule from ESPN
- then press Плей-офф or /playoffs

Expected /source version:
external-espn-schedule-v29-playoff-bracket-image

Notes:
- the image uses Pillow and the fonts already included in the project if assets/fonts exists
- if fonts are missing, it falls back to system/default fonts
- the layout is dynamic and adapts to the playoff matches available at the time of request
