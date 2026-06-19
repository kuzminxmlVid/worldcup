Patch: open any match card

Replace these files:
- main.py
- keyboards.py

What changed:
- search results now include a button for every found match
- today/tomorrow/7-days lists also include buttons for every match in the list
- pressing a match button opens the same match card and the personal post with prediction/note buttons
- this allows notes and predictions for any match, not only the next match
- fixed the user id path for inline “Следующий” so the personal prediction/note post belongs to the real user

Test:
1. /start
2. Поиск команды
3. France or Франция
4. Press any match button
5. Press Добавить заметку or Сделать прогноз
