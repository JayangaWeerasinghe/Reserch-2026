# Voice NLP trained artifacts

Both real files are currently present (approximately 171 KiB and 39 KiB):

- `paddyguard_best_classifier.pkl`: `MODEL_PATH=models/paddyguard_best_classifier.pkl`
- `paddyguard_tfidf.pkl`: `TFIDF_PATH=models/paddyguard_tfidf.pkl`

Paths resolve relative to the working directory (`/app` in Docker). The Docker
context includes both artifacts. Root `.gitignore` explicitly permits these two
files while other model formats remain ignored. Ordinary Git is appropriate for
these small files; Git LFS is unnecessary and no LFS checkout is required.

Supply the authentic trained pair before deploying any checkout that lacks them.
Never create fake placeholders or retrain substitute models to make deployment
pass. Load only trusted pickle/joblib files, which can execute code. Validate
compatibility with the pinned scikit-learn 1.5.2 runtime. Presence and size have
been checked here; loading and prediction require the provisioned runtime tests.
