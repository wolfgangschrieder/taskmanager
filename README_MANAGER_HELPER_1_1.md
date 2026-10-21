# Manager Helper 1.1 — Windows preview

Run: download the feature/apex-ui2 branch ZIP, extract, close old app, then double-click start_ui2_windows.bat.

Data: %USERPROFILE%/.apex_task_control/apex.db (shared with the original version).
Backups: %USERPROFILE%/.apex_task_control/backups/.
Before an upgrade, close the app and make an extra manual copy of the database.

Features: Kanban boards, columns, tasks, deadlines, appearance settings, Telegram links, schedule, notebook autosave, and silent overdue dialogs.

Quality checks: isolated SQLite tests and a QML smoke test that creates one column and one task. CI also captures a screenshot artifact.

Known limitations: no Kanban drag-and-drop in the new QML UI yet; the silent alarm requires the app to be running and may not overlay unrelated Windows programs.
Do not run the old and new UI against the database at the same time.
If an earlier buggy build created duplicate empty columns, open the column menu, choose Delete empty column, and confirm. A column containing tasks is never deleted by this action.
