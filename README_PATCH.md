Patch: fix prediction/note + polished match card

Replace these files:
- main.py
- match_card.py

Also keep these font files in the repo:
- assets/fonts/DejaVuSans.ttf
- assets/fonts/DejaVuSans-Bold.ttf

Fixes:
- prediction and note now save correctly
- the pending input is stored under the real Telegram user id
- match card is redesigned closer to the premium reference
- rectangular flags
- no emoji inside the generated image

Prediction and note remain in the separate text post.
The match image contains only match data.
