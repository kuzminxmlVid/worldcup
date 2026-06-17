Patch: prediction/note pending input fix

Replace only this file:
- main.py

What changed:
- prediction and note are now stored under the real Telegram user id
- replies use ForceReply, so Telegram clearly ties the next user message to the prompt
- if the database pending state is not found, bot can recover the action from the reply marker
- added logging for pending input set/found/recovered
- Show/Clear buttons now use the real callback user id

After redeploy:
1. Press /start
2. Press /next
3. Press Сделать прогноз
4. Reply to the bot prompt or just type the forecast
5. Press Добавить заметку
6. Reply to the bot prompt or just type the note

If it still fails, send logs containing lines with:
- Pending input set
- Pending input found in DB
- Pending input recovered from reply marker
- No pending input found
