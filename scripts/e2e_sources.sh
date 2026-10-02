#!/bin/bash
# End-to-end check of external knowledge sources against the local stack (docs/LOCAL_SETUP.md).
#
# It serves a tiny documentation website from a throwaway container on the stack's network (robots.txt, sitemap,
# a page that must never be crawled), connects it as a "web" source, and exercises the whole lifecycle through the
# real API and worker: create paused -> test -> preview -> sync -> answer with a citation -> change/remove pages ->
# incremental sync -> scheduling -> webhook -> pause/resume -> credentials never returned -> tenant isolation.
#
# Needs the full local stack, the worker, and CONNECTOR_CREDENTIAL_KEYS + CONNECTOR_ALLOW_PRIVATE_HOSTS=true in
# .env (the test site lives on the private compose network). Removes everything it creates.
GW=http://localhost:3301; RAG=http://localhost:8088/api/v1; O="Origin: http://localhost:3000"
ADMIN_EMAIL=${E2E_ADMIN_EMAIL:-super-admin@example.com}; ADMIN_PW=${E2E_ADMIN_PASSWORD:-'ChangeMe@Local123!'}
NET=${E2E_NETWORK:-langchain-knoledgebase-rag_ai-platform}; IMAGE=${E2E_IMAGE:-langchain-knoledgebase-rag-api}
TS=$(date +%s); NAME="e2e-site-$TS"
SITE=$(mktemp -d); SITE_W=$(cygpath -m "$SITE" 2>/dev/null || echo "$SITE")
pass=0; fail=0
ok(){ printf "  PASS  %s\n" "$1"; pass=$((pass+1)); }
bad(){ printf "  FAIL  %s\n" "$1"; fail=$((fail+1)); }
chk(){ [ "$2" = "$3" ] && ok "$1 ($2)" || bad "$1: expected $3, got $2"; }
J(){ python -c "import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    print(''); sys.exit()
$1"; }
PSQL(){ docker exec langchain-knoledgebase-rag-postgres-1 psql -U my_db_user -d my_database_name -tAc "$1" 2>/dev/null | tr -d '\r'; }

cleanup(){ [ -n "$SRC" ] && curl -s -o /dev/null -X DELETE $RAG/knowledge-sources/$SRC -H "Authorization: Bearer $ATOK"; docker rm -f "$NAME" >/dev/null 2>&1; rm -rf "$SITE"; }
trap cleanup EXIT

login(){ for _ in 1 2 3; do r=$(curl -s -X POST $GW/api/auth/login -H 'Content-Type: application/json' -H "$O" -d "{\"email\":\"$1\",\"password\":\"$2\"}" | J "print(d['data']['accessToken'])"); [ -n "$r" ] && { echo "$r"; return; }; sleep 65; done; }
ATOK=$(login $ADMIN_EMAIL "$ADMIN_PW"); [ ${#ATOK} -gt 100 ] || { echo "login failed"; exit 1; }
A="Authorization: Bearer $ATOK"
api(){ curl -s -m 180 -H "$A" -H 'Content-Type: application/json' "$@"; }
S=$RAG/knowledge-sources

# ---------------------------------------------------------------- the site
mkdir -p "$SITE/docs" "$SITE/private" "$SITE/admin"
printf 'User-agent: *\nDisallow: /private/\n' > "$SITE/robots.txt"
cat > "$SITE/index.html" <<'HTML'
<html><head><title>Orion Docs</title></head><body><nav><a href="/">Home</a><a href="/pricing">Pricing</a></nav>
<div class="cookie-banner">We use cookies <button>OK</button></div>
<main><h1>Orion Documentation</h1><p>Orion is a messaging gateway used by internal services to exchange events reliably between teams. Start with the guides below to learn about limits and authentication.</p>
<ul><li><a href="/docs/limits.html">Limits</a></li><li><a href="/docs/auth.html">Authentication</a></li><li><a href="/private/secret.html">Private</a></li><li><a href="/admin/panel.html">Admin</a></li></ul></main><footer>Copyright junk</footer></body></html>
HTML
cat > "$SITE/docs/limits.html" <<'HTML'
<html><head><title>Limits - Orion Docs</title></head><body><main><h1>Orion limits</h1><p>The Orion gateway allows 600 requests per minute per API key with a burst allowance of 50 requests. Above that it answers HTTP 429 with a Retry-After header telling the client how long to wait.</p></main></body></html>
HTML
cat > "$SITE/docs/auth.html" <<'HTML'
<html><head><title>Authentication - Orion Docs</title></head><body><main><h1>Orion authentication</h1><p>Orion access tokens expire after 45 minutes. Clients must refresh the token before it expires by calling the token endpoint with their refresh credential.</p></main></body></html>
HTML
printf '<html><head><title>Private</title></head><body><main><h1>Private</h1><p>The Orion admin password is hunter2 and must never be shared outside the platform team.</p></main></body></html>' > "$SITE/private/secret.html"
printf '<html><head><title>Admin</title></head><body><main><h1>Admin</h1><p>The admin panel key is ZEBRA-9911, confidential material for operators only.</p></main></body></html>' > "$SITE/admin/panel.html"
MSYS_NO_PATHCONV=1 docker run -d --name "$NAME" --network "$NET" -v "$SITE_W:/site" "$IMAGE" python -m http.server 8099 --directory /site >/dev/null 2>&1
sleep 4
BASE="http://$NAME:8099"

wait_run(){ local s=""; for _ in $(seq 1 60); do s=$(api $S/$SRC/runs/$1 | J "print(d['data']['status'])"); case "$s" in succeeded|partial|failed|cancelled) break;; esac; sleep 3; done; echo "$s"; }
run_counts(){ api $S/$SRC/runs/$1 | J "x=d['data']; print(x['documents_discovered'],x['documents_created'],x['documents_updated'],x['documents_deleted'],x['documents_skipped'],x['documents_failed'])"; }
start_sync(){ api -X POST $S/$SRC/sync -d "${1:-{\}}" | J "print(d['data']['id'])"; }

echo "== 1. Catalogue and validation"
api $S/types | J "print(','.join(sorted(t['type'] for t in d['data']['types'] if t['available'])))" | grep -q "confluence,microsoft_teams,onedrive,sharepoint,web,wikipedia" && ok "six connectors available, the rest listed as planned" || bad "connector catalogue"
chk "invalid configuration is rejected" "$(api -o /dev/null -w '%{http_code}' -X POST $S -d '{"name":"x","type":"web","configuration":{"seed_urls":["ftp://x"]}}')" 422
chk "unknown type is rejected" "$(api -o /dev/null -w '%{http_code}' -X POST $S -d '{"name":"x","type":"myspace","configuration":{}}')" 422
chk "an unavailable (planned) type is rejected" "$(api -o /dev/null -w '%{http_code}' -X POST $S -d '{"name":"x","type":"notion","configuration":{}}')" 422
api -X POST $S/test -d '{"type":"web","configuration":{"seed_urls":["'$BASE'/"]}}' | J "print(d['data']['ok'])" | grep -q True && ok "unsaved configuration passes a connection test" || bad "unsaved test"
chk "SSRF: a source may not point at cloud metadata" "$(api -X POST $S/test -d '{"type":"web","configuration":{"seed_urls":["http://169.254.169.254/latest/meta-data/"]}}' | J "print(d['data']['ok'])")" False

echo; echo "== 2. Create (paused: nothing ingested yet), preview, test"
CR=$(api -X POST $S -d '{"name":"'$NAME'","type":"web","description":"e2e","configuration":{"seed_urls":["'$BASE'/"],"max_depth":2,"max_pages":20,"request_interval_seconds":0.1,"exclude_patterns":["'$NAME':8099/admin/*"]},"sync_mode":"manual"}')
SRC=$(echo "$CR" | J "print(d['data']['id'])")
[ -n "$SRC" ] && ok "source created ($SRC)" || { bad "create failed: $CR"; exit 1; }
chk "a new source is paused" "$(api $S/$SRC | J "print(d['data']['status'])")" paused
chk "nothing was ingested before confirmation" "$(PSQL "select count(*) from documents where source_id='$SRC'")" 0
chk "duplicate name is refused" "$(api -o /dev/null -w '%{http_code}' -X POST $S -d '{"name":"'$NAME'","type":"web","configuration":{"seed_urls":["'$BASE'/"]}}')" 409
api -X POST "$S/$SRC/preview?limit=10" | J "t=sorted(i['title'] for i in d['data']['items']); print('yes' if t==['Authentication - Orion Docs','Limits - Orion Docs','Orion Docs'] else t)" | grep -q yes && ok "preview lists what would be ingested (robots and excluded paths left out)" || bad "preview"
chk "preview stored nothing" "$(PSQL "select count(*) from documents where source_id='$SRC'")" 0
api -X POST $S/$SRC/test-connection | J "print(d['data']['ok'])" | grep -q True && ok "saved connection test passes" || bad "saved test"

echo; echo "== 3. First sync"
R1=$(start_sync '{"activate":true}'); chk "sync finishes" "$(wait_run $R1)" succeeded
chk "3 pages created, nothing else" "$(run_counts $R1)" "3 3 0 0 0 0"
chk "source is now connected" "$(api $S/$SRC | J "print(d['data']['status'])")" active
chk "robots.txt-disallowed and excluded pages were never indexed" "$(PSQL "select count(*) from documents where source_id='$SRC' and (canonical_url like '%/private/%' or canonical_url like '%/admin/%')")" 0
chk "each page carries source provenance" "$(PSQL "select count(*) from documents where source_id='$SRC' and source_type='web' and external_id is not null and canonical_url is not null and sync_id is not null and external_updated_at is not null")" 3
chk "chunk metadata carries source, url, version and sync" "$(PSQL "select count(*) from document_chunks c join documents d on d.id=c.document_id where d.source_id='$SRC' and c.chunk_index>=0 and (c.metadata->>'source_id')='$SRC' and (c.metadata->>'canonical_url') is not null and (c.metadata->>'sync_id') is not null")" 3

echo; echo "== 4. Ask a question; citations trace to the original page"
CID=$(python -c "import uuid;print(uuid.uuid4())")
CR=$(api -X POST $RAG/chat -d '{"message":"What is the Orion API rate limit per key?","conversation_id":"'$CID'","stream":false}')
echo "$CR" | grep -q "600" && ok "answer uses the crawled page" || bad "answer did not contain 600: $(echo "$CR" | head -c 200)"
echo "$CR" | J "c=(d['data'] or {}).get('citations') or []; print('yes' if any(x['source_type']=='web' and (x['url'] or '').endswith('/docs/limits.html') and x['source_name']=='$NAME' and x['updated_at'] for x in c) else c[:2])" | grep -q yes && ok "citation names the source, type, original URL and update time" || bad "citation source fields"
api "$RAG/conversations/$CID/messages" | J "m=[x for x in d['data']['messages'] if x['role']=='ASSISTANT'][-1]['sources']; print('yes' if m and m[0]['url'] and m[0]['source_type']=='web' and 'document_id' not in m[0] and 'score' not in m[0] else m)" | grep -q yes && ok "customer history shows the source without internal ids or scores" || bad "history sources"
api -X POST $RAG/search -d '{"query":"Orion admin password hunter2","limit":8}' | J "print(any('hunter2' in r['content'] for r in d['data']['results']))" | grep -q False && ok "the disallowed private page is not retrievable" || bad "private page leaked"
api -X POST $RAG/search -d '{"query":"requests per minute burst","limit":8,"source_ids":["'$SRC'"]}' | J "r=d['data']['results']; print('yes' if r else 'no')" | grep -q yes && ok "search can be limited to this source" || bad "source_ids filter"
api -X POST $RAG/search -d '{"query":"requests per minute burst","limit":8,"sources":["confluence"]}' | J "print(any('600 requests' in r['content'] for r in d['data']['results']))" | grep -q False && ok "search limited to another source type never returns this source's pages" || bad "sources filter"
api "$RAG/retrieval-logs?limit=1&conversation_id=$CID" | J "print(d['data']['retrievals'][0]['retrieval_id'])" > "$SITE/rid" ; RID=$(tr -d '\r' < "$SITE/rid")
api "$RAG/retrieval-logs/$RID" | J "r=[x for x in d['data']['results'] if x['selected_for_context']]; print('yes' if r and r[0]['source_type']=='web' and r[0]['source_name']=='$NAME' and r[0]['canonical_url'] else r[:1])" | grep -q yes && ok "retrieval log traces a chunk to its source and page" || bad "retrieval log source"

echo; echo "== 5. Incremental sync: nothing fetched twice, changes applied, removals archived"
R2=$(start_sync); chk "unchanged site: sync finishes" "$(wait_run $R2)" succeeded
chk "unchanged site: nothing created/updated/removed (all skipped)" "$(run_counts $R2)" "3 0 0 0 3 0"
sed -i 's/expire after 45 minutes/expire after 60 minutes/' "$SITE/docs/auth.html"; mv "$SITE/docs/limits.html" "$SITE/docs/limits.html.off"; sleep 2
R3=$(start_sync); chk "changed site: sync finishes" "$(wait_run $R3)" succeeded
chk "one page updated, one removed, one unchanged" "$(run_counts $R3)" "2 0 1 1 1 0"
chk "the old version is kept, the new one is current" "$(PSQL "select string_agg(is_current::text, ',' order by created_at) from documents where source_id='$SRC' and title like 'Authentication%'")" "false,true"
chk "the removed page is archived, not deleted" "$(PSQL "select status from documents where source_id='$SRC' and title like 'Limits%' and is_current")" ARCHIVED
api -X POST $RAG/search -d '{"query":"600 requests per minute burst Retry-After","limit":8,"source_ids":["'$SRC'"]}' | J "print(any('600 requests' in r['content'] for r in d['data']['results']))" | grep -q False && ok "the removed page is no longer retrievable" || bad "removed page still retrievable"
api -X POST $RAG/search -d '{"query":"Orion access tokens expire after","limit":8,"source_ids":["'$SRC'"]}' | J "t=' '.join(r['content'] for r in d['data']['results']); print('60 minutes' in t and '45 minutes' not in t)" | grep -q True && ok "only the new version of a changed page is served" || bad "version served"
mv "$SITE/docs/limits.html.off" "$SITE/docs/limits.html"; R4=$(start_sync); wait_run $R4 >/dev/null
chk "a page that returns is restored" "$(PSQL "select status from documents where source_id='$SRC' and title like 'Limits%' and is_current")" READY

echo; echo "== 6. Health, history, summary, audit"
api $S/$SRC/health | J "x=d['data']; print('yes' if x['connection']=='healthy' and x['authentication']=='valid' and x['documents_indexed']==3 and x['documents_failed']==0 else x)" | grep -q yes && ok "health: healthy, 3 indexed, 0 failed" || bad "health"
chk "sync history has every run" "$(api $S/$SRC/runs | J "print(d['data']['total'])")" 4
api $S/summary | J "x=d['data']; print('yes' if x['total_sources']>=1 and x['total_documents']>=3 and x['total_chunks']>=3 else x)" | grep -q yes && ok "summary counts sources, documents and chunks" || bad "summary"
api "$RAG/observability/audit?limit=60" | J "a={e['action'] for e in d['data']['events']}; need={'source.created','source.sync_started','source.sync_completed','source.documents_indexed','source.documents_removed'}; print('yes' if need<=a else need-a)" | grep -q yes && ok "audit trail covers create, sync start/complete, indexed and removed" || bad "audit actions"

echo; echo "== 7. Concurrency, schedule, webhook, pause/resume"
R5=$(start_sync); C2=$(api -o /dev/null -w '%{http_code}' -X POST $S/$SRC/sync -d '{}'); chk "a second sync while one runs is refused" "$C2" 409; wait_run $R5 >/dev/null
chk "reject an unsupported schedule" "$(api -o /dev/null -w '%{http_code}' -X PATCH $S/$SRC -d '{"sync_mode":"scheduled","sync_interval_minutes":7}')" 422
api -X PATCH $S/$SRC -d '{"sync_mode":"scheduled","sync_interval_minutes":15}' | J "print(d['data']['sync_mode'])" | grep -q scheduled && ok "schedule set to every 15 minutes" || bad "schedule"
PSQL "update knowledge_sources set next_sync_at = now() - interval '1 minute' where id='$SRC'" >/dev/null
T=""; for _ in $(seq 1 14); do T=$(PSQL "select trigger from source_sync_runs where source_id='$SRC' order by created_at desc limit 1"); [ "$T" = schedule ] && break; sleep 6; done
chk "the scheduler queues a due sync" "$T" schedule
W=$(api -X PATCH $S/$SRC -d '{"sync_mode":"webhook"}' | J "print(d['data'].get('webhook_secret') or '')")
[ ${#W} -gt 20 ] && ok "webhook secret is issued once" || bad "webhook secret"
chk "the secret is not shown again" "$(api $S/$SRC | J "print(d['data']['webhook_secret'])")" None
sleep 8
chk "webhook with a wrong secret" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/webhooks/sources/$SRC -H 'X-Webhook-Secret: nope')" 404
chk "webhook without a secret" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/webhooks/sources/$SRC)" 404
chk "webhook with the right secret queues a sync" "$(curl -s -X POST $RAG/webhooks/sources/$SRC -H "X-Webhook-Secret: $W" | J "print(d['status'])")" queued
sleep 10
chk "pause" "$(api -X POST $S/$SRC/pause | J "print(d['data']['status'])")" paused
chk "a paused source ignores webhooks" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/webhooks/sources/$SRC -H "X-Webhook-Secret: $W")" 404
chk "resume" "$(api -X POST $S/$SRC/resume | J "print(d['data']['status'])")" active

echo; echo "== 8. Credentials are write-only and isolated"
api -X POST $S -d '{"name":"'$NAME'-conf","type":"confluence","configuration":{"base_url":"http://'$NAME':8099/wiki","spaces":["ENG"]},"credentials":{"email":"a@b.c","api_token":"S3CR3T-TOKEN-VALUE"},"sync_mode":"manual"}' > "$SITE/conf.json"
CONF=$(J "print(d['data']['id'])" < "$SITE/conf.json")
grep -q "S3CR3T-TOKEN-VALUE" "$SITE/conf.json" && bad "secret returned by create" || ok "create response contains no secret"
api $S/$CONF | grep -q "S3CR3T" && bad "secret returned by get" || ok "get response contains no secret"
api $S | grep -q "S3CR3T" && bad "secret returned by list" || ok "list response contains no secret"
chk "the ciphertext does not contain the token" "$(PSQL "select position('S3CR3T' in ciphertext)=0 from source_credentials where source_id='$CONF'")" t
docker compose logs api worker --tail 400 2>/dev/null | grep -q "S3CR3T-TOKEN-VALUE" && bad "secret found in service logs" || ok "the secret appears in no service log"
chk "revoke destroys the stored secret" "$(api -X DELETE $S/$CONF/credentials >/dev/null; PSQL "select ciphertext is null from source_credentials where source_id='$CONF'")" t
api -X DELETE $S/$CONF >/dev/null
OTHER=$(python -c "import uuid;print(uuid.uuid4())")
chk "another tenant cannot read the source" "$(curl -s -o /dev/null -w '%{http_code}' $S/$SRC -H "$A" -H "X-Tenant-ID: $OTHER")" 404
chk "another tenant sees none of it in the list" "$(curl -s $S -H "$A" -H "X-Tenant-ID: $OTHER" | J "print(d['data']['total'])")" 0
chk "another tenant cannot trigger a sync" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $S/$SRC/sync -H "$A" -H "X-Tenant-ID: $OTHER" -H 'Content-Type: application/json' -d '{}')" 404
chk "no token is refused" "$(curl -s -o /dev/null -w '%{http_code}' $S)" 401

echo; echo "== 9. Delete: documents are archived, credentials gone"
chk "delete the source" "$(api -o /dev/null -w '%{http_code}' -X DELETE $S/$SRC)" 200
chk "its documents are archived, not deleted" "$(PSQL "select count(*) from documents where source_id='$SRC' and status='ARCHIVED'")" "$(PSQL "select count(*) from documents where source_id='$SRC'")"
chk "and it is gone from the list" "$(api $S | J "print(any(s['id']=='$SRC' for s in d['data']['sources']))")" False
SRC=""

echo; echo "RESULT: $pass passed, $fail failed"
[ $fail -eq 0 ]
