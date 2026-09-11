# POPLA Focus Desk

플래너와 포모도로를 결합한 Flet 데스크톱 앱입니다
작업 목록은 `saves/plan.json`에 저장됩니다

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## 빌드

Flet은 대상 운영체제에서 각각 빌드해야 합니다

```bash
flet build macos
flet build windows
flet build linux
```

테스트는 안해봐서 될지 모름

## 테스트

```bash
python3 -m unittest discover -s tests -v
```
