Причина проблемы: на Railway не находился системный шрифт, поэтому Pillow падал в ImageFont.load_default(), и весь текст становился крошечным.

Что делать:
- замени match_card.py
- добавь папку assets/fonts с двумя файлами шрифтов


Patch with updated clean card.

Replace these files:
- db.py
- formatting.py
- keyboards.py
- main.py
- match_card.py

What changed:
- the match card is redesigned in a cleaner premium style
- flags are rectangular
- the card contains only teams, flags, date, time, group and stadium
- prediction and note stay in a separate text post
- note limit is 1500 characters
- unsupported emoji inside the image were removed
- after you save a prediction or note, the separate text post updates in place
