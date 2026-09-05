"""Measure edited narration and retain all unchanged audio in a candidate project."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description='Aggiorna soltanto le scene narrate modificate.')
    parser.add_argument('--battle', '--document', dest='battle', required=True)
    parser.add_argument('--scenes', default='', help='ID separati da virgole; vuoto conserva tutta la voce')
    args = parser.parse_args()
    from engine.common import ROOT, read_json
    from engine.revision_narration import revise_narration
    path = (ROOT / args.battle).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Il documento deve trovarsi nello spazio di lavoro candidato.')
    pack = read_json(path)
    selected = [part.strip() for part in args.scenes.split(',') if part.strip()]
    revise_narration(pack, selected)


if __name__ == '__main__':
    main()
