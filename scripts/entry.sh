#!/bin/zsh
# Finder launches a login-independent shell; support known macOS/user tool locations.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd -- "${0:A:h:h}" || exit 1
mode="$1"
shift
if [[ "$mode" != install && -x server/.venv/bin/python ]]; then
  interpreter="$PWD/server/.venv/bin/python"
else
  interpreter="$(command -v python3.14)"
fi
if [[ -z "$interpreter" ]]; then
  print '缺少 Python 3.14。请先按 docs/05-local-setup-and-trial.md 安装，再双击 Install.command。'
  result=1
elif [[ "$mode" == install ]]; then
  "$interpreter" scripts/install.py "$@"
  result=$?
else
  "$interpreter" scripts/local.py "$mode" "$@"
  result=$?
fi
if [[ -t 0 ]]; then
  read "?按回车关闭此窗口。"
fi
exit "$result"
