#!/bin/bash
# Workspace switching, end to end through the SAME frontend routes the browser uses:
# an existing member is invited into a second workspace, accepts, lists their workspaces,
# switches (and is refused a workspace they are not in), and their data follows the workspace.
# Needs the whole stack running with sign-up invite-only or open. Creates one throwaway
# workspace and one throwaway user in the local dev instance.
# Override the admin login with E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD.
GW=http://localhost:3301; FE=http://localhost:3000; RAG=http://localhost:8088/api/v1; MP=http://localhost:8025/api/v1; O="Origin: http://localhost:3000"
TS=$(date +%s); PW='Str0ng!Pass1'
DC="docker compose -f c:/Users/kisho/WorkSpace/learning/ai/langchain-knoledgebase-rag/docker-compose.yml"
pass=0; fail=0
ok(){ printf "  PASS  %s\n" "$1"; pass=$((pass+1)); }
bad(){ printf "  FAIL  %s\n" "$1"; fail=$((fail+1)); }
chk(){ [ "$2" = "$3" ] && ok "$1 ($2)" || bad "$1: expected $3, got $2"; }
J(){ python -c "import sys,json
try: d=json.load(sys.stdin)
except Exception: print(''); sys.exit()
$1"; }
code(){ curl -s -o /dev/null -w '%{http_code}' "$@"; }
# NOTE: IAM throttles sign-ins to 5 per 60 s per IP and extends the block on every extra attempt,
# so a retry must wait a full window; hammering keeps the lockout alive.
login(){ for i in 1 2 3; do r=$(curl -s -X POST $GW/api/auth/login -H 'Content-Type: application/json' -H "$O" -d "{\"email\":\"$1\",\"password\":\"$2\"}" | J "print(d['data']['accessToken'])"); [ -n "$r" ] && { echo "$r"; return; }; sleep 65; done; }
fe_login(){ for i in $(seq 1 20); do c=$(curl -s -o /dev/null -w '%{http_code}' -c "$1" -X POST $FE/api/auth/login -H 'Content-Type: application/json' -d "{\"email\":\"$2\",\"password\":\"$3\"}"); [ "$c" = 200 ] && return 0; sleep 65; done; return 1; }
session_tenant(){ curl -s -b "$1" $FE/api/auth/session | J "print((d.get('user') or {}).get('tenantId',''))"; }

ATOK=$(login ${E2E_ADMIN_EMAIL:-super-admin@example.com} "${E2E_ADMIN_PASSWORD:-ChangeMe@Local123!}"); A="Authorization: Bearer $ATOK"
DEF=$(curl -s $GW/api/auth/me -H "$A" -H "$O" | J "print(d['data']['tenantId'])")
T2=$(curl -s -X POST $GW/api/tenants -H "$A" -H "$O" -H 'Content-Type: application/json' -d "{\"name\":\"E2E Switch $TS\",\"slug\":\"e2e-switch-$TS\"}" | J "x=d.get('data',d); print(x.get('internalId') or x.get('id') or '')")
[ -n "$T2" ] && echo "  created a second workspace for the test" || { echo "  could not create a second workspace"; exit 1; }
ROLE=$(curl -s $GW/api/rbac/roles -H "$A" -H "$O" | J "
x=d.get('data',d); x=x.get('items',x) if isinstance(x,dict) else x
print([r['id'] for r in x if r.get('name')=='member'][0])")

echo "== 1. An EXISTING member (default workspace) is invited into workspace 2"
U="switcher.$TS@example.com"
# create a default-workspace member: needs an invitation while sign-up is invite-only
chk "invite $U to the default workspace" "$(code -X POST $GW/api/tenants/$DEF/invite -H "$A" -H "$O" -H 'Content-Type: application/json' -d "{\"email\":\"$U\",\"roleId\":\"$ROLE\"}")" 201
for i in $(seq 1 15); do M1=$(curl -s "$MP/search?query=to:$U" | J "m=d.get('messages',[]); print(m[0]['ID'] if m else '')"); [ -n "$M1" ] && break; sleep 2; done
TOK1=$(curl -s "$MP/message/$M1" | J "import re;print((re.findall(r'inviteToken=([A-Za-z0-9_-]+)',(d.get('Text','')+d.get('HTML','')))+[''])[0])")
chk "registers" "$(code -X POST $GW/api/auth/register -H 'Content-Type: application/json' -H "$O" -d "{\"email\":\"$U\",\"password\":\"$PW\",\"firstName\":\"S\",\"lastName\":\"W\",\"inviteToken\":\"$TOK1\"}")" 201
chk "invite $U to workspace 2" "$(code -X POST $GW/api/tenants/$T2/invite -H "$A" -H "$O" -H 'Content-Type: application/json' -d "{\"email\":\"$U\",\"roleId\":\"$ROLE\"}")" 201
sleep 3
M2=$(curl -s "$MP/search?query=to:$U" | J "m=sorted(d.get('messages',[]), key=lambda x:x['Created']); print(m[-1]['ID'] if m else '')")
TOK2=$(curl -s "$MP/message/$M2" | J "import re;print((re.findall(r'inviteToken=([A-Za-z0-9_-]+)',(d.get('Text','')+d.get('HTML','')))+[''])[0])")
[ -n "$TOK2" ] && [ "$TOK2" != "$TOK1" ] && ok "second invitation email received (own token)" || bad "second invitation token missing"

echo; echo "== 2. Through the frontend routes (the same ones the browser uses)"
jar=$(mktemp); fe_login "$jar" "$U" "$PW" && ok "sign in via /api/auth/login" || bad "sign in"
chk "starts in the default workspace" "$(session_tenant "$jar")" "$DEF"
AC=$(curl -s -w '\n%{http_code}' -b "$jar" -X POST $FE/api/iam/tenants/invitations/accept -H 'Content-Type: application/json' -d "{\"token\":\"$TOK2\"}")
chk "accept the invitation (own email)" "$(echo "$AC" | tail -1)" 200
JOINED=$(echo "$AC" | head -1 | J "x=d.get('data',{}); x=x.get('data',x); print(x.get('tenantId',''))")
[ "$JOINED" = "$T2" ] && ok "accept response names workspace 2 (used to switch straight in)" || bad "accept response tenant '$JOINED'"
MINE=$(curl -s -b "$jar" $FE/api/iam/tenants/mine)
echo "$MINE" | J "x=d.get('data',d); x=x.get('data',x) if isinstance(x,dict) else x; print('  workspaces:',[(w['name'],w['roles']) for w in x])"
N=$(echo "$MINE" | J "x=d.get('data',d); x=x.get('data',x) if isinstance(x,dict) else x; print(len(x))"); chk "GET /tenants/mine lists both workspaces" "$N" 2
chk "switch into workspace 2" "$(code -b "$jar" -c "$jar" -X POST $FE/api/auth/switch-workspace -H 'Content-Type: application/json' -d "{\"tenantId\":\"$T2\"}")" 200
chk "session is now workspace 2" "$(session_tenant "$jar")" "$T2"
chk "switch back to the default workspace" "$(code -b "$jar" -c "$jar" -X POST $FE/api/auth/switch-workspace -H 'Content-Type: application/json' -d "{\"tenantId\":\"$DEF\"}")" 200
chk "session is back in the default workspace" "$(session_tenant "$jar")" "$DEF"
chk "cannot switch into a workspace you are not in (400)" "$(code -b "$jar" -c "$jar" -X POST $FE/api/auth/switch-workspace -H 'Content-Type: application/json' -d '{"tenantId":"99999999-9999-9999-9999-999999999999"}')" 400
chk "switch route needs a session (401)" "$(code -X POST $FE/api/auth/switch-workspace -H 'Content-Type: application/json' -d "{\"tenantId\":\"$T2\"}")" 401
echo "  -- data really follows the workspace:"
code -b "$jar" -c "$jar" -X POST $FE/api/auth/switch-workspace -H 'Content-Type: application/json' -d "{\"tenantId\":\"$T2\"}" >/dev/null
CID=$(curl -s -b "$jar" -X POST $FE/api/rag/conversations -H 'Content-Type: application/json' -d '{}' | J "print((d.get('data') or {}).get('id',''))")
if [ -n "$CID" ]; then
  T=$($DC exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"select tenant_id from conversations where id='$CID'\"" 2>/dev/null | tr -d '\r\n ')
  [ "$T" = "$T2" ] && ok "a chat opened after switching is stored under workspace 2" || bad "stored under $T"
  $DC exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -c \"delete from conversations where id='$CID'\"" >/dev/null 2>&1
fi
rm -f "$jar"

echo; echo "RESULT: $pass passed, $fail failed"
