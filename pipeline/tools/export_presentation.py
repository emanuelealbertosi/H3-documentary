"""Standalone export using the bundled renderer and another project's asset root."""
import argparse,json,sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description='Esporta le scene approvate in una presentazione PDF, senza rigenerare il film.')
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--variant',choices=['compact','teaching'],default='compact')
    parser.add_argument('--narration',choices=['full','none'],default='full')
    args=parser.parse_args()
    from engine.presentation_pdf import export_presentation
    result=export_presentation(args.workspace,args.output,args.variant,args.narration,args.manifest)
    print(json.dumps({'presentation':result['output'],'pages':result['pages'],'sha256':result['sha256']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
