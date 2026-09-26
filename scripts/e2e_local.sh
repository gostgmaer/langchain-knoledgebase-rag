#!/bin/bash
# End-to-end API checks for the local RAG stack. Needs the whole stack running (docs/LOCAL_SETUP.md).
# Creates throwaway data (one user, one invitation, one uploaded document) in the local dev workspace.
# Override the admin login with E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD.
GW=http://localhost:3301; RAG=http://localhost:8088/api/v1; MP=http://localhost:8025/api/v1
O="Origin: http://localhost:3000"; TS=$(date +%s); PW='Str0ng!Pass1'
ADMIN_EMAIL=${E2E_ADMIN_EMAIL:-super-admin@example.com}; ADMIN_PW=${E2E_ADMIN_PASSWORD:-'ChangeMe@Local123!'}   # local dev defaults from IAM's seed
# Native curl on Windows cannot read MSYS paths (/tmp, /c/...): use a Windows-style path when cygpath exists.
TMPD=$(cygpath -m "${TMPDIR:-/tmp}" 2>/dev/null || echo "${TMPDIR:-/tmp}")
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
# NOTE: IAM throttles sign-ins to 5 per 60 s per IP and extends the block on every extra attempt,
# so a retry must wait a full window; hammering keeps the lockout alive.
login(){ for _ in 1 2 3; do r=$(curl -s -X POST $GW/api/auth/login -H 'Content-Type: application/json' -H "$O" -d "{\"email\":\"$1\",\"password\":\"$2\"}" | J "print(d['data']['accessToken'])"); [ -n "$r" ] && { echo "$r"; return; }; sleep 65; done; }

echo "== 1. Email/password login and session"
ATOK=$(login $ADMIN_EMAIL "$ADMIN_PW"); [ ${#ATOK} -gt 100 ] && ok "admin login returns an access token" || bad "admin login"
ME=$(curl -s $GW/api/auth/me -H "Authorization: Bearer $ATOK" -H "$O")
TENANT=$(echo "$ME" | J "print(d['data'].get('tenantId',''))"); ROLES=$(echo "$ME" | J "print(','.join(d['data'].get('roles',[])))")
[ -n "$TENANT" ] && ok "/auth/me has tenantId, roles=$ROLES" || bad "/auth/me has no tenantId"
chk "wrong password rejected" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $GW/api/auth/login -H 'Content-Type: application/json' -H "$O" -d '{"email":"'$ADMIN_EMAIL'","password":"definitely-wrong"}')" 401

echo; echo "== 2. RAG API enforces IAM"
chk "no token -> 401" "$(curl -s -o /dev/null -w '%{http_code}' $RAG/knowledge-bases)" 401
chk "garbage token -> 401" "$(curl -s -o /dev/null -w '%{http_code}' $RAG/knowledge-bases -H 'Authorization: Bearer not-a-token')" 401
chk "health is public" "$(curl -s -o /dev/null -w '%{http_code}' $RAG/health)" 200
chk "valid token -> 200" "$(curl -s -o /dev/null -w '%{http_code}' $RAG/knowledge-bases -H "Authorization: Bearer $ATOK")" 200
SPOOF=99999999-9999-9999-9999-999999999999
tenant_of_conversation(){  # $1 = bearer token, $2 = X-Tenant-ID header value -> prints the tenant the row was stored under
  local cid tenant
  cid=$(curl -s -X POST $RAG/conversations -H "Authorization: Bearer $1" -H "X-Tenant-ID: $2" -H 'Content-Type: application/json' -d '{}' | J "print((d.get('data') or {}).get('id',''))")
  [ -z "$cid" ] && return
  tenant=$(docker compose -f "c:/Users/kisho/WorkSpace/learning/ai/langchain-knoledgebase-rag/docker-compose.yml" exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"select tenant_id from conversations where id='$cid'\"" 2>/dev/null | tr -d '\r\n ')
  docker compose -f "c:/Users/kisho/WorkSpace/learning/ai/langchain-knoledgebase-rag/docker-compose.yml" exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -c \"delete from conversations where id='$cid'\"" >/dev/null 2>&1
  echo "$tenant"
}
T=$(tenant_of_conversation "$ATOK" "$SPOOF")
[ "$T" = "$SPOOF" ] && ok "super admin can act on behalf of another tenant (X-Tenant-ID honoured)" || bad "super admin override: stored '$T', expected '$SPOOF'"

echo; echo "== 3. Invite: admin invites an email, the email arrives in Mailpit"
INV="e2e.invitee.$TS@example.com"
ROLE_ID=$(curl -s $GW/api/rbac/roles -H "Authorization: Bearer $ATOK" -H "$O" | J "
items=d.get('data',d); items=items.get('items',items) if isinstance(items,dict) else items
r=[x for x in items if x.get('name')=='member']
print(r[0]['id'] if r else '')")
[ -n "$ROLE_ID" ] && ok "found the 'member' role" || bad "member role not found"
IC=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GW/api/tenants/$TENANT/invite" -H "Authorization: Bearer $ATOK" -H "$O" -H 'Content-Type: application/json' -d "{\"email\":\"$INV\",\"roleId\":\"$ROLE_ID\"}")
case "$IC" in 200|201) ok "invite accepted by IAM ($IC)";; *) bad "invite returned $IC";; esac
MSG=""; for i in $(seq 1 20); do MSG=$(curl -s "$MP/search?query=to:$INV" | J "m=d.get('messages',[]); print(m[0]['ID'] if m else '')"); [ -n "$MSG" ] && break; sleep 2; done
if [ -n "$MSG" ]; then
  ok "invitation email delivered to Mailpit"
  BODY=$(curl -s "$MP/message/$MSG" | J "print(d.get('Text','')+' '+d.get('HTML',''))")
  LINK=$(echo "$BODY" | grep -oE "register\?inviteToken=[A-Za-z0-9_-]+" | head -1)
  [ -n "$LINK" ] && ok "email contains the /register?inviteToken=... link" || bad "no inviteToken link in the email"
  ITOKEN=${LINK#register?inviteToken=}
else bad "no invitation email in Mailpit after 40 s (check notification-service / worker logs)"; fi

echo; echo "== 4. Invitee registers, accepts the invite, lands in the admin's workspace"
RC=$(curl -s -o /dev/null -w '%{http_code}' -X POST $GW/api/auth/register -H 'Content-Type: application/json' -H "$O" -d "{\"email\":\"$INV\",\"password\":\"$PW\",\"firstName\":\"E2E\",\"lastName\":\"Invitee\",\"inviteToken\":\"$ITOKEN\"}")
case "$RC" in 200|201) ok "invitee registered with the invite token ($RC)";; *) bad "register returned $RC";; esac
UTOK=$(login "$INV" "$PW")
[ -n "$UTOK" ] && ok "invitee can log in" || bad "invitee login failed (email verification required?)"
if [ -n "$UTOK" ]; then
  UT=$(curl -s $GW/api/auth/me -H "Authorization: Bearer $UTOK" -H "$O" | J "print(d['data'].get('tenantId',''))")
  [ "$UT" = "$TENANT" ] && ok "invitee landed in the admin's workspace" || bad "invitee tenant '$UT' != '$TENANT'"
  chk "invitee (member) can use the chat API" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/conversations -H "Authorization: Bearer $UTOK" -H 'Content-Type: application/json' -d '{}')" 201
  chk "invitee (member) cannot create agents" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/agents -H "Authorization: Bearer $UTOK" -H 'Content-Type: application/json' -d '{"name":"x","system_prompt":"x"}')" 403
fi
echo "$INV" > "$TMPD/e2e_last_user.txt"

echo; echo "== 4b. Authorization: a member is restricted, admin is not"
if [ -n "$UTOK" ]; then
  MA="Authorization: Bearer $UTOK"
  chk "member cannot create a feature flag" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/feature-flags -H "$MA" -H 'Content-Type: application/json' -d '{"key":"e2e_probe","enabled":false}')" 403
  chk "member cannot create a knowledge base" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/knowledge-bases -H "$MA" -H 'Content-Type: application/json' -d '{"name":"e2e-probe"}')" 403
  for ep in feature-flags analytics/summary usage feedback model-profiles documents agents; do
    chk "member cannot read /$ep" "$(curl -s -o /dev/null -w '%{http_code}' $RAG/$ep -H "$MA")" 403
  done
  T=$(tenant_of_conversation "$UTOK" "$SPOOF")
  [ "$T" = "$TENANT" ] && ok "a member sending X-Tenant-ID is pinned to their own tenant" || bad "member override leaked: stored '$T', expected '$TENANT'"
  chk "member can still open a conversation" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $RAG/conversations -H "$MA" -H 'Content-Type: application/json' -d '{}')" 201
fi
FLAG=$(curl -s -X POST $RAG/feature-flags -H "Authorization: Bearer $ATOK" -H 'Content-Type: application/json' -d "{\"key\":\"e2e_flag_$TS\",\"enabled\":false}" | J "print((d.get('data') or {}).get('id',''))")
if [ -n "$FLAG" ]; then
  chk "admin toggles a feature flag" "$(curl -s -o /dev/null -w '%{http_code}' -X PATCH $RAG/feature-flags/$FLAG/toggle -H "Authorization: Bearer $ATOK" -H 'Content-Type: application/json' -d '{"enabled":true}')" 200
  chk "admin deletes it again" "$(curl -s -o /dev/null -w '%{http_code}' -X DELETE $RAG/feature-flags/$FLAG -H "Authorization: Bearer $ATOK")" 200
else bad "admin could not create a feature flag"; fi

echo; echo "== 5. Document upload and ingestion"
DOCF="$TMPD/e2e_doc_$TS.txt"   # unique file name, so this run's document is unambiguous
printf 'Test document %s. The secret launch code for test document %s is BLUE-HERON-%s.
' "$TS" "$TS" "$TS" > "$DOCF"
UP=$(curl -s -m 60 -X POST $RAG/documents -H "Authorization: Bearer $ATOK" -F "file=@$DOCF;type=text/plain")
JOB=$(echo "$UP" | J "print((d.get('data') or {}).get('upload_job_id',''))")
[ -n "$JOB" ] && ok "upload accepted (job $JOB)" || bad "upload failed: $(echo "$UP" | head -c 200)"
if [ -n "$JOB" ]; then
  S=""; for i in $(seq 1 40); do S=$(curl -s $RAG/upload-jobs/$JOB -H "Authorization: Bearer $ATOK" | J "print((d.get('data') or {}).get('status',''))"); case "$S" in SUCCEEDED|FAILED) break;; esac; sleep 5; done
  [ "$S" = SUCCEEDED ] && ok "ingestion job SUCCEEDED" || bad "ingestion job ended as '$S'"
fi
echo "BLUE-HERON-$TS" > "$TMPD/e2e_secret.txt"

echo; echo "== 5b. Chat answers from the uploaded document, with citations"
CR=$(curl -s -m 170 -X POST $RAG/chat -H "Authorization: Bearer $ATOK" -H 'Content-Type: application/json' -d '{"message":"What is the secret launch code for test document '$TS'?","stream":false}')
echo "$CR" | grep -q "BLUE-HERON-$TS" && ok "answer contains the code from the document" || bad "answer did not contain BLUE-HERON-$TS (LLM overloaded? $(echo "$CR" | head -c 120))"
NC=$(echo "$CR" | J "x=d.get('data') or d; print(len(x.get('citations') or x.get('sources') or []))"); [ "${NC:-0}" -ge 1 ] && ok "answer has $NC citation(s)" || bad "no citations"

echo; echo "== 5c. Provenance, retrieval log and observability"
DOCID=$(curl -s "$RAG/documents?limit=200" -H "Authorization: Bearer $ATOK" | J "print(next((x['id'] for x in (d.get('data') or {}).get('documents',[]) if x['file_name']=='e2e_doc_$TS.txt'),''))")
if [ -n "$DOCID" ]; then
  CH=$(curl -s "$RAG/documents/$DOCID/chunks?limit=5" -H "Authorization: Bearer $ATOK")
  echo "$CH" | J "c=[x for x in (d.get('data') or {}).get('chunks',[]) if x['kind']=='chunk']; print('yes' if c and c[0]['content_hash'] and c[0]['embedding_model'] and c[0]['pipeline_version'] and c[0]['indexed_at'] else 'no')" | grep -q yes && ok "chunks carry hash, embedding model, pipeline version and index time" || bad "chunk provenance missing"
  curl -s "$RAG/documents/$DOCID" -H "Authorization: Bearer $ATOK" | J "x=d.get('data') or {}; print('yes' if x.get('processing_stage')=='completed' and x.get('uploaded_by') and x.get('chunking') else 'no')" | grep -q yes && ok "document records uploader, stage and chunking" || bad "document provenance missing"
else bad "could not find the uploaded document"; fi
RID=$(curl -s "$RAG/retrieval-logs?limit=1" -H "Authorization: Bearer $ATOK" | J "r=(d.get('data') or {}).get('retrievals',[]); print(r[0]['retrieval_id'] if r else '')")
if [ -n "$RID" ]; then
  ok "retrieval was logged ($RID)"
  curl -s "$RAG/retrieval-logs/$RID" -H "Authorization: Bearer $ATOK" | J "x=d.get('data') or {}; r=x.get('results',[]); print('yes' if r and any(i['selected_for_context'] for i in r) and x.get('query_hash') and 'query' not in x else 'no')" | grep -q yes && ok "retrieval log explains candidates and stores a query hash, not the query" || bad "retrieval log incomplete"
else bad "no retrieval was logged"; fi
chk "observability summary" "$(curl -s -o /dev/null -w '%{http_code}' "$RAG/observability/summary" -H "Authorization: Bearer $ATOK")" 200
chk "audit trail" "$(curl -s -o /dev/null -w '%{http_code}' "$RAG/observability/audit" -H "Authorization: Bearer $ATOK")" 200
if [ -n "${MA:-}" ]; then
  for ep in retrieval-logs observability/summary observability/audit; do
    chk "member cannot read /$ep" "$(curl -s -o /dev/null -w '%{http_code}' $RAG/$ep -H "$MA")" 403
  done
fi

echo; echo "== 6. Connected accounts API"
chk "list connected accounts" "$(curl -s -o /dev/null -w '%{http_code}' $GW/api/auth/social/accounts -H "Authorization: Bearer $ATOK" -H "$O")" 200
chk "Google authorize redirect" "$(curl -s -o /dev/null -w '%{http_code}' $GW/api/auth/social/google/start -H "$O")" 302
chk "Microsoft authorize redirect" "$(curl -s -o /dev/null -w '%{http_code}' $GW/api/auth/social/microsoft/start -H "$O")" 302

echo; echo "RESULT: $pass passed, $fail failed"
