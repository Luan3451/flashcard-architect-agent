"""Interactive terminal interface; no browser server or exposed endpoints."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

try:
    from .deck_maintenance import AnkiClient, build_plan, apply_plan, write_json
except ImportError:
    from deck_maintenance import AnkiClient, build_plan, apply_plan, write_json


def maintain():
    client = AnkiClient()
    decks = client('deckNames')
    for index, deck in enumerate(decks, 1):
        print(f'{index}: {deck}')
    index = int(input('Número do deck (inclui subdecks): '))
    if not 1 <= index <= len(decks):
        raise ValueError('Deck inválido')
    actions = ['style', 'highlight', 'remove-topic', 'remove-broken-audio']
    print('1 Estilizar | 2 Destacar termos | 3 Remover por tema | 4 Remover com áudio inválido')
    choice = int(input('Ação: '))
    if not 1 <= choice <= len(actions):
        raise ValueError('Ação inválida')
    action = actions[choice - 1]
    terms = input('Termos separados por vírgula: ').split(',') if action in {'highlight', 'remove-topic'} else []
    theme = input('Tema studio/atlas/paper/contrast [paper]: ').strip() or 'paper' if action == 'style' else 'paper'
    spec = {'decks': [decks[index - 1]], 'action': action, 'terms': terms, 'theme': theme}
    plan = build_plan(client, spec)
    folder = Path('maintenance_plans')
    folder.mkdir(exist_ok=True)
    path = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
    write_json(path, plan)
    print(json.dumps({k: plan[k] for k in ('matches', 'blocked', 'field_updates', 'model_updates', 'affected_cards', 'audio')}, ensure_ascii=False, indent=2))
    print(f'Prévia salva em {path}. Leia antes de aplicar. Feche revisões/edições e não sincronize durante a operação.')
    print(f"Para aplicar, digite exatamente {plan['token']}; Enter cancela.")
    if input('Confirmação: ').strip() != plan['token']:
        print('Nenhuma alteração aplicada.')
        return
    root = Path(input('Pasta local de backup [backups]: ').strip() or 'backups').expanduser().resolve()
    print(f'Concluído. Backup: {apply_plan(client, plan, root, plan["token"])}')


def main():
    print('Flashcard Architect\n1 Criar cards\n2 Manter decks existentes (EXPERIMENTAL)\n3 Transcrever aula (EXPERIMENTAL)')
    choice = input('Opção: ').strip()
    try:
        if choice == '2':
            maintain()
        elif choice in {'1', '3'}:
            script = 'anki_generator.py' if choice == '1' else 'audio_experimental.py'
            args = ['--input', input('Arquivo de entrada: ').strip()]
            if choice == '3':
                args += ['--model-dir', input('Pasta local dos pesos faster-whisper: ').strip(),
                         '--output-dir', input('Nova pasta para transcrição: ').strip()]
            else:
                args += ['--output', input('Arquivo de saída .apkg: ').strip()]
            result = subprocess.run([sys.executable, str(Path(__file__).with_name(script)), *args], check=False)
            return result.returncode
        else:
            raise ValueError('Opção inválida')
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'Falha: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
