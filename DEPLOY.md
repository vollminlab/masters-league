# Deployment Checklist — Masters League 2026

## 0. Harbor pull secret

Nothing to do — this is already wired up and needs no per-deploy action.

The Deployment references the `harbor-vollminlab-pull` image pull secret, which the
External Secrets Operator materializes from 1Password. It lives in the cluster repo at
`clusters/vollminlab-cluster/dmz/masters-league/app/harbor-vollminlab-pull-externalsecret.yaml`.

> Earlier revisions of this checklist described sealing a pull secret with `kubeseal` via
> `make create-pull-secret`. The sealed-secrets controller was removed on 2026-05-31 and
> every secret in the cluster now comes from 1Password through ESO, so that path no longer
> works. Rotating the Harbor robot credential means updating the 1Password item — the
> cluster picks it up on the ExternalSecret's next refresh.

## 1. Build & push the image

```bash
cd /home/vollmin/repos/vollminlab/masters-league
make login        # log in to harbor.vollminlab.com
make build-push   # build + push in one step
```

## 2. HAProxy DMZ — add to haproxydmz01 AND haproxydmz02

Add to the `ft_https` frontend (after the existing `acl host_bluemap` line):

```haproxy
    acl host_masters hdr(host) -i mastersleague.vollminlab.com
    use_backend bk_masters if host_masters
```

Add a new backend (after `bk_bluemap`):

```haproxy
backend bk_masters
        mode http
        option httpchk GET /api/health
        http-check expect status 200
        balance roundrobin
        server masters05 192.168.152.15:32567 check inter 3000 fall 3 rise 2
        server masters06 192.168.152.16:32567 check inter 3000 fall 3 rise 2
```

Reload HAProxy on both nodes:

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg   # validate config first
sudo systemctl reload haproxy
```

## 3. TLS certificate

`mastersleague.vollminlab.com` must be covered by the cert in `/etc/haproxy/certs/`.
If you have a wildcard `*.vollminlab.com` cert there already (same as bluemap), nothing to do.
Otherwise add the cert for this hostname.

## 4. UDM firewall — DMZ_LAN rule

In the UniFi UI add a rule to **DMZ_LAN** (before "block all"):

| Field       | Value                          |
|-------------|--------------------------------|
| Name        | `haproxydmz -> masters-league` |
| Action      | Accept                         |
| Source      | haproxydmz01/02 (160.2, 160.3) |
| Destination | k8sworker05/06 (152.15, 152.16)|
| Port        | TCP 32567                      |

> The existing WAN_DMZ rule already forwards ports 80/443 to the haproxydmz VIP — no new WAN rule needed.

## 5. Cloudflare DNS

Add a CNAME record (same pattern as Bluemap):

| Type  | Name            | Target                   | Proxied |
|-------|-----------------|--------------------------|---------|
| CNAME | `mastersleague` | `dynamic.vollminlab.com` | Yes     |

## 6. Deploy via Flux (GitOps)

```bash
cd /home/vollmin/repos/vollminlab/k8s-vollminlab-cluster
git checkout main && git pull
git checkout -b feat/masters-league-dmz
git add clusters/vollminlab-cluster/dmz/masters-league/
git add clusters/vollminlab-cluster/dmz/kustomization.yaml
git commit -m "feat(dmz): add masters-league fantasy golf dashboard"
# open PR → merge → Flux reconciles within 5 minutes
```

## 7. Verify

```bash
# Pod and service status
make status

# Follow logs
make logs

# Port-forward to test locally before DNS is wired up
make port-forward   # then open http://localhost:8080

# External test (after DNS + HAProxy)
curl -I https://mastersleague.vollminlab.com/api/health
```
