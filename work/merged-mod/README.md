# Объединённый мод Victoria 3 — рабочая сборка

Эта папка содержит результаты поэтапного объединения Morgenröte – Dawn of Flavor, Better Politics Mod и Tech & Res.

## Источники
- Morgenröte: https://github.com/Morgenrote-Team/Morgenroete-Beta (ветка Main)
- Better Politics Mod: https://github.com/Better-Politics-Mod/Better-Politics-Mod-Vic-3 (папка better-politics-mod, ветка main; вариант lite не используется)
- Tech & Res: https://github.com/mattia2110/tech-and-res (ветка main)

## Правила объединения
- При совпадении путей не перезаписывать файлы автоматически.
- Объединять определения и блоки по смыслу, избегать повторных одноимённых групп.
- Сохранять функциональные файлы и уже существующие русские переводы.
- Отдельно проверять зависимости, порядок загрузки, игровые версии и синтаксис Paradox.

## Выполнено
- `common/achievement_groups.txt`: взята полная версия Morgenröte; добавлена отдельная группа достижений Better Politics Mod `bpm_achievements`. Повторяющиеся определения `easy_group`, `medium_group`, `hard_group` и `very_hard_group` из BPM не добавлялись, поскольку они уже представлены в более полной версии Morgenröte.

## Важно
Это промежуточная рабочая сборка. Полный перенос всех файлов, ресурсов и локализаций ещё не завершён. Игровая проверка не выполнена.
