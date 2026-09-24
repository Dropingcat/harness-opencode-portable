# GitHub Access — `Dropingcat/harness-opencode-portable`

Инструкция по подключению внешнего репозитория GitHub и безопасному хранению токена.

## 1. Внешний репозиторий (remote)

Репозиторий подключён к локальному git как remote с именем `origin`:

```bash
git remote -v
# origin  https://github.com/Dropingcat/harness-opencode-portable.git (fetch)
# origin  https://github.com/Dropingcat/harness-opencode-portable.git (push)
```

Рабочие команды:

```bash
git fetch origin          # забрать изменения из удалённого репозитория
git push origin <branch>  # отправить изменения (нужен валидный токен)
```

## 2. Безопасный токен (переменная окружения)

Токен хранится в файле **`.github-token.env`** в виде переменной окружения:

```bash
export GITHUB_TOKEN="ghp_************"   # значение смаскировано в README
```

Файл `.github-token.env` добавлен в `.gitignore` — он **никогда не должен попадать в коммиты**.

### Использование

```bash
# Linux / macOS / Git Bash
source ./.github-token.env
echo "$GITHUB_TOKEN"        # переменная доступна в текущей сессии

# PowerShell (Windows)
Get-Content .\.github-token.env | ForEach-Object { Invoke-Expression $_ }
$env:GITHUB_TOKEN
```

### Передача токена git без записи в URL

Не встраивайте токен в URL remote — он остаётся в `.git/config` и виден в `git remote -v`.
Вместо этого используйте credential helper, читающий переменную окружения:

```bash
git config --local credential.helper '!f() { echo "username=x-access-token"; echo "password=$GITHUB_TOKEN"; }; f'
```

После этого `git fetch` / `git push` будут автоматически подставлять токен из `GITHUB_TOKEN`.

## 2b. Настройка credential helper (однократно, локально для репозитория)

Чтобы git автоматически подставлял токен из переменной окружения при fetch/push
(токен при этом **не** попадает в URL и в `.git/config`):

```bash
source ./.github-token.env
git config --local credential.helper '!f() { echo "username=x-access-token"; echo "password=$GITHUB_TOKEN"; }; f'
```

## 3. ⚠️ Текущий статус проверки (важно)

На момент настройки выполнена проверка подключения:

| Проверка | Результат |
|---|---|
| `git ls-remote origin` (по токену) | ❌ `401 Authentication failed` |
| `GET https://api.github.com/user` с Bearer-токеном | ❌ `401 Bad credentials` |
| `GET https://api.github.com/repos/Dropingcat/harness-opencode-portable` (без токена) | ❌ `404 Not Found` |

**Выводы:**

1. Предоставленный токен **не является действующим** (просрочен, отозван или введён с ошибкой).
2. Репозиторий `Dropingcat/harness-opencode-portable` **недоступен как публичный** — он либо приватный, либо ещё не создан, либо имя владельца/репозитория указано неточно.

Remote настроен корректно; для полноценной работы (`fetch`/`push`) необходимо заменить токен на валидный Personal Access Token.

## 4. Как получить рабочий токен

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens**.
2. Создайте *Fine-grained token* (или classic) со scope:
   - Fine-grained: доступ к репозиторию `harness-opencode-portable`, права **Contents: Read and Write**;
   - Classic: scope `repo`.
3. Запишите новый токен в `.github-token.env` (файл в `.gitignore`).
4. Проверьте доступ:

```bash
source ./.github-token.env
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user   # должно быть 200
git ls-remote --heads origin                                             # должны перечислиться ветки
```

## 5. Правила безопасности

- ❌ Не коммитьте `.github-token.env` и не вставляйте токен в код, README, URL remote или CI-логи.
- ❌ Не выводите токен в open issue / PR.
- ✅ Если токен мог засветиться — немедленно отзовите его в GitHub Settings и перевыпустите.
- ✅ Регулярно проверяйте срок действия токена и отзывайте неиспользуемые.
- ✅ Держите файл только с правами на чтение владельцем: `chmod 600 .github-token.env`.
