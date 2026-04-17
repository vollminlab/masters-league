# Masters League

Fantasy golf dashboard for the Masters tournament. Ten players each draft five PGA golfers; the team score is the sum of the three best (lowest) to-par scores among active players. Live data is pulled from the ESPN API, cached in Redis, and served by a FastAPI backend behind a React frontend.

Deployed at <https://mastersleague.vollminlab.com>.

## Stack

| Layer     | Technology                              |
|-----------|-----------------------------------------|
| Frontend  | React 18 + TypeScript, Vite, Tailwind   |
| Backend   | FastAPI (Python 3.12), Uvicorn          |
| Cache     | Redis (30 s leaderboard, 60 s scorecard)|
| Container | Docker multi-stage build                |
| Registry  | Harbor — `harbor.vollminlab.com/vollminlab/masters-league` |
| Runtime   | Kubernetes `dmz` namespace, NodePort 32567 |
| GitOps    | Flux — `k8s-vollminlab-cluster` repo    |
| Ingress   | HAProxy DMZ (haproxydmz01/02 VIP)      |

## Local dev

Prerequisites: Python 3.12, Node 22, Redis running on `localhost:6379`.

```bash
make dev-backend    # FastAPI on :8000 (hot-reload)
make dev-frontend   # Vite on :5173  (proxies /api → :8000)
```

## Make targets

| Target              | Description                                          |
|---------------------|------------------------------------------------------|
| `build`             | Build container image                                |
| `push`              | Push image to Harbor                                 |
| `build-push`        | Build + push in one step                             |
| `login`             | Interactive login to Harbor                          |
| `login-stdin`       | Login via `HARBOR_USER` / `HARBOR_PASS` env vars     |
| `status`            | Pod + service status in the cluster                  |
| `logs`              | Follow app logs                                      |
| `logs-redis`        | Follow Redis logs                                    |
| `restart`           | Rolling restart (same tag, new pull)                 |
| `deploy-image`      | Update running image without waiting for Flux        |
| `port-forward`      | Forward cluster service to `localhost:8080`          |
| `debug-espn`        | Run ESPN fetch from inside the app pod               |
| `dev-backend`       | Run backend locally                                  |
| `dev-frontend`      | Run Vite dev server                                  |
| `create-pull-secret`| Seal a Harbor pull secret (one-time setup)           |

## Networking

Traffic path: Cloudflare → WAN → haproxydmz VIP → HAProxy (`bk_masters`) → NodePort 32567 on k8sworker05/06 → `masters-league` pod.

The UDM requires a **DMZ_LAN** firewall rule to allow HAProxy to reach the NodePort:

| Field       | Value                              |
|-------------|------------------------------------|
| Name        | `haproxydmz -> masters-league`     |
| Action      | Accept                             |
| Source      | haproxydmz01/02 (160.2, 160.3)     |
| Destination | k8sworker05/06 (152.15, 152.16)    |
| Port        | TCP 32567                          |

Without this rule the health checks fail and HAProxy marks both backends down.

## Deployment

See [DEPLOY.md](DEPLOY.md) for the full checklist: Harbor setup, HAProxy config, TLS, DNS, Flux GitOps, and verification steps.
