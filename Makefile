REGISTRY := harbor.vollminlab.com
PROJECT  := homelab
IMAGE    := masters-league
TAG      := v1.1.0
FULL     := $(REGISTRY)/$(PROJECT)/$(IMAGE):$(TAG)

NAMESPACE := dmz

# Use podman if available, fall back to docker
CTR := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)

.DEFAULT_GOAL := help

# ── Image ─────────────────────────────────────────────────────────────────────

.PHONY: build
build:  ## Build the container image
	$(CTR) build -t $(FULL) .

.PHONY: push
push:  ## Push image to Harbor
	$(CTR) push $(FULL)

.PHONY: build-push
build-push: build push  ## Build and push in one step

.PHONY: login
login:  ## Log in to Harbor registry (interactive)
	$(CTR) login $(REGISTRY)

.PHONY: login-stdin
login-stdin:  ## Log in to Harbor using HARBOR_USER / HARBOR_PASS env vars (tmux-safe)
	@test -n "$(HARBOR_USER)" || (echo "Set HARBOR_USER=admin" && exit 1)
	@test -n "$(HARBOR_PASS)" || (echo "Set HARBOR_PASS=yourpassword" && exit 1)
	@echo "$(HARBOR_PASS)" | $(CTR) login $(REGISTRY) --username $(HARBOR_USER) --password-stdin

# ── Cluster ───────────────────────────────────────────────────────────────────

.PHONY: status
status:  ## Show pod and service status
	@echo "=== Pods ==="
	@kubectl get pods -n $(NAMESPACE) -l 'app in (masters-league,masters-redis)' -o wide
	@echo ""
	@echo "=== Services ==="
	@kubectl get svc -n $(NAMESPACE) masters-league masters-redis

.PHONY: logs
logs:  ## Follow app logs
	kubectl logs -n $(NAMESPACE) -l app=masters-league -f --tail=100

.PHONY: logs-redis
logs-redis:  ## Follow Redis logs
	kubectl logs -n $(NAMESPACE) -l app=masters-redis -f --tail=50

.PHONY: restart
restart:  ## Force a rolling restart (picks up a new image with same tag)
	kubectl rollout restart deployment/masters-league -n $(NAMESPACE)
	kubectl rollout status deployment/masters-league -n $(NAMESPACE)

.PHONY: deploy-image
deploy-image:  ## Update the running image without waiting for Flux (useful during tournament)
	kubectl set image deployment/masters-league \
		masters-league=$(FULL) -n $(NAMESPACE)
	kubectl rollout status deployment/masters-league -n $(NAMESPACE)

.PHONY: port-forward
port-forward:  ## Forward app to localhost:8080 for local testing
	@echo "Dashboard available at http://localhost:8080"
	kubectl port-forward -n $(NAMESPACE) svc/masters-league 8080:8000

.PHONY: debug-espn
debug-espn:  ## Hit the ESPN API directly from inside the app pod
	kubectl exec -n $(NAMESPACE) \
		$$(kubectl get pod -n $(NAMESPACE) -l app=masters-league -o jsonpath='{.items[0].metadata.name}') \
		-- python3 -c "import asyncio, espn; d=asyncio.run(espn.fetch_players()); print(list(d.items())[:3])"

# ── Dev ───────────────────────────────────────────────────────────────────────

.PHONY: create-pull-secret
create-pull-secret:  ## Seal a Harbor pull secret (run once; needs HARBOR_USER and HARBOR_TOKEN env vars)
	@test -n "$(HARBOR_USER)" || (echo "Set HARBOR_USER=robot\$$masters-league" && exit 1)
	@test -n "$(HARBOR_TOKEN)" || (echo "Set HARBOR_TOKEN=<robot-account-token>" && exit 1)
	kubectl create secret docker-registry harbor-pull-secret \
		--docker-server=$(REGISTRY) \
		--docker-username=$(HARBOR_USER) \
		--docker-password=$(HARBOR_TOKEN) \
		--namespace=$(NAMESPACE) \
		--dry-run=client -o yaml \
	| kubeseal --fetch-cert \
		--controller-namespace sealed-secrets \
		--controller-name sealed-secrets-controller \
	| kubeseal --format yaml \
		--controller-namespace sealed-secrets \
		--controller-name sealed-secrets-controller \
	> $(CURDIR)/../k8s-vollminlab-cluster/clusters/vollminlab-cluster/dmz/masters-league/app/harbor-pull-sealedsecret.yaml
	@echo "Sealed secret written. Add it to app/kustomization.yaml resources, then commit."

.PHONY: dev-backend
dev-backend:  ## Run backend locally (requires Redis on localhost:6379)
	cd backend && pip install -r requirements.txt -q && \
	uvicorn main:app --reload --port 8000

.PHONY: dev-frontend
dev-frontend:  ## Run Vite dev server (proxies /api to localhost:8000)
	cd frontend && npm install && npm run dev

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
