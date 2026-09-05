"""Geographic provenance travels with the pack, sources, credits and public description."""
def attach_credits(document,report):
    document['boundary_report']=report
    document.setdefault('metadata',{})['boundary_usage']=report['usage']
    lines=['Provenienza delle aree geografiche: ricostruzioni, archivi datati e dati mancanti sono distinti in legenda.']
    for s in report.get('sources',[]):
        lines.append(f"{s['citation']} {s['url']} — {s['license']}: {s['license_url']}. Estratti selezionati per identità e periodo, riproiettati e colorati; geometrie originali in assets/boundaries. SHA-256 archivio: {s['sha256']}.")
    document['extra_credits']=(document.get('extra_credits','Base fisica moderna: Natural Earth (pubblico dominio), rilievo Mapzen / Copernicus; attribuzioni in assets/geography/terrain-attribution.md.')+'\n'+'\n'.join(lines)).strip()
    document['territorial_note']='\n'.join(r['label']+': '+' '.join(r['notes']) for r in report.get('layers',[]))
    if any(s['license']=='CC-BY-NC-SA-4.0' for s in report.get('sources',[])):
        document['video_license']='Le mappe derivate da CShapes sono distribuite con CC BY-NC-SA 4.0: uso non commerciale, attribuzione e condivisione alle stesse condizioni. https://creativecommons.org/licenses/by-nc-sa/4.0/ Gli altri materiali conservano le licenze indicate nei crediti.'
