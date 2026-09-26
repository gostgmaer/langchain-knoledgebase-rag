#!/bin/bash
# Loads (up) or removes (down) the bundled retrieval-evaluation corpus in the local dev workspace
# (eval/corpus, labelled by eval/retrieval_eval_set.json). Needs the local stack (docs/LOCAL_SETUP.md).
#   scripts/eval_corpus.sh up      upload the corpus and wait for ingestion
#   scripts/eval_corpus.sh down    delete it again
# Then:  docker compose exec api sh -c "cd /app && PYTHONPATH=. python scripts/evaluate_retrieval.py eval/retrieval_eval_set.json --tenant-id <tenant>
GW=http://localhost:3301; RAG=http://localhost:8088/api/v1; O="Origin: http://localhost:3000"
EMAIL=${E2E_ADMIN_EMAIL:-super-admin@example.com}; PW=${E2E_ADMIN_PASSWORD:-'ChangeMe@Local123!'}
DIR="$(cd "$(dirname "$0")/.." && pwd)/eval/corpus"
J(){ python -c "import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    print(''); sys.exit()
$1"; }

TOK=""
for _ in 1 2 3; do
  TOK=$(curl -s -X POST $GW/api/auth/login -H 'Content-Type: application/json' -H "$O" -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}" | J "print(d['data']['accessToken'])")
  [ -n "$TOK" ] && break; sleep 65
done
[ -z "$TOK" ] && { echo "login failed"; exit 1; }
A="Authorization: Bearer $TOK"
echo "tenant: $(curl -s $GW/api/auth/me -H "$A" -H "$O" | J "print(d['data'].get('tenantId',''))")"

case "$1" in
  up)
    for f in "$DIR"/*.txt; do
      name=$(basename "$f")
      job=$(curl -s -m 60 -X POST $RAG/documents -H "$A" -F "file=@$(cygpath -m "$f" 2>/dev/null || echo "$f");type=text/plain" | J "print((d.get('data') or {}).get('upload_job_id',''))" | tr -d '\r')
      [ -z "$job" ] && { echo "  $name: upload failed"; continue; }
      s=""; for _ in $(seq 1 40); do s=$(curl -s $RAG/upload-jobs/$job -H "$A" | J "print((d.get('data') or {}).get('status',''))" | tr -d '\r'); case "$s" in SUCCEEDED|FAILED) break;; esac; sleep 3; done
      echo "  $name: $s"
    done ;;
  down)
    ids=$(curl -s "$RAG/documents?limit=200" -H "$A" | J "print(' '.join(x['id'] for x in (d.get('data') or {}).get('documents',[]) if x['file_name'].startswith('eval_corp_')))" | tr -d '\r')
    for id in $ids; do echo "  delete $id -> $(curl -s -o /dev/null -w '%{http_code}' -X DELETE $RAG/documents/$id -H "$A")"; done ;;
  *) echo "usage: $0 up|down"; exit 2 ;;
esac
