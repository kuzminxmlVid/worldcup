Patch: team search fallback fix

Replace these files:
- main.py
- db.py

What changed:
- search no longer depends only on pending_inputs or ForceReply
- after pressing Поиск команды, if the next text is not caught as pending input, the bot still treats it as a team search
- any normal free text like Франция or france is now searched as a team name instead of returning “Не понял команду”
- existing prediction/note logic stays before fallback and should keep working

Test:
1. /start
2. Поиск команды
3. Франция
4. france
5. Португалия
