# Preparazione e pubblicazione di H3-documentary

La cartella è predisposta come repository indipendente. Il nome del repository remoto previsto è **H3-documentary**. Nessuna credenziale o destinazione GitHub personale è incorporata.

Per il primo push, crea su GitHub un repository vuoto chiamato `H3-documentary`, senza inizializzare un secondo README, e copia il suo URL. Dalla cartella del progetto:

```powershell
git remote add origin URL-COPIATO-DA-GITHUB
git push -u origin main
```

Se esiste già un remote `origin`, controlla `git remote -v` e usa `git remote set-url origin URL-COPIATO-DA-GITHUB` solo se vuoi cambiarlo. Non serve forzare il push. L'eventuale autenticazione GitHub è gestita da Git sul tuo PC.

Chi clona il progetto apre INSTALLA.bat e START.bat; STOP.bat chiude il server locale prima dei test. AVVIA.bat resta un alias compatibile per l'avvio. Chi scarica lo ZIP deve prima estrarlo. I modelli LLM restano sul server che ogni utente configura; voce italiana, Python e librerie sono preparati automaticamente.

## Creare un nuovo ZIP sorgente

Dopo aver salvato le modifiche in un commit:

```powershell
.\.venv\Scripts\python.exe scripts/package_release.py
```

Il pacchetto viene generato esclusivamente dal commit corrente, con cartella radice `H3-documentary/`, e salvato in `dist/`. Il manifest affiancato contiene commit e SHA-256. Le modifiche non committate non finiscono nello ZIP.

Non aggiungere a Git `data/`, ambienti, cache, registrazioni personali, pesi, video o file `.env`. `.gitignore` li esclude. La suite in `.github/workflows/tests.yml` verifica automaticamente app e distribuzione su Windows dopo un push; non richiede chiavi o modelli.

Il primo commit della distribuzione può usare l'identità tecnica «H3-documentary packaging» se sul PC non è configurato un autore Git. È un'identità di build, non l'identità GitHub dell'utente. Configura la tua normale identità per i commit successivi.
